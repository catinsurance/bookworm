import sys
import os
import re
import uuid
import cv2
import requests
import threading, time

from datetime import datetime as date
from skimage import io
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import defusedxml.ElementTree as ET
import xml.etree.ElementTree as OtherET
import qtawesome as qta
import bbcode
from bs4 import BeautifulSoup

STEAM_PATH = None
WORKSHOP_ITEM_URL = "https://steamcommunity.com/sharedfiles/filedetails/?id="

selectedMod = None
iconQueueOpen = True
iconQueue = []

# Taken from Basement Renovator.
def getSteamPath():
    global STEAM_PATH
    if not STEAM_PATH:
        STEAM_PATH = QSettings(
            "HKEY_CURRENT_USER\\Software\\Valve\\Steam", QSettings.NativeFormat
        ).value("SteamPath")
    return STEAM_PATH

# TODO: Make this function prompt the user to locate the Isaac install directory themselves.
def locatePath():
    pass

# Based on code from Basement Renovator.
def getModsFolderPath():
    modsFolderPath = settings.value("ModsFolder")

    if modsFolderPath:
        # Return if folder exists at path, otherwise continue.
        if QFile.exists(modsFolderPath):
            return modsFolderPath

    # Mods folder path is no longer correct, search again.
    steamPath = getSteamPath()
    if not steamPath:
        # Could not find the Steam directory
        modsFolderPath = locatePath()
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
                    modsFolderPath = locatePath()

                # Get mods folder from this directory.
                modsFolderPath = os.path.join(installPath, "mods")

        # Could not find path, make sure locate it themselves.
        if not modsFolderPath or modsFolderPath == "" or not os.path.isdir(modsFolderPath):
            modsFolderPath = locatePath()

    settings.setValue("ModsFolder", modsFolderPath)
    return modsFolderPath


def applyDefaultSettings(settings):
    # Create default config file.

    getModsFolderPath()

def parseWorkshopPage(html):
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("img", recursive=True, attrs={"id":"previewImageMain"})
    if tag is not None:
        return tag.attrs["src"]

    return None

def handleIconQueue():
    while iconQueueOpen:
        if len(iconQueue) > 0:
            queued = iconQueue.pop(0)
            filePath = f"cache/thumb-{queued.workshopId}.png"

            if not os.path.exists(filePath):
                fetched = requests.get(WORKSHOP_ITEM_URL + queued.workshopId)
                html = fetched.content
                parsed = parseWorkshopPage(html)
                if parsed is not None:
                    if not os.path.exists("cache/") or not os.path.isdir("cache/"):
                        os.makedirs("cache/")

                    imgData = io.imread(parsed)

                    # cv2 uses BGR for some reason so swap stuff.
                    b,g,r = cv2.split(imgData)
                    rgbImgData = cv2.merge([r,g,b])

                    cv2.imwrite(filePath, cv2.resize(rgbImgData, (64, 64)))

                    modIcon = QPixmap(filePath)
                    queued.thumbnail.setIcon(modIcon)
                else:
                    print(f"Could not grab icon for workshop id {queued.workshopId}")

                    modIcon = QPixmap("resources/no_icon.png")
                    queued.thumbnailLabel.setText("Cannot download!")
                    queued.thumbnail.setIcon(modIcon)
                    queued.downloadFailure = True
            else:
                modIcon = QPixmap(filePath)
                queued.thumbnail.setIcon(modIcon)

            queued.thumbnail.setEnabled(True)
            queued.thumbnailLabel.setVisible(True)

        time.sleep(1)

# https://www.geeksforgeeks.org/pyqt5-scrollable-label/
class ScrollLabel(QScrollArea):

    # constructor
    def __init__(self, *args, **kwargs):
        QScrollArea.__init__(self, *args, **kwargs)

        # making widget resizable
        self.setWidgetResizable(True)

        # making qwidget object
        content = QWidget(self)
        self.setWidget(content)

        # vertical box layout
        lay = QVBoxLayout(content)

        # creating label
        self.label = QLabel(content)

        # setting alignment to the text
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # making label multi-line
        self.label.setWordWrap(True)

        # adding label to the layout
        lay.addWidget(self.label)

    # the setText method
    def setText(self, text):
        # setting text to the label
        self.label.setText(text)

