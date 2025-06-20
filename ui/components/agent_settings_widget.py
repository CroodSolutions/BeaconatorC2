from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QLineEdit, QPushButton, QLabel, QMessageBox)
from database import AgentRepository
from utils import FontManager

class AgentSettingsWidget(QWidget):
    """Widget for managing agent settings and lifecycle"""
    def __init__(self, agent_repository: AgentRepository):
        super().__init__()
        self.agent_repository = agent_repository
        self.current_agent_id = None
        
        # Try to use FontManager, but don't fail if it's not available
        try:
            FontManager().add_relative_font_widget(self, 0)
        except:
            pass
            
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Check-in Settings
        settings_group = QGroupBox()
        settings_layout = QHBoxLayout()
        
        interval_input = QLabel("Update Check-In: ")
        self.interval_input = QLineEdit()
        self.interval_input.setPlaceholderText("Interval (seconds)")
        self.interval_input.setToolTip(
            "Enter the new check in interval in seconds\n"
            "Example: 30"
        )
        self.UpdateCheckIn_btn = QPushButton("Update")
        self.UpdateCheckIn_btn.clicked.connect(self.send_UpdateCheckIn)
        
        settings_layout.addWidget(interval_input)
        settings_layout.addWidget(self.interval_input)
        settings_layout.addWidget(self.UpdateCheckIn_btn)
        settings_group.setLayout(settings_layout)

        # Agent Control
        control_group = QGroupBox()
        control_layout = QVBoxLayout()
        
        # Shutdown button
        self.shutdown_btn = QPushButton("Shutdown Agent")
        self.shutdown_btn.setMinimumHeight(40)  # Medium height
        self.shutdown_btn.setStyleSheet(self.styleSheet() + """
            QPushButton {
                background-color: #8B0000;
                color: white;
            }
            QPushButton:hover {
                background-color: #A00000;
            }
        """)
        self.shutdown_btn.clicked.connect(self.shutdown_agent)
        
        # Delete button
        self.delete_btn = QPushButton("Delete Agent")
        self.delete_btn.setMinimumHeight(50)  # Larger height
        self.delete_btn.setStyleSheet(self.styleSheet() + """
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A00000;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_agent)

        control_layout.addWidget(self.shutdown_btn)
        control_layout.addWidget(self.delete_btn)
        control_group.setLayout(control_layout)

        # Add styles
        base_style = settings_group.styleSheet()
        style = """ 
                    QGroupBox {
                background: #303030
            }
            QGroupBox::title {              
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding-left: 2000px;
                padding-right: 2000px;
            }
        """
        settings_group.setStyleSheet(base_style + style)
        control_group.setStyleSheet(base_style + style)
        
        # Add sections to main layout
        layout.addWidget(settings_group)
        layout.addWidget(control_group)
        layout.addStretch()  # Pushes widgets to top
        self.setLayout(layout)

    def send_UpdateCheckIn(self):
        """Update agent check-in interval"""
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        try:
            interval = int(self.interval_input.text())

            command = f"execute_module|UpdateCheckIn|{interval}"

            self.agent_repository.update_agent_command(self.current_agent_id, command)
            QMessageBox.information(
                self,
                "Success",
                f"Check-in interval update scheduled for agent {self.current_agent_id}"
            )
            self.interval_input.clear()
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid number of seconds")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Update error: {str(e)}")

    def shutdown_agent(self):
        """Shutdown the selected agent"""
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Shutdown",
            f"Are you sure you want to shutdown agent {self.current_agent_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Placeholder for actual implementation
                self.agent_repository.update_agent_command(
                    self.current_agent_id,
                    "shutdown"
                )
                QMessageBox.information(
                    self,
                    "Success",
                    f"Shutdown command sent to agent {self.current_agent_id}"
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Shutdown error: {str(e)}")

    def delete_agent(self):
        """Delete the selected agent"""
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete agent {self.current_agent_id}?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.agent_repository.delete_agent(self.current_agent_id):
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Agent {self.current_agent_id} has been deleted"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Agent {self.current_agent_id} not found"
                    )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Delete error: {str(e)}")

    def set_agent(self, agent_id: str):
        """Set the current agent ID"""
        self.current_agent_id = agent_id