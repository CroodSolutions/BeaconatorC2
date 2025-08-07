"""
Variables Content Widget

Extracted from VariablesPanel to work within the unified SidePanel system.
Handles workflow variable management with inline editing and add/delete functionality.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                            QScrollArea, QFrame, QLineEdit, QMessageBox, QSizePolicy,
                            QListWidget, QListWidgetItem, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from typing import Dict, Any


class VariableListItem(QWidget):
    """Custom widget for displaying and editing a single variable"""
    
    variable_changed = pyqtSignal(str, str, str)  # old_name, new_name, new_value
    variable_deleted = pyqtSignal(str)  # variable_name
    
    def __init__(self, name: str, value: Any, parent=None):
        super().__init__(parent)
        self.original_name = name
        self.setup_ui(name, value)
        
    def setup_ui(self, name: str, value: Any):
        """Set up the variable item UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Variable name field
        self.name_field = QLineEdit(name)
        self.name_field.setPlaceholderText("Variable name")
        self.name_field.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 6px;
                border-radius: 3px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border-color: #4a90e2;
            }
        """)
        self.name_field.textChanged.connect(self._on_name_changed)
        layout.addWidget(self.name_field, 1)
        
        # Equals label
        equals_label = QLabel("=")
        equals_label.setStyleSheet("color: #cccccc; font-weight: bold; font-size: 12px;")
        layout.addWidget(equals_label)
        
        # Variable value field
        self.value_field = QLineEdit(str(value))
        self.value_field.setPlaceholderText("Variable value")
        self.value_field.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                border: 1px solid #666666;
                color: white;
                padding: 6px;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border-color: #4a90e2;
            }
        """)
        self.value_field.textChanged.connect(self._on_value_changed)
        layout.addWidget(self.value_field, 2)
        
        # Delete button with × character
        self.delete_button = QPushButton("×")
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setToolTip("Delete variable")
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                border: none;
                border-radius: 3px;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.delete_button)
        
        self.setLayout(layout)
        
    def _on_name_changed(self):
        """Handle variable name change"""
        old_name = self.original_name
        new_name = self.name_field.text().strip()
        new_value = self.value_field.text()
        
        if new_name and new_name != old_name:
            self.original_name = new_name
            self.variable_changed.emit(old_name, new_name, new_value)
            
    def _on_value_changed(self):
        """Handle variable value change"""
        name = self.name_field.text().strip()
        value = self.value_field.text()
        
        if name:
            self.variable_changed.emit(name, name, value)  # Same name, new value
            
    def _on_delete_clicked(self):
        """Handle delete button click"""
        name = self.name_field.text().strip()
        if name:
            self.variable_deleted.emit(name)
            
    def get_variable_data(self) -> tuple[str, str]:
        """Get current variable name and value"""
        return self.name_field.text().strip(), self.value_field.text()


