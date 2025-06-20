from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QSpinBox, QPushButton, QApplication, QMessageBox)
from config import ConfigManager, ServerConfig
from services import ServerManager
from utils import FontManager

class SettingsPage(QWidget):
    def __init__(self, config_manager: ConfigManager, 
                 server_manager: ServerManager,
                 parent: QWidget = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.server_manager = server_manager
        
        # Try to use FontManager, but don't fail if it's not available
        try:
            FontManager().add_relative_font_widget(self, 0)
        except:
            pass

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Font Settings Group
        font_group = QGroupBox("Font Size")
        font_layout = QVBoxLayout()
        
        # Font size spinner and apply button
        font_size_layout = QHBoxLayout()
        
        self.font_size_spinner = QSpinBox()
        self.font_size_spinner.setRange(8, 32)
        self.font_size_spinner.setValue(QApplication.instance().font().pointSize())
        
        self.apply_font_button = QPushButton("Apply")
        self.apply_font_button.clicked.connect(self.on_font_size_changed)
        
        font_size_layout.addWidget(self.font_size_spinner)
        font_size_layout.addWidget(self.apply_font_button)
        font_size_layout.addStretch()
        font_layout.addLayout(font_size_layout)
        font_group.setLayout(font_layout)
        
        # Port Settings Group
        port_group = QGroupBox("Server Listener Port")
        base_style = port_group.styleSheet()
        style = """ 
            QGroupBox {
                background: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #424242, stop:1 #232323);
            }
            QGroupBox::title {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #232323);                
                padding-right: 2000px;
            }
        """
        port_group.setStyleSheet(base_style + style)
        font_group.setStyleSheet(base_style + style)

        port_layout = QVBoxLayout()
        
        # Port number input and apply button
        port_input_layout = QHBoxLayout()
        
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        
        # Get current port from config
        config = ServerConfig()
        self.port_input.setValue(config.COMBINED_PORT)
        
        self.apply_port_button = QPushButton("Apply")
        self.apply_port_button.clicked.connect(self.on_port_changed)
        
        port_input_layout.addWidget(self.port_input)
        port_input_layout.addWidget(self.apply_port_button)
        port_input_layout.addStretch()
        port_layout.addLayout(port_input_layout)
        port_group.setLayout(port_layout)
        
        # Add groups to main layout
        layout.addWidget(font_group)
        layout.addWidget(port_group)
        layout.addStretch()

    def on_font_size_changed(self):
        size = self.font_size_spinner.value()
        app = QApplication.instance()
        font = app.font()
        font.setPointSize(size)
        app.setFont(font)
        
        # Update all relative fonts
        try:
            FontManager().update_all_relative_fonts()
        except:
            pass
        
        self.config_manager.save_settings(self.port_input.value(), size)
        
    def on_port_changed(self):
        port = self.port_input.value()
        
        success = self.server_manager.change_port(port)
        
        if success:
            self.config_manager.save_settings(port, self.font_size_spinner.value())
            QMessageBox.information(self, "Success", f"Server port changed to {port}")
        else:
            QMessageBox.critical(self, "Error", "Failed to change port")
            # Reset to current config port
            config = ServerConfig()
            self.port_input.setValue(config.COMBINED_PORT)