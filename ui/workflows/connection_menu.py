from PyQt6.QtWidgets import QMenu, QWidgetAction, QLabel, QVBoxLayout, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QFont

from services.workflows.node_compatibility import NodeCompatibilityManager, ConnectionOption, ConnectionType
from services.workflows.node_factory import NodeTemplateRegistry, NodeTemplate


class ConnectionMenu(QMenu):
    """Smart menu that shows appropriate connection options with template integration"""
    
    connection_option_selected = pyqtSignal(object)  # Emits the selected template
    
    def __init__(self, source_node, action_point, compatibility_manager: NodeCompatibilityManager, 
                 template_registry: NodeTemplateRegistry):
        super().__init__()
        self.source_node = source_node
        self.action_point = action_point
        self.compatibility_manager = compatibility_manager
        self.template_registry = template_registry
        
        self.setTitle("Add Connection")
        self.setMinimumWidth(300)
        self.setup_styling()
        self.build_enhanced_menu()
        
    def setup_styling(self):
        """Set up the menu styling"""
        self.setStyleSheet("""
            QMenu {
                background-color: #3c3c3c;
                border: 2px solid #666666;
                border-radius: 8px;
                color: white;
                font-size: 12px;
                padding: 4px;
            }
            QMenu::item {
                padding: 0px;
                margin: 1px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #555555;
            }
            QMenu::separator {
                height: 2px;
                background-color: #666666;
                margin: 6px 4px;
                border-radius: 1px;
            }
        """)
        
    def build_enhanced_menu(self):
        """Build enhanced menu with templates and visual indicators"""
        # Get connection type string for compatibility manager
        connection_type_str = self._connection_type_to_string(self.action_point.connection_type)
        print(f"DEBUG: Building menu for connection type: {connection_type_str}, source node: {self.source_node.node_type}")
        
        # Get compatible node types
        compatible_types = self.compatibility_manager.get_compatible_nodes(
            self.source_node.node_type, 
            connection_type_str
        )
        print(f"DEBUG: Compatible node types: {compatible_types}")
        
        if not compatible_types:
            print("DEBUG: No compatible node types found")
            self._add_no_options_message()
            return
            
        # Get templates for compatible types
        templates_by_category = self._group_templates_by_category(compatible_types)
        print(f"DEBUG: Templates by category: {list(templates_by_category.keys())}")
        print(f"DEBUG: Total templates found: {sum(len(templates) for templates in templates_by_category.values())}")
        
        # Debug: Check template registry state
        print(f"DEBUG: Template registry has {len(self.template_registry.templates)} total templates")
        print(f"DEBUG: Template registry categories: {self.template_registry.get_all_categories()}")
        
        if not templates_by_category:
            print("DEBUG: No templates found for compatible types")
            self._add_no_templates_message()
            return
            
        # Build menu structure
        self._build_categorized_menu(templates_by_category)
        
    def _group_templates_by_category(self, compatible_types):
        """Group templates by category"""
        templates_by_category = {}
        
        for node_type in compatible_types:
            template = self.template_registry.get_template(node_type)
            print(f"DEBUG: Looking for template '{node_type}': {'Found' if template else 'Not found'}")
            if template:
                category = template.category
                if category not in templates_by_category:
                    templates_by_category[category] = []
                templates_by_category[category].append(template)
                print(f"DEBUG: Added template '{template.display_name}' to category '{category}'")
                
        return templates_by_category
        
    def _build_categorized_menu(self, templates_by_category):
        """Build the categorized menu structure with schema grouping"""
        # Category order for logical arrangement
        category_order = [
            "Control Flow",
            "Actions - Basic Commands",
            "Actions - Discovery", 
            "Actions - File Operations",
            "Actions - Information Gathering",
            "Actions - Persistence",
            "Actions - Movement", 
            "Actions - Data Operations",
            "Communication",
            "Error Handling"
        ]
        
        # Add connection type header
        self._add_connection_type_header()
        self.addSeparator()
        
        # Group templates by schema within categories
        templates_by_schema = self._group_templates_by_schema(templates_by_category)
        
        # Check if we have multiple schemas to decide grouping approach
        schema_count = len(templates_by_schema)
        
        if schema_count <= 1:
            # Single or no schema - use original category-based grouping
            self._build_single_schema_menu(templates_by_category, category_order)
        else:
            # Multiple schemas - group by schema first, then by category
            self._build_multi_schema_menu(templates_by_schema, category_order)
                
    def _add_connection_type_header(self):
        """Add header showing the connection type"""
        connection_name = self._get_connection_display_name()
        header_action = self._create_header_action(f"Add {connection_name}")
        self.addAction(header_action)
        
    def _get_connection_display_name(self):
        """Get display name for connection type"""
        if self.action_point.connection_type == ConnectionType.SEQUENTIAL:
            return "Next Step"
        elif self.action_point.connection_type == ConnectionType.CONDITIONAL_TRUE:
            return "True Branch"
        elif self.action_point.connection_type == ConnectionType.CONDITIONAL_FALSE:
            return "False Branch"
        else:
            return "Connection"
            
    def _add_category_section(self, category, templates):
        """Add a category section with its templates"""
        # Add category header
        category_action = self._create_category_header(category)
        self.addAction(category_action)
        
        # Add templates in this category
        for template in sorted(templates, key=lambda t: t.display_name):
            template_action = self._create_template_action(template)
            self.addAction(template_action)
            
    def _create_header_action(self, text):
        """Create a styled header action"""
        action = QAction(text, self)
        action.setEnabled(False)
        font = action.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        action.setFont(font)
        return action
        
    def _create_category_header(self, category):
        """Create a category header action"""
        widget_action = QWidgetAction(self)
        widget = CategoryHeaderWidget(category)
        widget_action.setDefaultWidget(widget)
        return widget_action
        
    def _create_template_action(self, template):
        """Create an action for a template with enhanced display"""
        widget_action = QWidgetAction(self)
        widget = TemplateOptionWidget(template, self)
        widget_action.setDefaultWidget(widget)
        
        # Connect selection
        widget.template_selected.connect(lambda: self.connection_option_selected.emit(template))
        
        return widget_action
        
    def _add_no_options_message(self):
        """Add message when no options are available"""
        action = QAction("No valid connections available for this node type", self)
        action.setEnabled(False)
        self.addAction(action)
        
        # Add helpful hint
        hint_action = QAction("Hint: Make sure schemas are selected in the workflow", self)
        hint_action.setEnabled(False)
        self.addAction(hint_action)
        
    def _add_no_templates_message(self):
        """Add message when no templates are found"""
        action = QAction("No node templates available", self)
        action.setEnabled(False)
        self.addAction(action)
        
        # Add helpful information
        info_action = QAction("Check: Are schemas selected? Are templates loaded?", self)
        info_action.setEnabled(False)
        self.addAction(info_action)
                    
    def _connection_type_to_string(self, connection_type):
        """Convert ConnectionType enum to string for compatibility manager"""
        type_mapping = {
            "SEQUENTIAL": "output",
            "CONDITIONAL_TRUE": "true_output", 
            "CONDITIONAL_FALSE": "false_output",
            "ERROR": "error",
            "PARALLEL": "parallel"
        }
        return type_mapping.get(connection_type.name, "output")
    
    def _group_templates_by_schema(self, templates_by_category):
        """Group all templates by their source schema"""
        templates_by_schema = {}
        
        for category, templates in templates_by_category.items():
            for template in templates:
                schema_file = self._get_template_schema(template)
                if schema_file not in templates_by_schema:
                    templates_by_schema[schema_file] = {}
                if category not in templates_by_schema[schema_file]:
                    templates_by_schema[schema_file][category] = []
                templates_by_schema[schema_file][category].append(template)
                
        return templates_by_schema
    
    def _get_template_schema(self, template):
        """Get the schema file name for a template"""
        if hasattr(template, 'schema_integration') and template.schema_integration:
            return template.schema_integration.get('schema_file', 'built-in')
        return 'built-in'
    
    def _get_schema_display_name(self, schema_file):
        """Get a user-friendly display name for a schema"""
        if schema_file == 'built-in':
            return 'Built-in Actions'
        return schema_file.replace('.yaml', '').replace('_', ' ').title()
    
    def _build_single_schema_menu(self, templates_by_category, category_order):
        """Build menu for single schema (original approach)"""
        first_category = True
        for category in category_order:
            if category in templates_by_category:
                if not first_category:
                    self.addSeparator()
                    
                self._add_category_section(category, templates_by_category[category])
                first_category = False
                
        # Add any remaining categories
        for category, templates in templates_by_category.items():
            if category not in category_order:
                if not first_category:
                    self.addSeparator()
                self._add_category_section(category, templates)
                first_category = False
    
    def _build_multi_schema_menu(self, templates_by_schema, category_order):
        """Build menu for multiple schemas with schema grouping"""
        first_schema = True
        
        # Sort schemas to ensure consistent ordering (built-in first, then alphabetically)
        sorted_schemas = sorted(templates_by_schema.keys(), 
                               key=lambda x: (x != 'built-in', x))
        
        for schema_file in sorted_schemas:
            schema_templates = templates_by_schema[schema_file]
            
            if not first_schema:
                self.addSeparator()
            
            # Add schema header
            self._add_schema_header(schema_file)
            
            # Add categories for this schema
            first_category = True
            for category in category_order:
                if category in schema_templates:
                    if not first_category:
                        # Use thinner separator between categories within schema
                        self._add_thin_separator()
                        
                    self._add_category_section_with_schema_context(
                        category, schema_templates[category], schema_file)
                    first_category = False
                    
            # Add any remaining categories for this schema
            for category, templates in schema_templates.items():
                if category not in category_order:
                    if not first_category:
                        self._add_thin_separator()
                    self._add_category_section_with_schema_context(
                        category, templates, schema_file)
                    first_category = False
            
            first_schema = False
    
    def _add_schema_header(self, schema_file):
        """Add header for a schema section"""
        schema_name = self._get_schema_display_name(schema_file)
        widget_action = QWidgetAction(self)
        widget = SchemaHeaderWidget(schema_name, schema_file)
        widget_action.setDefaultWidget(widget)
        self.addAction(widget_action)
    
    def _add_thin_separator(self):
        """Add a thinner separator for within-schema separation"""
        separator = self.addSeparator()
        # Note: Can't style QAction separators directly, just add the separator
    
    def _add_category_section_with_schema_context(self, category, templates, schema_file):
        """Add category section with schema context indicators"""
        # Add category header (slightly smaller for schema context)
        category_action = self._create_category_header_for_schema(category, schema_file)
        self.addAction(category_action)
        
        # Add templates with schema indicators
        for template in sorted(templates, key=lambda t: t.display_name):
            template_action = self._create_template_action_with_schema(template, schema_file)
            self.addAction(template_action)
    
    def _create_category_header_for_schema(self, category, schema_file):
        """Create category header with schema context"""
        widget_action = QWidgetAction(self)
        widget = CategoryHeaderWithSchemaWidget(category, schema_file)
        widget_action.setDefaultWidget(widget)
        return widget_action
    
    def _create_template_action_with_schema(self, template, schema_file):
        """Create template action with schema indicators"""
        widget_action = QWidgetAction(self)
        widget = TemplateOptionWithSchemaWidget(template, schema_file, self)
        widget_action.setDefaultWidget(widget)
        
        # Connect selection
        widget.template_selected.connect(lambda: self.connection_option_selected.emit(template))
        
        return widget_action


