from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import pyqtSignal, QPropertyAnimation
from PyQt6.QtGui import QIcon, QFontMetrics
from PyQt6.QtWidgets import QStyle
from utils import FontManager

class NavigationMenu(QWidget):
    """Collapsible navigation menu widget"""
    nav_changed = pyqtSignal(str)  # Signal when navigation item is selected
    doc_panel_toggled = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.expanded = True
        self.current_page = "beacons"
        self.min_width = 35
        self.max_width = 165  # temporary initial value
        self.button_texts = {}
        
        # Try to use FontManager, but don't fail if it's not available
        try:
            font_manager = FontManager()
            font_manager.add_relative_font_widget(self, 0)
            font_manager.add_font_update_callback(self.update_font_and_width)
        except:
            pass
        
        self.setMinimumWidth(self.max_width)
        self.setup_ui()
        
        # Now calculate max width after buttons are created
        self.max_width = self.calculate_max_width()
        self.setMinimumWidth(self.max_width)
        self.setMaximumWidth(self.max_width)
        
    def setup_ui(self):
        self.setMaximumWidth(self.max_width)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Navigation buttons including toggle
        self.nav_buttons = {}
        nav_items = {
            "toggle": ("Hide", QStyle.StandardPixmap.SP_ArrowLeft),
            "beacons": ("Beacons", QStyle.StandardPixmap.SP_ComputerIcon),
            "settings": ("Settings", QStyle.StandardPixmap.SP_FileDialogListView),
            "docs": ("Documentation", QStyle.StandardPixmap.SP_FileDialogDetailedView),  
        }
        
        for nav_id, (text, icon) in nav_items.items():
            btn = QPushButton()
            btn.setIcon(QIcon(self.style().standardIcon(icon)))
            btn.setText(text)
            
            if nav_id == "toggle":
                btn.clicked.connect(self.toggle_menu)
            elif nav_id == "docs":
                btn.setCheckable(True)
                btn.clicked.connect(self.toggle_documentation)
            else:
                btn.setCheckable(True)
                btn.clicked.connect(lambda checked, x=nav_id: self.nav_changed.emit(x))
            
            self.nav_buttons[nav_id] = btn
            self.button_texts[nav_id] = text
            layout.addWidget(btn)
            
        layout.addStretch()
        self.setLayout(layout)
        
        # Set initial state
        self.nav_buttons["beacons"].setChecked(True)
        self.set_style()

    def toggle_documentation(self):
        """Handle documentation panel toggle button clicks"""
        is_checked = self.nav_buttons["docs"].isChecked()
        self.doc_panel_toggled.emit(is_checked)
        
    def set_style(self):
        base_style = self.styleSheet()
        style = """
            QPushButton {
                text-align: left;
                padding: 10px;
                border: none;
                border-radius: 0;
            }
            QPushButton:checked {
                background-color: #404040;
            }
            QPushButton:hover:!checked {
                background-color: #353535;
            }
        """
        self.setStyleSheet(base_style + style)
        
    def toggle_menu(self):
        self.expanded = not self.expanded
        new_width = self.max_width if self.expanded else self.min_width
        
        # Create animations
        self.max_animation = QPropertyAnimation(self, b"maximumWidth")
        self.max_animation.setDuration(200)
        self.max_animation.setStartValue(self.width())
        self.max_animation.setEndValue(new_width)
        
        self.min_animation = QPropertyAnimation(self, b"minimumWidth")
        self.min_animation.setDuration(200)
        self.min_animation.setStartValue(self.width())
        self.min_animation.setEndValue(new_width)
        
        # Update button texts
        for nav_id, btn in self.nav_buttons.items():
            btn.setText(self.button_texts[nav_id] if self.expanded else "")
        
        # Update toggle button icon and text
        toggle_icon = QStyle.StandardPixmap.SP_ArrowLeft if self.expanded else QStyle.StandardPixmap.SP_ArrowRight
        toggle_text = "Hide" if self.expanded else "Expand"
        self.nav_buttons["toggle"].setIcon(QIcon(self.style().standardIcon(toggle_icon)))
        self.button_texts["toggle"] = toggle_text
        if self.expanded:
            self.nav_buttons["toggle"].setText(toggle_text)

        # Start animations
        self.max_animation.start()
        self.min_animation.start()

    def set_current_page(self, page_id: str):
        """Update the selected navigation button"""
        for nav_id, btn in self.nav_buttons.items():
            if nav_id != "toggle" and nav_id != "docs":  # Don't affect toggle or docs button
                btn.setChecked(nav_id == page_id)

    def calculate_max_width(self):
        max_width = self.min_width
        font_metrics = QFontMetrics(self.font())
        
        # Account for padding and icon
        padding = 20  # 10px padding on each side 
        icon_width = 20  # Approximate icon width
        
        for nav_id, btn in self.nav_buttons.items():
            text_width = font_metrics.horizontalAdvance(self.button_texts[nav_id])
            button_width = text_width + padding + icon_width
            max_width = max(max_width, button_width)
        
        return max_width
    
    def update_font_and_width(self):
        """Called when font changes to update both font and recalculate width"""
        self.max_width = self.calculate_max_width()
        if self.expanded:
            self.setMinimumWidth(self.max_width)
            self.setMaximumWidth(self.max_width)