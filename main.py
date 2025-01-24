import sys
import os
import re
import random
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import defusedxml.ElementTree as ET
import qtawesome as qta
import bbcode

STEAM_PATH = None

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
            print(f"Load state for {folderPath}: {self.loaded}")

            # TODO: Get mod icon if workshop upload.
            modIcon = QPixmap()
            modIcon.size().setWidth(64)
            modIcon.size().setHeight(64)
            modIcon.load("resources/no_icon.png")
            self.thumbnail = QLabel()
            self.thumbnail.setPixmap(modIcon)

            # Truncate text if too long.
            name = self.name
            truncate_length = 56
            if len(name) > truncate_length:
                name = name[0:(truncate_length - 3)] + "..."

            # Add checkbox
            self.checkbox = QPushButton()
            self.checkbox.iconDisabled = qta.icon("fa5s.square")
            self.checkbox.iconEnabled = qta.icon("fa5s.check-square")

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

        self.setLayout(self.layout)

    def parseBBCode(self, text):
        bbcodeParser = bbcode.Parser(replace_links=False)
        bbcodeParser.add_simple_formatter("h1", "<font size=5>%(value)s</font>")
        bbcodeParser.add_simple_formatter("h2", "<font size=4>%(value)s</font>")
        bbcodeParser.add_simple_formatter("h3", "<font size=3>%(value)s</font>")

        bbcodeParser.add_simple_formatter("olist", "<ol>%(value)s</ol>")

        bbcodeParser.add_simple_formatter("img", '<i>[image]</i>')

        return bbcodeParser.format(text)


    def selectionChanged(self, current, previous):
        # Set title
        self.titleLabel.setText(f"<font size=8>{current.name}</font> <font size=3>    ({current.directory})</font>")

        # Set workshop id.
        if hasattr(current, "workshopId"):
            self.workshopLabel.setText(f"Workshop ID: {current.workshopId}")
        else:
            self.workshopLabel.setText("Workshop ID: -")

        # Set description

        html = self.parseBBCode(current.description)
        self.descriptionLabel.setText(html)





class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Isaac Mod Manager")

        self.modList = ModList()
        self.modListDock = QDockWidget("Mod List")
        self.modListDock.setWidget(self.modList)
        self.modListDock.setObjectName("ModListDock")
        self.modListDock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.modListDock)

        self.modViewer = ModViewer()
        self.modViewer.modList = self.modList
        self.setCentralWidget(self.modViewer)

        self.modList.currentItemChanged.connect(self.modViewer.selectionChanged)

if __name__ == "__main__":
    app = QApplication([])

    settings = QSettings("settings.ini", QSettings.IniFormat)

    widget = MainWindow()
    widget.setMinimumSize(1200, 800)
    widget.setMaximumSize(1200, 800)

    widget.show()

    sys.exit(app.exec())