from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont

class LogWidget(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setMaximumHeight(200)
        self.setPlaceholderText("Logs will appear here...")
        
        # Set monospace font for better log readability
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)

    @pyqtSlot(str)
    def append_log(self, message: str):
        """Append a log message to the widget"""
        self.append(message)
        
        # Auto-scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())