class CategoryHeaderWidget(QWidget):
    """Enhanced widget for category headers in menu"""
    
    def __init__(self, category_name: str):
        super().__init__()
        self.category_name = category_name
        self.setFixedHeight(30)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 6, 12, 6)
        
        label = QLabel(category_name)
        label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                background-color: transparent;
            }
        """)
        
        layout.addWidget(label)
        layout.addStretch()
        
        self.setLayout(layout)
        self.setStyleSheet("""
            CategoryHeaderWidget {
                background-color: #404040;
                border-radius: 4px;
                margin: 2px;
            }
        """)


class TemplateOptionWidget(QWidget):
    """Enhanced widget for template options in menu"""
    
    template_selected = pyqtSignal()
    
    def __init__(self, template: NodeTemplate, parent=None):
        super().__init__(parent)
        self.template = template
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.setup_ui()
        self.setup_styling()
        
    def setup_ui(self):
        """Set up the widget UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Icon
        icon_label = QLabel()
        icon_pixmap = self._create_template_icon()
        icon_label.setPixmap(icon_pixmap)
        icon_label.setFixedSize(24, 24)
        layout.addWidget(icon_label)
        
        # Content area
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)
        
        # Name
        name_label = QLabel(self.template.display_name)
        name_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        content_layout.addWidget(name_label)
        
        # Description
        if self.template.description:
            desc_text = self.template.description
            if len(desc_text) > 50:
                desc_text = desc_text[:47] + "..."
                
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
        
        # Parameters indicator
        if self.template.default_parameters:
            param_count = len(self.template.default_parameters)
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
        
        self.setLayout(layout)
        
    def setup_styling(self):
        """Set up widget styling"""
        self.setStyleSheet("""
            TemplateOptionWidget {
                background-color: transparent;
                border-radius: 4px;
                margin: 1px;
            }
            TemplateOptionWidget:hover {
                background-color: #555555;
            }
        """)
        
    def _create_template_icon(self):
        """Create an icon for the template"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Choose color based on template category/type
        color = self._get_template_color()
        
        painter.setBrush(QColor(color))
        painter.setPen(QColor(255, 255, 255, 100))
        painter.drawRoundedRect(2, 2, 20, 20, 4, 4)
        
        # Add simple icon based on node type
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        
        # Get first letter of display name
        text = self.template.display_name[0].upper()
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        
        painter.end()
        return pixmap
        
    def _get_template_color(self):
        """Get color for template based on category"""
        color_map = {
            "Control Flow": "#4CAF50",      # Green
            "Actions - Basic Commands": "#2196F3",   # Blue
            "Actions - Discovery": "#FF9800",  # Orange
            "Actions - File Operations": "#9C27B0",    # Purple
            "Actions - Information Gathering": "#FF9800",  # Orange
            "Actions - Persistence": "#F44336",        # Red
            "Actions - Movement": "#607D8B",           # Blue Grey
            "Actions - Data Operations": "#795548",     # Brown
            "Communication": "#3F51B5",      # Indigo
            "Error Handling": "#E91E63"      # Pink
        }
        return color_map.get(self.template.category, "#757575")  # Default grey
        
    def mousePressEvent(self, event):
        """Handle mouse press to select template"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.template_selected.emit()
        super().mousePressEvent(event)


