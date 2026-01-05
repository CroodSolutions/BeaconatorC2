"""
Command Widget - Schema-driven module interface
Generates UI dynamically based on beacon module schemas
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
                            QTextEdit, QLabel, QComboBox, QTreeWidget, QTreeWidgetItem,
                            QStackedWidget, QSplitter, QSpinBox, QDoubleSpinBox, QCheckBox,
                            QGridLayout, QMessageBox, QFileDialog, QGroupBox, QTabWidget,
                            QScrollArea, QFrame, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, Qt, QPoint
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QStyle
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import base64

from database import BeaconRepository
from services import SchemaService, BeaconSchema, Module, Category, ParameterType
from utils import FontManager
import utils
from ..widgets import OutputDisplay
from .documentation_panel import DocumentationPanel

class ParameterWidget:
    """Base class for parameter input widgets"""
    def __init__(self, parameter, parent=None):
        self.parameter = parameter
        self.parent = parent
        self.widget = None
        self.label = None
        self.setup_widget()
    
    def setup_widget(self):
        """Create the input widget based on parameter type"""
        if self.parameter.type == ParameterType.TEXT:
            self.widget = QLineEdit()
            self.widget.setPlaceholderText(self.parameter.description)
            if self.parameter.default:
                self.widget.setText(str(self.parameter.default))
                
        elif self.parameter.type == ParameterType.TEXTAREA:
            self.widget = QTextEdit()
            self.widget.setPlaceholderText(self.parameter.description)
            self.widget.setMaximumHeight(150)
            if self.parameter.default:
                self.widget.setText(str(self.parameter.default))
                
        elif self.parameter.type == ParameterType.INTEGER:
            self.widget = QSpinBox()
            if self.parameter.validation:
                if self.parameter.validation.min_value is not None:
                    self.widget.setMinimum(int(self.parameter.validation.min_value))
                if self.parameter.validation.max_value is not None:
                    self.widget.setMaximum(int(self.parameter.validation.max_value))
            if self.parameter.default is not None and str(self.parameter.default).strip():
                try:
                    self.widget.setValue(int(self.parameter.default))
                except (ValueError, TypeError):
                    # Handle invalid default values gracefully
                    if self.parameter.validation and self.parameter.validation.min_value is not None:
                        self.widget.setValue(int(self.parameter.validation.min_value))
                    else:
                        self.widget.setValue(0)
                
        elif self.parameter.type == ParameterType.FLOAT:
            self.widget = QDoubleSpinBox()
            if self.parameter.validation:
                if self.parameter.validation.min_value is not None:
                    self.widget.setMinimum(float(self.parameter.validation.min_value))
                if self.parameter.validation.max_value is not None:
                    self.widget.setMaximum(float(self.parameter.validation.max_value))
            if self.parameter.default is not None and str(self.parameter.default).strip():
                try:
                    self.widget.setValue(float(self.parameter.default))
                except (ValueError, TypeError):
                    # Handle invalid default values gracefully
                    if self.parameter.validation and self.parameter.validation.min_value is not None:
                        self.widget.setValue(float(self.parameter.validation.min_value))
                    else:
                        self.widget.setValue(0.0)
                
        elif self.parameter.type == ParameterType.BOOLEAN:
            self.widget = QCheckBox()
            if self.parameter.default is not None:
                self.widget.setChecked(bool(self.parameter.default))
                
        elif self.parameter.type == ParameterType.CHOICE:
            self.widget = QComboBox()
            if self.parameter.choices:
                self.widget.addItems(self.parameter.choices)
            if self.parameter.default:
                index = self.widget.findText(str(self.parameter.default))
                if index >= 0:
                    self.widget.setCurrentIndex(index)
                    
        elif self.parameter.type in [ParameterType.FILE, ParameterType.DIRECTORY]:
            # Create a horizontal layout with text field and browse button
            container = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            
            self.text_widget = QLineEdit()
            self.text_widget.setPlaceholderText(self.parameter.description)
            if self.parameter.default:
                self.text_widget.setText(str(self.parameter.default))
            
            browse_btn = QPushButton("Browse")
            browse_btn.clicked.connect(self._browse_file_or_directory)
            
            layout.addWidget(self.text_widget)
            layout.addWidget(browse_btn)
            container.setLayout(layout)
            self.widget = container
        
        # Set tooltip
        if hasattr(self.widget, 'setToolTip'):
            self.widget.setToolTip(self.parameter.description)
        
        # Create label
        self.label = QLabel(self.parameter.display_name)
        if self.parameter.required:
            self.label.setStyleSheet("QLabel { font-weight: bold; }")
    
    def _browse_file_or_directory(self):
        """Handle file/directory browsing"""
        if self.parameter.type == ParameterType.FILE:
            file_filter = "All Files (*.*)"
            if self.parameter.file_filters:
                filter_str = " ".join([f"*{ext}" for ext in self.parameter.file_filters])
                file_filter = f"Supported Files ({filter_str});;All Files (*.*)"
            
            file_path, _ = QFileDialog.getOpenFileName(
                self.parent, f"Select {self.parameter.display_name}", "", file_filter
            )
            if file_path:
                self.text_widget.setText(file_path)
        else:  # DIRECTORY
            dir_path = QFileDialog.getExistingDirectory(
                self.parent, f"Select {self.parameter.display_name}"
            )
            if dir_path:
                self.text_widget.setText(dir_path)
    
    def get_value(self) -> Any:
        """Get the current value from the widget"""
        if self.parameter.type == ParameterType.TEXT:
            return self.widget.text()
        elif self.parameter.type == ParameterType.TEXTAREA:
            return self.widget.toPlainText()
        elif self.parameter.type == ParameterType.INTEGER:
            return self.widget.value()
        elif self.parameter.type == ParameterType.FLOAT:
            return self.widget.value()
        elif self.parameter.type == ParameterType.BOOLEAN:
            return self.widget.isChecked()
        elif self.parameter.type == ParameterType.CHOICE:
            return self.widget.currentText()
        elif self.parameter.type in [ParameterType.FILE, ParameterType.DIRECTORY]:
            return self.text_widget.text()
        return None
    
    def validate(self) -> Tuple[bool, str]:
        """Validate the current value"""
        value = self.get_value()
        
        # Check required fields
        if self.parameter.required and not value:
            return False, f"{self.parameter.display_name} is required"
        
        # Run parameter validation if present
        if self.parameter.validation and value:
            return self.parameter.validation.validate(value, self.parameter.type)
        
        return True, ""

class ModuleInterface(QWidget):
    """Interface for a single module"""
    def __init__(self, module: Module, beacon_repository: BeaconRepository, module_yaml_data: dict = None, parent=None, category_name: str = None, module_name: str = None):
        super().__init__(parent)
        self.module = module
        self.beacon_repository = beacon_repository
        self.module_yaml_data = module_yaml_data or {}
        self.parameter_widgets: Dict[str, ParameterWidget] = {}
        self.current_beacon_id = None
        self.parent_widget = parent  # Store reference to parent CommandWidget
        self.category_name = category_name  # Store category name for documentation
        self.module_name = module_name      # Store module name for documentation
        self.setup_ui()
    
    def set_agent(self, beacon_id: str):
        """Set the current agent ID for command execution"""
        self.current_beacon_id = beacon_id
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Module description
        if self.module.description:
            desc_label = QLabel(self.module.description)
            desc_label.setWordWrap(True)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #000000;
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030);
                    padding: 8px;
                    border-radius: 4px;
                }
            """)
            layout.addWidget(desc_label)
        
        # Parameters section
        if self.module.parameters:
            if self.module.ui.layout == "tabbed":
                self.setup_tabbed_parameters(layout)
            elif self.module.ui.layout == "advanced":
                self.setup_grouped_parameters(layout)
            else:
                self.setup_simple_parameters(layout)
        
        # Execution button
        execute_btn = QPushButton("Execute")
        execute_btn.setIcon(QIcon("resources/bolt.svg"))
        execute_btn.clicked.connect(self.execute_module)
        layout.addWidget(execute_btn)
        
        # Documentation button (if available)
        if self.module.documentation.content or self.module.parameters:
            docs_btn = QPushButton("Show Documentation")
            docs_btn.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
            docs_btn.clicked.connect(self.show_documentation)
            layout.addWidget(docs_btn)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def setup_simple_parameters(self, layout):
        """Setup parameters in a simple grid layout"""
        if not self.module.parameters:
            return
            
        param_widget = QWidget()
        param_layout = QGridLayout()
        
        row = 0
        for param_name, parameter in self.module.parameters.items():
            param_widget_obj = ParameterWidget(parameter, self)
            self.parameter_widgets[param_name] = param_widget_obj
            
            param_layout.addWidget(param_widget_obj.label, row, 0)
            param_layout.addWidget(param_widget_obj.widget, row, 1)
            row += 1
        
        param_widget.setLayout(param_layout)
        layout.addWidget(param_widget)
    
    def setup_grouped_parameters(self, layout):
        """Setup parameters with grouping"""
        if not self.module.parameters:
            return
            
        if self.module.ui.grouping:
            # Use defined grouping
            for group in self.module.ui.grouping:
                group_box = QGroupBox()
                group_layout = QGridLayout()
                
                row = 0
                for param_name in group:
                    if param_name in self.module.parameters:
                        parameter = self.module.parameters[param_name]
                        param_widget_obj = ParameterWidget(parameter, self)
                        self.parameter_widgets[param_name] = param_widget_obj
                        
                        group_layout.addWidget(param_widget_obj.label, row, 0)
                        group_layout.addWidget(param_widget_obj.widget, row, 1)
                        row += 1
                
                group_box.setLayout(group_layout)
                layout.addWidget(group_box)
        else:
            # Fallback to simple layout
            self.setup_simple_parameters(layout)
    
    def setup_tabbed_parameters(self, layout):
        """Setup parameters in tabs"""
        if not self.module.parameters:
            return
            
        tabs = QTabWidget()
        
        if self.module.ui.grouping:
            # Create tabs based on grouping
            for i, group in enumerate(self.module.ui.grouping):
                tab_widget = QWidget()
                tab_layout = QGridLayout()
                
                row = 0
                for param_name in group:
                    if param_name in self.module.parameters:
                        parameter = self.module.parameters[param_name]
                        param_widget_obj = ParameterWidget(parameter, self)
                        self.parameter_widgets[param_name] = param_widget_obj
                        
                        tab_layout.addWidget(param_widget_obj.label, row, 0)
                        tab_layout.addWidget(param_widget_obj.widget, row, 1)
                        row += 1
                
                tab_widget.setLayout(tab_layout)
                tabs.addTab(tab_widget, f"Group {i+1}")
        else:
            # Single tab with all parameters
            tab_widget = QWidget()
            tab_layout = QGridLayout()
            
            row = 0
            for param_name, parameter in self.module.parameters.items():
                param_widget_obj = ParameterWidget(parameter, self)
                self.parameter_widgets[param_name] = param_widget_obj
                
                tab_layout.addWidget(param_widget_obj.label, row, 0)
                tab_layout.addWidget(param_widget_obj.widget, row, 1)
                row += 1
            
            tab_widget.setLayout(tab_layout)
            tabs.addTab(tab_widget, "Parameters")
        
        layout.addWidget(tabs)
    
    def execute_module(self):
        """Execute the module with current parameter values"""
        # Check if an agent is selected
        if not self.current_beacon_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        # Validate all parameters
        parameter_values = {}
        for param_name, param_widget in self.parameter_widgets.items():
            valid, error = param_widget.validate()
            if not valid:
                QMessageBox.warning(self, "Validation Error", error)
                return
            parameter_values[param_name] = param_widget.get_value()

        try:
            # Process file parameters with encoding (e.g., base64)
            is_module_command = False
            for param_name, param_def in self.module.parameters.items():
                if param_def.type == ParameterType.FILE and param_def.encoding == "base64":
                    file_path = parameter_values.get(param_name, "")
                    if file_path:
                        # Read file and base64 encode it
                        encoded_data = self._encode_file_base64(file_path)
                        if encoded_data is None:
                            QMessageBox.warning(self, "Error", f"Failed to read file: {file_path}")
                            return
                        parameter_values[param_name] = encoded_data
                        is_module_command = True  # File-based modules use execute_module

            # Format command using module template
            command = self.module.format_command(parameter_values)

            # Prefix with execute_module| if this is a module command (not a simple shell command)
            # Module commands include file-encoded parameters or specific module types
            if is_module_command:
                command = f"execute_module|{command}"

            # Send command to agent via repository
            self.beacon_repository.update_beacon_command(self.current_beacon_id, command)

            # Show success message with a tooltip-style notification
            self.show_success_notification(f"Module '{self.module.display_name}' queued for agent {self.current_beacon_id}")

        except Exception as e:
            # Log the error
            if utils.logger:
                utils.logger.log_message(f"Failed to send command to {self.current_beacon_id}: {e}")
            QMessageBox.warning(self, "Error", f"Failed to execute module: {str(e)}")

    def _encode_file_base64(self, file_path: str) -> Optional[str]:
        """Read a file and return its contents as base64-encoded string"""
        try:
            path = Path(file_path)
            if not path.exists():
                if utils.logger:
                    utils.logger.log_message(f"File not found: {file_path}")
                return None

            with open(path, 'rb') as f:
                file_data = f.read()

            encoded = base64.b64encode(file_data).decode('ascii')

            if utils.logger:
                utils.logger.log_message(f"Encoded file {path.name}: {len(file_data)} bytes -> {len(encoded)} chars base64")

            return encoded

        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Failed to encode file {file_path}: {e}")
            return None
    
    def show_success_notification(self, message: str):
        """Show a brief success notification"""
        # Create a temporary message box that auto-closes
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Success")
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    
    def show_documentation(self):
        """Show module documentation in the documentation panel or toggle it closed if already showing this module"""
        if hasattr(self.parent_widget, 'doc_panel') and self.parent_widget.doc_panel:
            doc_panel = self.parent_widget.doc_panel
            
            # Check if the panel is currently showing this exact module
            if doc_panel.is_showing_module(self.module):
                # Same module is displayed, toggle panel closed
                doc_panel.toggle_panel()
            else:
                # Different module or panel is closed, show documentation
                # Pass category and module names for Save & Apply functionality
                doc_panel.set_module_documentation(self.module, self.module_yaml_data, self.category_name, self.module_name)
                doc_panel.show_panel()
                # Track that documentation panel is now visible
                self.parent_widget.documentation_visible = True

