from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                            QListWidgetItem, QCheckBox, QPushButton, QLabel, 
                            QDialog, QDialogButtonBox, QScrollArea, QFrame,
                            QGroupBox, QTextEdit, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPalette, QIcon, QPixmap, QPainter, QColor

from services.workflows.workflow_schema_manager import WorkflowSchemaManager, WorkflowSchemaInfo


class SchemaInfoWidget(QWidget):
    """Widget displaying detailed information about a schema"""
    
    def __init__(self, schema_info: WorkflowSchemaInfo, parent=None):
        super().__init__(parent)
        self.schema_info = schema_info
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        
        # Schema name and type
        header_layout = QHBoxLayout()
        
        name_label = QLabel(self.schema_info.schema_name)
        name_label.setFont(QFont("", 11, QFont.Weight.Bold))
        header_layout.addWidget(name_label)
        
        header_layout.addStretch()
        
        type_label = QLabel(self.schema_info.beacon_type)
        type_label.setStyleSheet("""
            QLabel {
                background-color: #4a90e2;
                color: white;
                padding: 2px 8px;
                border-radius: 10px;
                font-size: 10px;
                font-weight: bold;
            }
        """)
        header_layout.addWidget(type_label)
        
        layout.addLayout(header_layout)
        
        # Description
        if self.schema_info.description:
            desc_label = QLabel(self.schema_info.description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("QLabel { color: #666666; font-size: 10px; }")
            layout.addWidget(desc_label)
        
        # Stats
        stats_layout = QHBoxLayout()
        
        modules_label = QLabel(f"{self.schema_info.module_count} modules")
        modules_label.setStyleSheet("QLabel { color: #888888; font-size: 9px; }")
        stats_layout.addWidget(modules_label)
        
        categories_label = QLabel(f"{self.schema_info.category_count} categories")
        categories_label.setStyleSheet("QLabel { color: #888888; font-size: 9px; }")
        stats_layout.addWidget(categories_label)
        
        stats_layout.addStretch()
        
        # Version
        version_label = QLabel(f"v{self.schema_info.version}")
        version_label.setStyleSheet("QLabel { color: #999999; font-size: 9px; }")
        stats_layout.addWidget(version_label)
        
        layout.addLayout(stats_layout)
        
        self.setLayout(layout)


class SchemaListItem(QWidget):
    """Custom widget for schema list items with checkbox"""
    
    schema_toggled = pyqtSignal(str, bool)  # schema_file, is_active
    
    def __init__(self, schema_info: WorkflowSchemaInfo, parent=None):
        super().__init__(parent)
        self.schema_info = schema_info
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.schema_info.is_active)
        self.checkbox.toggled.connect(self._on_toggled)
        layout.addWidget(self.checkbox)
        
        # Schema icon/indicator
        icon_label = QLabel()
        icon_pixmap = self._create_schema_icon()
        icon_label.setPixmap(icon_pixmap)
        icon_label.setFixedSize(24, 24)
        layout.addWidget(icon_label)
        
        # Schema info widget
        info_widget = SchemaInfoWidget(self.schema_info)
        layout.addWidget(info_widget)
        
        self.setLayout(layout)
        
        # Style the item
        self.setStyleSheet("""
            SchemaListItem {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                margin: 2px;
            }
            SchemaListItem:hover {
                background-color: #f5f5f5;
                border-color: #4a90e2;
            }
        """)
        
    def _create_schema_icon(self):
        """Create a colored icon for the schema based on beacon type"""
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Color based on beacon type
        color_map = {
            "python": "#3776ab",      # Python blue
            "windows": "#00bcf2",     # Windows blue
            "linux": "#e95420",       # Ubuntu orange
            "autohotkey": "#334455",  # AHK gray-blue
            "powershell": "#012456",  # PowerShell blue
        }
        
        # Default color if beacon type not in map
        beacon_type_lower = self.schema_info.beacon_type.lower()
        color = QColor(color_map.get(beacon_type_lower, "#666666"))
        
        painter.setBrush(color)
        painter.setPen(QColor(255, 255, 255, 100))
        painter.drawRoundedRect(2, 2, 20, 20, 4, 4)
        
        # Add first letter of beacon type
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        
        text = self.schema_info.beacon_type[0].upper()
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        
        painter.end()
        return pixmap
    
    def _on_toggled(self, checked: bool):
        """Handle checkbox toggle"""
        self.schema_info.is_active = checked
        self.schema_toggled.emit(self.schema_info.schema_file, checked)
    
    def set_active(self, active: bool):
        """Update the active state"""
        self.schema_info.is_active = active
        self.checkbox.setChecked(active)