class ModItem(QListWidgetItem):
    def __init__(self, folderPath):

        QListWidgetItem.__init__(self)

        self.loaded = self.loadFromFile(folderPath=folderPath)
        self.widget = QWidget()

        if not self.loaded:
            # Failed to load mod, tell the user and don't put any mod data.
            sadIcon = qta.icon("fa5s.sad-cry").pixmap(QSize(64, 64))
            self.thumbnail = QLabel()
            self.thumbnail.setPixmap(sadIcon)
            self.label = QLabel(f"<font size=5>Failed to read mod data!</font><br><font size=3><i>{folderPath}</i></font>")
        else:
            modIcon = QPixmap()
            modIcon.size().setWidth(64)
            modIcon.size().setHeight(64)

            self.workshopThumbLoaded = False

            if hasattr(self, "workshopId"):
                workshopThumb = f"cache/thumb-{self.workshopId}.png"
                if os.path.exists(workshopThumb):
                    modIcon.load(workshopThumb)
                    self.workshopThumbLoaded = True
                else:
                    modIcon.load("resources/no_icon.png")
            else:
                modIcon.load("resources/no_icon.png")

            self.thumbnail = QPushButton()
            self.thumbnail.setIcon(modIcon)
            self.thumbnail.setIconSize(QSize(64, 64))
            self.thumbnail.setEnabled(True)

            self.thumbnail.setStyleSheet("background-color: rgba(255, 255, 255, 0);")

            if hasattr(self, "workshopId"):
                self.thumbnail.setMouseTracking(True)
                self.thumbnail.clicked.connect(self.thumbnailClick)

                self.thumbnailLabel = QLabel(self.thumbnail)
                if self.workshopThumbLoaded:
                    self.thumbnailLabel.setText("Click to delete thumbnail")
                else:
                    self.thumbnailLabel.setText("Click to download thumbnail")

                self.thumbnailLabel.setWordWrap(True)
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
            truncate_length = 56
            if len(name) > truncate_length:
                name = name[0:(truncate_length - 3)] + "..."

            # Add checkbox
            self.checkbox = QPushButton()
            self.checkbox.iconDisabled = qta.icon("fa5s.square")
            self.checkbox.iconEnabled = qta.icon("fa5s.check-square")
            self.checkbox.setStyleSheet("background-color: rgba(255, 255, 255, 0);")

            if self.enabled:
                self.checkbox.setIcon(self.checkbox.iconEnabled)
            else:
                self.checkbox.setIcon(self.checkbox.iconDisabled)

            self.checkbox.setIconSize(QSize(64, 64))
            self.checkbox.clicked.connect(self.toggleMod)

            # Set text.
            self.label = QLabel(f"<font size=5>{name}</font><br><font size=3><i>{self.directory}</i></font>")

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(3, 3, 3, 3)

        self.thumbnail.setFixedSize(64, 64)
        self.layout.addWidget(self.thumbnail, alignment=Qt.AlignmentFlag.AlignLeft)
        self.layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.layout.addStretch()
        if hasattr(self, "checkbox"):
            self.checkbox.setFixedSize(64, 64)
            self.layout.addWidget(self.checkbox, alignment=Qt.AlignmentFlag.AlignRight)

        # Set item size.
        self.widget.setLayout(self.layout)
        self.setSizeHint(QSize(200, 70))

    def thumbnailClick(self):
        if hasattr(self, "downloadFailure"):
            return

        if not hasattr(self, "workshopId"):
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
            modIcon = QPixmap()
            modIcon.size().setWidth(64)
            modIcon.size().setHeight(64)
            self.thumbnail.setEnabled(False)
            iconQueue.append(self)
            self.thumbnail.setIcon(modIcon)

            self.thumbnailLabel.setVisible(False)
            self.thumbnailLabel.setText("Click to delete thumbnail")
            self.workshopThumbLoaded = True


    # Toggle the mod on or off.
    def toggleMod(self):
        if not self.loaded:
            return

        path = os.path.join(self.folderPath, "disable.it")
        if self.enabled:
            # Create disable.it at path.
            with open(path, "w") as fp:
                pass

            self.checkbox.setIcon(self.checkbox.iconDisabled)
            self.enabled = False
        else:
            # Remove disable.it (if it exists)
            if os.path.exists(path):
                os.remove(path)

            self.checkbox.setIcon(self.checkbox.iconEnabled)
            self.enabled = True

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