class CommandWidget(QWidget):
    """Dynamic command widget that generates UI from schemas"""
    
    def __init__(self, beacon_repository: BeaconRepository, doc_panel: DocumentationPanel = None):
        super().__init__()
        self.beacon_repository = beacon_repository
        self.doc_panel = doc_panel
        self.current_beacon_id = None
        self.schema_service = SchemaService()
        self.current_schema: Optional[BeaconSchema] = None
        self.documentation_visible = False  # Track if documentation panel is currently shown
        
        # Schema caching to avoid duplicate database queries
        self._schema_cache: Dict[str, Optional[str]] = {}  # beacon_id -> schema_file
        
        # UI caching to avoid rebuilding navigation tree
        self._loaded_schema_file: Optional[str] = None  # Currently loaded schema
        self._ui_built_for_schema: Optional[str] = None  # Schema file for which UI is built
        
        FontManager().add_relative_font_widget(self, 0)
        self.setup_ui()
        
        # Load default schema for testing (defer until after UI setup)
        # self.load_schema("default_windows_agent.yaml")
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create horizontal splitter for nav tree and module content
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.setChildrenCollapsible(False)
        
        # Left side - Category/Module tree
        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setMinimumWidth(200)
        self.nav_tree.setMaximumWidth(300)
        self.nav_tree.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.nav_tree.currentItemChanged.connect(self.on_nav_changed)
        content_splitter.addWidget(self.nav_tree)
        
        # Right side - Module interface stack
        self.module_stack = QStackedWidget()
        self.module_stack.setMinimumWidth(300)
        self.module_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_splitter.addWidget(self.module_stack)
        
        # Set initial sizes for content splitter (nav:module ratio)
        content_splitter.setSizes([250, 350])
        content_splitter.setStretchFactor(0, 0)  # Nav tree doesn't stretch much
        content_splitter.setStretchFactor(1, 1)  # Module area gets most stretch
        
        # Output display
        self.output_display = OutputDisplay(self.beacon_repository)
        self.output_display.setMinimumHeight(250)
        
        # Create vertical splitter for content and output
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.addWidget(content_splitter)
        main_splitter.addWidget(self.output_display)
        main_splitter.setSizes([400, 200])
        main_splitter.setStretchFactor(0, 2)  # Content area gets more space
        main_splitter.setStretchFactor(1, 1)  # Output area gets less space
        
        main_layout.addWidget(main_splitter)
        self.setLayout(main_layout)
        
        # Initialize with empty state
        self.show_no_beacon_message()
    
    def show_no_beacon_message(self):
        """Show message when no beacon is selected"""
        self.nav_tree.clear()
        
        # Clear the stack widget
        while self.module_stack.count():
            widget = self.module_stack.widget(0)
            self.module_stack.removeWidget(widget)
            widget.deleteLater()
        
        # Add a message widget
        message_widget = QWidget()
        message_layout = QVBoxLayout()
        
        message_label = QLabel("Select a beacon")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 16px;
                font-style: italic;
            }
        """)
        
        message_layout.addWidget(message_label)
        message_widget.setLayout(message_layout)
        self.module_stack.addWidget(message_widget)
    

    def load_schema(self, schema_file: str):
        """Load and apply a schema"""
        try:
            self.current_schema = self.schema_service.load_schema(schema_file)
            # Set schema_file attribute for caching
            if self.current_schema:
                self.current_schema.schema_file = schema_file
            
            self.build_navigation_tree()

        except Exception as e:
            QMessageBox.warning(self, "Schema Error", f"Failed to load schema {schema_file}: {e}")
    
    def build_navigation_tree(self):
        """Build the navigation tree from the current schema with caching"""
        # Check if UI is already built for this schema
        schema_id = self._loaded_schema_file  # Use the loaded schema file instead

        # Only cache hit if we have a real schema (not None) and it matches
        if schema_id and schema_id == self._ui_built_for_schema and hasattr(self, 'module_interfaces'):
            # UI already built for this actual schema, just update agent references
            if self.current_beacon_id and hasattr(self, 'module_interfaces'):
                for interface in self.module_interfaces.values():
                    interface.set_agent(self.current_beacon_id)
            return
        
        self.nav_tree.clear()
        
        # Clear the stack widget by removing all widgets
        while self.module_stack.count():
            widget = self.module_stack.widget(0)
            self.module_stack.removeWidget(widget)
            widget.deleteLater()
        
        # Mark that UI is built for this schema
        self._ui_built_for_schema = schema_id
        
        if not self.current_schema:
            # No schema - clear cache and return early (don't cache None state)
            self.module_interfaces = {}
            self.module_metadata = {} 
            self._ui_built_for_schema = None  # Don't cache no-schema state
            return
        
        # Build tree structure quickly without creating heavy module interfaces
        for cat_name, category in self.current_schema.categories.items():
            cat_item = QTreeWidgetItem([category.display_name])
            cat_item.setData(0, Qt.ItemDataRole.UserRole, ("category", cat_name))
            
            for mod_name, module in category.modules.items():
                mod_item = QTreeWidgetItem([module.display_name])
                mod_item.setData(0, Qt.ItemDataRole.UserRole, ("module", cat_name, mod_name))
                cat_item.addChild(mod_item)
            
            self.nav_tree.addTopLevelItem(cat_item)
        
        # Initialize empty interfaces dict - interfaces will be created on-demand
        if not hasattr(self, 'module_interfaces'):
            self.module_interfaces = {}
        else:
            self.module_interfaces.clear()
        
        if not hasattr(self, 'module_metadata'):
            self.module_metadata = {}
        else:
            self.module_metadata.clear()
        
        # Store module metadata for lazy interface creation
        # We have current_schema at this point, so we can always store metadata
        for cat_name, category in self.current_schema.categories.items():
            for mod_name, module in category.modules.items():
                # Get YAML data efficiently using the improved method
                module_yaml_data = self.get_module_yaml_data(cat_name, mod_name)
                self.module_metadata[(cat_name, mod_name)] = (module, module_yaml_data)

        self.nav_tree.update()
        self.nav_tree.repaint()
    
    def get_module_yaml_data(self, category_name: str, module_name: str) -> dict:
        """Extract the YAML data for a specific module using efficient caching"""
        try:
            # Get the schema file path - check current_schema first (available during build), then loaded file
            schema_file = None
            if self.current_schema and hasattr(self.current_schema, 'schema_file'):
                schema_file = self.current_schema.schema_file
            elif self._loaded_schema_file:
                schema_file = self._loaded_schema_file
            
            if not schema_file:
                print(f"Debug: No schema file available for {category_name}/{module_name}")
                return {}
            
            # Use the schema service's cached method
            yaml_data = self.schema_service.get_module_yaml_data(schema_file, category_name, module_name)
            
            return yaml_data
            
        except Exception as e:
            print(f"Error loading module YAML data for {category_name}/{module_name}: {e}")
        
        return {}
    
    def update_documentation_visibility(self):
        """Update the documentation visibility state based on panel state"""
        if self.doc_panel:
            self.documentation_visible = self.doc_panel.is_visible()

    
    def on_nav_changed(self, current, previous):
        """Handle navigation tree selection changes with lazy loading"""
        if not current:
            return
        
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        if data[0] == "module":
            _, cat_name, mod_name = data
            
            # Check if interface already exists
            interface = self.module_interfaces.get((cat_name, mod_name))
            if not interface:
                # Create interface on-demand (lazy loading)
                if (cat_name, mod_name) in self.module_metadata:
                    module, module_yaml_data = self.module_metadata[(cat_name, mod_name)]
                    interface = ModuleInterface(module, self.beacon_repository, module_yaml_data, self, cat_name, mod_name)
                    
                    # Set current agent if one is already selected
                    if self.current_beacon_id:
                        interface.set_agent(self.current_beacon_id)
                    
                    self.module_stack.addWidget(interface)
                    self.module_interfaces[(cat_name, mod_name)] = interface
            
            if interface:
                index = self.module_stack.indexOf(interface)
                if index >= 0:
                    self.module_stack.setCurrentIndex(index)
                    
                    # If documentation panel is currently visible, update it with the new module
                    if self.documentation_visible and self.doc_panel:
                        if (cat_name, mod_name) in self.module_metadata:
                            _, module_yaml_data = self.module_metadata[(cat_name, mod_name)]
                            self.doc_panel.set_module_documentation(interface.module, module_yaml_data, cat_name, mod_name)
    
    def set_agent(self, beacon_id: str, force_reload: bool = False):
        """Set the current beacon ID and load associated schema with caching"""
        # Early exit if same agent (unless force_reload is True)
        if beacon_id == self.current_beacon_id and not force_reload:
            return
            
        self.current_beacon_id = beacon_id
        
        # Update output display
        if self.output_display:
            self.output_display.set_agent(beacon_id)
        
        if beacon_id:
            # Check cache first to avoid database query
            schema_file = self._schema_cache.get(beacon_id)
            if schema_file is None:  # Not in cache
                schema_file = self.beacon_repository.get_beacon_schema(beacon_id)
                self._schema_cache[beacon_id] = schema_file
            
            if schema_file:
                # Only load schema if different from currently loaded one (unless force_reload is True)
                if schema_file != self._loaded_schema_file or force_reload:
                    try:
                        self.load_schema(schema_file)
                        self._loaded_schema_file = schema_file
                    except Exception as e:
                        self.show_schema_error(f"Failed to load beacon schema: {schema_file}")
                else:
                    # Same schema already loaded, just update agent references
                    if hasattr(self, 'module_interfaces'):
                        for interface in self.module_interfaces.values():
                            interface.set_agent(beacon_id)
            else:
                # No schema associated with this beacon - always clear and show message
                self._loaded_schema_file = None
                self._ui_built_for_schema = None
                self.current_schema = None
                self.show_no_schema_message(beacon_id)
    
    def set_beacon(self, beacon_id: str, force_reload: bool = False):
        """Set the current beacon ID - delegates to set_agent for compatibility"""
        self.set_agent(beacon_id, force_reload)

    def on_schema_applied(self, beacon_id: str, schema_file: str):
        """Handle schema being applied to a beacon"""
        # Only update if this is for the currently selected beacon
        if beacon_id == self.current_beacon_id:
            if schema_file:
                # Load the new schema
                try:
                    self.load_schema(schema_file)
                except Exception as e:
                    self.show_schema_error(f"Failed to load applied schema: {schema_file}")
            else:
                # Schema was removed
                self.show_no_schema_message(beacon_id)

    
    def show_no_schema_message(self, beacon_id: str):
        """Show message when beacon has no associated schema"""
        self.nav_tree.clear()
        
        # Clear the stack widget
        while self.module_stack.count():
            widget = self.module_stack.widget(0)
            self.module_stack.removeWidget(widget)
            widget.deleteLater()
        
        # Clear interfaces and metadata
        if hasattr(self, 'module_interfaces'):
            self.module_interfaces.clear()
        if hasattr(self, 'module_metadata'):
            self.module_metadata.clear()
        
        # Add a message widget
        message_widget = QWidget()
        message_layout = QVBoxLayout()
        
        message_label = QLabel(f"Beacon {beacon_id} has no associated schema.\nConfigure schema in Beacon Settings.")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("""
            QLabel {
                color: #FFB86C;
                font-size: 14px;
                padding: 8px;
            }
        """)
        
        message_layout.addWidget(message_label)
        message_widget.setLayout(message_layout)
        self.module_stack.addWidget(message_widget)
    
    def show_schema_error(self, error_message: str):
        """Show error message when schema loading fails"""
        self.nav_tree.clear()
        
        # Clear the stack widget
        while self.module_stack.count():
            widget = self.module_stack.widget(0)
            self.module_stack.removeWidget(widget)
            widget.deleteLater()
        
        # Add an error message widget
        message_widget = QWidget()
        message_layout = QVBoxLayout()
        
        message_label = QLabel(f"Schema Error:\n{error_message}")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("""
            QLabel {
                color: #FF5555;
                font-size: 14px;
                margin: 50px;
            }
        """)
        
        message_layout.addWidget(message_label)
        message_widget.setLayout(message_layout)
        self.module_stack.addWidget(message_widget)