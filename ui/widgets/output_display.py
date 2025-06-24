import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QSizePolicy
from PyQt6.QtGui import QFont
from database import AgentRepository
from workers import CommandOutputMonitor
from utils import FontManager

class OutputDisplay(QWidget):
    def __init__(self, agent_repository: AgentRepository):
        super().__init__()
        self.agent_repository = agent_repository
        self.current_agent_id = None
        self.output_monitor = None
        
        # Set size policy to prevent unwanted expansion
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(120)
        self.setMaximumHeight(400)
        
        # Try to use FontManager, but don't fail if it's not available
        try:
            FontManager().add_relative_font_widget(self, 0)
            self.font_manager = FontManager()
        except:
            self.font_manager = None
            
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.output_display = QPlainTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setPlaceholderText("Waiting for command output...")
        
        if self.font_manager:
            self.font_manager.add_relative_font_widget(self.output_display, -4)
        self.output_display.setFont(QFont("Consolas", 10))
        
        layout.addWidget(self.output_display)
        self.setLayout(layout)

    def set_agent(self, agent_id: str):
        """Switch to monitoring a different agent"""
        if agent_id == self.current_agent_id:
            return
            
        self.current_agent_id = agent_id
        self.output_display.clear()
        
        # Stop existing monitor if any
        if self.output_monitor is not None:
            self.output_monitor.stop()
            self.output_monitor.wait()
        
        # Start new monitor
        from config import ServerConfig
        config = ServerConfig()
        self.output_monitor = CommandOutputMonitor(agent_id, self.agent_repository, config)
        self.output_monitor.output_received.connect(self.update_output)
        self.output_monitor.start()

    def update_output(self, text: str):
        """Update the display with new content, filtering out blank lines"""
        filtered_text = '\n'.join(filter(lambda x: not re.match(r'^\s*$', x), text.split('\n')))
        if filtered_text:
            # Update the text
            self.output_display.setPlainText(filtered_text)
            # Scroll to bottom since we have new content
            self.output_display.verticalScrollBar().setValue(
                self.output_display.verticalScrollBar().maximum()
            )

    def cleanup(self):
        """Cleanup resources before widget destruction"""
        if self.output_monitor is not None:
            self.output_monitor.stop()
            self.output_monitor.wait()