"""
Conditional Editing Content Widget

Specialized content widget for editing conditional nodes within the unified SidePanel system.
Handles condition type selection, parameter configuration, and node operations.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                            QComboBox, QFormLayout, QLineEdit, QTextEdit, QSpinBox, 
                            QDoubleSpinBox, QCheckBox, QMessageBox, QFrame, QSizePolicy, 
                            QSpacerItem)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from services.schema_service import ParameterType

# Import template system
try:
    from ui.workflows.template_variable_picker import TemplateInsertButton
    from services.workflows.parameter_template_engine import ParameterTemplateEngine
    TEMPLATE_SYSTEM_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Template system not available: {e}")
    TEMPLATE_SYSTEM_AVAILABLE = False


class ConditionalEditingContent(QWidget):
    """Content widget for conditional node editing within unified side panel"""
    
    # Signals
    node_updated = pyqtSignal(object, dict)  # node, parameters
    node_deleted = pyqtSignal(object)  # node
    node_execution_requested = pyqtSignal(object)  # node execution requested
    close_requested = pyqtSignal()  # close panel requested
    
    def __init__(self):
        super().__init__()
        self.current_node = None
        self.workflow_context = None
        self.parameter_widgets = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the content UI"""
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
        
        self.node_title_label = QLabel("Condition Node")
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
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(15)
        
        # Condition type selection
        type_layout = QVBoxLayout()
        type_layout.setSpacing(8)
        
        type_label = QLabel("Condition Type")
        type_label.setStyleSheet("""
            color: #ffffff;
            font-weight: bold;
            font-size: 12px;
        """)
        type_layout.addWidget(type_label)
        
        self.condition_type_combo = QComboBox()
        self.condition_type_combo.addItems([
            "Contains Text",
            "Equals Text", 
            "Regex Match",
            "Numeric Comparison"
        ])
        self.condition_type_combo.setStyleSheet("""
            QComboBox {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 8px;
                border-radius: 4px;
                font-size: 12px;
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
        self.condition_type_combo.currentTextChanged.connect(self.on_condition_type_changed)
        type_layout.addWidget(self.condition_type_combo)
        
        layout.addLayout(type_layout)
        
        # Parameters area
        self.parameters_container = QWidget()
        self.parameters_layout = QFormLayout()
        self.parameters_layout.setContentsMargins(0, 0, 0, 0)
        self.parameters_layout.setSpacing(12)
        self.parameters_layout.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        self.parameters_container.setLayout(self.parameters_layout)
        
        layout.addWidget(self.parameters_container)
        
        # Add stretch to push everything to the top
        layout.addStretch()
        
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
        self.reset_button = QPushButton("Reset")
        self.reset_button.setFixedSize(70, 35)
        self.reset_button.setStyleSheet("""
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
        self.reset_button.clicked.connect(self.reset_parameters)
        self.reset_button.setEnabled(False)
        
        self.save_button = QPushButton("Save")
        self.save_button.setFixedSize(70, 35)
        self.save_button.setStyleSheet("""
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
        self.save_button.clicked.connect(self.save_parameters)
        self.save_button.setEnabled(False)
        
        footer_layout.addWidget(self.reset_button)
        footer_layout.addWidget(self.save_button)
        
        self.footer.setLayout(footer_layout)
        
    def on_panel_shown(self, node=None, workflow_context=None):
        """Called when the panel is shown with conditional editing content"""
        if node and workflow_context:
            self.show_node(node, workflow_context)
            
    def show_node(self, node, workflow_context=None):
        """Show editing interface for a conditional node"""
        self.current_node = node
        self.workflow_context = workflow_context
        
        # Update header
        self.node_title_label.setText("Condition Check")
        self.node_type_label.setText(f"ID: {node.node_id}")
        
        # Load current condition configuration
        self.load_condition_configuration()
        
        # Enable buttons
        self.execute_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.reset_button.setEnabled(True)
        self.save_button.setEnabled(False)
        
    def load_condition_configuration(self):
        """Load the current condition configuration from the node"""
        if not self.current_node or not hasattr(self.current_node, 'parameters'):
            return
            
        params = self.current_node.parameters
        
        # Determine condition type from parameters
        if 'condition_type' in params:
            condition_type = params['condition_type']
        else:
            condition_type = 'contains'  # Default
            
        # Set combo box selection
        type_map = {
            'contains': "Contains Text",
            'equals': "Equals Text",
            'regex': "Regex Match", 
            'numeric': "Numeric Comparison"
        }
        display_name = type_map.get(condition_type, "Contains Text")
        index = self.condition_type_combo.findText(display_name)
        if index >= 0:
            self.condition_type_combo.setCurrentIndex(index)
            
        # Load parameters for current type
        self.create_condition_parameters(condition_type)
        
    def on_condition_type_changed(self, display_text):
        """Handle condition type selection change"""
        # Map display text to internal type
        type_map = {
            "Contains Text": 'contains',
            "Equals Text": 'equals',
            "Regex Match": 'regex',
            "Numeric Comparison": 'numeric'
        }
        condition_type = type_map.get(display_text, 'contains')
        
        # Create parameters for selected type
        self.create_condition_parameters(condition_type)
        
        # Enable save button
        self.save_button.setEnabled(True)
        self.status_label.setText("Condition type changed")
        
    def create_condition_parameters(self, condition_type):
        """Create parameter widgets based on condition type"""
        # Clear existing parameter widgets
        self.clear_parameters()
        
        # Always add input variable selection first
        self.create_input_variable_parameter()
        
        if condition_type == 'contains':
            self.create_text_condition_parameters()
        elif condition_type == 'equals':
            self.create_text_condition_parameters(exact_match=True)
        elif condition_type == 'regex':
            self.create_regex_condition_parameters()
        elif condition_type == 'numeric':
            self.create_numeric_condition_parameters()
            
    def create_text_condition_parameters(self, exact_match=False):
        """Create parameters for text-based conditions"""
        # Value parameter
        value_label = QLabel("Text Value" if not exact_match else "Expected Value")
        value_label.setStyleSheet("color: white; font-weight: bold;")
        
        value_widget = QLineEdit()
        value_widget.setPlaceholderText("Enter text to search for" if not exact_match else "Enter exact text to match")
        value_widget.setStyleSheet("""
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
        
        # Load current value
        if self.current_node and hasattr(self.current_node, 'parameters'):
            current_value = self.current_node.parameters.get('condition_value', '')
            value_widget.setText(str(current_value))
            
        value_widget.textChanged.connect(self.on_parameter_changed)
        self.parameter_widgets['condition_value'] = value_widget
        self.parameters_layout.addRow(value_label, value_widget)
        
        # Case sensitive parameter
        case_label = QLabel("Case Sensitive")
        case_label.setStyleSheet("color: white; font-weight: bold;")
        
        case_widget = QCheckBox()
        case_widget.setStyleSheet("""
            QCheckBox {
                color: white;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #404040;
                border: 1px solid #666666;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a90e2;
                border-color: #4a90e2;
            }
        """)
        
        # Load current value
        if self.current_node and hasattr(self.current_node, 'parameters'):
            current_value = self.current_node.parameters.get('case_sensitive', False)
            case_widget.setChecked(bool(current_value))
            
        case_widget.toggled.connect(self.on_parameter_changed)
        self.parameter_widgets['case_sensitive'] = case_widget
        self.parameters_layout.addRow(case_label, case_widget)
        
    def create_regex_condition_parameters(self):
        """Create parameters for regex conditions"""
        # Pattern parameter
        pattern_label = QLabel("Regex Pattern")
        pattern_label.setStyleSheet("color: white; font-weight: bold;")
        
        pattern_widget = QLineEdit()
        pattern_widget.setPlaceholderText("Enter regular expression pattern")
        pattern_widget.setStyleSheet("""
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
        
        # Load current value
        if self.current_node and hasattr(self.current_node, 'parameters'):
            current_value = self.current_node.parameters.get('pattern', '')
            pattern_widget.setText(str(current_value))
            
        pattern_widget.textChanged.connect(self.on_parameter_changed)
        self.parameter_widgets['pattern'] = pattern_widget
        self.parameters_layout.addRow(pattern_label, pattern_widget)
        
        # Case sensitive parameter (same as text conditions)
        case_label = QLabel("Case Sensitive")
        case_label.setStyleSheet("color: white; font-weight: bold;")
        
        case_widget = QCheckBox()
        case_widget.setStyleSheet("""
            QCheckBox {
                color: white;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #404040;
                border: 1px solid #666666;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a90e2;
                border-color: #4a90e2;
            }
        """)
        
        # Load current value
        if self.current_node and hasattr(self.current_node, 'parameters'):
            current_value = self.current_node.parameters.get('case_sensitive', False)
            case_widget.setChecked(bool(current_value))
            
        case_widget.toggled.connect(self.on_parameter_changed)
        self.parameter_widgets['case_sensitive'] = case_widget
        self.parameters_layout.addRow(case_label, case_widget)
        
    def create_numeric_condition_parameters(self):
        """Create parameters for numeric conditions"""
        # Value parameter
        value_label = QLabel("Compare Value")
        value_label.setStyleSheet("color: white; font-weight: bold;")
        
        value_widget = QDoubleSpinBox()
        value_widget.setRange(-1e10, 1e10)
        value_widget.setDecimals(6)
        value_widget.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QDoubleSpinBox:focus {
                border-color: #4a90e2;
            }
        """)
        
        # Load current value
        if self.current_node and hasattr(self.current_node, 'parameters'):
            current_value = self.current_node.parameters.get('value', 0.0)
            value_widget.setValue(float(current_value))
            
        value_widget.valueChanged.connect(self.on_parameter_changed)
        self.parameter_widgets['value'] = value_widget
        self.parameters_layout.addRow(value_label, value_widget)
        
        # Operator parameter
        operator_label = QLabel("Operator")
        operator_label.setStyleSheet("color: white; font-weight: bold;")
        
        operator_widget = QComboBox()
        operator_widget.addItems([
            "equals", "greater", "less", "greater_equal", "less_equal"
        ])
        operator_widget.setStyleSheet("""
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
        
        # Load current value
        if self.current_node and hasattr(self.current_node, 'parameters'):
            current_value = self.current_node.parameters.get('operator', 'equals')
            index = operator_widget.findText(str(current_value))
            if index >= 0:
                operator_widget.setCurrentIndex(index)
                
        operator_widget.currentTextChanged.connect(self.on_parameter_changed)
        self.parameter_widgets['operator'] = operator_widget
        self.parameters_layout.addRow(operator_label, operator_widget)
        
    def create_input_variable_parameter(self):
        """Create input variable selection parameter with template support"""
        # Input variable label
        input_label = QLabel("Input Variable")
        input_label.setStyleSheet("color: white; font-weight: bold;")
        
        # Create horizontal layout for input field and template button
        input_layout = QHBoxLayout()
        input_layout.setSpacing(5)
        input_layout.setContentsMargins(0, 0, 0, 0)
        
        # Input variable text field
        input_widget = QLineEdit()
        input_widget.setPlaceholderText("Variable to compare (e.g., {{previous_output}})")
        input_widget.setStyleSheet("""
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
        
        # Load current value (default to previous output)
        if self.current_node and hasattr(self.current_node, 'parameters'):
            current_value = self.current_node.parameters.get('input_variable', '{{previous_output}}')
            input_widget.setText(str(current_value))
        else:
            input_widget.setText('{{previous_output}}')  # Default value
            
        input_widget.textChanged.connect(self.on_parameter_changed)
        self.parameter_widgets['input_variable'] = input_widget
        input_layout.addWidget(input_widget)
        
        # Add template variable button if template system is available
        if TEMPLATE_SYSTEM_AVAILABLE and self.workflow_context:
            try:
                # Get workflow context components
                canvas_variables = self.workflow_context.get('canvas_variables', {})
                workflow_connections = self.workflow_context.get('workflow_connections', [])
                
                template_button = TemplateInsertButton(
                    context=None,  # No execution context available during design-time
                    current_node=self.current_node,
                    workflow_connections=workflow_connections,
                    canvas_variables=canvas_variables,
                    parent=input_widget
                )
                template_button.setFixedSize(30, 30)
                
                # Store reference to input widget for signal handler
                self._current_input_widget = input_widget
                
                # Connect signal
                template_button.variable_selected.connect(self._insert_template_variable)
                
                input_layout.addWidget(template_button)
                
            except Exception as e:
                print(f"Error creating template button: {e}")
        
        # Create container widget for the layout
        input_container = QWidget()
        input_container.setLayout(input_layout)
        
        self.parameters_layout.addRow(input_label, input_container)
        
    def clear_parameters(self):
        """Clear all parameter widgets"""
        while self.parameters_layout.count():
            child = self.parameters_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.parameter_widgets.clear()
        
    def on_parameter_changed(self):
        """Handle parameter value changes"""
        self.save_button.setEnabled(True)
        self.status_label.setText("Parameters modified")
        
    def get_parameter_values(self):
        """Get current parameter values from widgets"""
        values = {}
        
        # Get condition type
        display_text = self.condition_type_combo.currentText()
        type_map = {
            "Contains Text": 'contains',
            "Equals Text": 'equals',
            "Regex Match": 'regex',
            "Numeric Comparison": 'numeric'
        }
        values['condition_type'] = type_map.get(display_text, 'contains')
        
        # Get parameter values
        for param_name, widget in self.parameter_widgets.items():
            if isinstance(widget, QLineEdit):
                values[param_name] = widget.text()
            elif isinstance(widget, QCheckBox):
                values[param_name] = widget.isChecked()
            elif isinstance(widget, QDoubleSpinBox):
                values[param_name] = widget.value()
            elif isinstance(widget, QComboBox):
                values[param_name] = widget.currentText()
                
        return values
        
    def save_parameters(self):
        """Save parameter changes to the node"""
        if not self.current_node:
            return
            
        try:
            # Get parameter values
            updated_parameters = self.get_parameter_values()
            
            # Validate required parameters
            if not updated_parameters.get('input_variable'):
                QMessageBox.warning(self, "Validation Error", "Please provide an input variable to compare.")
                return
                
            condition_type = updated_parameters.get('condition_type', 'contains')
            if condition_type in ['contains', 'equals'] and not updated_parameters.get('condition_value'):
                QMessageBox.warning(self, "Validation Error", "Please provide a value for the condition.")
                return
            elif condition_type == 'regex' and not updated_parameters.get('pattern'):
                QMessageBox.warning(self, "Validation Error", "Please provide a regex pattern.")
                return
                
            # Update node parameters
            if not hasattr(self.current_node, 'parameters'):
                self.current_node.parameters = {}
                
            self.current_node.parameters.update(updated_parameters)
            
            # Update parameter display if node has this method
            if hasattr(self.current_node, 'update_parameter_display'):
                self.current_node.update_parameter_display()
                
            # Emit signal
            self.node_updated.emit(self.current_node, updated_parameters)
            
            self.save_button.setEnabled(False)
            self.status_label.setText("Parameters saved")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save parameters: {e}")
            
    def reset_parameters(self):
        """Reset parameters to default or current node values"""
        if self.current_node:
            self.load_condition_configuration()
            self.save_button.setEnabled(False)
            self.status_label.setText("Parameters reset")
            
    def execute_node(self):
        """Execute the current node"""
        if self.current_node:
            self.node_execution_requested.emit(self.current_node)
            
    def delete_node(self):
        """Delete the current node"""
        if self.current_node:
            reply = QMessageBox.question(
                self, "Delete Node",
                f"Are you sure you want to delete this condition node?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.node_deleted.emit(self.current_node)
                
    def _insert_template_variable(self, variable_text):
        """Insert template variable into the current input widget"""
        if hasattr(self, '_current_input_widget') and self._current_input_widget:
            cursor_pos = self._current_input_widget.cursorPosition()
            current_text = self._current_input_widget.text()
            new_text = current_text[:cursor_pos] + variable_text + current_text[cursor_pos:]
            self._current_input_widget.setText(new_text)
            self._current_input_widget.setCursorPosition(cursor_pos + len(variable_text))
            
            # Mark parameters as changed
            self.on_parameter_changed()
            
    def close_panel(self):
        """Request to close the panel"""
        self.close_requested.emit()