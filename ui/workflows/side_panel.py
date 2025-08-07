"""
Unified Side Panel System

Provides a single side panel that can display different content types:
- Node editing (parameters, execution, etc.)
- Variables management (create, edit, delete variables)
- Future: Settings, help, workflow properties, etc.

The panel ensures mutual exclusivity - only one content type can be visible at a time.
"""

from enum import Enum
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                            QStackedWidget, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QPropertyAnimation, pyqtSignal
from PyQt6.QtGui import QFont
from typing import Optional, Any


class SidePanelMode(Enum):
    """Available side panel modes"""
    CLOSED = "closed"
    NODE_EDITING = "node_editing"
    CONDITIONAL_EDITING = "conditional_editing"
    SET_VARIABLE_EDITING = "set_variable_editing"
    FILE_TRANSFER_EDITING = "file_transfer_editing"
    VARIABLES = "variables"


class SidePanel(QWidget):
    """Unified side panel that can display different content types"""
    
    # Signals
    panel_closed = pyqtSignal()  # Panel closed
    mode_changed = pyqtSignal(SidePanelMode)  # Panel mode changed
    
    # Content-specific signals (forwarded from content widgets)
    node_updated = pyqtSignal(object, dict)  # node, parameters
    node_deleted = pyqtSignal(object)  # node
    node_execution_requested = pyqtSignal(object)  # node execution requested
    variables_updated = pyqtSignal(dict)  # Updated variables dict
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mode = SidePanelMode.CLOSED
        self.content_widgets = {}  # mode -> widget mapping
        
        # Panel state
        self.expanded = False
        self.min_width = 0
        self.default_width = 550  # Slightly wider to accommodate both content types
        
        self.setup_ui()
        
        # Start in minimized state
        self.setMaximumWidth(self.min_width)
        self.setFixedWidth(self.min_width)
        
    def setup_ui(self):
        """Set up the panel UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create main content area
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border: none;
            }
        """)
        
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Header (removed - content widgets handle their own headers)
        
        # Content area with stacked widget
        self.create_content_area()
        content_layout.addWidget(self.content_area)
        
        self.content_widget.setLayout(content_layout)
        layout.addWidget(self.content_widget)
        self.setLayout(layout)
        
        
    def create_content_area(self):
        """Create the content area with stacked widget"""
        self.content_area = QFrame()
        self.content_area.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: none;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Stacked widget for different content types
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("""
            QStackedWidget {
                background-color: #2b2b2b;
                border: none;
            }
        """)
        
        layout.addWidget(self.stacked_widget)
        self.content_area.setLayout(layout)
        
    def register_content_widget(self, mode: SidePanelMode, widget: QWidget, title: str, subtitle: str = ""):
        """Register a content widget for a specific mode"""
        self.content_widgets[mode] = {
            'widget': widget,
            'title': title,
            'subtitle': subtitle
        }
        self.stacked_widget.addWidget(widget)
        
    def show_mode(self, mode: SidePanelMode, **kwargs):
        """Show the panel in a specific mode"""
        if mode == SidePanelMode.CLOSED:
            self.close_panel()
            return
            
        if mode not in self.content_widgets:
            print(f"Warning: No content widget registered for mode {mode}")
            return
            
        # Update current mode
        old_mode = self.current_mode
        self.current_mode = mode
        
        # Get content info for this mode
        content_info = self.content_widgets[mode]
        
        # Switch to the appropriate content widget
        self.stacked_widget.setCurrentWidget(content_info['widget'])
        
        # Call mode-specific setup if widget has it
        widget = content_info['widget']
        if hasattr(widget, 'on_panel_shown'):
            widget.on_panel_shown(**kwargs)
            
        # Show panel if not already visible
        if not self.expanded:
            self.show_panel()
        
        # Emit mode changed signal
        if old_mode != mode:
            self.mode_changed.emit(mode)
            
    def show_node_editing(self, node, workflow_context):
        """Show node editing content"""
        self.show_mode(SidePanelMode.NODE_EDITING, node=node, workflow_context=workflow_context)
        
    def show_conditional_editing(self, node, workflow_context):
        """Show conditional editing content"""
        self.show_mode(SidePanelMode.CONDITIONAL_EDITING, node=node, workflow_context=workflow_context)
        
    def show_set_variable_editing(self, node, workflow_context):
        """Show set variable editing content"""
        self.show_mode(SidePanelMode.SET_VARIABLE_EDITING, node=node, workflow_context=workflow_context)
        
    def show_file_transfer_editing(self, node, workflow_context):
        """Show file transfer editing content"""
        self.show_mode(SidePanelMode.FILE_TRANSFER_EDITING, node=node, workflow_context=workflow_context)
        
    def show_variables(self):
        """Show variables content"""
        self.show_mode(SidePanelMode.VARIABLES)
        
    def show_panel(self):
        """Show the panel with animation"""
        if not self.expanded:
            self.expanded = True
            self.show()
            self.setMaximumWidth(self.default_width)
            
            # Animate width expansion
            self.animation = QPropertyAnimation(self, b"minimumWidth")
            self.animation.setDuration(200)
            self.animation.setStartValue(self.width())
            self.animation.setEndValue(self.default_width)
            
            self.max_animation = QPropertyAnimation(self, b"maximumWidth")
            self.max_animation.setDuration(200)
            self.max_animation.setStartValue(self.width())
            self.max_animation.setEndValue(self.default_width)
            
            self.animation.start()
            self.max_animation.start()
            
    def hide_panel(self):
        """Hide the panel with animation"""
        if self.expanded:
            self.expanded = False
            
            # Animate width collapse
            self.animation = QPropertyAnimation(self, b"minimumWidth")
            self.animation.setDuration(200)
            self.animation.setStartValue(self.width())
            self.animation.setEndValue(self.min_width)
            
            self.max_animation = QPropertyAnimation(self, b"maximumWidth")
            self.max_animation.setDuration(200)
            self.max_animation.setStartValue(self.width())
            self.max_animation.setEndValue(self.min_width)
            
            self.animation.finished.connect(self.handle_animation_finished)
            
            self.animation.start()
            self.max_animation.start()
            
    def handle_animation_finished(self):
        """Handle animation completion"""
        if not self.expanded:
            self.hide()
            
    def close_panel(self):
        """Close the panel"""
        old_mode = self.current_mode
        self.current_mode = SidePanelMode.CLOSED
        
        if self.expanded:
            self.hide_panel()
            
        # Emit signals
        if old_mode != SidePanelMode.CLOSED:
            self.mode_changed.emit(SidePanelMode.CLOSED)
        self.panel_closed.emit()
        
    def is_visible(self):
        """Check if panel is currently visible"""
        return self.expanded
        
    def get_current_mode(self) -> SidePanelMode:
        """Get the current panel mode"""
        return self.current_mode