class ModList(QListWidget):
    def __init__(self):
        super().__init__()

        self.setAlternatingRowColors(True)
        self.setViewMode(self.ViewMode.ListMode)
        self.setSelectionMode(self.SelectionMode.SingleSelection)
        self.setResizeMode(self.ResizeMode.Adjust)
        self.setAutoScroll(True)
        self.setDragEnabled(False)
        self.setBaseSize(QSize(400, self.baseSize().height()))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(400)

        self.loadMods()

    def loadMods(self):
        modsPath = getModsFolderPath()
        if not os.path.isdir(modsPath):
            # Something went very wrong.
            return

        items = []
        modsList = os.listdir(modsPath)
        for modFolder in modsList:
            folderPath = os.path.join(modsPath, modFolder)
            if os.path.isdir(folderPath):
                modItem = ModItem(folderPath)
                items.append(modItem)

        items.sort(key=self.isaacSort)
        for item in items:
            self.addItem(item)
            self.setItemWidget(item, item.widget)

    # Gets the row that the mod with name `name` should show in.
    # Normal sorting is alphabetical case-insensitive, while this is alphabetical case-sensitive.
    def isaacSort(self, item):
        if not hasattr(item, "name"):
            return "zzzzzzzzzzzzz as low as possible"
        else:
            return item.name

