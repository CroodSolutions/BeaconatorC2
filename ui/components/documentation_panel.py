import re
import yaml
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QFrame, QApplication, QSplitter, 
                            QPushButton, QMessageBox, QLabel)
from PyQt6.QtCore import Qt, QPropertyAnimation
from PyQt6.QtGui import (QColor, QFont, QTextCursor, QTextCharFormat, 
                        QTextBlockFormat, QFontDatabase)
from utils import DocumentationManager, FontManager

class DocumentationPanel(QWidget):
    def __init__(self, doc_manager: DocumentationManager, command_widget=None):
        super().__init__()
        self.doc_manager = doc_manager
        self.command_widget = command_widget  # Reference to command widget for visibility updates
        self.expanded = False
        self.min_width = 0
        self.default_width = 500
        self.max_width = 900
        self.current_width = self.default_width
        self.resize_active = False
        self.current_module = None  # Track currently displayed module
        self.current_module_yaml_data = None  # Track current module YAML data
        self.current_category_name = None  # Track current category
        self.current_module_name = None  # Track current module name
        
        # Try to use FontManager, but don't fail if it's not available
        try:
            self.font_manager = FontManager()
        except:
            self.font_manager = None
        
        self.header_colors = {
            1: '#fb713f',  
            2: '#2dd35f',  
            3: '#2dd35f',  
            4: '#ff4d4d',  
            5: '#4ECDC4'   
        }
        
        self.setup_ui()
        self.setup_font_handling()
        
        self.setMaximumWidth(self.min_width)
        self.setFixedWidth(self.min_width)
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create splitter for documentation and YAML sections
        self.content_splitter = QSplitter(Qt.Orientation.Vertical)
        self.content_splitter.setStyleSheet("""
            QSplitter {
                background-color: #232323;
            }
        """)
        
        # Documentation view (read-only)
        self.doc_view = QTextEdit()
        self.doc_view.setReadOnly(True)
        self.doc_view.setStyleSheet("""
            QTextEdit {
                background-color: #232323;
                border: none;
            }
        """)
        
        # YAML editor section with controls
        yaml_container = QWidget()
        yaml_container.setStyleSheet("""
            QWidget {
                background-color: #232323;
                border: none;
            }
        """)
        yaml_layout = QVBoxLayout()
        yaml_layout.setContentsMargins(0, 0, 0, 0)
        yaml_layout.setSpacing(5)
        
        # YAML editor header with buttons
        yaml_header = QHBoxLayout()
        yaml_header.setContentsMargins(5, 5, 5, 0)
        
        yaml_label = QLabel("Module Configuration")
        yaml_label.setStyleSheet("color: #f8f8f2; font-weight: bold; font-size: 12px;")
        yaml_header.addWidget(yaml_label)
        yaml_header.addStretch()
        
        # Save & Apply buttons
        self.save_button = QPushButton("Save")
        self.save_button.setFixedSize(60, 25)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                font-size: 10px;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        self.save_button.clicked.connect(self.save_yaml_changes)
        self.save_button.setEnabled(False)
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.setFixedSize(60, 25)
        self.apply_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                border: none;
                color: white;
                font-size: 10px;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
        """)
        self.apply_button.clicked.connect(self.apply_yaml_changes)
        self.apply_button.setEnabled(False)
        
        yaml_header.addWidget(self.save_button)
        yaml_header.addWidget(self.apply_button)
        
        # YAML editor (editable)
        self.yaml_editor = QTextEdit()
        self.yaml_editor.setPlaceholderText("Module YAML content will appear here...")
        self.yaml_editor.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #404040;
                color: #f8f8f2;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
            }
        """)
        
        # Track changes to enable/disable buttons
        self.yaml_editor.textChanged.connect(self.on_yaml_content_changed)
        
        yaml_layout.addLayout(yaml_header)
        yaml_layout.addWidget(self.yaml_editor)
        yaml_container.setLayout(yaml_layout)
        
        # Add both to splitter
        self.content_splitter.addWidget(self.doc_view)
        self.content_splitter.addWidget(yaml_container)
        self.content_splitter.setSizes([300, 200])  # Documentation gets more space initially
        
        # Add resize handle area with visual indicator
        self.resize_area = QWidget()
        self.resize_area.setFixedWidth(12)
        self.resize_area.setCursor(Qt.CursorShape.SizeHorCursor)

        # Create grip layout
        grip_layout = QVBoxLayout()
        grip_layout.setContentsMargins(4, 0, 4, 0)
        grip_layout.setSpacing(2)

        # Add dot indicators to the center of the resize area
        dots_container = QWidget()
        dots_layout = QVBoxLayout()
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(4)

        for _ in range(5):
            dot = QFrame()
            dot.setFixedSize(2, 2)
            dot.setStyleSheet("""
                QFrame {
                    background-color: #666666;
                    border-radius: 1px;
                }
            """)
            dots_layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignCenter)

        # Add stretchers to center the dots vertically
        dots_layout.addStretch()
        dots_layout.insertStretch(0)

        dots_container.setLayout(dots_layout)
        grip_layout.addWidget(dots_container)
        self.resize_area.setLayout(grip_layout)

        self.resize_area.setStyleSheet("""
            QWidget {
                background-color: #232323;
                border: none;
            }
        """)
        
        container = QHBoxLayout()
        container.setContentsMargins(0, 0, 0, 0)
        container.setSpacing(0)
        container.addWidget(self.content_splitter)
        container.addWidget(self.resize_area)
        
        layout.addLayout(container)
        self.setLayout(layout)
        
        self.resize_area.mousePressEvent = self.start_resize
        self.resize_area.mouseReleaseEvent = self.stop_resize
        self.resize_area.mouseMoveEvent = self.do_resize

    def setup_font_handling(self):
        # Store the original content for reformatting
        self.original_content = ""
        if self.font_manager:
            self.font_manager.add_relative_font_widget(self.doc_view, -2)
            self.font_manager.add_font_update_callback(self.refresh_formatting)

    def convert_markdown_to_rich_text(self, markdown_text: str):
        self.original_content = markdown_text
        self.doc_view.clear()
        cursor = self.doc_view.textCursor()
        
        app_font_size = QApplication.instance().font().pointSize()
        base_size = app_font_size - 2

        # Line spacing configuration
        HEADER_LINE_HEIGHT = 125
        CODE_LINE_HEIGHT = 100
        NORMAL_LINE_HEIGHT = 110
        PROPORTIONAL_HEIGHT = 1  # PyQt6 constant for proportional height

        size_adjustments = {1: 10, 2: 8, 3: 7, 4: 6, 5: 4}

        blocks = []
        current_block = []
        in_code_block = False
        
        for line in markdown_text.split('\n'):
            if line.strip().startswith('```'):
                if in_code_block:
                    current_block.append(line)
                    blocks.append(('\n'.join(current_block), 'code_block'))
                    current_block = []
                    in_code_block = False
                else:
                    if current_block:
                        blocks.append(('\n'.join(current_block), 'normal'))
                    current_block = [line]
                    in_code_block = True
            else:
                current_block.append(line)
        
        if current_block:
            blocks.append(('\n'.join(current_block), 'normal'))

        for content, block_type in blocks:
            if block_type == 'code_block':
                lines = content.split('\n')
                code_content = '\n'.join(lines[1:-1])
                
                block_format = QTextBlockFormat()
                block_format.setBackground(QColor('#1E1E1E'))
                block_format.setTopMargin(0)
                block_format.setBottomMargin(0)
                block_format.setLeftMargin(20)
                block_format.setRightMargin(20)
                block_format.setLineHeight(CODE_LINE_HEIGHT, PROPORTIONAL_HEIGHT)
                cursor.setBlockFormat(block_format)
                
                code_format = QTextCharFormat()
                code_format.setFontFamily('Consolas')
                code_format.setFontPointSize(base_size)
                code_format.setForeground(QColor('#E0E0E0'))
                cursor.insertText(code_content, code_format)
                cursor.insertBlock()
            else:
                for line in content.split('\n'):
                    # Handle bullet points
                    bullet_match = re.match(r'^(\s*)-\s+(.+)$', line)
                    if bullet_match:
                        indent_level = len(bullet_match.group(1)) // 2
                        content = bullet_match.group(2)
                        
                        block_format = QTextBlockFormat()
                        block_format.setTopMargin(4)
                        block_format.setBottomMargin(4)
                        block_format.setLeftMargin(20 * (indent_level + 1))
                        block_format.setTextIndent((base_size * -1))
                        block_format.setLineHeight(NORMAL_LINE_HEIGHT, PROPORTIONAL_HEIGHT)
                        cursor.setBlockFormat(block_format)
                        
                        bullet_format = QTextCharFormat()
                        try:
                            bullet_format.setFontFamily(QFontDatabase.families()[0])
                        except:
                            pass
                        bullet_format.setFontPointSize(base_size)
                        bullet_format.setForeground(QColor('#F8F8F2'))
                        
                        cursor.insertText("• ", bullet_format)
                        
                        # Process inline formatting
                        parts = re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', content)
                        for part in parts:
                            code_match = re.match(r'`([^`]+)`', part)
                            bold_match = re.match(r'\*\*([^*]+)\*\*', part)
                            
                            if code_match:
                                code_format = QTextCharFormat()
                                try:
                                    code_format.setFontFamily(QFontDatabase.families()[1])
                                except:
                                    pass
                                code_format.setFontPointSize(base_size - 1)
                                code_format.setForeground(QColor('#edc0c0'))
                                cursor.insertText(code_match.group(1), code_format)
                            elif bold_match:
                                bold_format = QTextCharFormat()
                                bold_format.setFontPointSize(base_size)
                                bold_format.setFontWeight(QFont.Weight.Bold)
                                bold_format.setForeground(QColor('#F8F8F2'))
                                cursor.insertText(bold_match.group(1), bold_format)
                            else:
                                text_format = QTextCharFormat()
                                text_format.setFontPointSize(base_size)
                                try:
                                    text_format.setFontFamily(QFontDatabase.families()[0])
                                except:
                                    pass
                                text_format.setForeground(QColor('#F8F8F2'))
                                cursor.insertText(part, text_format)
                        
                        cursor.insertBlock()
                        continue
                    
                    # Handle headers
                    header_match = re.match(r'^(#{1,5})\s+(.+)$', line)
                    if header_match:
                        level = len(header_match.group(1))
                        content = header_match.group(2)
                        
                        block_format = QTextBlockFormat()
                        block_format.setTopMargin(10)
                        block_format.setBottomMargin(4)
                        block_format.setLineHeight(HEADER_LINE_HEIGHT, PROPORTIONAL_HEIGHT)
                        cursor.setBlockFormat(block_format)
                        
                        # Create and configure a QFont object
                        header_font = QFont()
                        try:
                            header_font.setFamily(QFontDatabase.families()[2])
                        except:
                            pass
                        header_font.setPointSize(base_size + size_adjustments.get(level, 0))
                        header_font.setWeight(QFont.Weight.Bold)
                        
                        char_format = QTextCharFormat()
                        char_format.setFont(header_font)
                        char_format.setForeground(QColor(self.header_colors[level]))
                        
                        cursor.insertText(content, char_format)
                        cursor.insertBlock()
                        continue
                    
                    # Handle regular text
                    block_format = QTextBlockFormat()
                    block_format.setTopMargin(8)
                    block_format.setBottomMargin(8)
                    block_format.setLineHeight(NORMAL_LINE_HEIGHT, PROPORTIONAL_HEIGHT)
                    cursor.setBlockFormat(block_format)
                    
                    parts = re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', line)
                    for part in parts:
                        code_match = re.match(r'`([^`]+)`', part)
                        bold_match = re.match(r'\*\*([^*]+)\*\*', part)
                        
                        if code_match:
                            code_format = QTextCharFormat()
                            try:
                                code_format.setFontFamily(QFontDatabase.families()[1])
                            except:
                                pass
                            code_format.setFontPointSize(base_size - 1)
                            code_format.setForeground(QColor('#edc0c0'))
                            cursor.insertText(code_match.group(1), code_format)
                        elif bold_match:
                            bold_format = QTextCharFormat()
                            bold_format.setFontPointSize(base_size)
                            bold_format.setFontWeight(QFont.Weight.Bold)
                            try:
                                bold_format.setFontFamily(QFontDatabase.families()[0])
                            except:
                                pass
                            bold_format.setForeground(QColor('#F8F8F2'))
                            cursor.insertText(bold_match.group(1), bold_format)
                        else:
                            text_format = QTextCharFormat()
                            text_format.setFontPointSize(base_size)
                            try:
                                text_format.setFontFamily(QFontDatabase.families()[0])
                            except:
                                pass
                            text_format.setForeground(QColor('#F8F8F2'))
                            cursor.insertText(part, text_format)
                    
                    if line.strip():
                        cursor.insertBlock()

    def refresh_formatting(self):
        if hasattr(self, 'original_content') and self.original_content:
            self.convert_markdown_to_rich_text(self.original_content)

    def set_content(self, section_name: str):
        content = self.doc_manager.get_section(section_name)
        self.convert_markdown_to_rich_text(content)
        self.doc_view.verticalScrollBar().setValue(0)
    
    def set_module_documentation(self, module, module_yaml_data: dict, category_name: str = None, module_name: str = None):
        """Display module documentation and YAML content"""
        # Track the currently displayed module and its context
        self.current_module = module
        self.current_module_yaml_data = module_yaml_data.copy()  # Store original for comparison
        self.current_category_name = category_name
        self.current_module_name = module_name
        
        # Reset button states
        self.save_button.setEnabled(False)
        self.apply_button.setEnabled(False)
        
        # Format documentation section
        doc_content = f"#### {module.display_name}\n\n"
        
        if module.documentation.content:
            doc_content += f"\n\n{module.documentation.content}\n\n"
        else:
            doc_content += f"**Description:** {module.description}\n\n"
        
        if module.documentation.examples:
            doc_content += "##### Examples\n\n"
            for example in module.documentation.examples:
                doc_content += f"- {example}\n"
            doc_content += "\n"
        
        if module.execution.requires_admin:
            doc_content += "⚠️ **Requires Administrator Privileges**\n\n"
        
        doc_content += f"**Timeout:** {module.execution.timeout} seconds\n\n"
        
        if module.parameters:
            doc_content += "##### Parameters\n\n"
            for param_name, param in module.parameters.items():
                required_text = "**Required**" if param.required else "Optional"
                doc_content += f"- **{param.display_name}** ({param.type.value}) - {required_text}\n"
                doc_content += f"  {param.description}\n"
                if param.default is not None:
                    doc_content += f"  Default: `{param.default}`\n"
                doc_content += "\n"
        
        # Display the formatted documentation
        self.convert_markdown_to_rich_text(doc_content)
        self.doc_view.verticalScrollBar().setValue(0)
        
        # Display the YAML content in the editor
        try:
            yaml_content = yaml.dump(module_yaml_data, default_flow_style=False, indent=2, sort_keys=False)
            self.yaml_editor.setPlainText(yaml_content)
        except Exception as e:
            self.yaml_editor.setPlainText(f"Error displaying YAML: {e}")
    
    def get_yaml_content(self) -> str:
        """Get the current YAML content from the editor"""
        return self.yaml_editor.toPlainText()
    
    def on_yaml_content_changed(self):
        """Handle YAML content changes to enable/disable buttons"""
        if not self.current_module or not self.current_module_yaml_data:
            return
            
        current_content = self.yaml_editor.toPlainText().strip()
        
        try:
            # Try to parse current content to check if it's valid YAML
            current_yaml = yaml.safe_load(current_content) if current_content else {}
            original_yaml = self.current_module_yaml_data
            
            # Check if content has changed
            has_changed = current_yaml != original_yaml
            
            # Enable buttons if content changed and is valid YAML
            self.save_button.setEnabled(has_changed)
            self.apply_button.setEnabled(has_changed)
            
        except yaml.YAMLError:
            # Invalid YAML - disable apply but allow save for fixing
            self.save_button.setEnabled(True)
            self.apply_button.setEnabled(False)
    
    def save_yaml_changes(self):
        """Save YAML changes to file"""
        if not self.current_module or not self.command_widget:
            QMessageBox.warning(self, "Error", "No module selected or command widget not available")
            return
        
        try:
            # Validate YAML syntax
            yaml_content = self.yaml_editor.toPlainText()
            parsed_yaml = yaml.safe_load(yaml_content) if yaml_content.strip() else {}
            
            # Get schema service from command widget
            schema_service = self.command_widget.schema_service
            schema_file = self.command_widget._loaded_schema_file
            
            if not schema_file:
                QMessageBox.warning(self, "Error", "No schema file loaded")
                return
            
            # Update the specific module in the schema file
            self._update_module_in_schema_file(schema_service, schema_file, 
                                             self.current_category_name, 
                                             self.current_module_name, 
                                             parsed_yaml)
            
            # Update cache with the new module data (more efficient than full invalidation)
            schema_path = schema_service.schemas_directory / schema_file
            schema_service.cache.update_module_cache(schema_file, schema_path,
                                                   self.current_category_name,
                                                   self.current_module_name,
                                                   parsed_yaml)
            
            # Update our stored reference
            self.current_module_yaml_data = parsed_yaml.copy()
            
            # Reset button states
            self.save_button.setEnabled(False)
            self.apply_button.setEnabled(False)
            
        except yaml.YAMLError as e:
            QMessageBox.warning(self, "YAML Error", f"Invalid YAML syntax: {e}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save changes: {e}")
    
    def apply_yaml_changes(self):
        """Apply YAML changes (save + reload schema)"""
        try:
            # First save the changes
            self.save_yaml_changes()
            
            # Then invalidate cache and reload schema for the current beacon
            if self.command_widget and self.command_widget.current_beacon_id:
                schema_service = self.command_widget.schema_service
                schema_file = self.command_widget._loaded_schema_file
                current_beacon_id = self.command_widget.current_beacon_id
                
                if schema_file:
                    # Invalidate the specific schema in cache
                    schema_service.cache.invalidate(schema_file)
                    
                    # Clear UI cache to force rebuild
                    self.command_widget._ui_built_for_schema = None
                    
                    # Reload the schema with force_reload=True to bypass early exit conditions
                    self.command_widget.set_agent(current_beacon_id, force_reload=True)
                    
                    QMessageBox.information(self, "Success", 
                                          "Module configuration applied successfully.\n"
                                          "The interface has been updated with your changes.")
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to apply changes: {e}")
    
    def _update_module_in_schema_file(self, schema_service, schema_file: str, 
                                    category_name: str, module_name: str, 
                                    new_module_data: dict):
        """Update a specific module in the schema file"""
        schema_path = schema_service.schemas_directory / schema_file
        
        # Read the current schema file
        with open(schema_path, 'r', encoding='utf-8') as file:
            schema_data = yaml.safe_load(file)
        
        # Navigate to the module and update it
        if 'categories' not in schema_data:
            schema_data['categories'] = {}
        
        if category_name not in schema_data['categories']:
            schema_data['categories'][category_name] = {}
        
        if 'modules' not in schema_data['categories'][category_name]:
            schema_data['categories'][category_name]['modules'] = {}
        
        # Update the specific module
        schema_data['categories'][category_name]['modules'][module_name] = new_module_data
        
        # Write back to file
        with open(schema_path, 'w', encoding='utf-8') as file:
            yaml.dump(schema_data, file, default_flow_style=False, indent=2, sort_keys=False)
    
    def clear_content(self):
        """Clear both documentation and YAML content"""
        self.doc_view.clear()
        self.yaml_editor.clear()
        self.current_module = None
        
    def start_resize(self, event):
        if self.expanded:
            self.resize_active = True
            self.resize_start_x = event.globalPosition().x()
            self.resize_start_width = self.width()

    def stop_resize(self, event):
        self.resize_active = False
        if self.expanded:
            self.current_width = self.width()

    def do_resize(self, event):
        if self.resize_active:
            delta = event.globalPosition().x() - self.resize_start_x
            new_width = min(max(self.resize_start_width + delta, 200), self.max_width)
            self.setFixedWidth(int(new_width))

    def toggle_panel(self):
        self.expanded = not self.expanded
        new_width = self.current_width if self.expanded else self.min_width
        
        if self.expanded:
            self.show()
            self.setMaximumWidth(self.max_width)
            self.doc_view.verticalScrollBar().setValue(0)
        
        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(200)
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(new_width)
        
        self.max_animation = QPropertyAnimation(self, b"maximumWidth")
        self.max_animation.setDuration(200)
        self.max_animation.setStartValue(self.width())
        self.max_animation.setEndValue(new_width)
        
        self.animation.finished.connect(self.handle_animation_finished)
        
        self.animation.start()
        self.max_animation.start()
    
    def handle_animation_finished(self):
        if not self.expanded:
            self.hide()
            # Clear current module when panel is hidden
            self.current_module = None
        # Notify command widget of visibility change
        if self.command_widget:
            self.command_widget.update_documentation_visibility()
    
    def show_panel(self):
        self.show()
        if not self.expanded:
            self.toggle_panel()
        # Notify command widget of visibility change
        if self.command_widget:
            self.command_widget.update_documentation_visibility()
            
    def hide_panel(self):
        if self.expanded:
            self.toggle_panel()
    
    def is_visible(self):
        """Check if the panel is currently expanded/visible"""
        return self.expanded
    
    def is_showing_module(self, module):
        """Check if the panel is currently showing documentation for the specified module"""
        return self.expanded and self.current_module == module

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.expanded:
            self.preferred_width = event.size().width()