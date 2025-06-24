"""
Dynamic Command Widget - Schema-driven module interface
Generates UI dynamically based on agent module schemas
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

from database import AgentRepository
from services import SchemaService, AgentSchema, Module, Category, ParameterType
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
            if self.parameter.default is not None:
                self.widget.setValue(int(self.parameter.default))
                
        elif self.parameter.type == ParameterType.FLOAT:
            self.widget = QDoubleSpinBox()
            if self.parameter.validation:
                if self.parameter.validation.min_value is not None:
                    self.widget.setMinimum(float(self.parameter.validation.min_value))
                if self.parameter.validation.max_value is not None:
                    self.widget.setMaximum(float(self.parameter.validation.max_value))
            if self.parameter.default is not None:
                self.widget.setValue(float(self.parameter.default))
                
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
    def __init__(self, module: Module, agent_repository: AgentRepository, parent=None):
        super().__init__(parent)
        self.module = module
        self.agent_repository = agent_repository
        self.parameter_widgets: Dict[str, ParameterWidget] = {}
        self.current_agent_id = None
        self.setup_ui()
    
    def set_agent(self, agent_id: str):
        """Set the current agent ID for command execution"""
        self.current_agent_id = agent_id
    
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
        execute_btn.clicked.connect(self.execute_module)
        layout.addWidget(execute_btn)
        
        # Documentation button (if available)
        if self.module.documentation.content:
            docs_btn = QPushButton("Show Documentation")
            docs_btn.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
            # TODO: Connect to documentation panel
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
        if not self.current_agent_id:
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
            # Format command using module template
            command = self.module.format_command(parameter_values)
            
            # Send command to agent via repository
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            
            # Log the command execution
            if utils.logger:
                utils.logger.log_message(f"Command sent to {self.current_agent_id}: {command}")
            
            # Show success message with a tooltip-style notification
            self.show_success_notification(f"Module '{self.module.display_name}' queued for agent {self.current_agent_id}")
            
        except Exception as e:
            # Log the error
            if utils.logger:
                utils.logger.log_message(f"Failed to send command to {self.current_agent_id}: {e}")
            QMessageBox.warning(self, "Error", f"Failed to execute module: {str(e)}")
    
    def show_success_notification(self, message: str):
        """Show a brief success notification"""
        # Create a temporary message box that auto-closes
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Success")
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

class CommandWidget(QWidget):
    """Dynamic command widget that generates UI from schemas"""
    
    def __init__(self, agent_repository: AgentRepository, doc_panel: DocumentationPanel = None):
        super().__init__()
        self.agent_repository = agent_repository
        self.doc_panel = doc_panel
        self.current_agent_id = None
        self.schema_service = SchemaService()
        self.current_schema: Optional[AgentSchema] = None
        
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
        self.output_display = OutputDisplay(self.agent_repository)
        self.output_display.setMinimumHeight(150)
        
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
            self.build_navigation_tree()

        except Exception as e:
            QMessageBox.warning(self, "Schema Error", f"Failed to load schema {schema_file}: {e}")
    
    def build_navigation_tree(self):
        """Build the navigation tree from the current schema"""
        self.nav_tree.clear()
        
        # Clear the stack widget by removing all widgets
        while self.module_stack.count():
            widget = self.module_stack.widget(0)
            self.module_stack.removeWidget(widget)
            widget.deleteLater()
            
        self.module_interfaces = {}
        
        if not self.current_schema:
            return
        
        for cat_name, category in self.current_schema.categories.items():
            cat_item = QTreeWidgetItem([category.display_name])
            cat_item.setData(0, Qt.ItemDataRole.UserRole, ("category", cat_name))
            
            for mod_name, module in category.modules.items():
                mod_item = QTreeWidgetItem([module.display_name])
                mod_item.setData(0, Qt.ItemDataRole.UserRole, ("module", cat_name, mod_name))
                cat_item.addChild(mod_item)
                
                # Create module interface
                module_interface = ModuleInterface(module, self.agent_repository, self)
                
                # Set current agent if one is already selected
                if self.current_agent_id:
                    module_interface.set_agent(self.current_agent_id)
                
                self.module_stack.addWidget(module_interface)
                self.module_interfaces[(cat_name, mod_name)] = module_interface
            
            self.nav_tree.addTopLevelItem(cat_item)
        
        # Force a repaint and expansion of the tree

        self.nav_tree.update()
        self.nav_tree.repaint()

    
    def on_nav_changed(self, current, previous):
        """Handle navigation tree selection changes"""
        if not current:
            return
        
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        if data[0] == "module":
            _, cat_name, mod_name = data
            interface = self.module_interfaces.get((cat_name, mod_name))
            if interface:
                index = self.module_stack.indexOf(interface)
                if index >= 0:
                    self.module_stack.setCurrentIndex(index)
    
    def set_agent(self, agent_id: str):
        """Set the current beacon ID and load associated schema"""
        self.current_agent_id = agent_id
        
        # Update output display
        if self.output_display:
            self.output_display.set_agent(agent_id)
        
        if agent_id:
            
            # Get beacon's associated schema
            schema_file = self.agent_repository.get_beacon_schema(agent_id)
            
            if schema_file:
                # Load the beacon's schema
                try:
                    self.load_schema(schema_file)
                except Exception as e:
                    self.show_schema_error(f"Failed to load beacon schema: {schema_file}")
            else:
                # No schema associated with this beacon
                self.show_no_schema_message(agent_id)

    def on_schema_applied(self, agent_id: str, schema_file: str):
        """Handle schema being applied to a beacon"""
        # Only update if this is for the currently selected beacon
        if agent_id == self.current_agent_id:
            if schema_file:
                # Load the new schema
                try:
                    self.load_schema(schema_file)
                except Exception as e:
                    self.show_schema_error(f"Failed to load applied schema: {schema_file}")
            else:
                # Schema was removed
                self.show_no_schema_message(agent_id)

    
    def show_no_schema_message(self, beacon_id: str):
        """Show message when beacon has no associated schema"""
        self.nav_tree.clear()
        
        # Clear the stack widget
        while self.module_stack.count():
            widget = self.module_stack.widget(0)
            self.module_stack.removeWidget(widget)
            widget.deleteLater()
        
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