class SchemaSelectorWidget(QWidget):
    """Main schema selector widget"""
    
    schema_selection_changed = pyqtSignal(list)  # Emits list of active schema files
    
    def __init__(self, schema_manager: WorkflowSchemaManager = None, parent=None):
        super().__init__(parent)
        self.schema_manager = schema_manager
        self.schema_items = {}  # schema_file -> SchemaListItem
        
        self.setup_ui()
        self.connect_signals()
        self.refresh_schemas()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("Workflow Schemas")
        title_label.setFont(QFont("", 12, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setMaximumWidth(80)
        refresh_btn.clicked.connect(self.refresh_schemas)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setMaximumWidth(80)
        self.select_all_btn.clicked.connect(self.select_all_schemas)
        controls_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.setMaximumWidth(80)
        self.select_none_btn.clicked.connect(self.select_no_schemas)
        controls_layout.addWidget(self.select_none_btn)
        
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Schema list in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.schema_list_widget = QWidget()
        self.schema_list_layout = QVBoxLayout()
        self.schema_list_layout.setContentsMargins(4, 4, 4, 4)
        self.schema_list_layout.setSpacing(4)
        self.schema_list_widget.setLayout(self.schema_list_layout)
        
        scroll_area.setWidget(self.schema_list_widget)
        layout.addWidget(scroll_area)
        
        # Summary info
        self.summary_label = QLabel()
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border-radius: 4px;
                padding: 8px;
                font-size: 10px;
                color: #666666;
            }
        """)
        layout.addWidget(self.summary_label)
        
        self.setLayout(layout)
        
    def connect_signals(self):
        """Connect schema manager signals"""
        if self.schema_manager:
            self.schema_manager.schema_selection_changed.connect(self.on_schema_selection_changed)
    
    def refresh_schemas(self):
        """Refresh the list of available schemas"""
        if not self.schema_manager:
            return
            
        # Clear existing items
        self.clear_schema_list()
        
        # Refresh schema manager
        self.schema_manager.refresh_schemas()
        
        # Populate with updated schemas
        available_schemas = self.schema_manager.get_available_schemas()
        
        for schema_info in available_schemas:
            self.add_schema_item(schema_info)
            
        # Add stretch to push items to top
        self.schema_list_layout.addStretch()
        
        self.update_summary()
    
    def clear_schema_list(self):
        """Clear all schema items from the list"""
        # Remove all widgets from layout
        while self.schema_list_layout.count():
            child = self.schema_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.schema_items.clear()
    
    def add_schema_item(self, schema_info: WorkflowSchemaInfo):
        """Add a schema item to the list"""
        item = SchemaListItem(schema_info)
        item.schema_toggled.connect(self.on_schema_toggled)
        
        self.schema_list_layout.addWidget(item)
        self.schema_items[schema_info.schema_file] = item
    
    def on_schema_toggled(self, schema_file: str, is_active: bool):
        """Handle individual schema toggle"""
        if not self.schema_manager:
            return
            
        if is_active:
            self.schema_manager.add_schema_to_workflow(schema_file)
        else:
            self.schema_manager.remove_schema_from_workflow(schema_file)
            
        self.update_summary()
    
    def on_schema_selection_changed(self, active_schema_files: list):
        """Handle schema selection changes from manager"""
        # Update UI to reflect new selection
        for schema_file, item in self.schema_items.items():
            is_active = schema_file in active_schema_files
            item.set_active(is_active)
            
        self.update_summary()
        
        # Emit signal for external listeners
        self.schema_selection_changed.emit(active_schema_files)
    
    def select_all_schemas(self):
        """Select all available schemas"""
        if not self.schema_manager:
            return
            
        available_schemas = self.schema_manager.get_available_schemas()
        schema_files = [schema.schema_file for schema in available_schemas]
        self.schema_manager.set_active_schemas(schema_files)
    
    def select_no_schemas(self):
        """Deselect all schemas"""
        if not self.schema_manager:
            return
            
        self.schema_manager.clear_all_schemas()
    
    def update_summary(self):
        """Update the summary information"""
        if not self.schema_manager:
            self.summary_label.setText("No schema manager available")
            return
            
        summary = self.schema_manager.get_workflow_summary()
        
        text_parts = []
        text_parts.append(f"{summary['active_schema_count']} schemas selected")
        text_parts.append(f"{summary['total_modules']} total modules")
        
        if summary['beacon_types']:
            types_str = ", ".join(summary['beacon_types'])
            text_parts.append(f"Types: {types_str}")
        
        self.summary_label.setText(" • ".join(text_parts))
    
    def get_active_schemas(self) -> list:
        """Get list of currently active schema files"""
        if not self.schema_manager:
            return []
        return self.schema_manager.get_active_schema_files()


class SchemaSelectorDialog(QDialog):
    """Dialog for selecting schemas in a workflow"""
    
    def __init__(self, schema_manager: WorkflowSchemaManager = None, parent=None):
        super().__init__(parent)
        self.schema_manager = schema_manager
        
        self.setWindowTitle("Select Workflow Schemas")
        self.setMinimumSize(500, 600)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Description
        desc_label = QLabel(
            "Select which beacon schemas to include in this workflow. "
            "You can combine multiple schemas for mixed-beacon workflows."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("QLabel { color: #666666; margin-bottom: 10px; }")
        layout.addWidget(desc_label)
        
        # Schema selector widget
        self.schema_selector = SchemaSelectorWidget(self.schema_manager)
        layout.addWidget(self.schema_selector)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def get_selected_schemas(self) -> list:
        """Get the selected schema files"""
        return self.schema_selector.get_active_schemas()


class CompactSchemaSelectorWidget(QWidget):
    """Compact version for toolbar use"""
    
    schema_selection_changed = pyqtSignal(list)
    
    def __init__(self, schema_manager: WorkflowSchemaManager = None, parent=None):
        super().__init__(parent)
        self.schema_manager = schema_manager
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        
        # Schema count label
        self.count_label = QLabel("0 schemas")
        self.count_label.setStyleSheet("QLabel { color: #666666; font-size: 11px; }")
        layout.addWidget(self.count_label)
        
        # Configure button
        self.config_btn = QPushButton("Configure...")
        self.config_btn.setMaximumWidth(80)
        self.config_btn.clicked.connect(self.show_schema_dialog)
        layout.addWidget(self.config_btn)
        
        self.setLayout(layout)
        self.update_display()
        
    def connect_signals(self):
        """Connect schema manager signals"""
        if self.schema_manager:
            self.schema_manager.schema_selection_changed.connect(self.on_schema_selection_changed)
            
    def on_schema_selection_changed(self, active_schema_files: list):
        """Handle schema selection changes"""
        self.update_display()
        self.schema_selection_changed.emit(active_schema_files)
        
    def update_display(self):
        """Update the display with current schema count"""
        if not self.schema_manager:
            self.count_label.setText("No schemas")
            return
            
        count = len(self.schema_manager.get_active_schema_files())
        self.count_label.setText(f"{count} schema{'s' if count != 1 else ''}")
        
        # Update button style based on selection
        if count > 0:
            self.config_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a90e2;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #357abd;
                }
            """)
        else:
            self.config_btn.setStyleSheet("")
            
    def show_schema_dialog(self):
        """Show the full schema selection dialog"""
        dialog = SchemaSelectorDialog(self.schema_manager, self)
        dialog.exec()
        
    def get_active_schemas(self) -> list:
        """Get list of currently active schema files"""
        if not self.schema_manager:
            return []
        return self.schema_manager.get_active_schema_files()