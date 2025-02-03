
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

class PaperLineEdit(QLineEdit):
    def __init__(self):
        super().__init__()

        self.setStyleSheet(f"""
            color: "#2f2322";
            border-width: 8px 16px 12px 16px;
            border-image: url(./resources/backgrounds/search_background_64.png) 8 16 12 16 round;
        """)

class PaperGenericWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setStyleSheet("""
            color: "#2f2322";
            border-width: 8px 16px 12px 16px;
            border-image: url(./resources/backgrounds/search_background_64.png) 8 16 12 16 round;
        """)


class PaperLargeWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("paperDockWidget")
        self.setContentsMargins(4, 4, 4, 4)
        self.setStyleSheet("""
            QWidget#paperDockWidget {
                color: "#2f2322";
                border-width: 32px 32px 32px 32px;
                border-image: url(./resources/backgrounds/dock_background_96.png) 32 32 32 32 round;
            }

            QListWidget {
                color: "#2f2322";
                border-width: 8px 16px 12px 16px;
                border-image: url(./resources/backgrounds/search_background_64.png) 8 16 12 16 round;
            }

            QListWidget::item {
                color: "#2f2322";
                border-width: 8px 8px 8px 8px;
                border-image: url(./resources/backgrounds/listitem_primary_64.png) 8 8 8 8 round;
            }

            QListWidget::item::alternate {
                color: "#2f2322";
                background-color: "#e1e1e1";
                border-width: 8px 8px 8px 8px;
                border-image: url(./resources/backgrounds/listitem_secondary_64.png) 8 8 8 8 round;
            }
        """)

    # Draw background.
    def paintEvent(self, event):
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)


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