"""
Template Variable Picker Component

Provides UI components for selecting and inserting template variables 
into parameter fields in workflow node configuration dialogs.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QListWidget, QListWidgetItem, 
                            QTextEdit, QDialog, QDialogButtonBox, QSplitter,
                            QGroupBox, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor

from services.workflows.parameter_template_engine import ParameterTemplateEngine, TemplateVariable


class TemplateVariableItem(QListWidgetItem):
    """Custom list item for template variables"""
    
    def __init__(self, template_variable: TemplateVariable):
        super().__init__()
        self.template_variable = template_variable
        self.setText(f"{template_variable.name}")
        self.setToolTip(f"{template_variable.description}\nValue: {template_variable.value}")
        
        # Set icon based on variable type
        icon = self._create_type_icon(template_variable.type)
        self.setIcon(icon)
        
    def _create_type_icon(self, var_type: str) -> QIcon:
        """Create a colored icon based on variable type"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Color based on variable type
        colors = {
            'previous_output': '#4CAF50',  # Green
            'node_output': '#2196F3',     # Blue  
            'variable': '#FF9800'       # Orange
        }
        
        color = QColor(colors.get(var_type, '#757575'))
        painter.setBrush(color)
        painter.setPen(QColor(255, 255, 255, 100))
        painter.drawEllipse(2, 2, 12, 12)
        
        painter.end()
        return QIcon(pixmap)


class TemplateVariablePicker(QWidget):
    """Compact template variable picker for parameter widgets"""
    
    variable_selected = pyqtSignal(str)  # Emits the template variable string
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.template_engine = ParameterTemplateEngine()
        self.available_variables = []
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the picker UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Header
        header = QLabel("Template Variables")
        header.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 11px;
                padding: 3px;
            }
        """)
        layout.addWidget(header)
        
        # Variable list
        self.variable_list = QListWidget()
        self.variable_list.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                border: 1px solid #555555;
                border-radius: 3px;
                selection-background-color: #4a90e2;
                color: white;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 4px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
        """)
        self.variable_list.setMaximumHeight(120)
        self.variable_list.itemDoubleClicked.connect(self._on_variable_selected)
        layout.addWidget(self.variable_list)
        
        # Info text
        info_label = QLabel("Double-click to insert variable")
        info_label.setStyleSheet("""
            QLabel {
                color: #999999;
                font-size: 10px;
                font-style: italic;
                padding: 2px;
            }
        """)
        layout.addWidget(info_label)
        
        self.setLayout(layout)
        
    def update_variables(self, context, current_node, workflow_connections):
        """Update available template variables"""
        try:
            self.available_variables = self.template_engine.get_available_variables(
                context, current_node, workflow_connections
            )
            self._populate_variable_list()
        except Exception as e:
            print(f"Error updating template variables: {e}")
            self.available_variables = []
            self._populate_variable_list()
            
    def _populate_variable_list(self):
        """Populate the variable list widget"""
        self.variable_list.clear()
        
        if not self.available_variables:
            item = QListWidgetItem("No variables available")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setForeground(QColor(150, 150, 150))
            self.variable_list.addItem(item)
            return
            
        for var in self.available_variables:
            item = TemplateVariableItem(var)
            self.variable_list.addItem(item)
            
    def _on_variable_selected(self, item):
        """Handle variable selection"""
        if isinstance(item, TemplateVariableItem):
            template_var = item.template_variable.value
            self.variable_selected.emit(template_var)


