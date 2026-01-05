"""
Node Editing Content Widget

Extracted from NodeEditingPanel to work within the unified SidePanel system.
Handles node parameter editing, schema/module selection, and node operations.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                            QScrollArea, QFrame, QFormLayout, QLineEdit, QTextEdit, 
                            QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QMessageBox,
                            QGroupBox, QSizePolicy, QGridLayout, QStackedWidget, QSpacerItem)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QPixmap, QPalette
from pathlib import Path

from services.schema_service import SchemaService, ParameterType
from ui.workflows.node_parameter_dialog import (TextParameterWidget, NumericParameterWidget,
                                                BooleanParameterWidget, FileParameterWidget,
                                                ChoiceParameterWidget)


class NodeEditingContent(QWidget):
    """Content widget for node editing within unified side panel"""
    
    # Signals
    node_updated = pyqtSignal(object, dict)  # node, parameters
    node_deleted = pyqtSignal(object)  # node
    node_execution_requested = pyqtSignal(object)  # node execution requested
    close_requested = pyqtSignal()  # close panel requested
    
    def __init__(self, schema_service: SchemaService = None):
        super().__init__()
        self.schema_service = schema_service
        self.current_node = None
        self.parameter_widgets = {}
        self.workflow_context = None
        
        # Schema and module selection state
        self.selected_schema = None
        self.selected_category = None
        self.selected_module = None
        self.module_cards = {}
        self.is_action_node = False
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the content UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Node info header (no close button - handled by parent panel)
        self.create_node_header()
        layout.addWidget(self.node_header)
        
        # Create stacked widget for multi-stage parameter editing
        self.create_parameter_stack()
        layout.addWidget(self.parameter_stack)
        
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
        
        self.node_title_label = QLabel("No Node Selected")
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
        
    def create_parameter_stack(self):
        """Create stacked widget for multi-stage parameter editing"""
        self.parameter_stack = QStackedWidget()
        
        # Stage 1: Schema selection (for action nodes)
        self.create_schema_selection_stage()
        self.parameter_stack.addWidget(self.schema_stage)
        
        # Stage 2: Module selection (for action nodes)
        self.create_module_selection_stage()
        self.parameter_stack.addWidget(self.module_stage)
        
        # Stage 3: Parameter input (all nodes)
        self.create_parameter_input_stage()
        self.parameter_stack.addWidget(self.parameter_stage)
        
        # Default view for non-action nodes or initial state
        self.create_placeholder_stage()
        self.parameter_stack.addWidget(self.placeholder_stage)
        
        # Start with placeholder
        self.parameter_stack.setCurrentWidget(self.placeholder_stage)
        
    def create_schema_selection_stage(self):
        """Create schema selection stage for action nodes"""
        self.schema_stage = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("Step 1: Select Schema File")
        header.setStyleSheet("""
            color: #ffffff;
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 10px;
        """)
        layout.addWidget(header)
        
        # Instructions
        instructions = QLabel("Select a schema file to view available modules for this action node.")
        instructions.setStyleSheet("color: #cccccc; font-style: italic; margin-bottom: 10px;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Schema list container (similar to parameter container)
        self.schema_container = QFrame()
        self.schema_container.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        
        self.schema_layout = QVBoxLayout()
        self.schema_layout.setContentsMargins(0, 0, 0, 0)
        self.schema_layout.setSpacing(0)
        self.schema_container.setLayout(self.schema_layout)
        
        layout.addWidget(self.schema_container)
        layout.addStretch()  # Push everything to the top
        self.schema_stage.setLayout(layout)
        
    def create_module_selection_stage(self):
        """Create module selection stage for action nodes"""
        self.module_stage = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(10)
        
        # Header with back button
        header_layout = QHBoxLayout()
        back_btn = QPushButton("← Back to Schema")
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                border: none;
                color: white;
                font-size: 11px;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
        """)
        back_btn.clicked.connect(self._go_to_schema_selection)
        header_layout.addWidget(back_btn)
        
        header_layout.addStretch()
        
        self.module_header_label = QLabel("Step 2: Select Module")
        self.module_header_label.setStyleSheet("""
            color: #ffffff;
            font-weight: bold;
            font-size: 14px;
        """)
        header_layout.addWidget(self.module_header_label)
        layout.addLayout(header_layout)
        
        # Module grid in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #2b2b2b;
                border: none;
            }
        """)
        
        self.module_grid_container = QWidget()
        self.module_grid_layout = QVBoxLayout()
        self.module_grid_container.setLayout(self.module_grid_layout)
        scroll_area.setWidget(self.module_grid_container)
        
        layout.addWidget(scroll_area)
        self.module_stage.setLayout(layout)
        
    def create_parameter_input_stage(self):
        """Create parameter input stage for all nodes"""
        self.parameter_stage = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 20, 15, 20)
        layout.setSpacing(10)
        
        # Header with navigation for action nodes
        self.param_header_layout = QHBoxLayout()
        
        # Back button (for action nodes)
        self.param_back_btn = QPushButton("← Back to Modules")
        self.param_back_btn.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                border: none;
                color: white;
                font-size: 11px;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
        """)
        self.param_back_btn.clicked.connect(self._go_to_module_selection)
        self.param_back_btn.hide()  # Hidden by default for non-action nodes
        self.param_header_layout.addWidget(self.param_back_btn)
        
        self.param_header_layout.addStretch()
        
        self.param_header_label = QLabel("")
        self.param_header_label.setStyleSheet("""
            color: #ffffff;
            font-weight: bold;
            font-size: 14px;
        """)
        self.param_header_layout.addWidget(self.param_header_label)
        layout.addLayout(self.param_header_layout)
        
        # Parameters container
        self.param_container = QWidget()
        self.param_form_layout = QFormLayout()
        self.param_form_layout.setContentsMargins(0, 0, 0, 0)
        self.param_form_layout.setSpacing(12)
        self.param_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignTop)
        self.param_container.setLayout(self.param_form_layout)
        
        layout.addWidget(self.param_container)
        self.parameter_stage.setLayout(layout)
        
    def create_placeholder_stage(self):
        """Create placeholder stage for initial state"""
        self.placeholder_stage = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 40, 20, 40)
        
        placeholder_label = QLabel("Select a node to edit its properties")
        placeholder_label.setStyleSheet("""
            color: #888888;
            font-size: 13px;
            font-style: italic;
        """)
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()
        layout.addWidget(placeholder_label)
        layout.addStretch()
        
        self.placeholder_stage.setLayout(layout)
        
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
        self.save_button.setEnabled(True)
        
        footer_layout.addWidget(self.reset_button)
        footer_layout.addWidget(self.save_button)
        
        self.footer.setLayout(footer_layout)
        
    def on_panel_shown(self, node=None, workflow_context=None):
        """Called when the panel is shown with node editing content"""
        if node and workflow_context:
            self.show_node(node, workflow_context)
            
    def show_node(self, node, workflow_context=None):
        """Show editing interface for a specific node"""
        self.current_node = node
        self.workflow_context = workflow_context
        
        # Clear previous selection state to prevent cross-contamination between nodes
        self.selected_schema = None
        self.selected_category = None
        self.selected_module = None
        
        # Update header
        if hasattr(node, 'module_info') and node.module_info and 'name' in node.module_info:
            self.node_title_label.setText(node.module_info['name'])
        else:
            self.node_title_label.setText(f"{node.node_type.title()} Node")
        
        self.node_type_label.setText(f"ID: {node.node_id}")
        
        # Enable buttons are handled at the end
        
        # Handle different node types
        if node.node_type == 'action':
            self.is_action_node = True
            self.show_action_node_interface(node)
        else:
            self.is_action_node = False
            self.show_simple_node_interface(node)
            
        # Enable/disable buttons
        self.execute_button.setEnabled(node.node_type != 'start')
        self.delete_button.setEnabled(True)
        self.reset_button.setEnabled(True)
        # Save button state will be set by load_node_parameters based on node type
            
    def show_action_node_interface(self, node):
        """Show interface for action nodes (schema/module selection)"""
        # Check if node has saved configuration (either in module_info or parameters)
        has_saved_config = False
        
        # First check module_info (legacy format)
        if hasattr(node, 'module_info') and node.module_info and 'name' in node.module_info:
            self.selected_schema = node.module_info.get('schema', '')
            self.selected_category = node.module_info.get('category', '')
            self.selected_module = node.module_info.get('name', '')
            has_saved_config = True
        # Then check parameters (current format)
        elif hasattr(node, 'parameters') and node.parameters:
            schema_file = node.parameters.get('schema_file')
            category = node.parameters.get('category')
            module = node.parameters.get('module')
            
            if schema_file and category and module:
                self.selected_schema = schema_file
                self.selected_category = category
                self.selected_module = module
                has_saved_config = True
                
                # Update module_info for consistency
                node.module_info = {
                    'schema': schema_file,
                    'category': category, 
                    'name': module
                }
        
        if has_saved_config:
            # Go directly to parameters with saved values
            self._load_module_parameters()
            self.parameter_stack.setCurrentWidget(self.parameter_stage)
            self.param_back_btn.setVisible(True)
            self.param_header_label.setText(f"Step 3: Configure {self.selected_module}")
        else:
            # Start with schema selection
            self.load_schemas()
            self.parameter_stack.setCurrentWidget(self.schema_stage)
            
    def show_simple_node_interface(self, node):
        """Show interface for simple nodes (direct to parameters)"""
        self.load_node_parameters(node)
        self.parameter_stack.setCurrentWidget(self.parameter_stage)
        self.param_back_btn.setVisible(False)
        
    def load_schemas(self):
        """Load available schemas as clickable rows"""
        if not self.schema_service or not hasattr(self, 'schema_layout'):
            return
            
        # Clear existing schema widgets
        while self.schema_layout.count():
            child = self.schema_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        try:
            schemas = self.schema_service.list_available_schemas()
            for schema_name in schemas:
                self._create_schema_card(schema_name)
        except Exception as e:
            print(f"Error loading schemas: {e}")
            # Add fallback items
            self._create_schema_card("python_beacon.yaml")
            self._create_schema_card("simple_python_beacon.yaml")
            
    def _create_schema_card(self, schema_name):
        """Create a clickable card for a schema"""
        card = QWidget()
        card.setFixedHeight(60)  # Increased height to accommodate label padding
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)  # Reduced margins to give label more space
        
        # Schema name label
        display_name = schema_name.replace('_', ' ').replace('.yaml', '').title()
        label = QLabel(display_name)
        label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                background-color: #404040;
                padding: 10px 15px;
                border-radius: 3px;
            }
        """)
        
        layout.addWidget(label)
        layout.addStretch()
        
        # Arrow indicator
        arrow_label = QLabel("→")
        arrow_label.setStyleSheet("color: #888888; font-size: 14px;")
        layout.addWidget(arrow_label)
        
        card.setLayout(layout)
        
        # Set card styling - transparent with hover effect
        card.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
            QWidget:hover {
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        
        card.mousePressEvent = lambda event: self._select_schema(schema_name)
        
        # Add card to layout
        self.schema_layout.addWidget(card)
        
    def _select_schema(self, schema_name):
        """Handle schema selection"""
        self.selected_schema = schema_name
        self.selected_category = None
        self.selected_module = None
        # Automatically advance to module selection
        self.load_modules_for_schema(schema_name)
        self.parameter_stack.setCurrentWidget(self.module_stage)
        self.module_header_label.setText(f"Step 2: Select Module - {schema_name.replace('.yaml', '').replace('_', ' ').title()}")
        
    def _go_to_schema_selection(self):
        """Navigate back to schema selection stage"""
        self.parameter_stack.setCurrentWidget(self.schema_stage)
        
    def _go_to_module_selection(self):
        """Navigate back to module selection stage"""
        if self.selected_schema:
            self.load_modules_for_schema(self.selected_schema)
            self.parameter_stack.setCurrentWidget(self.module_stage)
        else:
            self._go_to_schema_selection()
        
    def load_modules_for_schema(self, schema_name):
        """Load modules for selected schema"""
        # Clear existing module widgets
        self._clear_module_grid()
        
        if not schema_name:
            # Show message to select schema
            msg_label = QLabel("Please select a schema file to view available modules.")
            msg_label.setStyleSheet("color: #cccccc; font-style: italic; padding: 20px;")
            msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.module_grid_layout.addWidget(msg_label)
            return
                
        try:
            schema = self.schema_service.get_schema(schema_name)
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
        columns = 1  # Use single column for better spacing
        
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
        
    def _on_module_selected(self, category_name, module_name, selected):
        """Handle module selection"""
        if selected:
            self.selected_category = category_name
            self.selected_module = module_name
            # Automatically advance to parameter input
            self._load_module_parameters()
            self.param_back_btn.show()
            self.param_header_label.setText(f"Step 3: Configure {module_name}")
            self.parameter_stack.setCurrentWidget(self.parameter_stage)
        else:
            self.selected_category = None
            self.selected_module = None
            self._clear_parameters()
        
    def load_node_parameters(self, node):
        """Load parameters for the current node"""
        # Clear existing parameter widgets
        self.parameter_widgets.clear()
        while self.param_form_layout.count():
            child = self.param_form_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
            elif child.layout():
                while child.layout().count():
                    subchild = child.layout().takeAt(0)
                    if subchild.widget():
                        subchild.widget().setParent(None)
                        
        if not node:
            return
            
        # Get parameters from schema or node type
        parameters = []
        if self.is_action_node and hasattr(node, 'module_info') and node.module_info:
            # Get parameters from schema
            try:
                if self.schema_service:
                    schema = self.schema_service.get_schema(node.module_info.get('schema', ''))
                    if schema:
                        module = schema.get_module(
                            node.module_info.get('category', ''), 
                            node.module_info.get('name', '')
                        )
                        if module:
                            # Convert parameters to dict format safely
                            parameters = []
                            for param in module.parameters:
                                if hasattr(param, '__dict__'):
                                    parameters.append(param.__dict__)
                                elif isinstance(param, dict):
                                    parameters.append(param)
                                else:
                                    # Handle string or other parameter formats
                                    parameters.append({
                                        'name': str(param),
                                        'type': 'text',
                                        'description': '',
                                        'required': False
                                    })
                        else:
                            parameters = []
                    else:
                        parameters = []
            except Exception as e:
                print(f"Error loading schema parameters: {e}")
        else:
            # Simple node types - basic parameters
            if node.node_type == 'start':
                parameters = []
            elif node.node_type == 'condition':
                parameters = [
                    {
                        'name': 'condition',
                        'type': 'text',
                        'description': 'Condition expression to evaluate',
                        'required': True
                    }
                ]
                
        # Create parameter widgets
        for param_info in parameters:
            self.create_parameter_widget(param_info)
            
        # Enable/disable buttons based on parameters
        has_params = len(parameters) > 0
        self.reset_button.setEnabled(has_params)
        self.save_button.setEnabled(True)  # Always allow saving

            
    def create_parameter_widget(self, param_info):
        """Create a widget for a parameter"""
        param_name = param_info['name']
        param_type = param_info.get('type', 'text')
        param_desc = param_info.get('description', '')
        param_required = param_info.get('required', False)
        param_default = param_info.get('default', '')
        
        # Get current value from node
        current_value = ""
        if self.current_node and hasattr(self.current_node, 'parameters'):
            current_value = self.current_node.parameters.get(param_name, param_default)
            
        # Create appropriate widget based on parameter type
        if param_type in ['text', 'string']:
            widget = TextParameterWidget(
                param_info, current_value, self.workflow_context
            )
        elif param_type in ['int', 'integer', 'float', 'number']:
            widget = NumericParameterWidget(param_info, current_value)
        elif param_type in ['bool', 'boolean']:
            widget = BooleanParameterWidget(param_info, current_value)
        elif param_type == 'file':
            widget = FileParameterWidget(param_info, current_value)
        elif param_type in ['choice', 'select', 'enum']:
            widget = ChoiceParameterWidget(param_info, current_value)
        else:
            # Default to text widget
            widget = TextParameterWidget(
                param_info, current_value, self.workflow_context
            )
            
        # Store reference to widget
        self.parameter_widgets[param_name] = widget
        
        # Create label
        label_text = param_name
        if param_required:
            label_text += "*"
            
        label = QLabel(label_text)
        label.setStyleSheet("""
            color: white;
            font-weight: bold;
            padding: 2px 0px;
        """)
        
        if param_desc:
            label.setToolTip(param_desc)
            
        # Add to form layout
        container = QWidget()
        container_layout = QHBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        #container_layout.setSpacing(8)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        container_layout.addWidget(widget, 1)
        container.setLayout(container_layout)
        
        self.param_form_layout.addRow(label, container)
        
    def execute_node(self):
        """Execute the current node"""
        if self.current_node:
            self.node_execution_requested.emit(self.current_node)
            
    def delete_node(self):
        """Delete the current node"""
        if self.current_node:
            reply = QMessageBox.question(
                self, "Delete Node",
                f"Are you sure you want to delete this {self.current_node.node_type} node?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.node_deleted.emit(self.current_node)
                
    def reset_parameters(self):
        """Reset parameters to default values"""
        for param_name, widget in self.parameter_widgets.items():
            if hasattr(widget, 'reset_to_default'):
                widget.reset_to_default()
                
    def save_parameters(self):
        """Save parameter changes to the node"""
        if not self.current_node:
            return
            
        try:
            # For action nodes, validate that schema and module are selected
            if self.is_action_node:
                if not self.selected_schema:
                    QMessageBox.warning(self, "Validation Error", "Please select a schema file.")
                    return
                if not self.selected_category or not self.selected_module:
                    QMessageBox.warning(self, "Validation Error", "Please select a module.")
                    return
            
            # Collect parameter values
            updated_parameters = {}
            
            # For action nodes, save schema/module selection
            if self.is_action_node:
                updated_parameters['schema_file'] = self.selected_schema
                updated_parameters['category'] = self.selected_category
                updated_parameters['module'] = self.selected_module
            
            # Collect parameter values from widgets
            for param_name, widget_creator in self.parameter_widgets.items():
                if hasattr(widget_creator, 'get_value'):
                    # Use the widget creator to get the value
                    value = widget_creator.get_value()
                    updated_parameters[param_name] = value
                        
            # Update node parameters
            if not hasattr(self.current_node, 'parameters'):
                self.current_node.parameters = {}
                
            self.current_node.parameters.update(updated_parameters)
            
            # Update parameter display if node has this method
            if hasattr(self.current_node, 'update_parameter_display'):
                self.current_node.update_parameter_display()
                
            # Emit signal
            self.node_updated.emit(self.current_node, updated_parameters)
            
            self.save_button.setEnabled(True)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save parameters: {e}")

        
    def close_panel(self):
        """Request to close the panel"""
        self.close_requested.emit()
        
    def _create_module_card(self, category_name, module_name, module):
        """Create a compact module selection card"""
        card = QWidget()
        card.setFixedHeight(70)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Create layout
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)
        
        # Icon
        icon_label = QLabel()
        icon_pixmap = self._create_module_icon(category_name)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setFixedSize(20, 20)
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
                font-size: 12px;
            }
        """)
        content_layout.addWidget(name_label)
        
        # Description
        if hasattr(module, 'description') and module.description:
            desc_text = module.description[:50] + "..." if len(module.description) > 50 else module.description
            desc_label = QLabel(desc_text)
            desc_label.setStyleSheet("""
                QLabel {
                    color: #cccccc;
                    font-size: 10px;
                    font-style: italic;
                }
            """)
            desc_label.setWordWrap(True)
            content_layout.addWidget(desc_label)
        
        layout.addLayout(content_layout)
        layout.addStretch()
        
        # Parameter count indicator
        param_count = len(module.parameters) if hasattr(module, 'parameters') and module.parameters else 0
        if param_count > 0:
            param_label = QLabel(f"{param_count}")
            param_label.setStyleSheet("""
                QLabel {
                    color: #999999;
                    font-size: 9px;
                    background-color: #2a2a2a;
                    border-radius: 8px;
                    padding: 2px 5px;
                }
            """)
            layout.addWidget(param_label)
        
        card.setLayout(layout)
        
        # Card styling
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
        
        # Make it clickable
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
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Color rotation for categories - automatically assigns different colors
        color_palette = [
            "#2196F3",  # Blue
            "#9C27B0",  # Purple
            "#FF9800",  # Orange
            "#F44336",  # Red
            "#4CAF50",  # Green
            "#607D8B",  # Blue Gray
            "#795548",  # Brown
            "#E91E63",  # Pink
            "#FF5722",  # Deep Orange
            "#009688",  # Teal
            "#3F51B5",  # Indigo
            "#FFC107"   # Amber
        ]
        
        # Use hash of category name to get consistent color assignment
        color_index = hash(category_name) % len(color_palette)
        color = QColor(color_palette[color_index])
        painter.setBrush(color)
        painter.setPen(QColor(255, 255, 255, 100))
        painter.drawRoundedRect(2, 2, 16, 16, 3, 3)
        
        # Add category initial
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPixelSize(10)
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
            
    def _clear_module_grid(self):
        """Clear all widgets from the module grid"""
        if not hasattr(self, 'module_grid_layout') or not self.module_grid_layout:
            return
            
        while self.module_grid_layout.count():
            child = self.module_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.module_cards.clear()
        
    def _show_module_error(self, message):
        """Show error message in module area"""
        if not hasattr(self, 'module_grid_layout') or not self.module_grid_layout:
            return
            
        error_label = QLabel(message)
        error_label.setStyleSheet("color: #ff6666; font-style: italic; padding: 20px;")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.module_grid_layout.addWidget(error_label)
        
    def _clear_parameters(self):
        """Clear all parameter widgets"""
        if not hasattr(self, 'param_form_layout') or not self.param_form_layout:
            return
            
        while self.param_form_layout.count():
            child = self.param_form_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.parameter_widgets.clear()
        
    def _load_module_parameters(self):
        """Load parameters for the selected module"""
        if not all([self.selected_schema, self.selected_category, self.selected_module]):
            return
            
        try:
            schema = self.schema_service.get_schema(self.selected_schema)
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
            
            # Add stretch at the bottom to keep parameters at the top
            spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
            self.param_form_layout.addItem(spacer)
                
        except Exception as e:
            self._add_error_message(f"Error loading module parameters: {str(e)}")
            
    def _add_error_message(self, message: str):
        """Add an error message to the parameters area"""
        error_label = QLabel(message)
        error_label.setStyleSheet("color: #ff6666; font-style: italic; padding: 10px;")
        error_label.setWordWrap(True)
        self.param_form_layout.addWidget(error_label)
        
    def _add_info_message(self, message: str):
        """Add an info message to the parameters area"""
        info_label = QLabel(message)
        info_label.setStyleSheet("color: #cccccc; font-style: italic; padding: 10px;")
        info_label.setWordWrap(True)
        self.param_form_layout.addWidget(info_label)
        
    def _create_parameter_widget(self, param_name, param_config):
        """Create appropriate widget for parameter type with original styling"""
        try:

            
            if hasattr(param_config, 'type'):
                param_type = param_config.type
            else:
                param_type = ParameterType.TEXT
                
            # Create widget based on type using original styling

                    
            if param_type in [ParameterType.TEXTAREA, ParameterType.TEXT]:
                # Create container with textarea + template button
                container = QWidget()
                layout = QHBoxLayout()
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setSpacing(5)
                layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                
                widget = QTextEdit()
                placeholder_text = param_config.description if hasattr(param_config, 'description') else f"Enter {param_name}"
                widget.setPlaceholderText(placeholder_text)
                widget.setMaximumHeight(100)
                widget.setStyleSheet("""
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
                
                if hasattr(param_config, 'default') and param_config.default:
                    widget.setText(str(param_config.default))
                # Set current value
                if hasattr(self.current_node, 'parameters') and param_name in self.current_node.parameters:
                    widget.setText(str(self.current_node.parameters[param_name]))
                
                layout.addWidget(widget)
                
                # Store reference to the input widget before creating container
                actual_input_widget = widget
                
                # Add template variable button
                if self.workflow_context:
                    try:
                        from ui.workflows.template_variable_picker import TemplateInsertButton
                        template_button = TemplateInsertButton(
                            self.workflow_context.get('context'),
                            self.workflow_context.get('current_node'),
                            self.workflow_context.get('workflow_connections'),
                            self.workflow_context.get('canvas_variables', {})
                        )
                        # Connect to the actual input widget, not the container
                        template_button.variable_selected.connect(lambda var, w=actual_input_widget: self._insert_template_variable(w, var))
                        layout.addWidget(template_button)
                    except (ImportError, NameError):
                        pass  # Template button not available
                
                container.setLayout(layout)
                # Use container as widget, but store the actual input widget for value retrieval
                widget = container
                widget._input_widget = actual_input_widget  # Store reference for value retrieval
                    
            elif param_type == ParameterType.INTEGER:
                widget = QSpinBox()
                widget.setRange(-2147483648, 2147483647)
                widget.setStyleSheet("""
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
                if hasattr(param_config, 'validation') and param_config.validation:
                    if hasattr(param_config.validation, 'min_value') and param_config.validation.min_value is not None:
                        widget.setMinimum(int(param_config.validation.min_value))
                    if hasattr(param_config.validation, 'max_value') and param_config.validation.max_value is not None:
                        widget.setMaximum(int(param_config.validation.max_value))
                if hasattr(param_config, 'default') and param_config.default is not None:
                    widget.setValue(int(param_config.default))
                # Set current value
                if hasattr(self.current_node, 'parameters') and param_name in self.current_node.parameters:
                    widget.setValue(int(self.current_node.parameters[param_name]))
                    
            elif param_type == ParameterType.FLOAT:
                widget = QDoubleSpinBox()
                widget.setRange(-1e10, 1e10)
                widget.setDecimals(6)
                widget.setStyleSheet("""
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
                if hasattr(param_config, 'validation') and param_config.validation:
                    if hasattr(param_config.validation, 'min_value') and param_config.validation.min_value is not None:
                        widget.setMinimum(float(param_config.validation.min_value))
                    if hasattr(param_config.validation, 'max_value') and param_config.validation.max_value is not None:
                        widget.setMaximum(float(param_config.validation.max_value))
                if hasattr(param_config, 'default') and param_config.default is not None:
                    widget.setValue(float(param_config.default))
                # Set current value
                if hasattr(self.current_node, 'parameters') and param_name in self.current_node.parameters:
                    widget.setValue(float(self.current_node.parameters[param_name]))
                    
            elif param_type == ParameterType.BOOLEAN:
                widget = QCheckBox()
                widget.setStyleSheet("""
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
                if hasattr(param_config, 'default') and param_config.default is not None:
                    widget.setChecked(bool(param_config.default))
                # Set current value
                if hasattr(self.current_node, 'parameters') and param_name in self.current_node.parameters:
                    widget.setChecked(bool(self.current_node.parameters[param_name]))
                    
            elif param_type == ParameterType.CHOICE:
                widget = QComboBox()
                widget.setStyleSheet("""
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
                if hasattr(param_config, 'choices') and param_config.choices:
                    widget.addItems(param_config.choices)
                
                if hasattr(param_config, 'default') and param_config.default:
                    index = widget.findText(str(param_config.default))
                    if index >= 0:
                        widget.setCurrentIndex(index)
                # Set current value
                if hasattr(self.current_node, 'parameters') and param_name in self.current_node.parameters:
                    index = widget.findText(str(self.current_node.parameters[param_name]))
                    if index >= 0:
                        widget.setCurrentIndex(index)
                        
            elif param_type in [ParameterType.FILE, ParameterType.DIRECTORY]:
                # Create container with text field and browse button
                widget = QWidget()
                layout = QHBoxLayout()
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                
                text_widget = QLineEdit()
                text_widget.setPlaceholderText(param_config.description if hasattr(param_config, 'description') else f"Select {param_name}")
                if hasattr(param_config, 'default') and param_config.default:
                    text_widget.setText(str(param_config.default))
                # Set current value
                if hasattr(self.current_node, 'parameters') and param_name in self.current_node.parameters:
                    text_widget.setText(str(self.current_node.parameters[param_name]))
                
                browse_btn = QPushButton("Browse")
                browse_btn.setFixedWidth(60)
                browse_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #666666;
                        border: none;
                        color: white;
                        padding: 6px 12px;
                        border-radius: 3px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #777777;
                    }
                    QPushButton:pressed {
                        background-color: #555555;
                    }
                """)
                text_widget.setStyleSheet("""
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
                browse_btn.clicked.connect(lambda checked: self._browse_file_directory(text_widget, param_type, param_config))
                
                layout.addWidget(text_widget)
                layout.addWidget(browse_btn)
                widget.setLayout(layout)
                widget._text_widget = text_widget  # Store reference for value retrieval
            else:
                # Default to text widget
                widget = QLineEdit()
                widget.setPlaceholderText(param_config.description if hasattr(param_config, 'description') else f"Enter {param_name}")
                widget.setStyleSheet("""
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
                
            # Set tooltip (skip for text fields as they're already handled)
            if param_type not in [ParameterType.TEXT, ParameterType.TEXTAREA]:
                if hasattr(param_config, 'description') and param_config.description:
                    widget.setToolTip(param_config.description)
                
                # Create simple widget creator for value retrieval (non-text fields)
                widget_creator = self._create_simple_widget_creator(widget, param_type)
                self.parameter_widgets[param_name] = widget_creator
                
                # Connect change signals to enable save button
                self._connect_widget_change_signals(widget, param_type)
            
            # Create label with original styling
            label_text = param_config.display_name if hasattr(param_config, 'display_name') else param_name.replace('_', ' ').title()
            if hasattr(param_config, 'required') and param_config.required:
                label_text += " *"
                
            label = QLabel(label_text)
            if hasattr(param_config, 'required') and param_config.required:
                label.setStyleSheet("QLabel { color: white; font-weight: bold; }")
            else:
                label.setStyleSheet("QLabel { color: white; }")
                
            # Add to form layout
            self.param_form_layout.addRow(label, widget)
            
            # For text fields, create widget creator after adding to layout
            if param_type in [ParameterType.TEXT, ParameterType.TEXTAREA]:
                widget_creator = self._create_simple_widget_creator(widget, param_type)
                self.parameter_widgets[param_name] = widget_creator
                self._connect_widget_change_signals(widget, param_type)
            
            return widget
            
        except Exception as e:
            print(f"Error creating widget for parameter {param_name}: {e}")
            # Fallback to simple text widget
            widget = QLineEdit()
            widget.setStyleSheet("""
                QLineEdit {
                    background-color: #404040;
                    border: 1px solid #666666;
                    color: white;
                    padding: 8px;
                    border-radius: 4px;
                }
            """)
            
            # Add simple label and widget to form
            label = QLabel(param_name.replace('_', ' ').title())
            label.setStyleSheet("color: white; font-weight: bold;")
            self.param_form_layout.addRow(label, widget)
            
            # Store simple widget for fallback value retrieval
            self.parameter_widgets[param_name] = type('SimpleWidget', (), {
                'get_value': lambda self: widget.text(),
                'set_value': lambda self, value: widget.setText(str(value))
            })()
            
            return widget
            
    def _create_simple_widget_creator(self, widget, param_type):
        """Create a simple widget creator for value retrieval"""

        
        class WidgetCreator:
            def __init__(self, widget, param_type):
                self.widget = widget
                self.param_type = param_type
                
            def get_value(self):
                if self.param_type in [ParameterType.TEXT, ParameterType.TEXTAREA]:
                    # Both TEXT and TEXTAREA now use QTextEdit, so use toPlainText()
                    if hasattr(self.widget, '_input_widget'):
                        return self.widget._input_widget.toPlainText()
                    elif hasattr(self.widget, 'toPlainText'):
                        return self.widget.toPlainText()
                    elif hasattr(self.widget, 'text'):
                        return self.widget.text()  # Fallback for QLineEdit
                    return ""
                elif self.param_type == ParameterType.INTEGER:
                    return self.widget.value()
                elif self.param_type == ParameterType.FLOAT:
                    return self.widget.value()
                elif self.param_type == ParameterType.BOOLEAN:
                    return self.widget.isChecked()
                elif self.param_type == ParameterType.CHOICE:
                    return self.widget.currentText()
                elif self.param_type in [ParameterType.FILE, ParameterType.DIRECTORY]:
                    return self.widget._text_widget.text() if hasattr(self.widget, '_text_widget') else ""
                return ""
                
        return WidgetCreator(widget, param_type)
        
    def _browse_file_directory(self, text_widget, param_type, param_config):
        """Handle file/directory browsing for parameter inputs"""

        
        if param_type == ParameterType.FILE:
            file_filter = "All Files (*.*)"
            if hasattr(param_config, 'file_filters') and param_config.file_filters:
                filter_str = " ".join([f"*{ext}" for ext in param_config.file_filters])
                file_filter = f"Supported Files ({filter_str});;All Files (*.*)"
            
            display_name = param_config.display_name if hasattr(param_config, 'display_name') else "file"
            file_path, _ = QFileDialog.getOpenFileName(
                self, f"Select {display_name}", "", file_filter
            )
            if file_path:
                text_widget.setText(file_path)
        else:  # DIRECTORY
            display_name = param_config.display_name if hasattr(param_config, 'display_name') else "directory"
            dir_path = QFileDialog.getExistingDirectory(
                self, f"Select {display_name}"
            )
            if dir_path:
                text_widget.setText(dir_path)
                
    def _connect_widget_change_signals(self, widget, param_type):
        """Connect widget change signals to enable save button"""

        
        def on_parameter_changed():
            if hasattr(self, 'save_button'):
                self.save_button.setEnabled(True)
                self.status_label.setText("Parameters modified")
                
        try:
            if param_type in [ParameterType.TEXT, ParameterType.TEXTAREA]:
                # Both TEXT and TEXTAREA now use QTextEdit with container
                if hasattr(widget, '_input_widget') and hasattr(widget._input_widget, 'textChanged'):
                    widget._input_widget.textChanged.connect(on_parameter_changed)
                elif hasattr(widget, 'textChanged'):
                    widget.textChanged.connect(on_parameter_changed)
                elif hasattr(widget, 'text'):  # Fallback for QLineEdit-like widgets
                    # Try to find any text change signal
                    for signal_name in ['textChanged', 'textEdited']:
                        if hasattr(widget, signal_name):
                            getattr(widget, signal_name).connect(on_parameter_changed)
                            break
            elif param_type in [ParameterType.INTEGER, ParameterType.FLOAT]:
                if hasattr(widget, 'valueChanged'):
                    widget.valueChanged.connect(on_parameter_changed)
            elif param_type == ParameterType.BOOLEAN:
                if hasattr(widget, 'toggled'):
                    widget.toggled.connect(on_parameter_changed)
            elif param_type == ParameterType.CHOICE:
                if hasattr(widget, 'currentTextChanged'):
                    widget.currentTextChanged.connect(on_parameter_changed)
            elif param_type in [ParameterType.FILE, ParameterType.DIRECTORY]:
                if hasattr(widget, '_text_widget') and hasattr(widget._text_widget, 'textChanged'):
                    widget._text_widget.textChanged.connect(on_parameter_changed)
        except Exception as e:
            print(f"Error connecting change signals: {e}")
    
    def _insert_template_variable(self, widget, template_var: str):
        """Insert a template variable into the widget at cursor position"""
        try:

            
            if isinstance(widget, QTextEdit):
                cursor = widget.textCursor()
                cursor.insertText(template_var)
                widget.setTextCursor(cursor)  # Update the cursor position
            elif isinstance(widget, QLineEdit):
                cursor_pos = widget.cursorPosition()
                current_text = widget.text()
                new_text = current_text[:cursor_pos] + template_var + current_text[cursor_pos:]
                widget.setText(new_text)
                widget.setCursorPosition(cursor_pos + len(template_var))
            elif hasattr(widget, 'setText') and hasattr(widget, 'text'):
                current_text = widget.text()
                widget.setText(current_text + template_var)
        except Exception as e:
            print(f"Error inserting template variable: {e}")