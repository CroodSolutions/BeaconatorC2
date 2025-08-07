"""
Set Variable Editing Content Widget

Specialized content widget for editing set_variable nodes within the unified SidePanel system.
Handles variable name configuration, value assignment, and template variable integration.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                            QFormLayout, QLineEdit, QTextEdit, QMessageBox, QFrame, 
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
    TEMPLATE_SYSTEM_AVAILABLE = False


class SetVariableEditingContent(QWidget):
    """Content widget for set_variable node editing within unified side panel"""
    
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
        
        self.node_title_label = QLabel("Set Variable")
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
        
        # Parameters area
        self.parameters_container = QWidget()
        self.parameters_layout = QFormLayout()
        self.parameters_layout.setContentsMargins(0, 0, 0, 0)
        self.parameters_layout.setSpacing(15)
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
        """Called when the panel is shown with variable editing content"""
        if node and workflow_context:
            self.show_node(node, workflow_context)
            
    def show_node(self, node, workflow_context=None):
        """Show editing interface for a set_variable node"""
        self.current_node = node
        self.workflow_context = workflow_context
        
        # Update header
        self.node_title_label.setText("Set Variable")
        self.node_type_label.setText(f"ID: {node.node_id}")
        
        # Create parameter widgets with current context
        self.create_variable_parameters()
        
        # Load current variable configuration
        self.load_variable_configuration()
        
        # Enable buttons
        self.execute_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.reset_button.setEnabled(True)
        self.save_button.setEnabled(False)
        
    def create_variable_parameters(self):
        """Create parameter widgets for variable configuration"""
        # Clear existing parameter widgets
        self.clear_parameters()
        
        # Variable name parameter
        self.create_variable_name_parameter()
        
        # Variable value parameter  
        self.create_variable_value_parameter()
        
    def clear_parameters(self):
        """Clear all parameter widgets"""
        while self.parameters_layout.count():
            child = self.parameters_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.parameter_widgets.clear()
        
    def create_variable_name_parameter(self):
        """Create variable name input with template support"""
        # Variable name label
        name_label = QLabel("Variable Name")
        name_label.setStyleSheet("color: white; font-weight: bold;")
        
        # Create horizontal layout for input field and template button
        name_layout = QHBoxLayout()
        name_layout.setSpacing(5)
        name_layout.setContentsMargins(0, 0, 0, 0)
        
        # Variable name text field
        name_widget = QLineEdit()
        name_widget.setPlaceholderText("Enter variable name")
        name_widget.setStyleSheet("""
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
            current_value = self.current_node.parameters.get('variable_name', '')
            name_widget.setText(str(current_value))
            
        name_widget.textChanged.connect(self.on_parameter_changed)
        self.parameter_widgets['variable_name'] = name_widget
        name_layout.addWidget(name_widget)
        
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
                    parent=self
                )
                template_button.setFixedSize(30, 30)
                
                # Store reference to input widget for signal handler
                self._current_name_widget = name_widget
                
                # Connect signal
                template_button.variable_selected.connect(self._insert_template_variable_name)
                
                name_layout.addWidget(template_button)
                
            except Exception as e:
                pass  # Template button creation failed
        
        # Create container widget for the layout
        name_container = QWidget()
        name_container.setLayout(name_layout)
        
        self.parameters_layout.addRow(name_label, name_container)
        
    def create_variable_value_parameter(self):
        """Create variable value input with template support"""
        # Variable value label
        value_label = QLabel("Variable Value")
        value_label.setStyleSheet("color: white; font-weight: bold;")
        
        # Create horizontal layout for input field and template button
        value_layout = QHBoxLayout()
        value_layout.setSpacing(5)
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Variable value text area (multiline for complex values)
        value_widget = QTextEdit()
        value_widget.setPlaceholderText("Enter variable value")
        value_widget.setMaximumHeight(100)  # Limit height
        value_widget.setMinimumHeight(100)  # Ensure consistent height
        value_widget.setStyleSheet("""
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
        
        # Load current value
        if self.current_node and hasattr(self.current_node, 'parameters'):
            current_value = self.current_node.parameters.get('variable_value', '')
            value_widget.setPlainText(str(current_value))
            
        value_widget.textChanged.connect(self.on_parameter_changed)
        self.parameter_widgets['variable_value'] = value_widget
        value_layout.addWidget(value_widget, 1, Qt.AlignmentFlag.AlignTop)
        
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
                    parent=self
                )
                template_button.setFixedSize(30, 30)
                
                # Store reference to input widget for signal handler
                self._current_value_widget = value_widget
                
                # Connect signal
                template_button.variable_selected.connect(self._insert_template_variable_value)
                
                value_layout.addWidget(template_button, 0, Qt.AlignmentFlag.AlignTop)
                
            except Exception as e:
                pass  # Template button creation failed
        
        # Create container widget for the layout
        value_container = QWidget()
        value_container.setLayout(value_layout)
        
        self.parameters_layout.addRow(value_label, value_container)
        
    def load_variable_configuration(self):
        """Load the current variable configuration from the node"""
        if not self.current_node or not hasattr(self.current_node, 'parameters'):
            return
            
        params = self.current_node.parameters
        
        # Load variable name
        variable_name = params.get('variable_name', '')
        if 'variable_name' in self.parameter_widgets:
            self.parameter_widgets['variable_name'].setText(str(variable_name))
            
        # Load variable value
        variable_value = params.get('variable_value', '')
        if 'variable_value' in self.parameter_widgets:
            self.parameter_widgets['variable_value'].setPlainText(str(variable_value))
            
    def on_parameter_changed(self):
        """Handle parameter value changes"""
        self.save_button.setEnabled(True)
        self.status_label.setText("Parameters modified")
        
    def get_parameter_values(self):
        """Get current parameter values from widgets"""
        values = {}
        
        # Get parameter values
        for param_name, widget in self.parameter_widgets.items():
            if isinstance(widget, QLineEdit):
                values[param_name] = widget.text()
            elif isinstance(widget, QTextEdit):
                values[param_name] = widget.toPlainText()
                
        return values
        
    def save_parameters(self):
        """Save parameter changes to the node"""
        if not self.current_node:
            return
            
        try:
            # Get parameter values
            updated_parameters = self.get_parameter_values()
            
            # Validate required parameters
            variable_name = updated_parameters.get('variable_name', '').strip()
            variable_value = updated_parameters.get('variable_value', '').strip()
            
            if not variable_name:
                QMessageBox.warning(self, "Validation Error", "Please provide a variable name.")
                return
                
            if not variable_value:
                QMessageBox.warning(self, "Validation Error", "Please provide a variable value.")
                return
                
            # Validate variable name format (alphanumeric, underscores, hyphens)
            if not variable_name.replace('_', '').replace('-', '').replace('{{', '').replace('}}', '').replace('.', '').isalnum():
                if not ('{{' in variable_name and '}}' in variable_name):  # Allow templates
                    QMessageBox.warning(self, "Validation Error", 
                                      "Variable name must contain only alphanumeric characters, underscores, and hyphens, or be a valid template.")
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
            self.status_label.setText("Variable configuration saved")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save parameters: {e}")
            
    def reset_parameters(self):
        """Reset parameters to default or current node values"""
        if self.current_node:
            self.load_variable_configuration()
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
                f"Are you sure you want to delete this variable node?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.node_deleted.emit(self.current_node)
                
    def _insert_template_variable_name(self, variable_text):
        """Insert template variable into the variable name widget"""
        if hasattr(self, '_current_name_widget') and self._current_name_widget:
            cursor_pos = self._current_name_widget.cursorPosition()
            current_text = self._current_name_widget.text()
            new_text = current_text[:cursor_pos] + variable_text + current_text[cursor_pos:]
            self._current_name_widget.setText(new_text)
            self._current_name_widget.setCursorPosition(cursor_pos + len(variable_text))
            
            # Mark parameters as changed
            self.on_parameter_changed()
            
    def _insert_template_variable_value(self, variable_text):
        """Insert template variable into the variable value widget"""
        if hasattr(self, '_current_value_widget') and self._current_value_widget:
            cursor = self._current_value_widget.textCursor()
            cursor.insertText(variable_text)
            
            # Mark parameters as changed
            self.on_parameter_changed()
            
    def close_panel(self):
        """Request to close the panel"""
        self.close_requested.emit()