class SchemaHeaderWidget(QWidget):
    """Widget for schema headers in multi-schema menus"""
    
    def __init__(self, schema_name: str, schema_file: str):
        super().__init__()
        self.schema_name = schema_name
        self.schema_file = schema_file
        self.setFixedHeight(35)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Schema icon
        icon_label = QLabel()
        icon_pixmap = self._create_schema_icon()
        icon_label.setPixmap(icon_pixmap)
        icon_label.setFixedSize(20, 20)
        layout.addWidget(icon_label)
        
        # Schema name
        label = QLabel(schema_name)
        label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                background-color: transparent;
            }
        """)
        layout.addWidget(label)
        
        layout.addStretch()
        
        # Schema type indicator
        if schema_file != 'built-in':
            type_label = QLabel("SCHEMA")
            type_label.setStyleSheet("""
                QLabel {
                    color: #cccccc;
                    font-size: 9px;
                    font-weight: bold;
                    background-color: transparent;
                }
            """)
            layout.addWidget(type_label)
        
        self.setLayout(layout)
        self.setStyleSheet("""
            SchemaHeaderWidget {
                background-color: #4a4a4a;
                border-radius: 6px;
                margin: 2px;
            }
        """)
    
    def _create_schema_icon(self):
        """Create an icon for the schema"""
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Different colors for different schema types
        if self.schema_file == 'built-in':
            color = QColor(100, 150, 255)  # Blue for built-in
        else:
            # Hash schema file name to get consistent color
            hash_val = hash(self.schema_file) % 360
            color = QColor.fromHsv(hash_val, 200, 255)
        
        painter.setBrush(color)
        painter.setPen(QColor(255, 255, 255, 100))
        painter.drawRoundedRect(2, 2, 16, 16, 3, 3)
        
        # Add icon based on schema type
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        
        if self.schema_file == 'built-in':
            text = "B"
        else:
            text = self.schema_name[0].upper()
        
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        return pixmap


class CategoryHeaderWithSchemaWidget(QWidget):
    """Category header widget with schema context"""
    
    def __init__(self, category_name: str, schema_file: str):
        super().__init__()
        self.category_name = category_name
        self.schema_file = schema_file
        self.setFixedHeight(25)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(20, 4, 12, 4)  # Indent more than schema headers
        
        label = QLabel(category_name)
        label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-weight: bold;
                font-size: 11px;
                background-color: transparent;
            }
        """)
        
        layout.addWidget(label)
        layout.addStretch()
        
        self.setLayout(layout)
        self.setStyleSheet("""
            CategoryHeaderWithSchemaWidget {
                background-color: #383838;
                border-radius: 4px;
                margin: 1px;
            }
        """)