class PackItem(QListWidgetItem):
    def __init__(self, packList, filePath = None):
        super().__init__()

        self.packList = packList

        dateNow = date.now().strftime("%H:%M:%S")
        self.name = "New Pack (" + dateNow + ")"
        self.uuid = str(uuid.uuid4())
        self.dateCreated = dateNow
        self.dateModified = dateNow
        self.mods = []
        self.loaded = False

        if filePath is not None:
            self.loaded = self.deserialize(filePath)
        else:
            self.serialize()
            self.loaded = True

        if not self.loaded:
            print(f"Could not load modpack of file path {filePath}")

        self.widget = QWidget()
        self.layout = QVBoxLayout()

        # Create rename button.

        # Create name and count labels.
        self.title = QLineEdit()
        self.title.setFixedSize(QSize(300, 30))
        f = self.title.font()
        f.setPointSize(12)
        self.title.setFont(f)
        self.title.editingFinished.connect(self.rename)

        self.modCount = QLabel()

        self.setLabel()

        self.layout.addWidget(self.title)
        self.layout.addWidget(self.modCount)

        # Create buttons in grid.
        self.buttonGrid = QGridLayout()

        self.apply = QPushButton("Apply")
        self.buttonGrid.addWidget(self.apply, 0, 0, 1, 1)
        self.apply.clicked.connect(self.applyPack)

        self.filter = QPushButton("Filter")
        self.buttonGrid.addWidget(self.filter, 0, 1, 1, 1)

        self.export = QPushButton("Export")
        self.buttonGrid.addWidget(self.export, 1, 0, 1, 1)
        self.export.clicked.connect(self.exportPack)

        self.delete = QPushButton("Delete")
        self.buttonGrid.addWidget(self.delete, 1, 1, 1, 1)
        self.delete.clicked.connect(self.remove)

        self.layout.addLayout(self.buttonGrid)
        self.apply.setVisible(False)
        self.filter.setVisible(False)
        self.export.setVisible(False)
        self.delete.setVisible(False)

        # Set item sizes.
        self.widget.setLayout(self.layout)
        self.setSizeHint(QSize(200, 70))

    def expand(self):
        self.setSizeHint(QSize(200, 140))
        self.apply.setVisible(True)
        self.filter.setVisible(True)
        self.export.setVisible(True)
        self.delete.setVisible(True)

    def shrink(self):
        self.setSizeHint(QSize(200, 70))
        self.apply.setVisible(False)
        self.filter.setVisible(False)
        self.export.setVisible(False)
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
            for x in range(self.packList.count()):
                item = self.packList.item(x)
                if hasattr(item, "uuid") and item.uuid == self.uuid:
                    self.packList.takeItem(x)

            return

        confirmation = QMessageBox()
        confirmation.setText(f'Are you sure you want to delete pack "{self.name}"?')
        confirmation.setInformativeText('This action is irreversible.')
        confirmation.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        confirmation.setDefaultButton(QMessageBox.StandardButton.Yes)

        ret = confirmation.exec()
        if ret == QMessageBox.StandardButton.Yes:
            if os.path.exists(self.filePath):
                os.remove(self.filePath)

            for x in range(self.packList.count()):
                item = self.packList.item(x)
                if hasattr(item, "uuid") and item.uuid == self.uuid:
                    self.packList.takeItem(x)

    def rename(self):
        self.name = self.title.displayText()
        self.packList.updateModViewerPackList()

    def setLabel(self):
        self.title.setText(self.name)
        self.modCount.setText(f"<font size=3><i>Mods: {len(self.mods)}</i></font>")

    def deserialize(self, filePath):
        self.filePath = filePath

        try:
            tree = ET.parse(self.filePath)
        except:
            print(f"Could not parse pack data at path {filePath}")
            return False

        root = tree.getroot()

        # Get name of pack.
        name = root.find("name")
        if name == None:
            print(f"No name found for pack of path {filePath}")
            return False

        self.name = name.text

        uuid = root.find("uuid")
        if uuid == None:
            print(f"No UUID found for pack of path {filePath}")
            return False

        for x in range(self.packList.count()):
            item = self.packList.item(x)
            if hasattr(item, "uuid") and item.uuid == uuid.text:
                print(f"Pack of path {filePath} is already loaded!")
                return False

        self.uuid = uuid.text

        # Get date information.
        dateNow = date.now().strftime("%H:%M:%S")
        dateTag = root.find("date")
        if date == None:
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
            return False

        mods = modTag.findall("mod")
        for mod in mods:
            self.mods.append(mod.text)

        return True


    def serialize(self, forcePath = None):
        # Serialize as XML.
        root = OtherET.Element("modpack")

        # Name tag.
        name = OtherET.SubElement(root, "name")
        name.text = self.name

        # UUID tag.
        uuid = OtherET.SubElement(root, "uuid")
        uuid.text = self.uuid

        # Date tag.
        dateNow = date.now().strftime("%H:%M:%S")
        self.dateModified = dateNow
        dateTag = OtherET.SubElement(root, "date", attrib={
            "created": self.dateCreated,
            "modified": self.dateModified,
        })

        # Mod tags.
        modTag = OtherET.SubElement(root, "mods")
        for mod in self.mods:
            tag = OtherET.SubElement(modTag, "mod")
            tag.text = mod

        # Write.
        tree = OtherET.ElementTree(root)
        OtherET.indent(tree, space="\t", level=0)

        # Find file path.
        # https://stackoverflow.com/a/7406369
        keepCharacters = (' ','.','_')
        filename = "".join(c for c in self.name if c.isalnum() or c in keepCharacters).rstrip()

        # Write (for real).
        filePath = "packs/" + filename + ".xml"

        # Only set the filepath if it's NOT being exported.
        if forcePath:
            filePath = forcePath
            tree.write(filePath, encoding="utf-8")
        else:
            self.filePath = filePath
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

    def applyPack(self):
        if len(self.mods) == 0:
            return

        for x in range(self.packList.modList.count()):
            mod = self.packList.modList.item(x)
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
        self.layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignLeft)

        self.checkbox = QCheckBox()

        self.checkbox.checkStateChanged.connect(self.checkChanged)
        self.layout.addWidget(self.checkbox, alignment=Qt.AlignmentFlag.AlignRight)

        self.widget.setLayout(self.layout)
        self.setSizeHint(QSize(200, 30))

    def checkChanged(self):
        if self.suppressChangeEvent:
            return

        if selectedMod is not None:
            if self.checkbox.isChecked():
                self.pack.addMod(selectedMod.directory)
            else:
                self.pack.removeMod(selectedMod.directory)