class TemplateVariableDialog(QDialog):
    """Full dialog for browsing and selecting template variables"""
    
    variable_selected = pyqtSignal(str)
    
    def __init__(self, context=None, current_node=None, workflow_connections=None, canvas_variables=None, all_nodes=None, parent=None):
        super().__init__(parent)
        self.context = context
        self.current_node = current_node
        self.workflow_connections = workflow_connections or []
        self.canvas_variables = canvas_variables or {}
        self.all_nodes = all_nodes or []
        self.template_engine = ParameterTemplateEngine()
        self.available_variables = []
        
        self.setWindowTitle("Template Variables")
        self.setModal(True)
        self.resize(600, 400)
        
        self.setup_ui()
        self.load_variables()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout()
        
        # Create splitter for main content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - variable list
        left_widget = self._create_variable_list_section()
        splitter.addWidget(left_widget)
        
        # Right side - variable details and preview
        right_widget = self._create_details_section()
        splitter.addWidget(right_widget)
        
        # Set splitter proportions
        splitter.setSizes([300, 300])
        layout.addWidget(splitter)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        insert_button = QPushButton("Insert Variable")
        insert_button.setDefault(True)
        insert_button.clicked.connect(self._insert_selected_variable)
        button_box.addButton(insert_button, QDialogButtonBox.ButtonRole.AcceptRole)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(button_box)
        self.setLayout(layout)
        
        # Store references
        self.insert_button = insert_button
        self.insert_button.setEnabled(False)  # Disabled until selection
        
    def _create_variable_list_section(self):
        """Create the variable list section"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header = QLabel("Available Variables")
        header.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 5px;
            }
        """)
        layout.addWidget(header)
        
        # Variable list grouped by type
        self.variable_list = QListWidget()
        self.variable_list.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                border: 1px solid #555555;
                border-radius: 3px;
                selection-background-color: #4a90e2;
                color: white;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
        """)
        self.variable_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.variable_list.itemDoubleClicked.connect(self._on_variable_double_clicked)
        layout.addWidget(self.variable_list)
        
        widget.setLayout(layout)
        return widget
        
    def _create_details_section(self):
        """Create the details and preview section"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Variable details
        details_group = QGroupBox("Variable Details")
        details_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 3px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        details_layout = QVBoxLayout()
        
        self.details_label = QLabel("Select a variable to see details")
        self.details_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                padding: 10px;
                font-style: italic;
            }
        """)
        self.details_label.setWordWrap(True)
        details_layout.addWidget(self.details_label)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Template syntax help
        help_group = QGroupBox("Template Syntax")
        help_group.setStyleSheet("""
            QGroupBox {
                color: white;
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 3px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        help_layout = QVBoxLayout()
        
        help_text = QLabel("""
Template variables are enclosed in double curly braces:

• {{previous_output}} - Output from previous node
• {{node_<id>.output}} - Output from specific node
• {{variables.<name>}} - Workflow variables  


Variables are resolved during workflow execution.
        """.strip())
        help_text.setStyleSheet("""
            QLabel {
                color: #cccccc;
                padding: 10px;
                font-size: 11px;
                line-height: 1.4;
            }
        """)
        help_text.setWordWrap(True)
        help_layout.addWidget(help_text)
        
        help_group.setLayout(help_layout)
        layout.addWidget(help_group)
        
        widget.setLayout(layout)
        return widget
        
    def load_variables(self):
        """Load available template variables"""
        if not self.current_node:
            # Create dummy variables for demonstration
            self._show_demo_variables()
            return
            
        try:
            self.available_variables = self.template_engine.get_available_variables(
                self.context, self.current_node, self.workflow_connections, self.canvas_variables, self.all_nodes
            )
            self._populate_variable_list()
        except Exception as e:
            print(f"Error loading template variables: {e}")
            import traceback
            traceback.print_exc()
            self._show_demo_variables()
            
    def refresh_variables(self, context=None, current_node=None, workflow_connections=None, canvas_variables=None, all_nodes=None):
        """Refresh variables with updated context"""
        # Update context if provided
        if context is not None:
            self.context = context
        if current_node is not None:
            self.current_node = current_node
        if workflow_connections is not None:
            self.workflow_connections = workflow_connections
        if canvas_variables is not None:
            self.canvas_variables = canvas_variables
        if all_nodes is not None:
            self.all_nodes = all_nodes
            
        # Reload variables with updated context
        self.load_variables()
            
    def _show_demo_variables(self):
        """Show demonstration variables when context is not available"""
        from services.workflows.parameter_template_engine import TemplateVariable
        
        self.available_variables = [
            TemplateVariable(
                name="previous_output",
                type="previous_output", 
                value="{{previous_output}}",
                description="Output from the immediately preceding node"
            ),
            TemplateVariable(
                name="variables.hostname",
                type="variable",
                value="{{variables.hostname}}",
                description="Hostname extracted from previous command output"
            ),
            TemplateVariable(
                name="input.raw",
                type="input",
                value="{{input.raw}}",
                description="Raw input data from previous node"
            )
        ]
        self._populate_variable_list()
        
    def _populate_variable_list(self):
        """Populate the variable list with grouping"""
        self.variable_list.clear()
        
        if not self.available_variables:
            item = QListWidgetItem("No variables available for this node position")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setForeground(QColor(150, 150, 150))
            self.variable_list.addItem(item)
            return
            
        # Group variables by type
        groups = {}
        for var in self.available_variables:
            if var.type not in groups:
                groups[var.type] = []
            groups[var.type].append(var)
            
        # Add grouped items
        for group_type, variables in groups.items():
            # Add group header with friendly names
            group_display_names = {
                'previous_output': 'Previous Output',
                'node_output': 'Node Outputs',  # Individual node outputs
                'variable': 'Variables'
            }
            
            header_text = group_display_names.get(group_type, group_type.replace('_', ' ').title())
            header_item = QListWidgetItem(f"--- {header_text} ---")
            header_item.setFlags(header_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            header_item.setForeground(QColor(100, 150, 255))
            font = header_item.font()
            font.setBold(True)
            header_item.setFont(font)
            self.variable_list.addItem(header_item)
            
            # Add variables in this group
            for var in variables:
                item = TemplateVariableItem(var)
                self.variable_list.addItem(item)
                
    def _on_selection_changed(self):
        """Handle variable selection change"""
        current_item = self.variable_list.currentItem()
        
        if isinstance(current_item, TemplateVariableItem):
            var = current_item.template_variable
            details_text = f"""
<b>Variable:</b> {var.name}<br>
<b>Type:</b> {var.type.replace('_', ' ').title()}<br>
<b>Template:</b> <code>{var.value}</code><br>
<b>Description:</b> {var.description}
            """.strip()
            self.details_label.setText(details_text)
            self.insert_button.setEnabled(True)
        else:
            self.details_label.setText("Select a variable to see details")
            self.insert_button.setEnabled(False)
            
    def _on_variable_double_clicked(self, item):
        """Handle double-click on variable"""
        if isinstance(item, TemplateVariableItem):
            self._insert_selected_variable()
            
    def _insert_selected_variable(self):
        """Insert the selected variable and close dialog"""
        current_item = self.variable_list.currentItem()
        
        if isinstance(current_item, TemplateVariableItem):
            template_var = current_item.template_variable.value
            self.variable_selected.emit(template_var)
            self.accept()


class TemplateInsertButton(QPushButton):
    """Button that opens template variable picker"""
    
    variable_selected = pyqtSignal(str)
    
    def __init__(self, context=None, current_node=None, workflow_connections=None, canvas_variables=None, parent=None):
        super().__init__(parent)  # Template variables button
        
        # Set icon from resources
        
        self.setIcon(QIcon("resources/cube-plus.svg"))
        self.setText("")  # No text, just icon
        self.context = context
        self.current_node = current_node  
        self.workflow_connections = workflow_connections
        self.canvas_variables = canvas_variables or {}
        
        self.setToolTip("Insert template variable")
        self.setFixedSize(28, 28)
        self.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                border: none;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #5a9ff2;
            }
            QPushButton:pressed {
                background-color: #3a80d2;
            }
        """)
        
        self.clicked.connect(self._show_template_dialog)
        
    def update_context(self, context, current_node, workflow_connections, canvas_variables=None):
        """Update the workflow context"""
        self.context = context
        self.current_node = current_node
        self.workflow_connections = workflow_connections
        self.canvas_variables = canvas_variables or {}
        
    def _show_template_dialog(self):
        """Show the template variable selection dialog"""
        # Try to get fresh context from parent widgets
        fresh_context = self._get_fresh_context()
        
        dialog = TemplateVariableDialog(
            fresh_context.get('context', self.context), 
            fresh_context.get('current_node', self.current_node), 
            fresh_context.get('workflow_connections', self.workflow_connections), 
            fresh_context.get('canvas_variables', self.canvas_variables),
            fresh_context.get('all_nodes', []),
            self
        )
        dialog.variable_selected.connect(self.variable_selected.emit)
        dialog.exec()
        
    def _get_fresh_context(self):
        """Try to get fresh context from parent widgets"""
        fresh_context = {}
        
        # Walk up the widget hierarchy to find workflow editor or canvas
        current_widget = self.parent()
        while current_widget:
            # Check if we can get workflow context from the parent
            if hasattr(current_widget, 'workflow_context'):
                workflow_context = current_widget.workflow_context
                if isinstance(workflow_context, dict):
                    fresh_context['canvas_variables'] = workflow_context.get('canvas_variables', {})
                    
            # Check if we can get canvas reference for workflow connections and nodes
            if hasattr(current_widget, 'canvas'):
                canvas = current_widget.canvas
                if hasattr(canvas, 'connections'):
                    fresh_context['workflow_connections'] = canvas.connections
                if hasattr(canvas, 'workflow_variables'):
                    fresh_context['canvas_variables'] = canvas.workflow_variables
                # Also get all nodes from canvas for better variable generation
                if hasattr(canvas, 'nodes'):
                    fresh_context['all_nodes'] = canvas.nodes
                    
            # Check if we can get current node from parent
            if hasattr(current_widget, 'current_node'):
                fresh_context['current_node'] = current_widget.current_node
                
            current_widget = current_widget.parent()
            
        return fresh_context