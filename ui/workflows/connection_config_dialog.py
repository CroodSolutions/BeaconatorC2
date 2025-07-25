"""
Dialog for configuring advanced connection features.
Allows users to set up variable substitution, conditions, and data transformations.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, 
                            QWidget, QLabel, QLineEdit, QTextEdit, QCheckBox, 
                            QPushButton, QListWidget, QListWidgetItem, QComboBox,
                            QFormLayout, QGroupBox, QSpinBox, QMessageBox,
                            QScrollArea, QFrame, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from services.workflows.connection_features import (ConnectionFeatureManager, VariableReference, 
                                                  ConnectionCondition, VariableType)


class ConnectionConfigDialog(QDialog):
    """Dialog for configuring advanced connection features"""
    
    connection_configured = pyqtSignal(dict)  # Emit configuration when saved
    
    def __init__(self, source_node, target_node, feature_manager: ConnectionFeatureManager, parent=None):
        super().__init__(parent)
        self.source_node = source_node
        self.target_node = target_node
        self.feature_manager = feature_manager
        self.config = {
            'variables': [],
            'conditions': [],
            'transformations': [],
            'enabled': True
        }
        
        self.setWindowTitle(f"Configure Connection: {source_node.get_display_name()} → {target_node.get_display_name()}")
        self.setModal(True)
        self.resize(700, 500)
        
        self.setup_ui()
        self.load_available_variables()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout()
        
        # Header
        self.create_header_section(layout)
        
        # Tab widget for different configuration sections
        self.tab_widget = QTabWidget()
        
        # Variables tab
        self.create_variables_tab()
        
        # Conditions tab
        self.create_conditions_tab()
        
        # Transformations tab
        self.create_transformations_tab()
        
        # Preview tab
        self.create_preview_tab()
        
        layout.addWidget(self.tab_widget)
        
        # Buttons
        self.create_buttons_section(layout)
        
        self.setLayout(layout)
        
    def create_header_section(self, parent_layout):
        """Create the header section with connection info"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #232323;
                border: 1px solid #666666;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Connection title
        title = QLabel(f"Advanced Connection Configuration")
        font = title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        title.setFont(font)
        title.setStyleSheet("color: white; margin-bottom: 5px;")
        layout.addWidget(title)
        
        # Connection details
        details = QLabel(f"From: {self.source_node.get_display_name()} → To: {self.target_node.get_display_name()}")
        details.setStyleSheet("color: #cccccc; font-style: italic;")
        layout.addWidget(details)
        
        # Enable checkbox
        self.enabled_checkbox = QCheckBox("Enable advanced features for this connection")
        self.enabled_checkbox.setChecked(True)
        self.enabled_checkbox.setStyleSheet("color: white; font-weight: bold;")
        self.enabled_checkbox.toggled.connect(self._on_enabled_toggled)
        layout.addWidget(self.enabled_checkbox)
        
        header_frame.setLayout(layout)
        parent_layout.addWidget(header_frame)
        
    def create_variables_tab(self):
        """Create the variables configuration tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Instructions
        info_label = QLabel("Configure variables that will be available during connection processing:")
        info_label.setStyleSheet("color: #cccccc; font-style: italic; margin-bottom: 10px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Splitter for available and configured variables
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Available variables section
        available_widget = self.create_available_variables_widget()
        splitter.addWidget(available_widget)
        
        # Configured variables section
        configured_widget = self.create_configured_variables_widget()
        splitter.addWidget(configured_widget)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        
        tab.setLayout(layout)
        self.tab_widget.addTab(tab, "Variables")
        
    def create_available_variables_widget(self):
        """Create widget showing available variables"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Available Variables")
        label.setStyleSheet("font-weight: bold; color: white;")
        layout.addWidget(label)
        
        self.available_vars_list = QListWidget()
        self.available_vars_list.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #444444;
            }
            QListWidget::item:selected {
                background-color: #4a4a4a;
            }
        """)
        layout.addWidget(self.available_vars_list)
        
        # Add variable button
        add_btn = QPushButton("Add Selected →")
        add_btn.clicked.connect(self._add_selected_variable)
        layout.addWidget(add_btn)
        
        widget.setLayout(layout)
        return widget
        
    def create_configured_variables_widget(self):
        """Create widget for configured variables"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Connection Variables")
        label.setStyleSheet("font-weight: bold; color: white;")
        layout.addWidget(label)
        
        self.configured_vars_list = QListWidget()
        self.configured_vars_list.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #444444;
            }
            QListWidget::item:selected {
                background-color: #4a4a4a;
            }
        """)
        layout.addWidget(self.configured_vars_list)
        
        # Variable actions
        actions_layout = QHBoxLayout()
        
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_selected_variable)
        actions_layout.addWidget(edit_btn)
        
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_selected_variable)
        actions_layout.addWidget(remove_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        widget.setLayout(layout)
        return widget
        
    def create_conditions_tab(self):
        """Create the conditions configuration tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Instructions
        info_label = QLabel("Set up conditions that must be met for this connection to execute:")
        info_label.setStyleSheet("color: #cccccc; font-style: italic; margin-bottom: 10px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Conditions list
        self.conditions_list = QListWidget()
        self.conditions_list.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444444;
            }
            QListWidget::item:selected {
                background-color: #4a4a4a;
            }
        """)
        layout.addWidget(self.conditions_list)
        
        # Condition actions
        actions_layout = QHBoxLayout()
        
        add_condition_btn = QPushButton("Add Condition")
        add_condition_btn.clicked.connect(self._add_condition)
        actions_layout.addWidget(add_condition_btn)
        
        edit_condition_btn = QPushButton("Edit")
        edit_condition_btn.clicked.connect(self._edit_condition)
        actions_layout.addWidget(edit_condition_btn)
        
        test_condition_btn = QPushButton("Test")
        test_condition_btn.clicked.connect(self._test_condition)
        actions_layout.addWidget(test_condition_btn)
        
        remove_condition_btn = QPushButton("Remove")
        remove_condition_btn.clicked.connect(self._remove_condition)
        actions_layout.addWidget(remove_condition_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        tab.setLayout(layout)
        self.tab_widget.addTab(tab, "Conditions")
        
    def create_transformations_tab(self):
        """Create the data transformations tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Instructions
        info_label = QLabel("Configure how data should be transformed as it flows through this connection:")
        info_label.setStyleSheet("color: #cccccc; font-style: italic; margin-bottom: 10px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Transformations list
        self.transformations_list = QListWidget()
        self.transformations_list.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444444;
            }
            QListWidget::item:selected {
                background-color: #4a4a4a;
            }
        """)
        layout.addWidget(self.transformations_list)
        
        # Transformation actions
        actions_layout = QHBoxLayout()
        
        add_transform_btn = QPushButton("Add Transformation")
        add_transform_btn.clicked.connect(self._add_transformation)
        actions_layout.addWidget(add_transform_btn)
        
        edit_transform_btn = QPushButton("Edit")
        edit_transform_btn.clicked.connect(self._edit_transformation)
        actions_layout.addWidget(edit_transform_btn)
        
        move_up_btn = QPushButton("Move Up")
        move_up_btn.clicked.connect(self._move_transformation_up)
        actions_layout.addWidget(move_up_btn)
        
        move_down_btn = QPushButton("Move Down")
        move_down_btn.clicked.connect(self._move_transformation_down)
        actions_layout.addWidget(move_down_btn)
        
        remove_transform_btn = QPushButton("Remove")
        remove_transform_btn.clicked.connect(self._remove_transformation)
        actions_layout.addWidget(remove_transform_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        tab.setLayout(layout)
        self.tab_widget.addTab(tab, "Transformations")
        
    def create_preview_tab(self):
        """Create the preview tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Instructions
        info_label = QLabel("Preview the complete connection configuration:")
        info_label.setStyleSheet("color: #cccccc; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Preview text
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                color: white;
                border: 1px solid #666666;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
            }
        """)
        layout.addWidget(self.preview_text)
        
        # Refresh preview button
        refresh_btn = QPushButton("Refresh Preview")
        refresh_btn.clicked.connect(self._refresh_preview)
        layout.addWidget(refresh_btn)
        
        tab.setLayout(layout)
        self.tab_widget.addTab(tab, "Preview")
        
    def create_buttons_section(self, parent_layout):
        """Create the dialog buttons"""
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        # Test configuration button
        test_btn = QPushButton("Test Configuration")
        test_btn.clicked.connect(self._test_configuration)
        buttons_layout.addWidget(test_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        # Save button
        save_btn = QPushButton("Save Configuration")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_configuration)
        buttons_layout.addWidget(save_btn)
        
        parent_layout.addLayout(buttons_layout)
        
    def load_available_variables(self):
        """Load available variables into the list"""
        available = self.feature_manager.get_available_variables()
        
        self.available_vars_list.clear()
        for name, info in available.items():
            item = QListWidgetItem(f"{name} ({info['type']})")
            item.setData(Qt.ItemDataRole.UserRole, {'name': name, 'info': info})
            self.available_vars_list.addItem(item)
            
        # Add node-specific variables
        if hasattr(self.source_node, 'parameters'):
            for param_name in self.source_node.parameters.keys():
                var_name = f"{self.source_node.node_id}.{param_name}"
                item = QListWidgetItem(f"{var_name} (parameter)")
                item.setData(Qt.ItemDataRole.UserRole, {
                    'name': var_name,
                    'info': {'type': 'parameter', 'value': None, 'display_name': f"Parameter {param_name}"}
                })
                self.available_vars_list.addItem(item)
                
    def _on_enabled_toggled(self, enabled):
        """Handle enabled checkbox toggle"""
        self.tab_widget.setEnabled(enabled)
        self.config['enabled'] = enabled
        
    def _add_selected_variable(self):
        """Add selected variable to configured list"""
        current_item = self.available_vars_list.currentItem()
        if current_item:
            data = current_item.data(Qt.ItemDataRole.UserRole)
            # Add to configured variables
            configured_item = QListWidgetItem(f"{data['name']} → Available in expressions")
            configured_item.setData(Qt.ItemDataRole.UserRole, data)
            self.configured_vars_list.addItem(configured_item)
            
    def _edit_selected_variable(self):
        """Edit selected configured variable"""
        # Implementation would open a variable editing dialog
        QMessageBox.information(self, "Edit Variable", "Variable editing dialog would open here")
        
    def _remove_selected_variable(self):
        """Remove selected configured variable"""
        current_row = self.configured_vars_list.currentRow()
        if current_row >= 0:
            self.configured_vars_list.takeItem(current_row)
            
    def _add_condition(self):
        """Add a new condition"""
        # Implementation would open a condition creation dialog
        QMessageBox.information(self, "Add Condition", "Condition creation dialog would open here")
        
    def _edit_condition(self):
        """Edit selected condition"""
        # Implementation would open a condition editing dialog
        QMessageBox.information(self, "Edit Condition", "Condition editing dialog would open here")
        
    def _test_condition(self):
        """Test selected condition"""
        # Implementation would test the condition with current values
        QMessageBox.information(self, "Test Condition", "Condition testing would run here")
        
    def _remove_condition(self):
        """Remove selected condition"""
        current_row = self.conditions_list.currentRow()
        if current_row >= 0:
            self.conditions_list.takeItem(current_row)
            
    def _add_transformation(self):
        """Add a new transformation"""
        # Implementation would open a transformation creation dialog
        QMessageBox.information(self, "Add Transformation", "Transformation creation dialog would open here")
        
    def _edit_transformation(self):
        """Edit selected transformation"""
        # Implementation would open a transformation editing dialog
        QMessageBox.information(self, "Edit Transformation", "Transformation editing dialog would open here")
        
    def _move_transformation_up(self):
        """Move selected transformation up in the list"""
        current_row = self.transformations_list.currentRow()
        if current_row > 0:
            item = self.transformations_list.takeItem(current_row)
            self.transformations_list.insertItem(current_row - 1, item)
            self.transformations_list.setCurrentRow(current_row - 1)
            
    def _move_transformation_down(self):
        """Move selected transformation down in the list"""
        current_row = self.transformations_list.currentRow()
        if current_row < self.transformations_list.count() - 1:
            item = self.transformations_list.takeItem(current_row)
            self.transformations_list.insertItem(current_row + 1, item)
            self.transformations_list.setCurrentRow(current_row + 1)
            
    def _remove_transformation(self):
        """Remove selected transformation"""
        current_row = self.transformations_list.currentRow()
        if current_row >= 0:
            self.transformations_list.takeItem(current_row)
            
    def _refresh_preview(self):
        """Refresh the configuration preview"""
        preview_text = "Connection Configuration Preview\n"
        preview_text += "=" * 40 + "\n\n"
        
        preview_text += f"Source: {self.source_node.get_display_name()}\n"
        preview_text += f"Target: {self.target_node.get_display_name()}\n"
        preview_text += f"Enabled: {self.config['enabled']}\n\n"
        
        # Variables section
        preview_text += "Variables:\n"
        if self.configured_vars_list.count() > 0:
            for i in range(self.configured_vars_list.count()):
                item = self.configured_vars_list.item(i)
                data = item.data(Qt.ItemDataRole.UserRole)
                preview_text += f"  - {data['name']} ({data['info']['type']})\n"
        else:
            preview_text += "  No variables configured\n"
        preview_text += "\n"
        
        # Conditions section
        preview_text += "Conditions:\n"
        if self.conditions_list.count() > 0:
            for i in range(self.conditions_list.count()):
                item = self.conditions_list.item(i)
                preview_text += f"  - {item.text()}\n"
        else:
            preview_text += "  No conditions configured\n"
        preview_text += "\n"
        
        # Transformations section
        preview_text += "Transformations:\n"
        if self.transformations_list.count() > 0:
            for i in range(self.transformations_list.count()):
                item = self.transformations_list.item(i)
                preview_text += f"  {i + 1}. {item.text()}\n"
        else:
            preview_text += "  No transformations configured\n"
        
        self.preview_text.setPlainText(preview_text)
        
    def _test_configuration(self):
        """Test the entire configuration"""
        # Implementation would test all components
        QMessageBox.information(self, "Test Configuration", "Configuration testing would run here")
        
    def _save_configuration(self):
        """Save the configuration and close dialog"""
        # Build configuration from UI
        self.config['enabled'] = self.enabled_checkbox.isChecked()
        
        # Collect variables
        variables = []
        for i in range(self.configured_vars_list.count()):
            item = self.configured_vars_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            variables.append(data)
        self.config['variables'] = variables
        
        # Emit configuration
        self.connection_configured.emit(self.config)
        self.accept()