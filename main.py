import sys
import os
import re
import random
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

import defusedxml.ElementTree as ET

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

class HTMLDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super(HTMLDelegate, self).__init__(parent)
        self.doc = QTextDocument(self)

    def paint(self, painter, option, index):
        painter.save()
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        self.doc.setHtml(options.text)
        options.text = ""
        style = QApplication.style() if options.widget is None \
            else options.widget.style()
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

        ctx = QAbstractTextDocumentLayout.PaintContext()
        if option.state & QStyle.State_Selected:
            ctx.palette.setColor(QPalette.Text, option.palette.color(
                QPalette.Active, QPalette.HighlightedText))
        else:
            ctx.palette.setColor(QPalette.Text, option.palette.color(
                QPalette.Active, QPalette.Text))
        textRect = style.subElementRect(QStyle.SE_ItemViewItemText, options, None)
        if index.column() != 0:
            textRect.adjust(5, 0, 0, 0)
        constant = 0
        margin = (option.rect.height() - options.fontMetrics.height()) / 4
        textRect.setTop(textRect.top() + margin)

        painter.translate(textRect.topLeft())
        painter.setClipRect(textRect.translated(-textRect.topLeft()))
        self.doc.documentLayout().draw(painter, ctx)
        painter.restore()

class ModItem(QListWidgetItem):
    def __init__(self, folderPath):

        QListWidgetItem.__init__(self)

        self.loaded = self.loadFromFile(folderPath=folderPath)

        if not self.loaded:
            return


        print(f"Load state for {folderPath}: {self.loaded}")

        self.icon = QIcon(QPixmap("resources/noicon.jpg"))

        # Apply loaded properties
        self.setText(f"{self.name}<br><font size=2>{self.directory}</font>")
        self.setIcon(self.icon)
        self.setSizeHint(QSize(200, 70))

        self.renderModIcon()

    # TODO: Get mod icon if workshop mod from Steam API.
    def renderModIcon(self):
        pass

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
            self.description = "[No description.]"
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
        self.setIconSize(QSize(52, 52))

        self.loadMods()

        # Sort list
        self.sortItems()

    def loadMods(self):
        modsPath = getModsFolderPath()
        if not os.path.isdir(modsPath):
            # Something went very wrong.
            return

        modsList = os.listdir(modsPath)
        for modFolder in modsList:
            folderPath = os.path.join(modsPath, modFolder)
            if os.path.isdir(folderPath):
                modItem = ModItem(folderPath)
                if modItem.loaded:
                    self.addItem(modItem)

class MainWidget(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Isaac Mod Manager")

        self.modList = ModList()
        self.modList.setItemDelegate(HTMLDelegate())
        self.modListDock = QDockWidget("Mod List")
        self.modListDock.setWidget(self.modList)
        self.modListDock.setObjectName("ModListDock")
        self.modListDock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.modListDock)

    @Slot()
    def magic(self):
        self.text.setText(random.choice(self.hello))


if __name__ == "__main__":
    app = QApplication([])

    settings = QSettings("settings.ini", QSettings.IniFormat)

    widget = MainWidget()
    widget.resize(800, 600)



    widget.show()

    sys.exit(app.exec())