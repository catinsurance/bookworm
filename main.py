import sys
import os
import re
import uuid
import requests
import threading, time

from enum import Enum
from datetime import datetime as date
from PIL import Image
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

from src.WidgetStyles import *
import defusedxml.ElementTree as ET
import xml.etree.ElementTree as OtherET
import bbcode
from bs4 import BeautifulSoup

STEAM_PATH = None
WORKSHOP_QUERY_WAIT = 0.8
WORKSHOP_ITEM_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id="


class ModSortingMode(Enum):
    NameAscending = 1
    NameDescending = 2
    Enabled = 3  # Enabled with NameAscending
    Disabled = 4  # Disabled with NameAscending


selectedMod = None
iconQueueOpen = True
iconQueue = []


class DirectoryLocationDialog(QFileDialog):
    def __init__(self, mainWindow=None):
        super().__init__()

        self.mainWindow = mainWindow

        self.setFileMode(QFileDialog.FileMode.Directory)
        self.setNameFilter("Mods Folder")
        self.setLabelText(QFileDialog.DialogLabel.FileName, "Locate mods folder")
        self.fileSelected.connect(self.directorySelected)

        self.exec()

    def directorySelected(self, path):
        if os.path.isdir(path):
            settings.setValue("ModsFolder", path)

        if self.mainWindow is not None:
            self.mainWindow.modFolderLocated()


# Taken from Basement Renovator.
def getSteamPath():
    global STEAM_PATH
    if not STEAM_PATH:
        STEAM_PATH = QSettings(
            "HKEY_CURRENT_USER\\Software\\Valve\\Steam", QSettings.NativeFormat
        ).value("SteamPath")
    return STEAM_PATH


# Based on code from Basement Renovator.
def getModsFolderPath(mainWindow=None):
    modsFolderPath = settings.value("ModsFolder")
    mainWindowProvided = False

    # This means we're trying to relocate it.
    if mainWindow is not None:
        modsFolderPath = None

    if modsFolderPath:
        # Return if folder exists at path, otherwise continue.
        if QFile.exists(modsFolderPath):
            return modsFolderPath

    # Mods folder path is no longer correct, search again.
    steamPath = getSteamPath()
    if not steamPath:
        # Could not find the Steam directory
        DirectoryLocationDialog(mainWindow)
        mainWindowProvided = True
    else:
        # Get Isaac path
        libconfig = os.path.join(steamPath, "steamapps", "libraaryfolders.vdf")
        if os.path.isfile(libconfig):
            libLines = list(open(libconfig, "r"))
            matcher = re.compile(r'"path"\s*"(.*?)"')
            installDirs = map(
                lambda res: os.path.normpath(res.group(1)),
                filter(
                    lambda res: res,
                    map(lambda line: matcher.search(line), libLines),
                ),
            )
            for root in installDirs:
                installPath = os.path.join(
                    root,
                    "steamapps",
                    "common",
                    "The Binding of Isaac Rebirth",
                )
                if not QFile.exists(installPath):
                    DirectoryLocationDialog(mainWindow)
                    mainWindowProvided = True

                # Get mods folder from this directory.
                modsFolderPath = os.path.join(installPath, "mods")
                settings.setValue("ModsFolder", modsFolderPath)

        # Could not find path, make sure locate it themselves.
        if (
            not modsFolderPath
            or modsFolderPath == ""
            or not os.path.isdir(modsFolderPath)
        ):
            DirectoryLocationDialog(mainWindow)
            mainWindowProvided = True

    if not mainWindowProvided:
        mainWindow.modFolderLocated()
    return modsFolderPath


def applyDefaultSettings(settings):
    # Create default config file.

    getModsFolderPath()
    if settings.value("AutomaticThumbnailDownload") is None:
        settings.setValue("AutomaticThumbnailDownload", "1")


def parseWorkshopPage(html):
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("img", recursive=True, attrs={"id": "previewImageMain"})
    if tag is not None:
        return tag.attrs["src"]

    # There's no thumbnails, just an icon.
    tag = soup.find(
        "img", recursive=True, attrs={"class": "workshopItemPreviewImageEnlargeable"}
    )
    if tag is not None:
        src = tag.attrs["src"]

        # Letterboxed is true, meaning it'll have black squares to the left and right.
        # Remove the letterbox by removing that from the end of the url.
        if src.endswith("true"):
            src = src.removesuffix("true")
            src = src + "false"

        return src

    return None

class IconQueueHandler(QObject):
    destroy = Signal()
    iconFetched = Signal(str, str, bool)

    def start(self):
        self.paused = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.process)
        self.timer.start(1000)

        self.destroy.connect(self.stop)

    def stop(self):
        self.timer.stop()
        QThread.currentThread().exit()

    def toggle(self):
        self.paused = not self.paused

    def process(self):
        if QThread.currentThread().isInterruptionRequested():
            self.stop()
            return

        if len(iconQueue) == 0 or self.paused:
            return

        workshopId = iconQueue.pop(0)
        filePath = f"cache/thumb-{workshopId}.png"

        if not os.path.exists(filePath):
            fetched = requests.get(WORKSHOP_ITEM_URL + workshopId)
            html = fetched.content
            parsed = parseWorkshopPage(html)
            if parsed is not None:
                if not os.path.exists("cache/") or not os.path.isdir("cache/"):
                    os.makedirs("cache/")

                imgData = requests.get(parsed)

                with open(filePath, "wb") as f:
                    f.write(imgData.content)

                # Resize to save on space.
                # It only displays as 64x64 anyway.
                image = Image.open(filePath)
                resized = image.resize((64, 64))
                resized.save(filePath)

                # Set mod icon.
                self.iconFetched.emit(workshopId, filePath, False)
            else:
                print(f"Could not grab icon for workshop id {workshopId}")
                self.iconFetched.emit(workshopId, "resources/no)icon.png", True)
        else:
            # Set mod icon.
            self.iconFetched.emit(workshopId, filePath, False)