class VariablesContent(QWidget):
    """Content widget for variable management within unified side panel"""
    
    # Signals
    variables_updated = pyqtSignal(dict)  # Updated variables dict
    close_requested = pyqtSignal()  # close panel requested
    
    def __init__(self, parent=None):
        super().__init__()
        self.canvas = None  # Will be set by parent panel
        self.variable_items = {}  # name -> VariableListItem
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the content UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Variables info header
        self.create_info_header()
        layout.addWidget(self.info_header)
        
        # Variables list area
        self.create_variables_area()
        layout.addWidget(self.variables_area)
        
        # Footer with add button
        self.create_footer()
        layout.addWidget(self.footer)
        
        self.setLayout(layout)
        
    def create_info_header(self):
        """Create the variables info header"""
        self.info_header = QFrame()
        self.info_header.setFixedHeight(50)
        self.info_header.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: none;
                border-bottom: 1px solid #555555;
            }
        """)
        
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(15, 10, 15, 10)
        
        # Info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        info_label = QLabel("Workflow Variables")
        info_label.setStyleSheet("""
            color: #ffffff;
            font-weight: bold;
            font-size: 14px;
        """)
        
        self.count_label = QLabel("0 variables")
        self.count_label.setStyleSheet("""
            color: #cccccc;
            font-size: 11px;
        """)
        
        info_layout.addWidget(info_label)
        info_layout.addWidget(self.count_label)
        header_layout.addLayout(info_layout)
        
        header_layout.addStretch()
        
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
        header_layout.addWidget(self.close_button)
        
        self.info_header.setLayout(header_layout)
        
    def create_variables_area(self):
        """Create the scrollable variables list area"""
        self.variables_area = QFrame()
        self.variables_area.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: none;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Scroll area for variables
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #2b2b2b;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #404040;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #888888;
            }
        """)
        
        # Container for variable items
        self.variables_container = QWidget()
        self.variables_layout = QVBoxLayout()
        self.variables_layout.setContentsMargins(0, 0, 0, 0)
        self.variables_layout.setSpacing(5)
        self.variables_layout.addStretch()  # Push items to top
        
        self.variables_container.setLayout(self.variables_layout)
        scroll_area.setWidget(self.variables_container)
        
        layout.addWidget(scroll_area)
        self.variables_area.setLayout(layout)
        
    def create_footer(self):
        """Create the footer with add button"""
        self.footer = QFrame()
        self.footer.setFixedHeight(60)
        self.footer.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border: none;
                border-top: 1px solid #555555;
            }
        """)
        
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(15, 10, 15, 10)
        
        # Add variable button
        self.add_button = QPushButton("+ Add Variable")
        self.add_button.setFixedHeight(35)
        self.add_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                border: none;
                color: white;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
                padding: 0 15px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.add_button.clicked.connect(self.add_variable)
        
        footer_layout.addWidget(self.add_button)
        footer_layout.addStretch()
        
        # Help text
        help_label = QLabel("Use {{variables.name}} in parameters")
        help_label.setStyleSheet("""
            color: #888888;
            font-size: 10px;
            font-style: italic;
        """)
        footer_layout.addWidget(help_label)
        
        self.footer.setLayout(footer_layout)
        
    def on_panel_shown(self):
        """Called when the panel is shown with variables content"""
        # Load current variables when panel is shown
        self.load_variables()
        
    def set_canvas(self, canvas):
        """Set the canvas reference for variable management"""
        self.canvas = canvas
        if canvas:
            # Load existing variables
            self.load_variables()
            
    def load_variables(self):
        """Load variables from canvas and populate the list"""
        if not self.canvas:
            return
            
        # Clear existing items
        self.clear_variables_list()
        
        # Add variables from canvas
        variables = self.canvas.get_all_variables()
        for name, value in variables.items():
            self._add_variable_item(name, value)
            
        self.update_count_label()
        
    def clear_variables_list(self):
        """Clear all variable items from the list"""
        # Remove all items except the stretch
        while self.variables_layout.count() > 1:
            child = self.variables_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        self.variable_items.clear()
        
    def add_variable(self):
        """Add a new variable"""
        name, ok = QInputDialog.getText(self, "Add Variable", "Variable name:")
        if ok and name.strip():
            name = name.strip()
            if name in self.variable_items:
                QMessageBox.warning(self, "Variable Exists", f"Variable '{name}' already exists.")
                return
                
            # Add to canvas
            if self.canvas:
                self.canvas.set_variable(name, "")
                
            # Add to UI
            self._add_variable_item(name, "")
            self.update_count_label()
            self.variables_updated.emit(self.canvas.get_all_variables() if self.canvas else {})
            
    def _add_variable_item(self, name: str, value: Any):
        """Add a variable item to the list"""
        item = VariableListItem(name, value)
        item.variable_changed.connect(self._on_variable_changed)
        item.variable_deleted.connect(self._on_variable_deleted)
        
        # Insert before the stretch item
        self.variables_layout.insertWidget(self.variables_layout.count() - 1, item)
        self.variable_items[name] = item
        
    def _on_variable_changed(self, old_name: str, new_name: str, new_value: str):
        """Handle variable change"""
        if not self.canvas:
            return
            
        # If name changed, remove old and add new
        if old_name != new_name:
            if old_name in self.variable_items:
                del self.variable_items[old_name]
                self.canvas.remove_variable(old_name)
                
            self.variable_items[new_name] = self.variable_items.get(old_name)
            
        # Update value
        self.canvas.set_variable(new_name, new_value)
        self.variables_updated.emit(self.canvas.get_all_variables())
        
    def _on_variable_deleted(self, name: str):
        """Handle variable deletion"""
        if not self.canvas:
            return
            
        reply = QMessageBox.question(
            self, "Delete Variable",
            f"Are you sure you want to delete variable '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Remove from canvas
            self.canvas.remove_variable(name)
            
            # Remove from UI
            if name in self.variable_items:
                item = self.variable_items[name]
                self.variables_layout.removeWidget(item)
                item.deleteLater()
                del self.variable_items[name]
                
            self.update_count_label()
            self.variables_updated.emit(self.canvas.get_all_variables())
            
    def update_count_label(self):
        """Update the count label"""
        count = len(self.variable_items)
        self.count_label.setText(f"{count} variable{'s' if count != 1 else ''}")
        
    def get_variable_count(self):
        """Get the current variable count"""
        return len(self.variable_items)
        
    def close_panel(self):
        """Request to close the panel"""
        self.close_requested.emit()