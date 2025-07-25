from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, 
                            QLabel, QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, 
                            QCheckBox, QComboBox, QPushButton, QFileDialog, QFrame,
                            QScrollArea, QWidget, QTabWidget, QGroupBox, QMessageBox,
                            QGridLayout, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPalette, QPixmap, QPainter, QColor
from pathlib import Path

from services.schema_service import SchemaService, ParameterType, ModuleParameter


class ParameterWidget:
    """Base class for parameter input widgets"""
    
    def __init__(self, parameter: ModuleParameter):
        self.parameter = parameter
        self.widget = None
        
    def create_widget(self) -> QWidget:
        """Create the appropriate input widget for this parameter type"""
        raise NotImplementedError
        
    def get_value(self):
        """Get the current value from the widget"""
        raise NotImplementedError
        
    def set_value(self, value):
        """Set the value in the widget"""
        raise NotImplementedError
        
    def validate(self) -> tuple[bool, str]:
        """Validate the current value"""
        value = self.get_value()
        if self.parameter.validation:
            return self.parameter.validation.validate(value, self.parameter.type)
        return True, ""


class TextParameterWidget(ParameterWidget):
    """Widget for text parameters with template variable support"""
    
    def __init__(self, parameter: ModuleParameter, workflow_context=None):
        super().__init__(parameter)
        self.workflow_context = workflow_context
        self.template_button = None
    
    def create_widget(self) -> QWidget:
        # Create container for text widget + template button
        container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        if self.parameter.type == ParameterType.TEXTAREA:
            self.widget = QTextEdit()
            self.widget.setMaximumHeight(100)
            if self.parameter.description:
                self.widget.setPlaceholderText(self.parameter.description)
        else:
            self.widget = QLineEdit()
            if self.parameter.description:
                self.widget.setPlaceholderText(self.parameter.description)
            
        if self.parameter.default:
            self.set_value(str(self.parameter.default))
            
        layout.addWidget(self.widget)
        
        # Add template variable button for text fields
        if self.workflow_context:
            from .template_variable_picker import TemplateInsertButton
            self.template_button = TemplateInsertButton(
                self.workflow_context.get('context'),
                self.workflow_context.get('current_node'),
                self.workflow_context.get('workflow_connections')
            )
            self.template_button.variable_selected.connect(self._insert_template_variable)
            layout.addWidget(self.template_button)
            
        container.setLayout(layout)
        return container
        
    def get_value(self):
        if isinstance(self.widget, QTextEdit):
            return self.widget.toPlainText()
        return self.widget.text()
        
    def set_value(self, value):
        if isinstance(self.widget, QTextEdit):
            self.widget.setPlainText(str(value))
        else:
            self.widget.setText(str(value))
            
    def _insert_template_variable(self, template_var: str):
        """Insert a template variable at the cursor position"""
        if isinstance(self.widget, QTextEdit):
            cursor = self.widget.textCursor()
            cursor.insertText(template_var)
        elif isinstance(self.widget, QLineEdit):
            cursor_pos = self.widget.cursorPosition()
            current_text = self.widget.text()
            new_text = current_text[:cursor_pos] + template_var + current_text[cursor_pos:]
            self.widget.setText(new_text)
            self.widget.setCursorPosition(cursor_pos + len(template_var))


class NumericParameterWidget(ParameterWidget):
    """Widget for numeric parameters"""
    
    def create_widget(self) -> QWidget:
        if self.parameter.type == ParameterType.INTEGER:
            self.widget = QSpinBox()
            self.widget.setRange(-2147483648, 2147483647)
            if self.parameter.validation:
                if self.parameter.validation.min_value is not None:
                    self.widget.setMinimum(int(self.parameter.validation.min_value))
                if self.parameter.validation.max_value is not None:
                    self.widget.setMaximum(int(self.parameter.validation.max_value))
        else:  # FLOAT
            self.widget = QDoubleSpinBox()
            self.widget.setRange(-1e10, 1e10)
            self.widget.setDecimals(6)
            if self.parameter.validation:
                if self.parameter.validation.min_value is not None:
                    self.widget.setMinimum(float(self.parameter.validation.min_value))
                if self.parameter.validation.max_value is not None:
                    self.widget.setMaximum(float(self.parameter.validation.max_value))
                    
        if self.parameter.default is not None:
            self.set_value(self.parameter.default)
            
        return self.widget
        
    def get_value(self):
        return self.widget.value()
        
    def set_value(self, value):
        if self.parameter.type == ParameterType.INTEGER:
            # Convert to int for QSpinBox
            self.widget.setValue(int(float(value)) if value else 0)
        else:
            # Convert to float for QDoubleSpinBox
            self.widget.setValue(float(value) if value else 0.0)


class BooleanParameterWidget(ParameterWidget):
    """Widget for boolean parameters"""
    
    def create_widget(self) -> QWidget:
        self.widget = QCheckBox()
        if self.parameter.default is not None:
            self.set_value(self.parameter.default)
        return self.widget
        
    def get_value(self):
        return self.widget.isChecked()
        
    def set_value(self, value):
        self.widget.setChecked(bool(value))


