import sys
from typing import Optional
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QWidget
from PySide6.QtGui import QColor, QPainter


class ColoredSquareWidget(QFrame):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = color
        self.setStyleSheet("border: 2px solid #FFaaaaaa")

    def sizeHint(self):
        return self.size()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.fillRect(rect, self.color)


class PixelColorWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        self.label = QLabel("<no color>")
        self.label.setFixedWidth(self.label.fontMetrics().boundingRect(self.label.text()).width())
        self.colored_square = ColoredSquareWidget(QColor(0, 0, 0, 0))  # Red square
        self.colored_square.setFixedHeight(self.label.sizeHint().height())
        self.colored_square.setFixedWidth(self.label.sizeHint().height())
        layout.addWidget(self.colored_square)
        layout.addWidget(self.label)

    def set_color(self, color: Optional[QColor]):
        if color is None:
            self.label.setText("<no color>")
            self.colored_square.color = QColor(0, 0, 0, 0)
        else:
            self.colored_square.color = color
            self.label.setText(color.name())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = PixelColorWidget()
    widget.set_color(None)
    widget.show()
    sys.exit(app.exec())
