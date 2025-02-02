
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

def lerp(a, b, t):
    return (1 - t) * a + t * b

PAPER_BUTTON_HOVER_HEIGHT = 20

class PaperButtonType():
    Primary = "./resources/buttons/primary_64"
    Danger = "./resources/buttons/danger_64"
    Confirm = "./resources/buttons/confirm_64"

# 10mb for a custom font in a stupid, archaic format? SATISFACTORY!!!!
class PaperLineEdit(QLineEdit):
    def __init__(self):
        super().__init__()

        self.setStyleSheet(f"""
            color: "#2f2322";
            border-width: 8px 16px 12px 16px;
            border-image: url(./resources/search_background_64.png) 8 16 12 16 round;
        """)

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
            border-width: 8px 16px 12px 16px;
            border-image: url({paperType + ".png"}) 8 16 12 16 round;
        """)

    def enterEvent(self, event):
        self.setStyleSheet(f"""
            border-width: 8px 16px 12px 16px;
            border-image: url({self.paperType + "_highlight.png"}) 8 16 12 16 round;
        """)
        return super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(f"""
            border-width: 8px 16px 12px 16px;
            border-image: url({self.paperType + ".png"}) 8 16 12 16 round;
        """)
        return super().leaveEvent(event)