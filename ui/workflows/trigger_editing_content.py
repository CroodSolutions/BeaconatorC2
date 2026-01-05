"""
Trigger Editing Content Widget

Provides UI for configuring workflow triggers including:
- Trigger type selection (manual, beacon connection, scheduled, etc.)
- Dynamic parameter configuration based on trigger type
- Enable/disable toggle for automatic execution
- Test trigger functionality
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QComboBox, QCheckBox, QPushButton, QTextEdit,
                            QLineEdit, QSpinBox, QGroupBox, QFormLayout,
                            QScrollArea, QFrame, QButtonGroup, QRadioButton,
                            QApplication, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from typing import Dict, Any, Optional


class TriggerEditingContent(QWidget):
    """Widget for editing trigger node parameters"""
    
    # Signals
    node_updated = pyqtSignal(object, dict)  # node, parameters
    test_trigger_requested = pyqtSignal(object, dict)  # node, test_parameters
    
    def __init__(self):
        super().__init__()
        self.current_node = None
        self.workflow_context = None
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Node info header
        self.create_node_header()
        layout.addWidget(self.node_header)
        
        # Main content area
        self.create_content_area()
        layout.addWidget(self.content_area)
        
        # Footer with action buttons
        self.create_footer()
        layout.addWidget(self.footer)
        
        self.setLayout(layout)
    
    def create_node_header(self):
        """Create the node info header"""
        self.node_header = QFrame()
        self.node_header.setFixedHeight(60)
        self.node_header.setStyleSheet("""
            QFrame {
                background-color: #424242;
                border: none;
                border-bottom: 1px solid #555555;
            }
        """)
        
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        # Node info section
        node_info_layout = QVBoxLayout()
        node_info_layout.setSpacing(2)
        
        self.node_title_label = QLabel("Trigger Configuration")
        self.node_title_label.setStyleSheet("""
            color: #ffffff;
            font-weight: bold;
            font-size: 14px;
        """)
        
        self.node_type_label = QLabel("")
        self.node_type_label.setStyleSheet("""
            color: #cccccc;
            font-size: 11px;
        """)
        
        node_info_layout.addWidget(self.node_title_label)
        node_info_layout.addWidget(self.node_type_label)
        header_layout.addLayout(node_info_layout)
        
        header_layout.addStretch()
        
        # Action buttons
        self.execute_button = QPushButton("Execute")
        self.execute_button.setFixedSize(60, 30)
        self.execute_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                border: none;
                color: white;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        self.execute_button.clicked.connect(self.execute_node)
        self.execute_button.setEnabled(False)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.setFixedSize(60, 30)
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                border: none;
                color: white;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        self.delete_button.clicked.connect(self.delete_node)
        self.delete_button.setEnabled(False)
        
        # Close button
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(30, 30)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                border: none;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #888888;
            }
        """)
        self.close_button.clicked.connect(self.close_panel)
        
        header_layout.addWidget(self.execute_button)
        header_layout.addWidget(self.delete_button)
        header_layout.addWidget(self.close_button)
        
        self.node_header.setLayout(header_layout)
    
    def create_content_area(self):
        """Create the main content area"""
        self.content_area = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 0, 15, 15)
        layout.setSpacing(0)

        # Trigger Type Section
        type_label = QLabel("Trigger Type")
        type_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                margin: 10px 0px 2px 0px;
                padding: 0px;
                border: none;
                background-color: transparent;
            }
        """)
        layout.addWidget(type_label)

        self.trigger_type_combo = QComboBox()
        self.trigger_type_combo.addItems([
            "Manual",
            "Beacon Connection",
            "Beacon Status Change",
            "Scheduled"
        ])
        self.trigger_type_combo.setStyleSheet("""
            QComboBox {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-size: 12px;
                margin: 0px 0px 8px 0px;
            }
            QComboBox:focus {
                border-color: #4a90e2;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #555555;
                border-radius: 3px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
            }
        """)
        self.trigger_type_combo.currentTextChanged.connect(self._on_trigger_type_changed)
        layout.addWidget(self.trigger_type_combo)

        # Enable checkbox
        self.enabled_checkbox = QCheckBox("Enable Automatic Execution")
        self.enabled_checkbox.setChecked(True)
        self.enabled_checkbox.setStyleSheet("""
            QCheckBox {
                color: white;
                font-size: 12px;
                margin: 0px 0px 0px 0px;
                padding: 0px;
            }
        """)
        layout.addWidget(self.enabled_checkbox)
        
        # Dynamic configuration section
        self.config_group = QGroupBox("Trigger Settings")
        self.config_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 5px;
                margin: 12px 0px 0px 0px;
                padding-top: 1em;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        self.config_layout = QVBoxLayout(self.config_group)
        self.config_layout.setContentsMargins(10, 10, 10, 10)
        self.config_layout.setSpacing(0)

        layout.addWidget(self.config_group)

        layout.addStretch()  # Push content to top

        self.content_area.setLayout(layout)
    
    def create_footer(self):
        """Create the footer with save/cancel buttons"""
        self.footer = QFrame()
        self.footer.setFixedHeight(60)
        self.footer.setStyleSheet("""
            QFrame {
                background-color: #424242;
                border: none;
                border-top: 1px solid #555555;
            }
        """)
        
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(15, 10, 15, 10)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        footer_layout.addWidget(self.status_label)
        
        footer_layout.addStretch()
        
        # Action buttons
        self.test_button = QPushButton("Test")
        self.test_button.setFixedSize(70, 35)
        self.test_button.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                border: none;
                color: white;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
            QPushButton:disabled {
                background-color: #444444;
                color: #888888;
            }
        """)
        self.test_button.clicked.connect(self._test_trigger)
        self.test_button.setEnabled(False)
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.setFixedSize(70, 35)
        self.apply_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                border: none;
                color: white;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #444444;
                color: #888888;
            }
        """)
        self.apply_button.clicked.connect(self._apply_changes)
        
        footer_layout.addWidget(self.test_button)
        footer_layout.addWidget(self.apply_button)
        
        self.footer.setLayout(footer_layout)
        
    def _connect_signals(self):
        """Connect UI signals"""
        self.enabled_checkbox.toggled.connect(self._on_enabled_changed)
    
    def _on_trigger_type_changed(self, trigger_type):
        """Handle trigger type selection change"""
        # Clear existing configuration
        self._clear_config_layout()
        
        trigger_type_lower = trigger_type.lower().replace(" ", "_")
        
        if trigger_type_lower == "manual":
            self._setup_manual_config()
        elif trigger_type_lower == "beacon_connection":
            self._setup_beacon_connection_config()
        elif trigger_type_lower == "beacon_status_change":
            self._setup_beacon_status_config()
        elif trigger_type_lower == "scheduled":
            self._setup_scheduled_config()
        
        # Enable/disable test button based on trigger type
        self.test_button.setEnabled(trigger_type_lower != "manual")
    
    def _clear_config_layout(self):
        """Clear the dynamic configuration layout"""
        # Hide widgets first for immediate visual feedback
        for i in range(self.config_layout.count()):
            item = self.config_layout.itemAt(i)
            if item and item.widget():
                item.widget().hide()
        
        # Then properly remove and delete them
        while self.config_layout.count():
            child = self.config_layout.takeAt(0)
            if child.widget():
                widget = child.widget()
                widget.setParent(None)  # Remove parent immediately
                widget.deleteLater()
            elif child.layout():
                # Handle nested layouts
                while child.layout().count():
                    nested_child = child.layout().takeAt(0)
                    if nested_child.widget():
                        nested_widget = nested_child.widget()
                        nested_widget.setParent(None)
                        nested_widget.deleteLater()
        
        # Process any pending deletions

        QApplication.processEvents()
    
    def _setup_manual_config(self):
        """Setup manual trigger configuration (minimal)"""
        info_label = QLabel("Manual triggers require user interaction to execute workflows.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-style: italic;
                margin: 0px;
                padding: 0px;
                border: none;
                background-color: transparent;
            }
        """)
        self.config_layout.addWidget(info_label)
    
    def _setup_beacon_connection_config(self):
        """Setup beacon connection trigger configuration"""
        form_layout = QFormLayout()
        
        # CIDR ranges
        self.cidr_ranges_edit = QTextEdit()
        self.cidr_ranges_edit.setPlaceholderText(
            "Enter CIDR ranges, one per line:\n192.168.1.0/24\n10.0.0.0/8\n* (for all IPs)"
        )
        self.cidr_ranges_edit.setToolTip("Enter CIDR ranges to filter by IP address. Use '*' to match all IP addresses, or specific ranges like '192.168.1.0/24'")
        
        # Computer name pattern
        self.beacon_pattern_edit = QLineEdit()
        self.beacon_pattern_edit.setText("*")
        self.beacon_pattern_edit.setPlaceholderText("Computer name pattern (regex) or * for all computers")
        self.beacon_pattern_edit.setToolTip("Regular expression pattern to match against computer names. Use '*' to match all computers, or specific patterns like 'DESKTOP-.*', 'PROD-.*', or '.*-WS[0-9]+'")
        
        # Receiver types
        receiver_group = QWidget()
        receiver_layout = QHBoxLayout(receiver_group)
        receiver_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tcp_checkbox = QCheckBox("TCP")
        self.udp_checkbox = QCheckBox("UDP")  
        self.http_checkbox = QCheckBox("HTTP")
        self.smb_checkbox = QCheckBox("SMB")
        
        # Check all by default
        for checkbox in [self.tcp_checkbox, self.udp_checkbox, 
                        self.http_checkbox, self.smb_checkbox]:
            checkbox.setChecked(True)
            receiver_layout.addWidget(checkbox)
        
        receiver_layout.addStretch()
        
        # Exclude patterns
        self.exclude_patterns_edit = QTextEdit()
        self.exclude_patterns_edit.setPlaceholderText(
            "Computer names to exclude (regex), one per line:\nTEST-.*\nDEMO-.*\n.*-LAB[0-9]+"
        )
        
        # Style all text inputs consistently
        self.cidr_ranges_edit.setStyleSheet("""
            QTextEdit {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QTextEdit:focus {
                border-color: #4a90e2;
            }
        """)
        
        self.beacon_pattern_edit.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #4a90e2;
            }
        """)
        
        self.exclude_patterns_edit.setStyleSheet("""
            QTextEdit {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QTextEdit:focus {
                border-color: #4a90e2;
            }
        """)
        
        # Style checkboxes with native appearance for better visibility
        for checkbox in [self.tcp_checkbox, self.udp_checkbox, 
                        self.http_checkbox, self.smb_checkbox]:
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: white;
                    font-size: 12px;
                }
            """)
        
        # Create labels with consistent styling
        cidr_label = QLabel("CIDR Ranges")
        cidr_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                margin: 0px 0px 2px 0px;
                padding: 0px;
                border: none;
                background-color: transparent;
            }
        """)

        pattern_label = QLabel("Computer Name Pattern")
        pattern_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                margin: 0px 0px 2px 0px;
                padding: 0px;
                border: none;
                background-color: transparent;
            }
        """)

        receiver_label = QLabel("Receiver Types")
        receiver_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                margin: 0px 0px 2px 0px;
                padding: 0px;
                border: none;
                background-color: transparent;
            }
        """)

        exclude_label = QLabel("Exclude Computer Names")
        exclude_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                margin: 0px 0px 2px 0px;
                padding: 0px;
                border: none;
                background-color: transparent;
            }
        """)
        
        form_layout.addRow(cidr_label, self.cidr_ranges_edit)
        form_layout.addRow(pattern_label, self.beacon_pattern_edit)
        form_layout.addRow(receiver_label, receiver_group)
        form_layout.addRow(exclude_label, self.exclude_patterns_edit)

        # Control spacing via widget margins, not layout spacing
        form_layout.setSpacing(0)
        form_layout.setVerticalSpacing(12)

        self.config_layout.addLayout(form_layout)
    
    def _setup_beacon_status_config(self):
        """Setup beacon status change trigger configuration"""
        form_layout = QFormLayout()
        
        # Status change type
        self.status_type_combo = QComboBox()
        self.status_type_combo.addItems([
            "Any Status Change",
            "Connected",
            "Disconnected", 
            "Timeout"
        ])
        
        # Computer name filter (same as connection)
        self.status_beacon_pattern_edit = QLineEdit()
        self.status_beacon_pattern_edit.setText("*")
        self.status_beacon_pattern_edit.setPlaceholderText("Computer name pattern (regex) or * for all computers")
        self.status_beacon_pattern_edit.setToolTip("Regular expression pattern to match against computer names. Use '*' to match all computers, or specific patterns like 'DESKTOP-.*', 'PROD-.*', or '.*-WS[0-9]+'")
        
        # Style widgets consistently
        self.status_type_combo.setStyleSheet("""
            QComboBox {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QComboBox:focus {
                border-color: #4a90e2;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #555555;
                border-radius: 3px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid white;
            }
        """)
        
        self.status_beacon_pattern_edit.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #4a90e2;
            }
        """)
        
        # Create labels with consistent styling
        status_label = QLabel("Status Change")
        status_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                margin: 0px 0px 2px 0px;
                padding: 0px;
                border: none;
                background-color: transparent;
            }
        """)

        pattern_label = QLabel("Computer Name Pattern")
        pattern_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                margin: 0px 0px 2px 0px;
                padding: 0px;
                border: none;
                background-color: transparent;
            }
        """)
        
        form_layout.addRow(status_label, self.status_type_combo)
        form_layout.addRow(pattern_label, self.status_beacon_pattern_edit)

        # Control spacing via widget margins
        form_layout.setSpacing(0)
        form_layout.setVerticalSpacing(12)

        self.config_layout.addLayout(form_layout)
    
    def _setup_scheduled_config(self):
        """Setup scheduled trigger configuration"""
        form_layout = QFormLayout()
        
        # Schedule type selection
        schedule_group = QWidget()
        schedule_layout = QVBoxLayout(schedule_group)
        
        self.schedule_button_group = QButtonGroup()
        
        self.interval_radio = QRadioButton("Interval-based")
        self.cron_radio = QRadioButton("Cron expression")
        self.interval_radio.setChecked(True)
        
        self.schedule_button_group.addButton(self.interval_radio, 0)
        self.schedule_button_group.addButton(self.cron_radio, 1)
        
        schedule_layout.addWidget(self.interval_radio)
        schedule_layout.addWidget(self.cron_radio)
        
        # Interval configuration
        interval_widget = QWidget()
        interval_layout = QHBoxLayout(interval_widget)
        interval_layout.setContentsMargins(20, 0, 0, 0)
        
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setMinimum(1)
        self.interval_spinbox.setMaximum(1440)  # 24 hours max
        self.interval_spinbox.setValue(30)
        self.interval_spinbox.setSuffix(" minutes")
        self.interval_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QSpinBox:focus {
                border-color: #4a90e2;
            }
        """)
        
        every_label = QLabel("Every")
        every_label.setStyleSheet("color: white;")
        interval_layout.addWidget(every_label)
        interval_layout.addWidget(self.interval_spinbox)
        interval_layout.addStretch()
        
        # Cron expression
        cron_widget = QWidget()
        cron_layout = QHBoxLayout(cron_widget)
        cron_layout.setContentsMargins(20, 0, 0, 0)
        
        self.cron_edit = QLineEdit()
        self.cron_edit.setPlaceholderText("0 */6 * * *  (every 6 hours)")
        self.cron_edit.setEnabled(False)
        self.cron_edit.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #4a90e2;
            }
            QLineEdit:disabled {
                background-color: #2a2a2a;
                color: #888888;
            }
        """)
        
        cron_layout.addWidget(self.cron_edit)
        
        # Connect radio button signals
        self.interval_radio.toggled.connect(
            lambda checked: self.interval_spinbox.setEnabled(checked)
        )
        self.cron_radio.toggled.connect(
            lambda checked: self.cron_edit.setEnabled(checked)
        )
        
        # Style radio buttons with native appearance for better visibility
        self.interval_radio.setStyleSheet("""
            QRadioButton {
                color: white;
                font-size: 12px;
            }
        """)
        
        self.cron_radio.setStyleSheet("""
            QRadioButton {
                color: white;
                font-size: 12px;
            }
        """)
        
        # Create labels with consistent styling
        schedule_label = QLabel("Schedule Type")
        schedule_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                margin: 0px 0px 2px 0px;
                padding: 0px;
                border: none;
                background-color: transparent;
            }
        """)
        
        form_layout.addRow(schedule_label, schedule_group)
        form_layout.addRow("", interval_widget)
        form_layout.addRow("", cron_widget)

        # Control spacing via widget margins
        form_layout.setSpacing(0)
        form_layout.setVerticalSpacing(12)

        self.config_layout.addLayout(form_layout)
    
    def on_panel_shown(self, node=None, workflow_context=None):
        """Called when the panel is shown with trigger editing content"""
        if node and workflow_context:
            self.set_node(node, workflow_context)
    
    def execute_node(self):
        """Execute the current node"""
        if self.current_node:
            # For trigger nodes, this might mean manually triggering the workflow
            pass
            
    def delete_node(self):
        """Delete the current node"""
        if self.current_node:

            reply = QMessageBox.question(
                self, "Delete Node",
                f"Are you sure you want to delete this trigger node?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Emit delete signal if needed
                pass
                
    def close_panel(self):
        """Request to close the panel"""
        # This would be handled by the parent panel
        pass
        
    def _on_enabled_changed(self, enabled):
        """Handle enabled checkbox change"""
        # Update visual state based on enabled status
        self.config_group.setEnabled(enabled)
        if enabled:
            self.config_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin: 12px 0px 0px 0px;
                    padding-top: 1em;
                    color: white;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
            """)
        else:
            self.config_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin: 12px 0px 0px 0px;
                    padding-top: 1em;
                    color: #888;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
            """)
    
    def _apply_changes(self):
        """Apply configuration changes to the node"""
        if not self.current_node:
            return
        
        # Build parameters dictionary
        parameters = self._build_parameters()
        
        # Update node parameters
        if not hasattr(self.current_node, 'parameters'):
            self.current_node.parameters = {}
        
        self.current_node.parameters.update(parameters)
        
        # Update node colors based on new settings
        if hasattr(self.current_node, '_set_node_colors'):
            self.current_node._set_node_colors()
        
        # Update status
        self.status_label.setText("Trigger configuration applied")
        
        # Emit signal for external handling
        self.node_updated.emit(self.current_node, parameters)
    
    def _build_parameters(self) -> Dict[str, Any]:
        """Build parameters dictionary from UI"""
        trigger_type_map = {
            "Manual": "manual",
            "Beacon Connection": "beacon_connection",
            "Beacon Status Change": "beacon_status", 
            "Scheduled": "scheduled"
        }
        
        trigger_type = trigger_type_map[self.trigger_type_combo.currentText()]
        
        parameters = {
            "trigger_type": trigger_type,
            "enabled": self.enabled_checkbox.isChecked(),
            "filters": {},
            "schedule": {}
        }
        
        if trigger_type == "beacon_connection":
            # Parse CIDR ranges
            cidr_text = self.cidr_ranges_edit.toPlainText().strip()
            cidr_ranges = [line.strip() for line in cidr_text.split('\n') if line.strip()]
            
            # Get receiver types
            receiver_types = []
            if self.tcp_checkbox.isChecked():
                receiver_types.append("tcp")
            if self.udp_checkbox.isChecked():
                receiver_types.append("udp")
            if self.http_checkbox.isChecked():
                receiver_types.append("http")
            if self.smb_checkbox.isChecked():
                receiver_types.append("smb")
            
            # Parse exclude patterns
            exclude_text = self.exclude_patterns_edit.toPlainText().strip()
            exclude_patterns = [line.strip() for line in exclude_text.split('\n') if line.strip()]
            
            parameters["filters"] = {
                "cidr_ranges": cidr_ranges,
                "beacon_pattern": self.beacon_pattern_edit.text().strip(),  # Note: keeping key name for compatibility
                "receiver_types": receiver_types,
                "exclude_patterns": exclude_patterns
            }
        
        elif trigger_type == "scheduled":
            if self.interval_radio.isChecked():
                parameters["schedule"] = {
                    "type": "interval",
                    "interval_minutes": self.interval_spinbox.value()
                }
            else:
                parameters["schedule"] = {
                    "type": "cron",
                    "cron_expression": self.cron_edit.text().strip()
                }
        
        return parameters
    
    def _test_trigger(self):
        """Test the current trigger configuration"""
        if not self.current_node:
            return
        
        parameters = self._build_parameters()
        self.test_trigger_requested.emit(self.current_node, parameters)
    
    def set_node(self, node, workflow_context):
        """Set the node to edit"""
        self.current_node = node
        self.workflow_context = workflow_context
        
        # Update header
        if node:
            self.node_title_label.setText("Trigger Configuration")
            self.node_type_label.setText(f"ID: {node.node_id}")
            
            # Enable buttons
            self.execute_button.setEnabled(True)
            self.delete_button.setEnabled(True)
        
        if node and hasattr(node, 'parameters'):
            self._load_parameters(node.parameters)
        else:
            self._load_default_parameters()
    
    def _load_parameters(self, parameters: Dict[str, Any]):
        """Load parameters into UI"""
        # Load trigger type
        trigger_type = parameters.get('trigger_type', 'manual')
        type_map = {
            'manual': 'Manual',
            'beacon_connection': 'Beacon Connection',
            'beacon_status': 'Beacon Status Change',
            'scheduled': 'Scheduled'
        }
        
        display_type = type_map.get(trigger_type, 'Manual')
        index = self.trigger_type_combo.findText(display_type)
        if index >= 0:
            self.trigger_type_combo.setCurrentIndex(index)
        
        # Load enabled state
        self.enabled_checkbox.setChecked(parameters.get('enabled', True))
        
        # Load type-specific parameters
        self._load_type_specific_parameters(trigger_type, parameters)
    
    def _load_type_specific_parameters(self, trigger_type: str, parameters: Dict[str, Any]):
        """Load type-specific parameters"""
        filters = parameters.get('filters', {})
        schedule = parameters.get('schedule', {})
        
        if trigger_type == 'beacon_connection' and hasattr(self, 'cidr_ranges_edit'):
            # Load CIDR ranges
            cidr_ranges = filters.get('cidr_ranges', [])
            self.cidr_ranges_edit.setPlainText('\n'.join(cidr_ranges))
            
            # Load beacon pattern  
            self.beacon_pattern_edit.setText(filters.get('beacon_pattern', '*'))
            
            # Load receiver types
            receiver_types = filters.get('receiver_types', ['tcp', 'udp', 'http', 'smb'])
            self.tcp_checkbox.setChecked('tcp' in receiver_types)
            self.udp_checkbox.setChecked('udp' in receiver_types)
            self.http_checkbox.setChecked('http' in receiver_types)
            self.smb_checkbox.setChecked('smb' in receiver_types)
            
            # Load exclude patterns
            exclude_patterns = filters.get('exclude_patterns', [])
            self.exclude_patterns_edit.setPlainText('\n'.join(exclude_patterns))
        
        elif trigger_type == 'scheduled' and hasattr(self, 'interval_spinbox'):
            schedule_type = schedule.get('type', 'interval')
            
            if schedule_type == 'interval':
                self.interval_radio.setChecked(True)
                interval = schedule.get('interval_minutes', 30)
                self.interval_spinbox.setValue(interval)
            else:
                self.cron_radio.setChecked(True)
                cron_expr = schedule.get('cron_expression', '')
                self.cron_edit.setText(cron_expr)
    
    def _load_default_parameters(self):
        """Load default parameters"""
        self.trigger_type_combo.setCurrentText("Manual")
        self.enabled_checkbox.setChecked(True)