class TemplateOptionWithSchemaWidget(QWidget):
    """Enhanced template option widget with schema indicators"""
    
    template_selected = pyqtSignal()
    
    def __init__(self, template: NodeTemplate, schema_file: str, parent=None):
        super().__init__(parent)
        self.template = template
        self.schema_file = schema_file
        self.setFixedHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.setup_ui()
        self.setup_styling()
        
    def setup_ui(self):
        """Set up the widget UI with schema indicators"""
        layout = QHBoxLayout()
        layout.setContentsMargins(24, 8, 12, 8)  # Extra indent for schema context
        layout.setSpacing(12)
        
        # Template icon
        icon_label = QLabel()
        icon_pixmap = self._create_template_icon()
        icon_label.setPixmap(icon_pixmap)
        icon_label.setFixedSize(24, 24)
        layout.addWidget(icon_label)
        
        # Content area
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)
        
        # Name with schema indicator
        name_layout = QHBoxLayout()
        name_layout.setContentsMargins(0, 0, 0, 0)
        
        name_label = QLabel(self.template.display_name)
        name_label.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 13px;
            }
        """)
        name_layout.addWidget(name_label)
        
        # Add schema badge for non-built-in templates
        if self.schema_file != 'built-in':
            schema_badge = QLabel(self._get_schema_short_name())
            schema_badge.setStyleSheet("""
                QLabel {
                    background-color: #4a90e2;
                    color: white;
                    padding: 1px 4px;
                    border-radius: 6px;
                    font-size: 8px;
                    font-weight: bold;
                    margin-left: 6px;
                }
            """)
            name_layout.addWidget(schema_badge)
        
        name_layout.addStretch()
        content_layout.addLayout(name_layout)
        
        # Description
        if self.template.description:
            desc_text = self.template.description
            if len(desc_text) > 45:  # Slightly shorter for schema context
                desc_text = desc_text[:42] + "..."
                
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
        
        # Parameters indicator
        if self.template.default_parameters:
            param_count = len(self.template.default_parameters)
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
        
        self.setLayout(layout)
    
    def _get_schema_short_name(self):
        """Get a short name for the schema badge"""
        if self.schema_file == 'built-in':
            return ""
        
        # Get first letters of significant words
        name = self.schema_file.replace('.yaml', '').replace('_', ' ')
        words = [w for w in name.split() if len(w) > 2]  # Skip short words
        if len(words) >= 2:
            return ''.join(w[0].upper() for w in words[:2])
        elif len(words) == 1:
            return words[0][:3].upper()
        else:
            return name[:3].upper()
        
    def setup_styling(self):
        """Set up widget styling"""
        self.setStyleSheet("""
            TemplateOptionWithSchemaWidget {
                background-color: transparent;
                border-radius: 4px;
                margin: 1px;
            }
            TemplateOptionWithSchemaWidget:hover {
                background-color: #555555;
            }
        """)
        
    def _create_template_icon(self):
        """Create an icon for the template with schema context"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Choose color based on template category/type with schema context
        if self.schema_file == 'built-in':
            color = self._get_builtin_template_color()
        else:
            # Slightly modify color based on schema for visual distinction
            base_color = self._get_template_color()
            # Create variation based on schema hash
            schema_hash = hash(self.schema_file) % 30 - 15  # -15 to +14 variation
            color = QColor(base_color)
            hue = color.hue()
            color.setHsv((hue + schema_hash) % 360, color.saturation(), color.value())
        
        painter.setBrush(color)
        painter.setPen(QColor(255, 255, 255, 100))
        painter.drawRoundedRect(2, 2, 20, 20, 4, 4)
        
        # Add simple icon based on node type
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        
        # Get first letter of display name
        text = self.template.display_name[0].upper()
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        
        painter.end()
        return pixmap
        
    def _get_builtin_template_color(self):
        """Get color for built-in templates"""
        color_map = {
            "Control Flow": "#4CAF50",      # Green
            "Communication": "#3F51B5",      # Indigo
            "Error Handling": "#E91E63"      # Pink
        }
        return QColor(color_map.get(self.template.category, "#757575"))
        
    def _get_template_color(self):
        """Get base color for template based on category"""
        color_map = {
            "Actions - Basic Commands": "#2196F3",   # Blue
            "Actions - Discovery": "#FF9800",  # Orange
            "Actions - File Operations": "#9C27B0",    # Purple
            "Actions - Information Gathering": "#FF9800",  # Orange
            "Actions - Persistence": "#F44336",        # Red
            "Actions - Movement": "#607D8B",           # Blue Grey
            "Actions - Data Operations": "#795548",     # Brown
        }
        return QColor(color_map.get(self.template.category, "#757575"))  # Default grey
        
    def mousePressEvent(self, event):
        """Handle mouse press to select template"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.template_selected.emit()
        super().mousePressEvent(event)