class ModItem(QListWidgetItem):
    def __init__(self, folderPath):

        super().__init__()

        self.loaded = self.loadFromFile(folderPath=folderPath)
        self.sortingMode = ModSortingMode.NameAscending
        self.widget = QWidget()

        self.thumbnailWidget = QWidget()
        self.thumbnailWidget.setFixedSize(72, 72)
        self.thumbnailLayout = QGridLayout()
        self.thumbnailLayout.setContentsMargins(0, 0, 0, 0)

        self.thumbnailBorder = QLabel()
        self.thumbnailBorder.setPixmap(QPixmap("./resources/mod_icon_frame.png"))
        self.thumbnailBorder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.thumbnail = QPushButton()
        self.thumbnail.setFixedSize(64, 64)
        self.thumbnail.setContentsMargins(2, 2, 2, 2)
        self.thumbnail.setEnabled(False)
        self.thumbnail.setFixedSize(64, 64)

        if not self.loaded:
            # Failed to load mod, tell the user and don't put any mod data.
            self.thumbnail.setIcon(QPixmap("resources/load_fail.png"))
            folderName = os.path.basename(folderPath)
            self.label = QLabel(
                f"<font size=5>Failed to read mod data!</font><br><font size=3><i>{folderName}</i></font>"
            )
            self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        else:
            modIcon = QPixmap()
            modIcon.size().setWidth(64)
            modIcon.size().setHeight(64)

            self.workshopThumbLoaded = False
            isAutomaticallyQuerying = False

            if hasattr(self, "workshopId"):
                workshopThumb = f"cache/thumb-{self.workshopId}.png"

                if os.path.exists(workshopThumb):
                    modIcon.load(workshopThumb)
                    self.workshopThumbLoaded = True
                elif settings.value("AutomaticThumbnailDownload") == "1":
                    isAutomaticallyQuerying = True
                    iconQueue.append(self.workshopId)
            else:
                modIcon.load("resources/no_icon.png")

            self.thumbnail.setIcon(modIcon)
            self.thumbnail.setIconSize(QSize(64, 64))
            self.thumbnailLayout.addWidget(self.thumbnail, 0, 0, Qt.AlignmentFlag.AlignCenter)

            self.thumbnail.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0);
            """)

            self.thumbnail.setEnabled(not isAutomaticallyQuerying)

            if hasattr(self, "workshopId"):
                self.thumbnail.setMouseTracking(True)
                self.thumbnail.clicked.connect(self.thumbnailClick)

                self.thumbnailLabel = QLabel(self.thumbnail)
                if self.workshopThumbLoaded:
                    self.thumbnailLabel.setText("Click to delete thumbnail")
                else:
                    self.thumbnailLabel.setText("Click to download thumbnail")

                self.thumbnailLabel.setWordWrap(True)
                self.thumbnailLabel.setVisible(not isAutomaticallyQuerying)
                self.thumbnailLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.thumbnailLabel.setObjectName("thumbnailLabel")
                self.thumbnailLabel.setTextFormat(Qt.TextFormat.RichText)
                self.thumbnailLabel.setStyleSheet(
                    """
                    QLabel#thumbnailLabel {
                        color: transparent;
                        background-color: rgba(0, 0, 0, 0);
                    }

                    QLabel#thumbnailLabel:hover {
                        color: white;
                        background-color: rgba(0, 0, 0, 0.5);
                    }
                    """
                )

                self.thumbnailLabel.setFixedSize(64, 64)

            # Truncate text if too long.
            name = self.name
            truncate_length = 27
            if len(name) > truncate_length:
                name = name[0 : (truncate_length - 3)] + "..."

            # Add checkbox
            self.checkbox = QPushButton()

            if self.enabled:
                self.checkbox.setObjectName("modItemEnabled")
            else:
                self.checkbox.setObjectName("modItemDisabled")

            self.refreshCheckboxStylesheet()
            self.checkbox.clicked.connect(self.toggleMod)

            # Set text.
            self.label = QLabel(
                f"<font size=5>{name}</font><br><font size=3><i>{self.directory}</i></font>"
            )

        self.thumbnailLayout.addWidget(self.thumbnailBorder, 0, 0, Qt.AlignmentFlag.AlignCenter)

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(3, 0, 3, 0)

        self.thumbnailWidget.setLayout(self.thumbnailLayout)
        self.layout.addWidget(self.thumbnailWidget, alignment=Qt.AlignmentFlag.AlignLeft)
        self.layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.layout.addStretch()
        if hasattr(self, "checkbox"):
            self.checkbox.setFixedSize(64, 64)
            self.layout.addWidget(self.checkbox, alignment=Qt.AlignmentFlag.AlignRight)

        # Set item size.
        self.widget.setLayout(self.layout)
        self.setSizeHint(QSize(200, 90))

    # Define sorting behavior for `self.sortItems()`.
    def __lt__(self, other):
        if not self.loaded:
            return False

        if not other.loaded:
            return True

        if self.sortingMode == ModSortingMode.NameAscending:
            return self.name < other.name
        elif self.sortingMode == ModSortingMode.NameDescending:
            return self.name > other.name
        elif self.sortingMode == ModSortingMode.Enabled:
            if self.enabled != other.enabled:
                return self.enabled and not other.enabled

            return self.name < other.name
        elif self.sortingMode == ModSortingMode.Disabled:
            if self.enabled != other.enabled:
                return not self.enabled and other.enabled

            return self.name < other.name

    def thumbnailClick(self):
        if not hasattr(self, "workshopId") or self.workshopId == "0":
            return

        if self.workshopThumbLoaded:
            workshopThumb = f"cache/thumb-{self.workshopId}.png"
            if os.path.exists(workshopThumb):
                os.remove(workshopThumb)

            modIcon = QPixmap()
            modIcon.size().setWidth(64)
            modIcon.size().setHeight(64)
            modIcon.load("resources/no_icon.png")
            self.thumbnail.setIcon(modIcon)

            self.thumbnailLabel.setText("Click to download thumbnail")
            self.workshopThumbLoaded = False
        else:
            iconQueue.append(self.workshopId)

    # Required after changing object name.
    def refreshCheckboxStylesheet(self):
        self.checkbox.setStyleSheet(
            """
            QPushButton#modItemEnabled{
                background-color: rgba(255, 255, 255, 0);
                border-image: url(resources/box_tick_on.png);
            }

            QPushButton#modItemEnabled:hover{
                background-color: rgba(255, 255, 255, 0);
                border-image: url(resources/box_tick_on_hover.png);
            }

            QPushButton#modItemDisabled{
                background-color: rgba(255, 255, 255, 0);
                border-image: url(resources/box_tick_off.png);
            }

            QPushButton#modItemDisabled:hover{
                background-color: rgba(255, 255, 255, 0);
                border-image: url(resources/box_tick_off_hover.png);
            }
            """
        )

    # Toggle the mod on or off.
    def toggleMod(self):
        if not self.loaded:
            return

        path = os.path.join(self.folderPath, "disable.it")
        if self.enabled:
            # Create disable.it at path.
            with open(path, "w") as fp:
                pass

            self.checkbox.setObjectName("modItemDisabled")
            self.enabled = False
        else:
            # Remove disable.it (if it exists)
            if os.path.exists(path):
                os.remove(path)

            self.checkbox.setObjectName("modItemEnabled")

            self.enabled = True

        self.refreshCheckboxStylesheet()

    def loadFromFile(self, folderPath):
        metadataPath = os.path.join(folderPath, "metadata.xml")
        if not metadataPath:
            # Not a mod.
            print(f"No metadata.xml found for folder of path {folderPath}")
            return

        self.folderPath = folderPath

        # Open metadata.xml.
        try:
            tree = ET.parse(metadataPath)
        except:
            print(f"Could not parse mod at path {folderPath}")
            return

        root = tree.getroot()

        # Get folder name (directory tag).
        # This is what keeps track of what mod this is.
        directory = root.find("directory")
        if directory == None:
            # Not a valid mod.
            print(f"No directory found for mod of path {folderPath}")
            return

        self.directory = directory.text

        # Check if mod is a workshop mod (id tag).
        workshopId = root.find("id")
        if workshopId != None:
            self.workshopId = workshopId.text

        # Get mod name.
        name = root.find("name")
        if name == None:
            # Not a valid mod.
            print(f"No name found for mod of path {folderPath}")
            return

        self.name = name.text

        # Get mod version.
        version = root.find("version")
        if version == None:
            # Not a valid mod.
            print(f"No version found for mod of path {folderPath}")
            return

        self.version = version.text

        # Get mod description.
        description = root.find("description")
        if description == None or description.text == None or description.text == "":
            self.description = "[No description]"
        else:
            self.description = description.text

        # Check if enabled by looking for disable.it
        disableItPath = os.path.join(folderPath, "disable.it")
        self.enabled = not os.path.exists(disableItPath)

        return True


class ModList(PaperListWidget):
    def __init__(self):
        super().__init__("#e1d0ba")

        self.setViewMode(self.ViewMode.ListMode)
        self.setSelectionMode(self.SelectionMode.SingleSelection)
        self.setResizeMode(self.ResizeMode.Adjust)
        self.setAutoScroll(True)
        self.setDragEnabled(False)
        self.setBaseSize(QSize(400, self.baseSize().height()))
        self.setSpacing(2)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(400)

        self.scrollbar = PaperScrollbar(PaperScrollbarType.DockedList, self)
        self.setVerticalScrollBar(self.scrollbar)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.loadMods()

        self.iconThread = QThread()

        self.modIconQueueHandler = IconQueueHandler()
        self.modIconQueueHandler.moveToThread(self.iconThread)
        self.modIconQueueHandler.iconFetched.connect(self.modIconFetched)

    def loadMods(self):
        self.clear()
        modsPath = getModsFolderPath()
        if modsPath is None or not os.path.isdir(modsPath):
            # Something went very wrong.
            return

        modsList = os.listdir(modsPath)
        for modFolder in modsList:
            folderPath = os.path.join(modsPath, modFolder)
            if os.path.isdir(folderPath):
                modItem = ModItem(folderPath)
                self.addItem(modItem)
                self.setItemWidget(modItem, modItem.widget)

        self.sortItems()

    def modIconFetched(self, workshopId, filePath, failedToLoad):
        for x in range(self.count()):
            item = self.item(x)
            if hasattr(item, "workshopId") and item.workshopId == workshopId:
                modIcon = QPixmap(filePath)
                item.thumbnail.setIcon(modIcon)
                item.thumbnail.setEnabled(True)
                item.thumbnailLabel.setVisible(True)

                if failedToLoad:
                    item.thumbnailLabel.setText("Couldn't download, click to retry")

                break


class ModListToolbar(QWidget):
    def __init__(self):
        super().__init__()

        self.packFilter = ""

        # Create a layout to house everything
        self.masterLayout = QVBoxLayout()
        self.masterLayout.setContentsMargins(0, 0, 0, 0)
        self.masterLayout.setSpacing(0)

        # Create a tools layout for the filter features.
        self.filterToolsLayout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.filterToolsLayout.setContentsMargins(0, 0, 0, 0)

        self.filterButtonIconOff = QPixmap("resources/filter_off.png")
        self.filterButtonIconOn = QPixmap("resources/filter_on.png")
        self.filterButton = PaperToolButton(PaperButtonType.Primary)
        self.filterButton.setIcon(self.filterButtonIconOff)
        self.filterButton.setIconSize(QSize(32, 32))

        self.filterMenu = PackListDropdownMenu(self)
        self.filterMenu.triggered.connect(self.choiceChanged)
        self.refreshPackChoices()

        self.filterButton.setMenu(self.filterMenu)
        self.filterButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self.filterToolsLayout.addWidget(self.filterButton)

        # Search box
        self.filterBox = PaperLineEdit()
        self.filterToolsLayout.addWidget(self.filterBox, stretch=2)
        self.filterBox.setPlaceholderText("Search...")
        self.filterBox.textChanged.connect(self.filter)

        self.masterLayout.addItem(self.filterToolsLayout)
        self.setLayout(self.masterLayout)

        # Filter by category (like file explorer).
        self.categoryWidget = QWidget()
        self.categoryBox = QHBoxLayout()
        self.categoryBox.setContentsMargins(0, 0, 0, 0)

        self.nameCategory = PaperPushButton(PaperButtonType.Primary)
        self.nameCategory.setFixedSize(295, 35)
        self.categoryBox.addWidget(self.nameCategory)
        self.nameCategory.clicked.connect(self.sortingModeName)

        self.enabledCategory = PaperPushButton(PaperButtonType.Primary)
        self.enabledCategory.setFixedSize(85, 35)
        self.categoryBox.addWidget(self.enabledCategory)
        self.enabledCategory.clicked.connect(self.sortingModeState)

        self.setSortingMode(ModSortingMode.NameAscending)

        self.categoryBox.addStretch()
        self.categoryWidget.setLayout(self.categoryBox)
        self.masterLayout.addWidget(self.categoryWidget)

    def setSortingMode(self, sortingMode):
        self.sortingMode = sortingMode

        if self.sortingMode == ModSortingMode.NameAscending:
            self.nameCategory.setText("Name ▾")
            self.enabledCategory.setText("Active")
        elif self.sortingMode == ModSortingMode.NameDescending:
            self.nameCategory.setText("Name ▴")
            self.enabledCategory.setText("Active")
        elif self.sortingMode == ModSortingMode.Enabled:
            self.nameCategory.setText("Name")
            self.enabledCategory.setText("Active ▾")
        elif self.sortingMode == ModSortingMode.Disabled:
            self.nameCategory.setText("Name")
            self.enabledCategory.setText("Active ▴")

        for x in range(mainWindow.modList.count()):
            item = mainWindow.modList.item(x)
            item.sortingMode = self.sortingMode

        mainWindow.modList.sortItems()

    def sortingModeName(self):
        if self.sortingMode != ModSortingMode.NameAscending:
            self.setSortingMode(ModSortingMode.NameAscending)
        elif self.sortingMode == ModSortingMode.NameAscending:
            self.setSortingMode(ModSortingMode.NameDescending)

    def sortingModeState(self):
        if self.sortingMode != ModSortingMode.Enabled:
            self.setSortingMode(ModSortingMode.Enabled)
        elif self.sortingMode == ModSortingMode.Enabled:
            self.setSortingMode(ModSortingMode.Disabled)

    def refreshPackChoices(self):
        self.filterMenu.clear()
        for x in range(mainWindow.packList.count()):
            pack = mainWindow.packList.item(x)
            name = pack.name
            if self.packFilter == pack.name:
                name = "[✓] " + name

            self.filterMenu.addAction(PaperWidgetAction(self.filterMenu, name))

    def choiceChanged(self, action):
        actionText = action.text()
        if actionText.startswith("[✓] "):
            actionText = actionText.removeprefix("[✓] ")

        if actionText != self.packFilter:
            self.packFilter = actionText
        else:
            self.packFilter = ""

        self.refreshPackChoices()
        self.filter()

        # Set icon.
        if self.packFilter != "":
            self.filterButton.setIcon(self.filterButtonIconOn)
        else:
            self.filterButton.setIcon(self.filterButtonIconOff)

    def filter(self):
        query = self.filterBox.displayText().lower()
        for i in range(mainWindow.modList.count()):
            item = mainWindow.modList.item(i)

            # Hide mods that failed to load.
            if (self.packFilter != "" or query != "") and not hasattr(item, "name"):
                item.setHidden(True)
            elif query != "" or self.packFilter != "":
                showsInSearchQuery = (
                    query not in item.name.lower()
                    and query not in item.directory.lower()
                )
                showsInPackFilter = False

                if self.packFilter == "":
                    showsInPackFilter = True
                else:
                    for x in range(mainWindow.packList.count()):
                        pack = mainWindow.packList.item(x)
                        if pack.name == self.packFilter and item.directory in pack.mods:
                            showsInPackFilter = True

                item.setHidden(showsInSearchQuery)

                if not showsInPackFilter:
                    item.setHidden(True)
            elif self.packFilter == "" and query == "":
                item.setHidden(False)


class PackItem(QListWidgetItem):
    def __init__(self, filePath=None):
        super().__init__()

        dateNow = date.now().strftime("%d/%m/%Y, %H:%M:%S")
        self.name = "New Pack (" + dateNow + ")"
        self.uuid = str(uuid.uuid4())
        self.dateCreated = dateNow
        self.dateModified = dateNow
        self.mods = []
        self.loaded = False
        self.filePath = None

        if filePath is not None:
            self.loaded = self.deserialize(filePath)
        else:
            self.loaded = True

        if not self.loaded:
            print(f"Could not load modpack of file path {filePath}")

        self.widget = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setSpacing(2)

        # Create name and count labels.
        self.title = PaperLineEdit()
        self.title.setMinimumSize(QSize(self.title.minimumSize().width(), 40))
        f = self.title.font()
        f.setBold(True)
        f.setPointSize(12)
        self.title.setFont(f)
        self.title.editingFinished.connect(self.rename)

        self.modCount = QLabel()

        self.setLabel()

        self.layout.addWidget(self.title)
        self.layout.addWidget(self.modCount)

        # Create buttons in grid.
        self.buttonGrid = QHBoxLayout()

        self.apply = PaperPushButton(PaperButtonType.Confirm, "Apply")
        self.buttonGrid.addWidget(self.apply)
        self.apply.clicked.connect(self.applyPack)

        self.export = PaperPushButton(PaperButtonType.Primary, "Export")
        self.buttonGrid.addWidget(self.export)
        self.export.clicked.connect(self.exportPack)

        self.duplicate = PaperPushButton(PaperButtonType.Primary, "Copy")
        self.buttonGrid.addWidget(self.duplicate)
        self.duplicate.clicked.connect(self.duplicatePack)

        self.delete = PaperPushButton(PaperButtonType.Danger, "Delete")
        self.buttonGrid.addWidget(self.delete)
        self.delete.clicked.connect(self.remove)

        self.layout.addLayout(self.buttonGrid)

        # Set item sizes.
        self.widget.setLayout(self.layout)
        self.shrink()

    # Checks if not a duplicate pack, and renames pack if duplicate name.
    def validate(self):
        # Check if duplicate UUID.
        for x in range(mainWindow.packList.count()):
            item = mainWindow.packList.item(x)
            if item.uuid == self.uuid:
                print(f"Pack of path {self.filePath} is already loaded!")
                QMessageBox.warning(
                    self, "Error", f'Pack "{self.name}" is already loaded!'
                )
                return False

        # Rename if duplicate
        for x in range(mainWindow.packList.count()):
            item = mainWindow.packList.item(x)
            if item.name == self.name:
                self.name = self.name + " (1)"
                self.setLabel()

        return True

    def expand(self):
        self.setSizeHint(QSize(200, 140))
        self.apply.setVisible(True)
        self.export.setVisible(True)
        self.duplicate.setVisible(True)
        self.delete.setVisible(True)

    def shrink(self):
        self.setSizeHint(QSize(200, 100))
        self.apply.setVisible(False)
        self.export.setVisible(False)
        self.duplicate.setVisible(False)
        self.delete.setVisible(False)

    def addMod(self, directory):
        if directory in self.mods:
            return

        self.mods.append(directory)
        self.setLabel()

    def removeMod(self, directory):
        self.mods.remove(directory)
        self.setLabel()

    def remove(self, cleanEntry):

        # Just remove the entry from the list without prompting a dialog.
        if cleanEntry:
            for x in range(mainWindow.packList.count() - 1, -1, -1):
                item = mainWindow.packList.item(x)
                if item.uuid == self.uuid:
                    mainWindow.packList.takeItem(x)

            return

        confirmation = QMessageBox()
        confirmation.setText(f'Are you sure you want to delete pack "{self.name}"?')
        confirmation.setInformativeText("This action is irreversible.")
        confirmation.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        confirmation.setDefaultButton(QMessageBox.StandardButton.Yes)

        ret = confirmation.exec()
        if ret == QMessageBox.StandardButton.Yes:
            for x in range(mainWindow.packList.count() - 1, -1, -1):
                item = mainWindow.packList.item(x)
                if item.uuid == self.uuid:
                    mainWindow.packList.takeItem(x)

            if self.filePath is not None and os.path.exists(self.filePath):
                os.remove(self.filePath)

            mainWindow.packList.updateModViewerPackList()

    def rename(self):
        # No change was made, don't bother the user.
        if self.title.displayText() == self.name:
            return

        for x in range(mainWindow.packList.count()):
            pack = mainWindow.packList.item(x)
            if pack.name == self.title.displayText():
                # Name already exists, reject and tell user.
                self.title.setText(self.name)
                QMessageBox.warning(
                    self.modCount, "Error", "This title already exists in another pack!"
                )

        self.name = self.title.displayText()
        mainWindow.packList.updateModViewerPackList()

    def setLabel(self):
        self.title.setText(self.name)
        self.modCount.setText(f"<font size=3><i>Mods: {len(self.mods)}</i></font>")

    def deserialize(self, filePath):
        self.filePath = filePath

        try:
            tree = ET.parse(filePath)
        except:
            print(f"Could not parse pack data at path {filePath}")
            return False

        root = tree.getroot()

        # Get name of pack.
        name = root.find("name")
        if name == None:
            print(f"No name found for pack of path {filePath}")
            QMessageBox.warning(
                self,
                "Error",
                f'Pack "{filePath}" could not be loaded (no name found)!',
            )
            return False

        self.name = name.text

        uuid = root.find("uuid")
        if uuid == None:
            print(f"No UUID found for pack of path {filePath}")
            QMessageBox.warning(
                self,
                "Error",
                f'Pack "{filePath}" could not be loaded (no uuid found)!',
            )
            return False

        self.uuid = uuid.text

        # Get date information.
        dateNow = date.now().strftime("%d/%m/%Y, %H:%M:%S")
        dateTag = root.find("date")
        if dateTag == None:
            self.dateCreated = dateNow
            self.dateModified = dateNow
        else:
            self.dateCreated = dateTag.get("created")
            self.dateModified = dateTag.get("modified")

        # Get mods in pack.
        self.mods = []
        modTag = root.find("mods")
        if modTag == None:
            print(f"No mods found for pack of path {filePath}")
            QMessageBox.warning(
                self,
                "Error",
                f'Pack "{filePath}" could not be loaded (no empty or filled mod list found)!',
            )
            return False

        mods = modTag.findall("mod")
        for mod in mods:
            self.mods.append(mod.text)

        return True

    def serialize(self, forcePath=None):
        # Serialize as XML.
        root = OtherET.Element("modpack")

        # Name tag.
        name = OtherET.SubElement(root, "name")
        name.text = self.name

        # UUID tag.
        uuidTag = OtherET.SubElement(root, "uuid")
        if forcePath:
            # Exporting, generate a new tag so that it can be imported again in the same list and be fine.
            uuidTag.text = str(uuid.uuid4())
        else:
            uuidTag.text = self.uuid

        # Date tag.
        dateNow = date.now().strftime("%d/%m/%Y, %H:%M:%S")
        self.dateModified = dateNow
        dateTag = OtherET.SubElement(
            root,
            "date",
            attrib={
                "created": self.dateCreated,
                "modified": self.dateModified,
            },
        )

        # Mod tags.
        modTag = OtherET.SubElement(root, "mods")
        for mod in self.mods:
            tag = OtherET.SubElement(modTag, "mod")
            tag.text = mod

        # Write.
        tree = OtherET.ElementTree(root)
        OtherET.indent(tree, space="\t", level=0)

        # Only set the filepath if it's being exported.
        if forcePath:
            tree.write(forcePath, encoding="utf-8")
        else:
            # Find file path.
            if self.filePath is None:
                # https://stackoverflow.com/a/7406369
                keepCharacters = (" ", ".", "_")
                filename = "".join(
                    c for c in self.name if c.isalnum() or c in keepCharacters
                ).rstrip()

                self.filePath = "packs/" + filename + ".xml"

            tree.write(self.filePath, encoding="utf-8")

        print(f"Successfully saved pack {self.name}")

    def exportPack(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter("Packs (*.xml)")
        dialog.setLabelText(QFileDialog.DialogLabel.FileName, "Export pack")
        dialog.fileSelected.connect(self.serialize)
        dialog.exec()

    def makeCopiedName(self, name=None):
        nameToCheck = name if name is not None else self.name
        for x in range(mainWindow.packList.count()):
            item = mainWindow.packList.item(x)
            if item.name == nameToCheck:
                nameToCheck += " (Copy)"
                return self.makeCopiedName(nameToCheck)

        return nameToCheck

    def duplicatePack(self):
        # Create new pack.
        newPack = PackItem()

        newPack.name = self.makeCopiedName()
        newPack.title.setText(newPack.name)

        newPack.mods = self.mods.copy()
        newPack.setLabel()

        mainWindow.packList.addItem(newPack)
        mainWindow.packList.setItemWidget(newPack, newPack.widget)

        mainWindow.packList.updateModViewerPackList()

    def applyPack(self):
        if len(self.mods) == 0:
            return

        for x in range(mainWindow.modList.count()):
            mod = mainWindow.modList.item(x)
            if mod.loaded:
                # If the mod is enabled and it shouldn't be.
                if mod.enabled and mod.directory not in self.mods:
                    mod.toggleMod()
                # If the mod is disabled and it shouldn't be.
                if not mod.enabled and mod.directory in self.mods:
                    mod.toggleMod()


class MiniPackItem(QListWidgetItem):
    def __init__(self, pack):
        super().__init__()

        self.pack = pack
        self.widget = QWidget()
        self.layout = QHBoxLayout()

        self.suppressChangeEvent = False

        self.label = QLabel(pack.name)

        f = self.label.font()
        f.setBold(True)
        f.setPointSize(10)
        self.label.setFont(f)

        self.layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.checkbox = QPushButton()
        self.checkbox.setFixedSize(16, 16)
        self.checkState = False

        self.refreshCheckboxStylesheet()

        self.checkbox.clicked.connect(self.checkClicked)

        self.layout.addWidget(self.checkbox, alignment=Qt.AlignmentFlag.AlignRight)

        self.widget.setLayout(self.layout)
        self.setSizeHint(QSize(200, 50))


    # Required after changing object name.
    # Required after changing object name.
    def refreshCheckboxStylesheet(self):
        if self.checkState:
            self.checkbox.setObjectName("modPackEnabled")
        else:
            self.checkbox.setObjectName("modPackDisabled")

        self.checkbox.setStyleSheet(
            """
            QPushButton#modPackEnabled{
                background-color: rgba(255, 255, 255, 0);
                border-image: url(resources/mini_box_tick_on.png);
            }

            QPushButton#modPackEnabled:hover{
                background-color: rgba(255, 255, 255, 0);
                border-image: url(resources/mini_box_tick_on_hover.png);
            }

            QPushButton#modPackDisabled{
                background-color: rgba(255, 255, 255, 0);
                border-image: url(resources/mini_box_tick_off.png);
            }

            QPushButton#modPackDisabled:hover{
                background-color: rgba(255, 255, 255, 0);
                border-image: url(resources/mini_box_tick_off_hover.png);
            }
            """
        )

    def checkClicked(self):
        self.checkState = not self.checkState
        self.checkChanged()

    def checkChanged(self):
        if self.suppressChangeEvent:
            return

        if selectedMod is not None:
            if self.checkState:
                self.pack.addMod(selectedMod.directory)
            else:
                self.pack.removeMod(selectedMod.directory)

        self.refreshCheckboxStylesheet()


class PackList(PaperListWidget):
    def __init__(self):
        super().__init__("#e1d0ba")

        self.setAlternatingRowColors(True)
        self.setViewMode(self.ViewMode.ListMode)
        self.setSelectionMode(self.SelectionMode.SingleSelection)
        self.setResizeMode(self.ResizeMode.Adjust)
        self.setAutoScroll(True)
        self.setDragEnabled(False)
        self.setBaseSize(QSize(400, self.baseSize().height()))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setSpacing(4)
        self.setMinimumWidth(400)

        self.scrollbar = PaperScrollbar(PaperScrollbarType.DockedList, self)
        self.setVerticalScrollBar(self.scrollbar)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.currentItemChanged.connect(self.selectionChanged)

        if not os.path.exists("packs/") or not os.path.isdir("packs/"):
            os.makedirs("packs/")

    def loadPacks(self):
        packsPath = "packs/"
        if not os.path.isdir(packsPath):
            # Create the packs directory.
            os.makedirs(packsPath)
            return

        items = []
        packsList = os.listdir(packsPath)
        for packXml in packsList:
            packPath = os.path.join(packsPath, packXml)
            if os.path.isfile(packPath) and packPath.lower().endswith(".xml"):
                packItem = PackItem(packPath)
                if packItem.validate():
                    items.append(packItem)

        items.sort(key=self.packSort)
        for item in items:
            self.addItem(item)
            self.setItemWidget(item, item.widget)

    def packSort(self, ele):
        return ele.dateCreated

    def selectionChanged(self, current, previous):
        if hasattr(previous, "shrink"):
            previous.shrink()

        if hasattr(current, "expand"):
            current.expand()

    def updateModViewerPackList(self):
        if mainWindow.modViewer is not None:
            mainWindow.modViewer.createPackList()


class PackListToolbar(QWidget):
    def __init__(self):
        super().__init__()

        # Create add pack button.
        self.packToolsLayout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.packToolsLayout.setContentsMargins(0, 0, 0, 0)

        self.newPackButton = PaperPushButton(PaperButtonType.Primary, "Add", self)
        self.packToolsLayout.addWidget(self.newPackButton)
        self.newPackButton.clicked.connect(self.addPack)

        # Create import pack button.
        self.importPackButton = PaperPushButton(PaperButtonType.Primary, "Import", self)
        self.packToolsLayout.addWidget(self.importPackButton)
        self.importPackButton.clicked.connect(self.importPack)

        # Create pack filter box.
        self.filterBox = PaperLineEdit()
        self.packToolsLayout.addWidget(self.filterBox, stretch=2)
        self.filterBox.setPlaceholderText("Search...")
        self.filterBox.textChanged.connect(self.filter)

        # Add pack filter stuff.
        self.setLayout(self.packToolsLayout)

    def filter(self):
        query = self.filterBox.displayText().lower()
        for i in range(mainWindow.packList.count()):
            item = mainWindow.packList.item(i)
            item.setHidden(query not in item.name.lower())

    def addPack(self):
        newPack = PackItem()
        mainWindow.packList.addItem(newPack)
        mainWindow.packList.setItemWidget(newPack, newPack.widget)
        self.updateModViewerPackList()

    def importPack(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter("Packs (*.xml)")
        dialog.setLabelText(QFileDialog.DialogLabel.FileName, "Import pack")
        dialog.fileSelected.connect(self.importedFile)
        dialog.exec()

    def importedFile(self, filePath):
        newPack = PackItem(filePath)
        if newPack.validate():
            # Update date created time.
            newPack.dateCreated = date.now().strftime("%d/%m/%Y, %H:%M:%S")

            # Remove file path so that it's generated later.
            # This prevents just saving to where the pack was imported from.
            newPack.filePath = None

            mainWindow.packList.addItem(newPack)
            mainWindow.packList.setItemWidget(newPack, newPack.widget)
            self.updateModViewerPackList()
        else:
            newPack.remove(True)

    def updateModViewerPackList(self):
        if mainWindow.modViewer is not None:
            mainWindow.modViewer.createPackList()


class PackListDropdownMenu(QMenu):
    def __init__(self, toolbar):
        super().__init__()
        self.toolbar = toolbar

        self.setStyleSheet("""
            color: "#2f2322";
            border-width: 8px 16px 12px 16px;
            border-image: url(./resources/backgrounds/textbrowser_background_64.png) 8 16 12 16 round;
            background: rgba(255, 255, 255, 0%);
        """)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def showEvent(self, event):
        self.toolbar.refreshPackChoices()
        event.accept()


class ModViewer(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("modViewer")
        self.setContentsMargins(8, 12, 8, 8)
        self.setStyleSheet("""
            QWidget#modViewer {
                color: "#2f2322";
                border-width: 32px 32px 32px 32px;
                border-image: url(./resources/backgrounds/modviewer_background_96.png) 32 32 32 32 round;
            }
        """)

        self.isaacFont = QFont("FontSouls_v3-Body")
        self.isaacFont.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        self.isaacFont.setPointSize(12)

        self.layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)

        self.titleLabel = QLabel()

        # Setup description area.
        self.descriptionLabel = PaperTextBrowser()
        self.descriptionLabel.setOpenExternalLinks(True)

        self.layout.addWidget(self.titleLabel)
        self.layout.addWidget(self.descriptionLabel)

        # Add/remove to pack button.
        self.addPackLayout = QBoxLayout(QBoxLayout.Direction.TopToBottom)

        self.addPackLabel = QLabel("<h2>Include in packs:</h2>")
        self.addPackLabel.setFont(self.isaacFont)
        self.addPackLayout.addWidget(self.addPackLabel)

        self.addPackList = PaperListWidget("#c5dff7")
        self.addPackList.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.addPackLayout.addWidget(self.addPackList)

        self.scrollbar = PaperScrollbar(PaperScrollbarType.MiniPackList, self)
        self.addPackList.setVerticalScrollBar(self.scrollbar)

        self.layout.addLayout(self.addPackLayout)
        self.setLayout(self.layout)

        self.createPackList()

    def createPackList(self):
        self.addPackList.clear()
        for x in range(mainWindow.packList.count()):
            item = mainWindow.packList.item(x)
            listItem = MiniPackItem(item)
            self.addPackList.addItem(listItem)
            self.addPackList.setItemWidget(listItem, listItem.widget)

        self.updatePackList()

    def updatePackList(self):
        for x in range(self.addPackList.count()):
            item = self.addPackList.item(x)
            if selectedMod is not None and selectedMod.directory in item.pack.mods:

                item.suppressChangeEvent = True
                item.checkState = True
                item.refreshCheckboxStylesheet()
                item.suppressChangeEvent = False
            else:
                item.suppressChangeEvent = True
                item.checkState = False
                item.refreshCheckboxStylesheet()
                item.suppressChangeEvent = False

    # Add custom rules to the bbcode parser, since Steam has some special tags.
    def parseBBCode(self, text):
        bbcodeParser = bbcode.Parser(replace_links=False)
        bbcodeParser.add_simple_formatter("h1", "<font size=5>%(value)s</font>")
        bbcodeParser.add_simple_formatter("h2", "<font size=4>%(value)s</font>")
        bbcodeParser.add_simple_formatter("h3", "<font size=3>%(value)s</font>")

        bbcodeParser.add_simple_formatter("olist", "<ol>%(value)s</ol>")

        bbcodeParser.add_simple_formatter("img", "<i>[image]</i>")

        bbcodeParser.add_simple_formatter(
            "spoiler", "<i>[start spoiler]</i> %(value)s <i>[end spoiler]</i>"
        )

        return bbcodeParser.format(text)

    def refresh(self):
        if not selectedMod:
            return

        self.selectionChanged(selectedMod)

    def selectionChanged(self, current):
        # Nothing is selected so just don't change.
        if current is None or not hasattr(current, "name"):
            return

        # Set title
        truncateConstant = 22
        title = current.name
        if len(title) > truncateConstant:
            title = title[0 : truncateConstant - 3] + "..."

        # Set workshop id.
        workshopId = "-"
        if hasattr(current, "workshopId"):
            workshopId = current.workshopId

        truncateConstant = 28
        directory = current.directory
        if len(directory) > truncateConstant:
            directory = directory[0 : truncateConstant - 3] + "..."

        self.titleLabel.setText(
            f"<font size=8><b>{title}</b></font><br/><font size=3><i>{directory} </i>/<i> Workshop ID: {workshopId}</i></font>"
        )

        # Parse description.
        html = self.parseBBCode(current.description)

        # Set description and update things.
        self.descriptionLabel.setText(html)

        global selectedMod
        selectedMod = current

        self.updatePackList()

    # Draw background.
    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Bookworm")
        self.setMinimumSize(1280, 800)
        self.setMaximumSize(1280, 800)

        self.mainBackground = QPixmap("./resources/backgrounds/library_background.png")
        self.mainBackground = self.mainBackground.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        self.backgroundPalette = QPalette()
        self.backgroundPalette.setBrush(QPalette.ColorRole.Window, self.mainBackground)
        self.setPalette(self.backgroundPalette)

    def setupWidgets(self):
        # Right side dock houses packs and settings.
        self.rightSideDock = QDockWidget()
        self.rightSideDock.setFeatures(
            QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        )

        self.rightSideDockWidget = QWidget()
        self.rightSideDockLayout = QVBoxLayout()

        # Set titlebar to empty widget to remove it.
        self.rightSideDock.setTitleBarWidget(QWidget())

        self.setupPackList()
        self.setupSettingsMenu()
        self.setupModList()
        self.setupModViewer()

        self.rightSideDockWidget.setLayout(self.rightSideDockLayout)
        self.rightSideDock.setWidget(self.rightSideDockWidget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.rightSideDock)

    def setupSettingsMenu(self):
        self.settingsMenuMasterWidget = PaperLargeWidget()
        self.settingsMenuMasterWidget.setContentsMargins(4, 38, 4, 4)
        self.settingsMenuMasterWidget.dockTitle = "Settings"
        self.settingsMenuMasterWidgetLayout = QHBoxLayout()

        self.locateMods = PaperPushButton(PaperButtonType.Primary, "Locate mods\nfolder")
        self.locateMods.clicked.connect(self.locateModsFolder)
        self.locateMods.setMaximumSize(120, 60)
        self.settingsMenuMasterWidgetLayout.addWidget(self.locateMods)

        self.disableAutoDownload = PaperPushButton(PaperButtonType.Primary)
        self.disableAutoDownload.clicked.connect(self.toggleAutoThumbnailDownload)
        self.disableAutoDownload.setMaximumSize(200, 60)
        self.settingsMenuMasterWidgetLayout.addWidget(self.disableAutoDownload)

        if settings.value("AutomaticThumbnailDownload") == "1":
            self.disableAutoDownload.setText("Disable automatic\nthumbnail download")
        else:
            self.disableAutoDownload.setText("Enable automatic\nthumbnail download")


        self.settingsMenuMasterWidget.setLayout(self.settingsMenuMasterWidgetLayout)

        self.rightSideDockLayout.addWidget(self.settingsMenuMasterWidget)

    def setupPackList(self):
        self.packListMasterWidget = PaperLargeWidget()
        self.packListMasterWidget.dockTitle = "Packs"
        self.packListMasterWidgetLayout = QHBoxLayout()

        self.packListDockWidget = QWidget()
        self.packListDockLayout = QBoxLayout(QBoxLayout.Direction.TopToBottom)

        # Create pack list.
        self.packList = PackList()
        self.packList.loadPacks()

        # Create toolbar.
        self.packToolbar = PackListToolbar()

        # Add widgets to dock.
        self.packListDockLayout.addWidget(self.packToolbar)
        self.packListDockLayout.addWidget(self.packList)

        self.packListDockWidget.setLayout(self.packListDockLayout)

        self.packListMasterWidgetLayout.addWidget(self.packListDockWidget)
        self.packListMasterWidget.setLayout(self.packListMasterWidgetLayout)

        self.rightSideDockLayout.addWidget(self.packListMasterWidget, stretch=2)

    def setupModList(self):
        self.modListMasterWidget = PaperLargeWidget()
        self.modListMasterWidget.dockTitle = "Mods"
        self.modListMasterWidgetLayout = QHBoxLayout()

        # Add mod list.
        self.modListDockWidget = QWidget()
        self.modListDockLayout = QBoxLayout(QBoxLayout.Direction.TopToBottom)
        self.modListDock = QDockWidget("Mods")
        self.modListDock.setObjectName("ModListDock")
        self.modListDock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.modListDock.setTitleBarWidget(QWidget())

        # Create mod list.
        self.modList = ModList()

        # Add mod list toolbar.
        self.modToolbar = ModListToolbar()

        # Add widgets to dock.
        self.modListDockLayout.addWidget(self.modToolbar)
        self.modListDockLayout.addWidget(self.modList)

        self.modListDockWidget.setLayout(self.modListDockLayout)

        self.modListMasterWidgetLayout.addWidget(self.modListDockWidget)
        self.modListMasterWidget.setLayout(self.modListMasterWidgetLayout)

        self.modListDock.setWidget(self.modListMasterWidget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.modListDock)

        # Setup icon queue thread.
        self.modList.iconThread.started.connect(self.modList.modIconQueueHandler.start)
        self.modList.iconThread.destroyed.connect(self.modList.modIconQueueHandler.stop)
        self.modList.iconThread.start(QThread.Priority.IdlePriority)

    def setupModViewer(self):
        # Add mod viewer.
        self.modViewer = ModViewer()

        self.setCentralWidget(self.modViewer)
        self.modList.currentItemChanged.connect(self.modViewer.selectionChanged)
        self.modViewer.selectionChanged(self.modList.item(0))

    def locateModsFolder(self):
        iconQueue.clear()
        getModsFolderPath(self)

    def toggleAutoThumbnailDownload(self):
        if settings.value("AutomaticThumbnailDownload") == "1":
            settings.setValue("AutomaticThumbnailDownload", "0")
            iconQueue.clear()
            self.modList.modIconQueueHandler.paused = True
            self.disableAutoDownload.setText("Enable automatic\nthumbnail download")
        else:
            settings.setValue("AutomaticThumbnailDownload", "1")
            self.modList.modIconQueueHandler.paused = False
            self.disableAutoDownload.setText("Disable automatic\nthumbnail download")

            # Reload mod list.
            mainWindow.modList.loadMods()

    def modFolderLocated(self):
        mainWindow.modList.loadMods()

    def closeIconTimer(self):
        self.modList.modIconQueueHandler.destroy.emit()

    def closeEvent(self, event):
        # Disable workshop icon queue.
        iconQueue.clear()

        self.modList.iconThread.requestInterruption()

        # Save packs.
        for x in range(mainWindow.packList.count()):
            item = mainWindow.packList.item(x)
            item.serialize()

        event.accept()


if __name__ == "__main__":
    app = QApplication([])
    app.setWindowIcon(QIcon("resources/app_icon.ico"))

    settings = QSettings("settings.ini", QSettings.IniFormat)
    applyDefaultSettings(settings)

    QFontDatabase.addApplicationFont("./resources/fonts/foursoulv3.otf")

    mainWindow = MainWindow()
    mainWindow.setupWidgets()

    mainWindow.show()

    app.exec()
    mainWindow.modList.iconThread.wait()
    sys.exit(0)