class PackList(QListWidget):
    def __init__(self, modList):
        super().__init__()

        self.modList = modList

        self.setAlternatingRowColors(True)
        self.setViewMode(self.ViewMode.ListMode)
        self.setSelectionMode(self.SelectionMode.SingleSelection)
        self.setResizeMode(self.ResizeMode.Adjust)
        self.setAutoScroll(True)
        self.setDragEnabled(False)
        self.setBaseSize(QSize(400, self.baseSize().height()))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(400)

        # Create add pack button.
        self.packToolsItem = QListWidgetItem()
        self.packToolsWidget = QWidget()
        self.packToolsLayout = QBoxLayout(QBoxLayout.Direction.LeftToRight)

        self.newPackButton = QPushButton("Add", self.packToolsWidget)
        self.packToolsLayout.addWidget(self.newPackButton)
        self.newPackButton.clicked.connect(self.addPack)

        # Create import pack button.
        self.importPackButton = QPushButton("Import", self.packToolsWidget)
        self.packToolsLayout.addWidget(self.importPackButton)
        self.importPackButton.clicked.connect(self.importPack)

        # Create pack filter box.
        self.filterBox = QLineEdit()
        self.packToolsLayout.addWidget(self.filterBox, stretch=2)
        self.filterBox.setPlaceholderText("Search...")
        self.filterBox.editingFinished.connect(self.filter)

        self.packToolsItem.setFlags(self.packToolsItem.flags() & ~Qt.ItemFlag.ItemIsSelectable)

        self.packToolsWidget.setLayout(self.packToolsLayout)
        self.packToolsItem.setSizeHint(QSize(200, 40))
        self.packToolsLayout.addStretch()
        self.addItem(self.packToolsItem)
        self.setItemWidget(self.packToolsItem, self.packToolsWidget)

        self.loadPacks()

    def importPack(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter("Packs (*.xml)")
        dialog.setLabelText(QFileDialog.DialogLabel.FileName, "Import pack")
        dialog.fileSelected.connect(self.importedFile)
        dialog.exec()

    def importedFile(self, filePath):
        newPack = PackItem(self, filePath)
        if newPack.loaded:
            self.addItem(newPack)
            self.setItemWidget(newPack, newPack.widget)
            self.updateModViewerPackList()
        else:
            newPack.remove(True)

    def addPack(self):
        newPack = PackItem(self, None)
        self.addItem(newPack)
        self.setItemWidget(newPack, newPack.widget)
        self.updateModViewerPackList()

    def updateModViewerPackList(self):
        if self.modViewer is not None:
            self.modViewer.createPackList(self)
            print("whahahaht")

    def filter(self):
        query = self.filterBox.displayText().lower()
        for i in range(self.count()):
            item = self.item(i)
            if hasattr(item, "name"):
                item.setHidden(query not in item.name.lower())


    def loadPacks(self):
        packsPath = "packs/"
        if not os.path.isdir(packsPath):
            # Something went very wrong.
            return

        items = []
        packsList = os.listdir(packsPath)
        for packXml in packsList:
            packPath = os.path.join(packsPath, packXml)
            if os.path.isfile(packPath) and packPath.lower().endswith(".xml"):
                packItem = PackItem(self, packPath)
                if packItem.loaded:
                    items.append(packItem)

        items.sort()
        for item in items:
            self.addItem(item)
            self.setItemWidget(item, item.widget)

    def selectionChanged(self, current, previous):
        if hasattr(previous, "shrink"):
            previous.shrink()

        if hasattr(current, "expand"):
            current.expand()

class ModViewer(QWidget):
    def __init__(self):
        super().__init__()

        self.layout = QBoxLayout(QBoxLayout.Direction.TopToBottom)

        self.titleLabel = QLabel()
        self.workshopLabel = QLabel()
        self.descriptionLabel = ScrollLabel()

        self.layout.addWidget(self.titleLabel)
        self.layout.addWidget(self.workshopLabel)
        self.layout.addWidget(self.descriptionLabel)

        # Add/remove to pack button.
        self.addPackLayout = QBoxLayout(QBoxLayout.Direction.TopToBottom)

        self.addPackLabel = QLabel("<h2>Included in packs:</h2>")
        self.addPackLayout.addWidget(self.addPackLabel)

        self.addPackList = QListWidget()
        self.addPackLayout.addWidget(self.addPackList)

        self.layout.addLayout(self.addPackLayout)
        self.setLayout(self.layout)

    def createPackList(self, packList):
        self.addPackList.clear()
        for x in range(packList.count()):
            item = packList.item(x)
            if hasattr(item, "name"):
                listItem = MiniPackItem(item)
                self.addPackList.addItem(listItem)
                self.addPackList.setItemWidget(listItem, listItem.widget)

    def updatePackList(self):
        for x in range(self.addPackList.count()):
            item = self.addPackList.item(x)
            if selectedMod is not None and selectedMod.directory in item.pack.mods:

                item.suppressChangeEvent = True
                item.checkbox.setCheckState(Qt.CheckState.Checked)
                item.suppressChangeEvent = False
            else:
                item.suppressChangeEvent = True
                item.checkbox.setCheckState(Qt.CheckState.Unchecked)
                item.suppressChangeEvent = False


    def parseBBCode(self, text):
        bbcodeParser = bbcode.Parser(replace_links=False)
        bbcodeParser.add_simple_formatter("h1", "<font size=5>%(value)s</font>")
        bbcodeParser.add_simple_formatter("h2", "<font size=4>%(value)s</font>")
        bbcodeParser.add_simple_formatter("h3", "<font size=3>%(value)s</font>")

        bbcodeParser.add_simple_formatter("olist", "<ol>%(value)s</ol>")

        bbcodeParser.add_simple_formatter("img", '<i>[image]</i>')

        # TODO: Implement spoiler tags with this.
        bbcodeParser.add_simple_formatter("spoiler", '<span class="spoiler">%(value)s</span>')

        return bbcodeParser.format(text)

    def refresh(self):
        if not selectedMod:
            return

        self.selectionChanged(selectedMod)

    def selectionChanged(self, current):
        # Set title
        self.titleLabel.setText(f"<font size=8>{current.name}</font><br/><font size=3>({current.directory})</font>")

        # Set workshop id.
        if hasattr(current, "workshopId"):
            self.workshopLabel.setText(f"Workshop ID: {current.workshopId}")
        else:
            self.workshopLabel.setText("Workshop ID: -")

        # Set description

        html = self.parseBBCode(current.description)
        self.descriptionLabel.setText(html)

        global selectedMod
        selectedMod = current

        self.updatePackList()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Isaac Mod Manager")

        self.modList = ModList()
        self.modListDock = QDockWidget("Mods")
        self.modListDock.setWidget(self.modList)
        self.modListDock.setObjectName("ModListDock")
        self.modListDock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.modListDock)

        self.packList = PackList(self.modList)
        self.packListDock = QDockWidget("Packs")
        self.packListDock.setWidget(self.packList)
        self.packListDock.setObjectName("PackListDock")
        self.packListDock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.packListDock)
        self.packList.currentItemChanged.connect(self.packList.selectionChanged)

        self.modViewer = ModViewer()
        self.modViewer.modList = self.modList
        self.packList.modViewer = self.modViewer
        self.modViewer.createPackList(self.packList)

        self.setCentralWidget(self.modViewer)
        self.modList.currentItemChanged.connect(self.modViewer.selectionChanged)

    def closeEvent(self, event):
        # Save packs.
        for x in range(self.packList.count()):
            item = self.packList.item(x)
            if hasattr(item, "serialize"):
                item.serialize()

    def closeEvent(self, event):
        global iconQueueOpen
        iconQueueOpen = False

        event.accept()


if __name__ == "__main__":
    app = QApplication([])

    settings = QSettings("settings.ini", QSettings.IniFormat)

    widget = MainWindow()
    widget.setMinimumSize(1200, 800)
    widget.setMaximumSize(1200, 800)

    widget.show()

    thread = threading.Thread(target=handleIconQueue)
    thread.start()

    sys.exit(app.exec())