class ChoiceParameterWidget(ParameterWidget):
    """Widget for choice parameters"""
    
    def create_widget(self) -> QWidget:
        self.widget = QComboBox()
        if self.parameter.choices:
            self.widget.addItems(self.parameter.choices)
        if self.parameter.default:
            self.set_value(self.parameter.default)
        return self.widget
        
    def get_value(self):
        return self.widget.currentText()
        
    def set_value(self, value):
        index = self.widget.findText(str(value))
        if index >= 0:
            self.widget.setCurrentIndex(index)


class FileParameterWidget(ParameterWidget):
    """Widget for file/directory parameters"""
    
    def create_widget(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.line_edit = QLineEdit()
        if self.parameter.description:
            self.line_edit.setPlaceholderText(self.parameter.description)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        
        layout.addWidget(self.line_edit)
        layout.addWidget(browse_btn)
        container.setLayout(layout)
        
        if self.parameter.default:
            self.set_value(str(self.parameter.default))
            
        self.widget = container
        return container
        
    def _browse_file(self):
        if self.parameter.type == ParameterType.DIRECTORY:
            path = QFileDialog.getExistingDirectory(self.widget, "Select Directory")
        else:
            filters = "All Files (*)"
            if self.parameter.file_filters:
                filters = ";;".join(self.parameter.file_filters) + ";;" + filters
            path, _ = QFileDialog.getOpenFileName(self.widget, "Select File", "", filters)
            
        if path:
            self.line_edit.setText(path)
            
    def get_value(self):
        return self.line_edit.text()
        
    def set_value(self, value):
        self.line_edit.setText(str(value))


class NodeParameterDialog(QDialog):
    """Dialog for editing node parameters based on schema definitions"""
    
    parameters_updated = pyqtSignal(dict)  # Emit updated parameters
    
    def __init__(self, node, schema_service: SchemaService, template_registry=None, 
                 workflow_context=None, parent=None):
        super().__init__(parent)
        self.node = node
        self.schema_service = schema_service
        self.template_registry = template_registry
        self.workflow_context = workflow_context or {}
        self.parameter_widgets = {}
        self.current_parameters = node.parameters.copy() if hasattr(node, 'parameters') else {}
        self.template = None
        self.is_action_node = (hasattr(node, 'node_type') and 
                              (node.node_type == 'action' or 
                               node.node_type.startswith('schema_') or 
                               node.node_type.startswith('action_')))
        
        # Action node specific UI elements
        self.schema_selector = None
        self.category_module_area = None
        self.selected_schema = None
        self.selected_category = None
        self.selected_module = None
        self.module_cards = {}
        
        # Get template if available
        if self.template_registry and hasattr(node, 'template') and node.template:
            self.template = node.template
        elif self.template_registry and hasattr(node, 'node_type'):
            self.template = self.template_registry.get_template(node.node_type)
        
        self.setWindowTitle(f"Edit Node: {node.get_display_name()}")
        self.setModal(True)
        
        # Larger dialog for action nodes with module selection
        if self.is_action_node:
            self.resize(900, 700)
        else:
            self.resize(700, 600)
        
        self.setup_ui()
        self.load_parameters()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout()
        
        # Node info header
        self.create_node_info_section(layout)
        
        # Parameters section
        self.create_parameters_section(layout)
        
        # Buttons
        self.create_buttons_section(layout)
        
        self.setLayout(layout)
        
    def create_node_info_section(self, parent_layout):
        """Create the node information section (skip for action nodes)"""
        if self.is_action_node:
            # For action nodes, skip the node info section as requested
            return
            
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #232323;
                border: 1px solid #666666;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Node type and name
        title = QLabel(f"{self.node.get_display_name()}")
        font = title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)  # Make it slightly larger
        title.setFont(font)
        title.setStyleSheet("color: white; margin-bottom: 5px;")
        layout.addWidget(title)
        
        # Node description (from template or module info)
        description = None
        if self.template and hasattr(self.template, 'description'):
            description = self.template.description
        elif hasattr(self.node, 'module_info') and self.node.module_info.get('description'):
            description = self.node.module_info['description']
            
        if description:
            desc = QLabel(description)
            desc.setStyleSheet("color: #cccccc; font-style: italic;")
            desc.setWordWrap(True)
            layout.addWidget(desc)
            
        # Template info
        if self.template:
            template_info = QLabel(f"Template: {self.template.category}")
            template_info.setStyleSheet("color: #4CAF50; font-size: 10px; margin-top: 5px;")
            layout.addWidget(template_info)
            
        info_frame.setLayout(layout)
        parent_layout.addWidget(info_frame)
        
    def create_parameters_section(self, parent_layout):
        """Create the parameters editing section"""
        if self.is_action_node:
            self._create_action_node_ui(parent_layout)
        else:
            self._create_standard_parameters_ui(parent_layout)
    
    def _create_standard_parameters_ui(self, parent_layout):
        """Create standard parameters UI for non-action nodes"""
        # Parameters header
        header = QLabel("Parameters")
        font = header.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)  # Make it slightly larger
        header.setFont(font)
        header.setStyleSheet("color: white; margin-top: 10px; margin-bottom: 5px;")
        parent_layout.addWidget(header)
        
        # Scroll area for parameters
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #232323;
                border: 1px solid #666666;
                border-radius: 5px;
            }
        """)
        
        # Container for parameter widgets
        self.params_container = QWidget()
        self.params_layout = QFormLayout()
        self.params_layout.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        self.params_container.setLayout(self.params_layout)
        
        scroll_area.setWidget(self.params_container)
        parent_layout.addWidget(scroll_area)
        
    def _create_action_node_ui(self, parent_layout):
        """Create enhanced UI for action nodes with schema and module selection"""
        # Schema selection section
        self._create_schema_selection_section(parent_layout)
        
        # Category/Module selection section
        self._create_category_module_section(parent_layout)
        
        # Parameters section (for selected module)
        self._create_dynamic_parameters_section(parent_layout)
        
    def create_buttons_section(self, parent_layout):
        """Create the dialog buttons"""
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        # Preset buttons (if template is available)
        if self.template:
            load_preset_btn = QPushButton("Load Preset")
            load_preset_btn.clicked.connect(self.load_preset)
            buttons_layout.addWidget(load_preset_btn)
            
            save_preset_btn = QPushButton("Save Preset")
            save_preset_btn.clicked.connect(self.save_preset)
            buttons_layout.addWidget(save_preset_btn)
            
            buttons_layout.addWidget(QLabel("|"))  # Separator
        
        # Validate button
        validate_btn = QPushButton("Validate")
        validate_btn.clicked.connect(self.validate_parameters)
        buttons_layout.addWidget(validate_btn)
        
        # Reset to defaults button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        buttons_layout.addWidget(reset_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        # Save button
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save_parameters)
        buttons_layout.addWidget(save_btn)
        
        parent_layout.addLayout(buttons_layout)
        
    def load_parameters(self):
        """Load parameters based on node type"""
        try:
            if self.is_action_node:
                self._load_action_node_parameters()
            elif self.template and self._load_template_parameters():
                return
            elif hasattr(self.node, 'node_type') and self.node.node_type.startswith('schema_'):
                self._load_schema_parameters()
            else:
                self._load_builtin_parameters()
                
        except Exception as e:
            QMessageBox.warning(self, "Parameter Loading Error", 
                              f"Failed to load parameters: {str(e)}")
                              
    def _load_action_node_parameters(self):
        """Load parameters for action nodes with schema/module selection"""
        # Load current selections from node parameters
        if 'schema_file' in self.current_parameters:
            schema_file = self.current_parameters['schema_file']
            # Find and set schema in dropdown
            for i in range(self.schema_selector.count()):
                if self.schema_selector.itemData(i) == schema_file:
                    self.schema_selector.setCurrentIndex(i)
                    self.selected_schema = schema_file
                    break
                    
        if 'category' in self.current_parameters and 'module' in self.current_parameters:
            self.selected_category = self.current_parameters['category']
            self.selected_module = self.current_parameters['module']
            
        # Update UI based on current selections
        if self.selected_schema:
            self._update_module_grid()
            
            # Select the module card if we have a selection
            if self.selected_category and self.selected_module:
                card_key = f"{self.selected_category}.{self.selected_module}"
                if card_key in self.module_cards:
                    card = self.module_cards[card_key]
                    card.selected = True
                    self._update_card_selection(card)
                    self._load_module_parameters()
                              
    def _load_template_parameters(self):
        """Load parameters from template (skip for action nodes)"""
        if self.is_action_node:
            return False
            
        if not self.template or not hasattr(self.template, 'default_parameters'):
            return False
            
        # Check if template has parameter definitions
        template_params = getattr(self.template, 'parameters', None)
        if not template_params:
            # Use default parameters as simple text fields
            for param_name, default_value in self.template.default_parameters.items():
                # Skip schema-related parameters for non-action nodes
                if param_name not in ['schema_file', 'category', 'module']:
                    self._create_simple_parameter_widget(param_name, default_value)
            return True
            
        # Use template parameter definitions
        for param_name, param_def in template_params.items():
            # Skip schema-related parameters for non-action nodes
            if param_name not in ['schema_file', 'category', 'module']:
                self._create_parameter_widget(param_name, param_def)
            
        return True
        
    def _create_simple_parameter_widget(self, param_name: str, default_value):
        """Create a simple parameter widget without full schema definition"""
        from services.schema_service import ModuleParameter, ParameterType
        
        # Infer parameter type from default value
        if isinstance(default_value, bool):
            param_type = ParameterType.BOOLEAN
        elif isinstance(default_value, int):
            param_type = ParameterType.INTEGER
        elif isinstance(default_value, float):
            param_type = ParameterType.FLOAT
        else:
            param_type = ParameterType.TEXT
            
        # Create parameter definition
        param_def = ModuleParameter(
            name=param_name,
            type=param_type,
            display_name=param_name.replace('_', ' ').title(),
            description=f"Parameter for {param_name}",
            required=False,
            default=default_value
        )
        
        self._create_parameter_widget(param_name, param_def)
            
    def _load_schema_parameters(self):
        """Load parameters for schema-based nodes"""
        module_info = self.node.module_info
        schema_file = module_info.get('schema_file')
        category_name = module_info.get('category')
        module_name = module_info.get('module_name')
        
        if not all([schema_file, category_name, module_name]):
            self._add_error_message("Missing module information for schema node")
            return
            
        # Load schema and get module
        schema = self.schema_service.get_schema(schema_file)
        if not schema:
            self._add_error_message(f"Failed to load schema: {schema_file}")
            return
            
        module = schema.get_module(category_name, module_name)
        if not module:
            self._add_error_message(f"Module not found: {category_name}.{module_name}")
            return
            
        # Create parameter widgets
        if not module.parameters:
            self._add_info_message("This module has no configurable parameters")
            return
            
        for param_name, param_def in module.parameters.items():
            self._create_parameter_widget(param_name, param_def)
            
    def _load_builtin_parameters(self):
        """Load parameters for built-in node types"""
        if self.node.node_type == 'delay':
            # Create delay parameter
            from services.schema_service import ModuleParameter, ParameterType
            delay_param = ModuleParameter(
                name='delay_seconds',
                type=ParameterType.INTEGER,
                display_name='Delay (seconds)',
                description='Number of seconds to wait',
                required=True,
                default=1
            )
            self._create_parameter_widget('delay_seconds', delay_param)
            
        elif self.node.node_type.startswith('condition_'):
            self._load_condition_parameters()
        else:
            self._add_info_message("This node type has no configurable parameters")
            
    def _load_condition_parameters(self):
        """Load parameters for condition nodes"""
        from services.schema_service import ModuleParameter, ParameterType
        
        if self.node.node_type == 'condition_contains':
            params = [
                ModuleParameter('value', ParameterType.TEXT, 'Text to find', 'Text that must be contained in the output'),
                ModuleParameter('case_sensitive', ParameterType.BOOLEAN, 'Case sensitive', 'Whether the search is case sensitive', False, False)
            ]
        elif self.node.node_type == 'condition_equals':
            params = [
                ModuleParameter('value', ParameterType.TEXT, 'Expected value', 'Exact text that output must match'),
                ModuleParameter('case_sensitive', ParameterType.BOOLEAN, 'Case sensitive', 'Whether the comparison is case sensitive', False, False)
            ]
        elif self.node.node_type == 'condition_regex':
            params = [
                ModuleParameter('pattern', ParameterType.TEXT, 'Regex pattern', 'Regular expression pattern to match'),
                ModuleParameter('case_sensitive', ParameterType.BOOLEAN, 'Case sensitive', 'Whether the regex is case sensitive', False, False)
            ]
        elif self.node.node_type == 'condition_numeric':
            params = [
                ModuleParameter('value', ParameterType.FLOAT, 'Compare value', 'Value to compare against'),
                ModuleParameter('operator', ParameterType.CHOICE, 'Operator', 'Comparison operator', True, 'equals', 
                              choices=['equals', 'greater', 'less', 'greater_equal', 'less_equal'])
            ]
        else:
            params = []
            
        for param in params:
            self._create_parameter_widget(param.name, param)
            
    def _create_parameter_widget(self, param_name: str, param_def: ModuleParameter):
        """Create a widget for a parameter"""
        # Create label
        label_text = param_def.display_name
        if param_def.required:
            label_text += " *"
            
        label = QLabel(label_text)
        label.setStyleSheet("color: white; font-weight: bold;")
        
        if param_def.description:
            label.setToolTip(param_def.description)
            
        # Create parameter widget based on type
        if param_def.type in [ParameterType.TEXT, ParameterType.TEXTAREA]:
            widget_creator = TextParameterWidget(param_def, self.workflow_context)
        elif param_def.type in [ParameterType.INTEGER, ParameterType.FLOAT]:
            widget_creator = NumericParameterWidget(param_def)
        elif param_def.type == ParameterType.BOOLEAN:
            widget_creator = BooleanParameterWidget(param_def)
        elif param_def.type == ParameterType.CHOICE:
            widget_creator = ChoiceParameterWidget(param_def)
        elif param_def.type in [ParameterType.FILE, ParameterType.DIRECTORY]:
            widget_creator = FileParameterWidget(param_def)
        else:
            # Fallback to text widget
            widget_creator = TextParameterWidget(param_def, self.workflow_context)
            
        widget = widget_creator.create_widget()
        
        # Set current value if it exists
        if param_name in self.current_parameters:
            widget_creator.set_value(self.current_parameters[param_name])
            
        # Store widget creator for value retrieval
        self.parameter_widgets[param_name] = widget_creator
        
        # Create container with description
        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 5)
        
        container_layout.addWidget(widget)
        
        if param_def.description:
            desc_label = QLabel(param_def.description)
            desc_label.setStyleSheet("color: #999999; font-size: 10px; font-style: italic;")
            desc_label.setWordWrap(True)
            container_layout.addWidget(desc_label)
            
        container.setLayout(container_layout)
        
        # Add to form layout
        self.params_layout.addRow(label, container)
        
    def _add_error_message(self, message: str):
        """Add an error message to the parameters area"""
        error_label = QLabel(message)
        error_label.setStyleSheet("color: #ff6666; font-style: italic; padding: 10px;")
        error_label.setWordWrap(True)
        self.params_layout.addWidget(error_label)
        
    def _add_info_message(self, message: str):
        """Add an info message to the parameters area"""
        info_label = QLabel(message)
        info_label.setStyleSheet("color: #cccccc; font-style: italic; padding: 10px;")
        info_label.setWordWrap(True)
        self.params_layout.addWidget(info_label)
        
    def validate_parameters(self):
        """Validate all parameters and show results"""
        errors = []
        
        for param_name, widget_creator in self.parameter_widgets.items():
            is_valid, error_msg = widget_creator.validate()
            if not is_valid:
                errors.append(f"{widget_creator.parameter.display_name}: {error_msg}")
                
        if errors:
            QMessageBox.warning(self, "Validation Errors", 
                              "The following validation errors were found:\n\n" + "\n".join(errors))
        else:
            QMessageBox.information(self, "Validation Success", 
                                  "All parameters are valid!")
            
    def save_parameters(self):
        """Save parameters and close dialog"""
        # For action nodes, validate schema and module selection
        if self.is_action_node:
            if not self.selected_schema:
                QMessageBox.warning(self, "Validation Error", "Please select a schema file.")
                return
            if not self.selected_category or not self.selected_module:
                QMessageBox.warning(self, "Validation Error", "Please select a module.")
                return
        
        # Validate parameters
        errors = []
        new_parameters = {}
        
        # For action nodes, save schema/module selection
        if self.is_action_node:
            new_parameters['schema_file'] = self.selected_schema
            new_parameters['category'] = self.selected_category
            new_parameters['module'] = self.selected_module
        
        # Validate and collect parameter values
        for param_name, widget_creator in self.parameter_widgets.items():
            is_valid, error_msg = widget_creator.validate()
            if not is_valid:
                errors.append(f"{widget_creator.parameter.display_name}: {error_msg}")
            else:
                new_parameters[param_name] = widget_creator.get_value()
                
        if errors:
            QMessageBox.warning(self, "Validation Errors", 
                              "Please fix the following errors before saving:\n\n" + "\n".join(errors))
            return
            
        # Save parameters to node
        self.node.parameters = new_parameters
        
        # Emit signal
        self.parameters_updated.emit(new_parameters)
        
        # Close dialog
        self.accept()
        
    def load_preset(self):
        """Load parameter preset from template"""
        if not self.template:
            return
            
        from PyQt6.QtWidgets import QInputDialog
        
        # Get available presets
        presets = getattr(self.template, 'parameter_presets', {})
        if not presets:
            QMessageBox.information(self, "No Presets", "No parameter presets are available for this template.")
            return
            
        # Show preset selection dialog
        preset_names = list(presets.keys())
        preset_name, ok = QInputDialog.getItem(self, "Load Preset", "Select preset:", preset_names, 0, False)
        
        if ok and preset_name:
            preset_params = presets[preset_name]
            # Apply preset parameters to widgets
            for param_name, value in preset_params.items():
                if param_name in self.parameter_widgets:
                    self.parameter_widgets[param_name].set_value(value)
                    
    def save_preset(self):
        """Save current parameters as a preset"""
        if not self.template:
            return
            
        from PyQt6.QtWidgets import QInputDialog
        
        # Get preset name from user
        preset_name, ok = QInputDialog.getText(self, "Save Preset", "Enter preset name:")
        
        if ok and preset_name:
            # Collect current parameters
            current_params = {}
            for param_name, widget_creator in self.parameter_widgets.items():
                try:
                    current_params[param_name] = widget_creator.get_value()
                except:
                    pass
                    
            # Save to template (in memory - would need persistence layer for permanent storage)
            if not hasattr(self.template, 'parameter_presets'):
                self.template.parameter_presets = {}
            self.template.parameter_presets[preset_name] = current_params
            
            QMessageBox.information(self, "Preset Saved", f"Preset '{preset_name}' has been saved.")
            
    def reset_to_defaults(self):
        """Reset all parameters to their default values"""
        for param_name, widget_creator in self.parameter_widgets.items():
            if hasattr(widget_creator.parameter, 'default') and widget_creator.parameter.default is not None:
                widget_creator.set_value(widget_creator.parameter.default)
                
        QMessageBox.information(self, "Reset Complete", "All parameters have been reset to their default values.")
        
    def _create_schema_selection_section(self, parent_layout):
        """Create schema selection dropdown section"""
        # Simple layout without header and borders - like command_widget style
        schema_layout = QHBoxLayout()
        schema_layout.setContentsMargins(0, 10, 0, 10)
        
        schema_label = QLabel("Schema File:")
        schema_label.setStyleSheet("color: white; font-weight: bold;")
        schema_layout.addWidget(schema_label)
        
        self.schema_selector = QComboBox()
        
        # Clean styling matching receiver_config_dialog
        self.schema_selector.setStyleSheet("""
            QComboBox {
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 5px;
                background-color: rgb(35, 35, 35);
                color: white;
                min-width: 250px;
                font-size: 12px;
            }
            QComboBox:focus {
                border: 1px solid #888888;
            }
            QComboBox QAbstractItemView {
                background-color: rgb(35, 35, 35);
                border: 1px solid #666666;
                selection-background-color: #4a90e2;
                color: white;
            }
        """)
        
        self.schema_selector.currentTextChanged.connect(self._on_schema_changed)
        self.schema_selector.currentIndexChanged.connect(self._on_schema_index_changed)
        self.schema_selector.setEnabled(True)
        self.schema_selector.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.schema_selector.setEditable(False)
        
        schema_layout.addWidget(self.schema_selector)
        schema_layout.addStretch()
        
        # Load schemas after creating the widget
        self._load_available_schemas()
        
        parent_layout.addLayout(schema_layout)
        
    def _create_category_module_section(self, parent_layout):
        """Create category and module selection section with grid UI"""
        # Clean section without borders
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 15, 0, 10)
        
        # Simple header without styling
        header = QLabel("Module Selection")
        header.setStyleSheet("color: white; font-weight: bold; font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Scroll area for module cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        
        # Container for module grid
        self.module_grid_container = QWidget()
        self.module_grid_layout = QVBoxLayout()
        self.module_grid_container.setLayout(self.module_grid_layout)
        
        scroll_area.setWidget(self.module_grid_container)
        layout.addWidget(scroll_area)
        
        parent_layout.addLayout(layout)
        
    def _create_dynamic_parameters_section(self, parent_layout):
        """Create dynamic parameters section that updates based on module selection"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 15, 0, 0)
        
        # Header
        header = QLabel("Parameters")
        header.setStyleSheet("color: white; font-weight: bold; font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Scroll area for parameters
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: 1px solid #555555;
                border-radius: 3px;
            }
        """)
        
        # Container for parameter widgets
        self.params_container = QWidget()
        self.params_layout = QFormLayout()
        self.params_layout.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        self.params_container.setLayout(self.params_layout)
        
        scroll_area.setWidget(self.params_container)
        layout.addWidget(scroll_area)
        
        parent_layout.addLayout(layout)
        
    def _load_available_schemas(self):
        """Load all available schema files into the dropdown"""
        # Check for None explicitly instead of using bool() which fails for uninitialized Qt widgets
        if self.schema_selector is None:
            return
            
        self.schema_selector.clear()
        self.schema_selector.addItem("Select a schema...", None)
        
        try:
            # Get available schema files - use absolute path resolution
            import os
            current_dir = os.getcwd()
            schemas_dir = Path(current_dir) / "schemas"
            
            if schemas_dir.exists():
                schema_files = list(schemas_dir.glob("*.yaml"))
                
                for schema_file in schema_files:
                    if schema_file.name != "beacon_schema_format.yaml":  # Skip format spec
                        display_name = schema_file.stem.replace('_', ' ').title()
                        self.schema_selector.addItem(display_name, schema_file.name)
            else:
                # Try alternative paths
                alt_paths = [
                    Path(current_dir).parent / "schemas",
                    Path("/home/defcon/BeaconatorC2/schemas")
                ]
                for alt_path in alt_paths:
                    if alt_path.exists():
                        schemas_dir = alt_path
                        for schema_file in schemas_dir.glob("*.yaml"):
                            if schema_file.name != "beacon_schema_format.yaml":
                                display_name = schema_file.stem.replace('_', ' ').title()
                                self.schema_selector.addItem(display_name, schema_file.name)
                        break
            
            # If no schemas were found, add some test items
            if self.schema_selector.count() <= 1:  # Only "Select a schema..." item
                self.schema_selector.addItem("Python Beacon", "python_beacon.yaml")
                self.schema_selector.addItem("Simple Python Beacon", "simple_python_beacon.yaml")
                self.schema_selector.addItem("AutoHotkey Beacon", "autohotkey_beacon.yaml")
            
            # Set current value if available
            if 'schema_file' in self.current_parameters:
                current_schema = self.current_parameters['schema_file']
                for i in range(self.schema_selector.count()):
                    if self.schema_selector.itemData(i) == current_schema:
                        self.schema_selector.setCurrentIndex(i)
                        break
                        
        except Exception as e:
            # Add fallback items
            self.schema_selector.addItem("Python Beacon", "python_beacon.yaml")
            self.schema_selector.addItem("Simple Python Beacon", "simple_python_beacon.yaml")
                    
    def _on_schema_changed(self, schema_display_name):
        """Handle schema selection change"""
        # Safety check - only handle schema changes for action nodes
        if not self.is_action_node:
            return
            
        schema_file = self.schema_selector.currentData()
        if schema_file != self.selected_schema:
            self.selected_schema = schema_file
            # Clear module selection when schema changes
            self.selected_category = None
            self.selected_module = None
            # Update module grid
            self._update_module_grid()
            # Clear parameters
            self._clear_parameters()
            
    def _on_schema_index_changed(self, index):
        """Handle schema selection index change"""
        # Safety check - only handle schema changes for action nodes
        if not self.is_action_node:
            return
            
        if index >= 0:
            schema_file = self.schema_selector.itemData(index)
            
            if schema_file != self.selected_schema:
                self.selected_schema = schema_file
                # Clear module selection when schema changes
                self.selected_category = None
                self.selected_module = None
                # Update module grid
                self._update_module_grid()
                # Clear parameters
                self._clear_parameters()
            
    def _update_module_grid(self):
        """Update the module selection grid based on current schema"""
        # Safety check - only update if this is an action node with module grid
        if not self.is_action_node or not hasattr(self, 'module_grid_layout'):
            return
            
        # Clear existing grid
        self._clear_module_grid()
        
        if not self.selected_schema:
            # Show message to select schema
            msg_label = QLabel("Please select a schema file to view available modules.")
            msg_label.setStyleSheet("color: #cccccc; font-style: italic; padding: 20px;")
            msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.module_grid_layout.addWidget(msg_label)
            return
            
        # Load schema and create module cards
        try:
            schema = self.schema_service.load_schema(self.selected_schema)
            if not schema:
                self._show_module_error("Failed to load schema file.")
                return
                
            if not schema.categories:
                self._show_module_error("No categories found in schema.")
                return
                
            # Create cards grouped by category
            for category_name, category in schema.categories.items():
                if category.modules:
                    self._create_category_section(category_name, category)
                    
        except Exception as e:
            self._show_module_error(f"Error loading schema: {str(e)}")
            
    def _create_category_section(self, category_name, category):
        """Create a category section with module cards"""
        # Category header
        category_header = QLabel(category_name.replace('_', ' ').title())
        font = category_header.font()
        font.setBold(True)
        category_header.setFont(font)
        category_header.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
                padding: 10px 5px 5px 5px;
                border-bottom: 1px solid #555555;
                margin-bottom: 10px;
            }
        """)
        self.module_grid_layout.addWidget(category_header)
        
        # Module grid for this category
        modules_grid = QGridLayout()
        modules_grid.setSpacing(10)
        
        modules = list(category.modules.items())
        columns = self._calculate_grid_columns()
        
        for i, (module_name, module) in enumerate(modules):
            row = i // columns
            col = i % columns
            
            card = self._create_module_card(category_name, module_name, module)
            modules_grid.addWidget(card, row, col)
            
        # Add stretch to fill remaining columns
        modules_grid.setColumnStretch(columns, 1)
        
        grid_widget = QWidget()
        grid_widget.setLayout(modules_grid)
        self.module_grid_layout.addWidget(grid_widget)
        
    def _calculate_grid_columns(self):
        """Calculate number of columns based on dialog width"""
        dialog_width = self.width()
        card_width = 250  # Approximate card width
        margin = 60  # Account for margins and scrollbar
        available_width = dialog_width - margin
        columns = max(1, available_width // card_width)
        return min(columns, 4)  # Max 4 columns
        
    def _create_module_card(self, category_name, module_name, module):
        """Create a compact module selection card using proper widget layout"""
        card = QWidget()
        card.setFixedHeight(80)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Create layout similar to connection_menu TemplateOptionWidget
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Icon (simple colored square like connection menu)
        icon_label = QLabel()
        icon_pixmap = self._create_module_icon(category_name)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setFixedSize(24, 24)
        layout.addWidget(icon_label)
        
        # Content area
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)
        
        # Module name
        name_label = QLabel(module.display_name)
        name_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        content_layout.addWidget(name_label)
        
        # Description
        if hasattr(module, 'description') and module.description:
            desc_text = module.description[:60] + "..." if len(module.description) > 60 else module.description
            desc_label = QLabel(desc_text)
            desc_label.setStyleSheet("""
                QLabel {
                    color: #cccccc;
                    font-size: 11px;
                    font-style: italic;
                }
            """)
            desc_label.setWordWrap(True)
            content_layout.addWidget(desc_label)
        
        layout.addLayout(content_layout)
        layout.addStretch()
        
        # Parameter indicators (like connection menu)
        param_count = len(module.parameters) if hasattr(module, 'parameters') and module.parameters else 0
        admin_required = getattr(module, 'requires_admin', False)
        
        if param_count > 0:
            param_label = QLabel(f"{param_count} param{'s' if param_count != 1 else ''}")
            param_label.setStyleSheet("""
                QLabel {
                    color: #999999;
                    font-size: 10px;
                    background-color: #2a2a2a;
                    border-radius: 8px;
                    padding: 2px 6px;
                }
            """)
            layout.addWidget(param_label)
            
        if admin_required:
            admin_label = QLabel("admin")
            admin_label.setStyleSheet("""
                QLabel {
                    color: #ff9999;
                    font-size: 10px;
                    background-color: #3a2a2a;
                    border-radius: 8px;
                    padding: 2px 6px;
                }
            """)
            layout.addWidget(admin_label)
        
        card.setLayout(layout)
        
        # Card styling similar to connection menu
        card.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border-radius: 4px;
                margin: 1px;
            }
            QWidget:hover {
                background-color: #555555;
            }
        """)
        
        # Make it clickable by storing selection state and handling mouse events
        card.selected = False
        card.category_name = category_name
        card.module_name = module_name
        
        def mousePressEvent(event):
            if event.button() == Qt.MouseButton.LeftButton:
                # Toggle selection
                card.selected = not card.selected
                self._update_card_selection(card)
                self._on_module_selected(category_name, module_name, card.selected)
        
        card.mousePressEvent = mousePressEvent
        
        # Store card reference
        card_key = f"{category_name}.{module_name}"
        self.module_cards[card_key] = card
        
        return card
        
    def _create_module_icon(self, category_name):
        """Create an icon for the module category"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Color based on category
        category_colors = {
            "basic_operations": "#2196F3",
            "file_operations": "#9C27B0", 
            "information_gathering": "#FF9800",
            "persistence": "#F44336",
            "movement": "#607D8B",
            "data_operations": "#795548"
        }
        
        color = QColor(category_colors.get(category_name.lower(), "#757575"))
        painter.setBrush(color)
        painter.setPen(QColor(255, 255, 255, 100))
        painter.drawRoundedRect(2, 2, 20, 20, 4, 4)
        
        # Add category initial
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        
        text = category_name[0].upper()
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        
        painter.end()
        return pixmap
        
    def _update_card_selection(self, selected_card):
        """Update visual selection state of cards"""
        # Unselect all other cards
        for card in self.module_cards.values():
            if card != selected_card:
                card.selected = False
                card.setStyleSheet("""
                    QWidget {
                        background-color: transparent;
                        border-radius: 4px;
                        margin: 1px;
                    }
                    QWidget:hover {
                        background-color: #555555;
                    }
                """)
        
        # Update selected card style
        if selected_card.selected:
            selected_card.setStyleSheet("""
                QWidget {
                    background-color: #4a90e2;
                    border-radius: 4px;
                    margin: 1px;
                }
                QWidget:hover {
                    background-color: #5a9ff2;
                }
            """)
        else:
            selected_card.setStyleSheet("""
                QWidget {
                    background-color: transparent;
                    border-radius: 4px;
                    margin: 1px;
                }
                QWidget:hover {
                    background-color: #555555;
                }
            """)
        
    def _on_module_selected(self, category_name, module_name, selected):
        """Handle module selection"""
        if selected:
            self.selected_category = category_name
            self.selected_module = module_name
            self._load_module_parameters()
        else:
            # If unchecking, clear selection
            self.selected_category = None
            self.selected_module = None
            self._clear_parameters()
            
    def _load_module_parameters(self):
        """Load parameters for the selected module"""
        if not all([self.selected_schema, self.selected_category, self.selected_module]):
            return
            
        try:
            schema = self.schema_service.load_schema(self.selected_schema)
            if not schema:
                return
                
            module = schema.get_module(self.selected_category, self.selected_module)
            if not module:
                return
                
            # Clear existing parameters
            self._clear_parameters()
            
            # Create parameter widgets
            if hasattr(module, 'parameters') and module.parameters:
                for param_name, param_def in module.parameters.items():
                    self._create_parameter_widget(param_name, param_def)
            else:
                self._add_info_message("This module has no configurable parameters.")
                
        except Exception as e:
            self._add_error_message(f"Error loading module parameters: {str(e)}")
            
    def _clear_module_grid(self):
        """Clear all widgets from the module grid"""
        if not hasattr(self, 'module_grid_layout') or not self.module_grid_layout:
            return
            
        while self.module_grid_layout.count():
            child = self.module_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.module_cards.clear()
        
    def _clear_parameters(self):
        """Clear all parameter widgets"""
        if not hasattr(self, 'params_layout') or not self.params_layout:
            return
            
        while self.params_layout.count():
            child = self.params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.parameter_widgets.clear()
        
    def _show_module_error(self, message):
        """Show error message in module area"""
        if not hasattr(self, 'module_grid_layout') or not self.module_grid_layout:
            return
            
        error_label = QLabel(message)
        error_label.setStyleSheet("color: #ff6666; font-style: italic; padding: 20px;")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.module_grid_layout.addWidget(error_label)