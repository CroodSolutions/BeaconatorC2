from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QLineEdit, QPushButton, QLabel, QMessageBox, QComboBox)
from PyQt6.QtCore import pyqtSignal
from database import BeaconRepository
from services import SchemaService
from utils import FontManager

class BeaconSettingsWidget(QWidget):
    """Widget for managing beacon settings and lifecycle"""
    
    # Signal emitted when a schema is applied to a beacon
    schema_applied = pyqtSignal(str, str)  # beacon_id, schema_file
    
    def __init__(self, beacon_repository: BeaconRepository):
        super().__init__()
        self.beacon_repository = beacon_repository
        self.schema_service = SchemaService()
        self.current_beacon_id = None
        
        # Schema cache shared with command widget to avoid duplicate queries
        self._schema_cache = getattr(beacon_repository, '_schema_cache', {})
        if not hasattr(beacon_repository, '_schema_cache'):
            beacon_repository._schema_cache = self._schema_cache
        
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

        # Beacon Control
        control_group = QGroupBox("Beacon Control")
        control_layout = QVBoxLayout()
        
        # Shutdown button
        self.shutdown_btn = QPushButton("Shutdown Beacon")
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
        self.delete_btn = QPushButton("Delete Beacon")
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
        self.delete_btn.clicked.connect(self.delete_beacon)

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
        
        # Beacon Schema Selection
        schema_group = QGroupBox("Beacon Schema")
        schema_layout = QVBoxLayout()
        
        # Schema selection with button in same row
        schema_select_layout = QHBoxLayout()
        schema_select_layout.addWidget(QLabel("Schema:"))
        self.schema_combo = QComboBox()
        self.schema_combo.setMinimumWidth(200)
        self.schema_combo.setMinimumHeight(30)  # Ensure adequate height
        # Ensure dropdown appears properly without conflicts
        self.schema_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.schema_combo.setMaxVisibleItems(10)  # Limit dropdown height
        schema_select_layout.addWidget(self.schema_combo)
        
        # Apply button in same row to avoid dropdown overlap
        apply_schema_btn = QPushButton("Apply")
        apply_schema_btn.setMinimumWidth(80)
        apply_schema_btn.setToolTip("Apply selected schema to this beacon")
        apply_schema_btn.clicked.connect(self.apply_schema)
        schema_select_layout.addWidget(apply_schema_btn)
        
        schema_layout.addLayout(schema_select_layout)
        
        # Add some spacing to prevent any layout issues
        schema_layout.addSpacing(10)
        schema_group.setLayout(schema_layout)

        # Add sections to main layout
        layout.addWidget(schema_group)
        layout.addWidget(settings_group)
        layout.addWidget(control_group)
        layout.addStretch()  # Pushes widgets to top
        self.setLayout(layout)
        
        # Apply styles to schema group
        schema_group.setStyleSheet(base_style + style)
        
        # Initialize schema list
        self.refresh_schemas()

    def refresh_schemas(self):
        """Refresh the list of available schemas"""
        current_selection = self.schema_combo.currentData()
        self.schema_combo.clear()
        self.schema_combo.addItem("No schema selected", "")
        
        try:
            schemas = self.schema_service.list_available_schemas()
            for schema in schemas:
                self.schema_combo.addItem(schema, schema)
            
            # Restore previous selection if possible
            if current_selection:
                index = self.schema_combo.findData(current_selection)
                if index >= 0:
                    self.schema_combo.setCurrentIndex(index)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load schemas: {e}")
    
    def apply_schema(self):
        """Apply selected schema to the current beacon"""
        if not self.current_beacon_id:
            QMessageBox.warning(self, "Warning", "No beacon selected!")
            return
        
        schema_file = self.schema_combo.currentData()
        
        try:
            if schema_file:
                # Update beacon's schema in database
                success = self.beacon_repository.update_beacon_schema(self.current_beacon_id, schema_file)
                if success:
                    # Emit signal to notify other widgets about the schema change
                    self.schema_applied.emit(self.current_beacon_id, schema_file)
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Schema '{schema_file}' applied to beacon {self.current_beacon_id}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Failed to apply schema to beacon {self.current_beacon_id}"
                    )
            else:
                # Remove schema association
                success = self.beacon_repository.update_beacon_schema(self.current_beacon_id, None)
                if success:
                    # Emit signal to notify other widgets about the schema removal
                    self.schema_applied.emit(self.current_beacon_id, "")
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Schema removed from beacon {self.current_beacon_id}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Failed to remove schema from beacon {self.current_beacon_id}"
                    )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Schema update error: {str(e)}")

    def send_UpdateCheckIn(self):
        """Update beacon check-in interval"""
        if not self.current_beacon_id:
            QMessageBox.warning(self, "Warning", "No beacon selected!")
            return

        try:
            interval = int(self.interval_input.text())

            command = f"execute_module|UpdateCheckIn|{interval}"

            self.beacon_repository.update_beacon_command(self.current_beacon_id, command)
            QMessageBox.information(
                self,
                "Success",
                f"Check-in interval update scheduled for beacon {self.current_beacon_id}"
            )
            self.interval_input.clear()
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid number of seconds")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Update error: {str(e)}")

    def shutdown_agent(self):
        """Shutdown the selected beacon"""
        if not self.current_beacon_id:
            QMessageBox.warning(self, "Warning", "No beacon selected!")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Shutdown",
            f"Are you sure you want to shutdown beacon {self.current_beacon_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Placeholder for actual implementation
                self.beacon_repository.update_beacon_command(
                    self.current_beacon_id,
                    "shutdown"
                )
                QMessageBox.information(
                    self,
                    "Success",
                    f"Shutdown command sent to beacon {self.current_beacon_id}"
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Shutdown error: {str(e)}")

    def delete_beacon(self):
        """Delete the selected beacon"""
        if not self.current_beacon_id:
            QMessageBox.warning(self, "Warning", "No beacon selected!")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete beacon {self.current_beacon_id}?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.beacon_repository.delete_beacon(self.current_beacon_id):
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Beacon {self.current_beacon_id} has been deleted"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Beacon {self.current_beacon_id} not found"
                    )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Delete error: {str(e)}")

    def set_beacon(self, beacon_id: str):
        """Set the current beacon ID and load its associated schema with caching"""
        # Early exit if same beacon
        if beacon_id == self.current_beacon_id:
            return
            
        self.current_beacon_id = beacon_id
        
        # Load beacon's current schema if available
        if beacon_id:
            try:
                # Check cache first to avoid database query
                current_schema = self._schema_cache.get(beacon_id)
                if current_schema is None:  # Not in cache
                    current_schema = self.beacon_repository.get_beacon_schema(beacon_id)
                    self._schema_cache[beacon_id] = current_schema
                if current_schema:
                    index = self.schema_combo.findData(current_schema)
                    if index >= 0:
                        self.schema_combo.setCurrentIndex(index)
                    else:
                        # Schema file exists but not in dropdown, add it
                        self.schema_combo.addItem(current_schema, current_schema)
                        self.schema_combo.setCurrentIndex(self.schema_combo.count() - 1)
                else:
                    # No schema associated
                    self.schema_combo.setCurrentIndex(0)  # "No schema selected"
            except Exception as e:
                # Handle error silently, just default to no selection
                self.schema_combo.setCurrentIndex(0)
    
    # Compatibility method for existing code
    def set_agent(self, beacon_id: str):
        """Compatibility method - delegates to set_beacon"""
        self.set_beacon(beacon_id)