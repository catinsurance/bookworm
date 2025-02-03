
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

def lerp(a, b, t):
    return (1 - t) * a + t * b

PAPER_BUTTON_HOVER_HEIGHT = 20

class PaperButtonType():
    Primary = "./resources/backgrounds/primary_64"
    Danger = "./resources/backgrounds/danger_64"
    Confirm = "./resources/backgrounds/confirm_64"

# (Resource path, background color)
class PaperScrollbarType():
    DockedList = ("./resources/backgrounds/scrollbar_packlist_32", "#e1d0ba")
    ModDescription = ("./resources/backgrounds/scrollbar_description_32", "#f9f8f7")

class PaperLineEdit(QLineEdit):
    def __init__(self):
        super().__init__()

        self.setStyleSheet("""
            color: "#2f2322";
            border-width: 8px 16px 12px 16px;
            border-image: url(./resources/backgrounds/search_background_64.png) 8 16 12 16 round;
        """)

class PaperTextBrowser(QTextBrowser):
    def __init__(self):
        super().__init__()

        self.setStyleSheet("""
            QTextBrowser {
                color: "#2f2322";
                border-width: 8px 16px 12px 16px;
                border-image: url(./resources/backgrounds/textbrowser_background_64.png) 8 16 12 16 round;
            }
        """)

        self.scrollbar = PaperScrollbar(PaperScrollbarType.ModDescription, self)
        self.setVerticalScrollBar(self.scrollbar)

# https://stackoverflow.com/a/16350754
class PaperScrollbar(QScrollBar):
    def __init__(self, scrollbarType, parent=None):
        super().__init__(parent)

        self.scrollbarType = scrollbarType
        self.setStyleSheet(f"""
            QScrollBar {{
                background: "#766d63";
                width: 12px;
                margin: 0px;
                border: none;
            }}

            QScrollBar::add-line:vertical {{
                background: none;
                border: none;
            }}

            QScrollBar::sub-line:vertical {{
                background: none;
                border: none;
            }}

            QScrollBar::handle:vertical {{
                background: "{self.scrollbarType[1]}";
                border-width: 8px 8px 8px 8px;
                border-image: url({self.scrollbarType[0]}.png) 8 8 8 8 round;
            }}
        """)
        self.valueChanged.connect(self.updateMask)
        self.rangeChanged.connect(self.updateMask)

    def updateMask(self):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)

        region = QRegion(self.style().subControlRect(QStyle.ComplexControl.CC_ScrollBar, opt, QStyle.SubControl.SC_ScrollBarSlider, self))
        self.setMask(region)

    def showEvent(self, event):
        QScrollBar.showEvent(self, event)
        self.updateMask()

class PaperListWidget(QListWidget):
    def __init__(self, backgroundColor):
        super().__init__()

        self.setAlternatingRowColors(True)
        self.setMouseTracking(True)
        self.setStyleSheet(f"""
            QListWidget {{
                color: transparent;
                background-color: transparent;
                border: none;
            }}

            QListWidget::item {{
                color: "#e1d0ba";
                background-color: none;
                border-width: 8px 8px 8px 8px;
                border-image: url(./resources/backgrounds/listitem_primary_64.png) 8 8 8 8 round;
            }}

            QListWidget::item::alternate {{
                color: "#e1d0ba";
                background-color: {backgroundColor};
                border-width: 8px 8px 8px 8px;
                border-image: url(./resources/backgrounds/listitem_secondary_64.png) 8 8 8 8 round;
            }}

            QListWidget::item:hover {{
                color: "#e1d0ba";
                background-color: none;
                border-width: 8px 8px 8px 8px;
                border-image: url(./resources/backgrounds/listitem_primary_64_highlight.png) 8 8 8 8 round;
            }}

            QListWidget::item::alternate:hover {{
                color: "#e1d0ba";
                background-color: "{backgroundColor}";
                border-width: 8px 8px 8px 8px;
                border-image: url(./resources/backgrounds/listitem_secondary_64_highlight.png) 8 8 8 8 round;
            }}
        """)

class PaperLargeWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.dockTitle = ""

        self.isaacFont = QFont("FontSouls_v3-Body")
        self.isaacFont.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        self.isaacFont.setPointSize(32)

        self.setObjectName("paperDockWidget")
        self.setContentsMargins(4, 32, 4, 4)
        self.setStyleSheet("""
            QWidget#paperDockWidget {
                color: "#2f2322";
                border-width: 32px 32px 32px 32px;
                border-image: url(./resources/backgrounds/dock_background_96.png) 32 32 32 32 round;
            }
        """)

    # Draw background.
    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)

        # Draw title
        painter.setFont(self.isaacFont)
        metrics = QFontMetrics(self.isaacFont)
        bounding = metrics.boundingRect(self.dockTitle)
        titlePoint = QPoint((event.rect().topRight().x() // 2) - (bounding.width() // 2), 38)
        painter.drawText(titlePoint, self.dockTitle)


class PaperToolButton(QToolButton):
    def __init__(self, paperType):
        super().__init__()

        self.paperType = paperType
        self.setStyleSheet(f"""
            border-width: 4px 8px 4px 8px;
            border-image: url({self.paperType + ".png"}) 4 8 4 8 round;
        """)

    def enterEvent(self, event):
        self.setStyleSheet(f"""
            border-width: 4px 8px 4px 8px;
            border-image: url({self.paperType + "_highlight.png"}) 4 8 4 8 round;
        """)
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(f"""
            border-width: 4px 8px 4px 8px;
            border-image: url({self.paperType + ".png"}) 4 8 4 8 round;
        """)
        return super().leaveEvent(event)

class PaperPushButton(QPushButton):
    def __init__(self, paperType, text = None, parent = None):
        super().__init__(text=text, parent=parent)

        self.paperType = paperType
        self.isaacFont = QFont("FontSouls_v3-Body")
        self.isaacFont.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        self.isaacFont.setPointSize(12)
        self.setFont(self.isaacFont)

        self.setStyleSheet(f"""
            border-width: 8px 12px 12px 12px;
            border-image: url({paperType + ".png"}) 8 12 12 12 round;
        """)

    def enterEvent(self, event):
        self.setStyleSheet(f"""
            border-width: 8px 12px 12px 12px;
            border-image: url({self.paperType + "_highlight.png"}) 8 12 12 12 round;
        """)
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(f"""
            border-width: 8px 12px 12px 12px;
            border-image: url({self.paperType + ".png"}) 8 12 12 12 round;
        """)
        return super().leaveEvent(event)