"""
Beacon Builder Widget

UI component for building custom beacons by selecting modules
and configuring options.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QTextEdit, QLineEdit,
    QSpinBox, QComboBox, QCheckBox, QFileDialog,
    QMessageBox, QGridLayout, QFrame, QScrollArea,
    QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

import yaml
from pathlib import Path

try:
    from utils import FontManager
except ImportError:
    FontManager = None

try:
    from services.beacon_builder import BeaconBuilderService
except ImportError:
    BeaconBuilderService = None


class CollapsibleCategory(QWidget):
    """A collapsible category section for organizing modules"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.is_expanded = True
        self.module_widgets = []
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button for collapse/expand
        self.header_btn = QPushButton(f"▼ {self.title}")
        self.header_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: none;
                padding: 8px 12px;
                text-align: left;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        self.header_btn.clicked.connect(self.toggle_expanded)
        layout.addWidget(self.header_btn)

        # Container for module items
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(8, 4, 8, 8)
        self.content_layout.setSpacing(4)
        self.content_widget.setLayout(self.content_layout)
        layout.addWidget(self.content_widget)

        self.setLayout(layout)

    def toggle_expanded(self):
        """Toggle the expanded/collapsed state"""
        self.is_expanded = not self.is_expanded
        self.content_widget.setVisible(self.is_expanded)
        arrow = "▼" if self.is_expanded else "▶"
        self.header_btn.setText(f"{arrow} {self.title}")

    def add_module(self, module_widget: QWidget):
        """Add a module widget to this category"""
        self.content_layout.addWidget(module_widget)
        self.module_widgets.append(module_widget)

    def clear_modules(self):
        """Remove all module widgets"""
        for widget in self.module_widgets:
            self.content_layout.removeWidget(widget)
            widget.deleteLater()
        self.module_widgets.clear()


class ModuleCard(QFrame):
    """A styled card widget for a single module"""

    toggled = pyqtSignal(str, bool)  # module_id, is_checked

    def __init__(self, module_id: str, name: str, description: str, requires: list = None, parent=None):
        super().__init__(parent)
        self.module_id = module_id
        self.module_name = name
        self.requires = requires or []
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_ui(name, description)

    def mousePressEvent(self, event):
        """Toggle checkbox when clicking anywhere on the card"""
        self.checkbox.setChecked(not self.checkbox.isChecked())
        super().mousePressEvent(event)

    def setup_ui(self, name: str, description: str):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ModuleCard {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 4px;
            }
            ModuleCard:hover {
                border-color: #5a5a5a;
                background-color: #333333;
            }
            ModuleCard QLabel {
                background: transparent;
            }
            ModuleCard QCheckBox {
                background: transparent;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self._on_state_changed)
        layout.addWidget(self.checkbox)

        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        # Module name
        name_label = QLabel(name)
        name_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        text_layout.addWidget(name_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #a0a0a0;")
        desc_label.setWordWrap(True)
        text_layout.addWidget(desc_label)

        # Dependencies hint
        if self.requires:
            deps_text = f"Requires: {', '.join(self.requires)}"
            deps_label = QLabel(deps_text)
            deps_label.setStyleSheet("color: #6a9fb5; font-style: italic;")
            text_layout.addWidget(deps_label)

        layout.addLayout(text_layout, 1)

        self.setLayout(layout)

    def _on_state_changed(self, state):
        is_checked = state == Qt.CheckState.Checked.value
        self.toggled.emit(self.module_id, is_checked)

    def set_checked(self, checked: bool):
        """Set the checkbox state without emitting signal"""
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(checked)
        self.checkbox.blockSignals(False)

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()


class BeaconBuilderWidget(QWidget):
    """Widget for building custom beacons with module selection"""

    beacon_built = pyqtSignal(str, str)  # code, schema_path
    schema_created = pyqtSignal(str)  # schema_filename - emitted when a new schema is generated

    def __init__(self):
        super().__init__()

        # Initialize service
        if BeaconBuilderService:
            self.service = BeaconBuilderService()
        else:
            self.service = None

        # Track selected modules
        self.selected_modules = set()

        # Category widgets
        self.category_widgets = {}
        self.module_cards = {}

        # Setup font management
        if FontManager:
            try:
                font_manager = FontManager()
                font_manager.add_relative_font_widget(self, 0)
            except:
                pass

        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Header with title and language selector (stacked vertically, left-aligned)
        header_layout = QVBoxLayout()
        header_layout.setSpacing(8)

        title_label = QLabel("Beacon Builder")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        # Language selector row (left-aligned)
        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)

        lang_label = QLabel("Language:")
        lang_row.addWidget(lang_label)

        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(120)
        self.populate_languages()
        self.language_combo.currentTextChanged.connect(self.on_language_changed)
        lang_row.addWidget(self.language_combo)

        lang_row.addStretch()  # Push everything to the left
        header_layout.addLayout(lang_row)

        layout.addLayout(header_layout)

        # Main content splitter (2 columns: Modules | Configuration)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Module selection (larger)
        module_panel = self.create_module_panel()
        splitter.addWidget(module_panel)

        # Right panel - Configuration
        config_panel = self.create_config_panel()
        splitter.addWidget(config_panel)

        # Set initial sizes - modules panel is larger
        splitter.setSizes([500, 300])
        splitter.setStretchFactor(0, 2)  # Modules stretch more
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

        # Bottom bar with build button
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.build_btn = QPushButton("Build Beacon")
        self.build_btn.clicked.connect(self.build_beacon)
        self.build_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a7c4e;
                color: white;
                padding: 10px 24px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #35996b;
            }
            QPushButton:pressed {
                background-color: #1f5c3a;
            }
        """)
        bottom_layout.addWidget(self.build_btn)

        layout.addLayout(bottom_layout)

        self.setLayout(layout)

        # Initialize with first language
        if self.language_combo.count() > 0:
            self.on_language_changed(self.language_combo.currentText())

    def create_module_panel(self):
        """Create the module selection panel with categorized modules"""
        # Container widget with label + bordered frame
        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        # Title row with label and buttons
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title_label = QLabel("Modules")
        title_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        title_row.addWidget(title_label)

        # Select All button
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_modules)
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                padding: 2px 8px;
                font-size: 11px;
            }
        """)
        title_row.addWidget(self.select_all_btn)

        # Deselect All button
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all_modules)
        self.deselect_all_btn.setStyleSheet("""
            QPushButton {
                padding: 2px 8px;
                font-size: 11px;
            }
        """)
        title_row.addWidget(self.deselect_all_btn)

        title_row.addStretch()
        container_layout.addLayout(title_row)

        # Bordered frame for content
        frame = QFrame()
        frame.setObjectName("modulesFrame")
        frame.setStyleSheet("""
            #modulesFrame {
                border: 1px solid #404040;
                border-radius: 4px;
                background-color: #1e1e1e;
            }
            #modulesFrame QScrollArea, #modulesFrame QWidget, #modulesFrame QLabel {
                border: none;
            }
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)

        # Scroll area for modules with dark background
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.modules_container = QWidget()
        self.modules_container.setObjectName("modulesContainer")
        self.modules_container.setStyleSheet("#modulesContainer { background-color: #1e1e1e; }")
        self.modules_layout = QVBoxLayout()
        self.modules_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.modules_layout.setSpacing(2)
        self.modules_layout.setContentsMargins(6, 6, 6, 6)
        self.modules_container.setLayout(self.modules_layout)

        scroll.setWidget(self.modules_container)
        layout.addWidget(scroll)

        frame.setLayout(layout)
        container_layout.addWidget(frame, 1)  # stretch factor 1 to fill space
        container.setLayout(container_layout)
        return container

    def create_config_panel(self):
        """Create the configuration panel with config options and summary"""
        # Container widget
        container = QWidget()
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(8)

        # === Configuration Section ===
        config_title = QLabel("Configuration")
        config_title.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        container_layout.addWidget(config_title)

        # Bordered frame for config options
        config_frame = QFrame()
        config_frame.setObjectName("configFrame")
        config_frame.setStyleSheet("""
            #configFrame {
                border: 1px solid #404040;
                border-radius: 4px;
                background-color: #1e1e1e;
            }
            #configFrame QScrollArea, #configFrame QWidget, #configFrame QLabel {
                border: none;
            }
        """)
        config_frame_layout = QVBoxLayout()
        config_frame_layout.setContentsMargins(4, 4, 4, 4)

        # Scroll area for config options
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.config_container = QWidget()
        self.config_container.setObjectName("configContainer")
        self.config_container.setStyleSheet("#configContainer { background-color: #1e1e1e; }")
        self.config_layout = QGridLayout()
        self.config_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.config_layout.setSpacing(8)
        self.config_container.setLayout(self.config_layout)

        scroll.setWidget(self.config_container)
        config_frame_layout.addWidget(scroll)
        config_frame.setLayout(config_frame_layout)
        container_layout.addWidget(config_frame, 1)

        # === Summary Section ===
        summary_title = QLabel("Summary")
        summary_title.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        container_layout.addWidget(summary_title)

        # Bordered frame for summary
        summary_frame = QFrame()
        summary_frame.setObjectName("summaryFrame")
        summary_frame.setStyleSheet("""
            #summaryFrame {
                border: 1px solid #404040;
                border-radius: 4px;
                background-color: #1e1e1e;
            }
            #summaryFrame QLabel {
                border: none;
            }
        """)
        summary_layout = QVBoxLayout()
        summary_layout.setContentsMargins(8, 8, 8, 8)
        summary_layout.setSpacing(4)

        # Selected modules list
        self.summary_modules_label = QLabel("No modules selected")
        self.summary_modules_label.setStyleSheet("color: #a0a0a0;")
        self.summary_modules_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_modules_label)

        # Estimated size
        self.estimated_size_label = QLabel("Estimated size: 0 KB")
        self.estimated_size_label.setStyleSheet("color: #888888; margin-top: 4px;")
        summary_layout.addWidget(self.estimated_size_label)

        summary_frame.setLayout(summary_layout)
        container_layout.addWidget(summary_frame)

        container.setLayout(container_layout)
        return container

    def populate_languages(self):
        """Populate the language dropdown"""
        self.language_combo.clear()

        if self.service:
            languages = self.service.get_languages()
            for lang in languages:
                self.language_combo.addItem(lang.upper(), lang)
        else:
            # Default to AHK if service not available
            self.language_combo.addItem("AHK", "ahk")

    def on_language_changed(self, language: str):
        """Handle language selection change"""
        if not self.service:
            return

        lang_code = self.language_combo.currentData() or language.lower()
        if self.service.set_language(lang_code):
            self.refresh_modules()
            self.refresh_config()
            self.update_estimated_size()

    def refresh_modules(self):
        """Refresh the module list organized by category"""
        # Clear existing categories
        for widget in self.category_widgets.values():
            self.modules_layout.removeWidget(widget)
            widget.deleteLater()
        self.category_widgets.clear()
        self.module_cards.clear()
        self.selected_modules.clear()

        if not self.service:
            return

        modules = self.service.get_modules()

        # Define category order and display names
        category_order = [
            ('shell', 'Basic Execution'),
            ('file_operations', 'File Operations'),
            ('bof_execution', 'BOF Execution'),
            ('discovery', 'Discovery'),
            ('persistence', 'Persistence'),
            ('evasion', 'Defense Evasion'),
            ('privilege_escalation', 'Privilege Escalation'),
            ('lateral_movement', 'Lateral Movement'),
            ('collection', 'Collection'),
            ('impact', 'Impact'),
            ('management', 'Management'),
        ]

        # Create a mapping for category lookup
        category_display = {cat_id: display for cat_id, display in category_order}

        # Group modules by category
        modules_by_category = {}
        for module in modules:
            cat_id = module.get('category_id', 'other')
            if cat_id not in modules_by_category:
                modules_by_category[cat_id] = []
            modules_by_category[cat_id].append(module)

        # Add categories in order
        for cat_id, display_name in category_order:
            if cat_id not in modules_by_category:
                continue

            category_widget = CollapsibleCategory(display_name)

            for module in modules_by_category[cat_id]:
                card = ModuleCard(
                    module_id=module['id'],
                    name=module['name'],
                    description=module['description'],
                    requires=module.get('requires', [])
                )
                card.toggled.connect(self.on_module_toggled)
                category_widget.add_module(card)
                self.module_cards[module['id']] = card

            self.modules_layout.addWidget(category_widget)
            self.category_widgets[cat_id] = category_widget

        # Add any remaining categories not in our order
        for cat_id, cat_modules in modules_by_category.items():
            if cat_id in category_display:
                continue  # Already added

            display_name = cat_id.replace('_', ' ').title()
            category_widget = CollapsibleCategory(display_name)

            for module in cat_modules:
                card = ModuleCard(
                    module_id=module['id'],
                    name=module['name'],
                    description=module['description'],
                    requires=module.get('requires', [])
                )
                card.toggled.connect(self.on_module_toggled)
                category_widget.add_module(card)
                self.module_cards[module['id']] = card

            self.modules_layout.addWidget(category_widget)
            self.category_widgets[cat_id] = category_widget

        # Add stretch at the end
        self.modules_layout.addStretch()

    def select_all_modules(self):
        """Select all available modules"""
        for module_id, card in self.module_cards.items():
            if not card.is_checked():
                card.set_checked(True)
                self.selected_modules.add(module_id)

        # Update service selection
        if self.service:
            self.service.select_modules(list(self.selected_modules))

        self.refresh_config()
        self.update_estimated_size()

    def deselect_all_modules(self):
        """Deselect all modules"""
        for module_id, card in self.module_cards.items():
            if card.is_checked():
                card.set_checked(False)

        self.selected_modules.clear()

        # Update service selection
        if self.service:
            self.service.select_modules([])

        self.refresh_config()
        self.update_estimated_size()

    def on_module_toggled(self, module_id: str, is_checked: bool):
        """Handle module checkbox toggle"""
        if is_checked:
            self.selected_modules.add(module_id)

            # Auto-select dependencies
            if self.service:
                module = self.service.builder.get_module(module_id)
                if module:
                    for dep in module.requires:
                        if dep in self.module_cards:
                            self.module_cards[dep].set_checked(True)
                            self.selected_modules.add(dep)
        else:
            self.selected_modules.discard(module_id)

        # Update service selection
        if self.service:
            self.service.select_modules(list(self.selected_modules))

        self.refresh_config()
        self.update_estimated_size()

    def refresh_config(self):
        """Refresh the configuration options"""
        # Clear existing config
        while self.config_layout.count():
            item = self.config_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.config_widgets = {}

        if not self.service:
            return

        # Add default config options
        default_configs = [
            ('server_ip', 'Server IP', 'string', '127.0.0.1'),
            ('server_port', 'Server Port', 'integer', 5074),
            ('checkin_interval', 'Check-in Interval (seconds)', 'integer', 15),
        ]

        row = 0
        for key, label, opt_type, default in default_configs:
            label_widget = QLabel(f"{label}:")
            label_widget.setStyleSheet("color: #e0e0e0;")
            self.config_layout.addWidget(label_widget, row, 0)

            if opt_type == 'integer':
                widget = QSpinBox()
                widget.setRange(1, 99999999)
                widget.setValue(default)
            else:
                widget = QLineEdit()
                widget.setText(str(default))

            self.config_layout.addWidget(widget, row, 1)
            self.config_widgets[key] = widget
            row += 1

        # Add module-specific config options
        options = self.service.get_config_options()
        for key, opt in options.items():
            if key in self.config_widgets:
                continue  # Skip if already added

            label = QLabel(f"{opt.get('label', key)}:")
            label.setStyleSheet("color: #e0e0e0;")
            self.config_layout.addWidget(label, row, 0)

            opt_type = opt.get('type', 'string')
            default = opt.get('default', '')

            if opt_type == 'integer':
                widget = QSpinBox()
                widget.setRange(1, 99999999)
                widget.setValue(int(default) if default else 0)
            elif opt_type == 'boolean':
                widget = QCheckBox()
                widget.setChecked(bool(default))
            elif opt_type == 'choice':
                widget = QComboBox()
                choices = opt.get('choices', [])
                for choice in choices:
                    widget.addItem(str(choice).upper(), choice)
                # Set default selection
                if default:
                    index = widget.findData(default)
                    if index >= 0:
                        widget.setCurrentIndex(index)
            else:
                widget = QLineEdit()
                widget.setText(str(default))

            self.config_layout.addWidget(widget, row, 1)
            self.config_widgets[key] = widget
            row += 1

    def get_config(self) -> dict:
        """Get current configuration values"""
        config = {}
        for key, widget in self.config_widgets.items():
            if isinstance(widget, QSpinBox):
                config[key] = widget.value()
            elif isinstance(widget, QCheckBox):
                config[key] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                config[key] = widget.text()
            elif isinstance(widget, QComboBox):
                config[key] = widget.currentData() or widget.currentText()
        return config

    def update_estimated_size(self):
        """Update the estimated size label and summary"""
        if self.service:
            size_bytes = self.service.get_estimated_size()
            size_kb = size_bytes / 1024
            self.estimated_size_label.setText(f"Estimated size: {size_kb:.1f} KB")

        # Update selected modules summary
        self.update_summary()

    def update_summary(self):
        """Update the summary with selected modules"""
        if not self.selected_modules:
            self.summary_modules_label.setText("No modules selected")
            return

        # Get module names for selected modules
        module_names = []
        for module_id in sorted(self.selected_modules):
            if module_id in self.module_cards:
                module_names.append(self.module_cards[module_id].module_name)
            else:
                module_names.append(module_id)

        # Display with "Modules:" prefix and bullet separators
        modules_text = "Modules:  " + "  •  ".join(module_names)
        self.summary_modules_label.setText(modules_text)

    def build_beacon(self):
        """Build the beacon and save to file with auto-generated schema"""
        if not self.service:
            QMessageBox.warning(self, "Error", "Beacon builder service not available")
            return

        config = self.get_config()

        # Get save path for beacon using language-specific extension
        from beacon_builder.builder import get_language_config
        lang_config = get_language_config(self.service.current_language)
        file_ext = lang_config.file_extension  # e.g., '.py', '.ahk'
        file_filter_map = {
            'ahk': "AutoHotkey Script (*.ahk)",
            'python': "Python Script (*.py)",
            'javascript': "JavaScript File (*.js)",
            'go': "Go Source (*.go)",
            'lua': "Lua Script (*.lua)",
            'vbs': "VBScript (*.vbs)",
            'powershell': "PowerShell Script (*.ps1)",
            'bash': "Shell Script (*.sh)",
        }
        file_filter = file_filter_map.get(self.service.current_language, f"All Files (*{file_ext})")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Beacon",
            f"custom_beacon{file_ext}",
            file_filter
        )

        if not file_path:
            return

        try:
            # Use the new build_and_save_with_schema to auto-save both files
            result = self.service.build_and_save_with_schema(config, file_path)

            QMessageBox.information(
                self,
                "Build Successful",
                f"Beacon saved to:\n{result['beacon_path']}\n\n"
                f"Schema saved to:\n{result['schema_path']}\n\n"
                f"Schema filename: {result['schema_filename']}\n\n"
                f"The beacon will automatically register with this schema."
            )
            self.beacon_built.emit("", file_path)

            # Notify that a new schema was created so other widgets can refresh
            self.schema_created.emit(result['schema_filename'])

        except Exception as e:
            QMessageBox.critical(self, "Build Error", str(e))
