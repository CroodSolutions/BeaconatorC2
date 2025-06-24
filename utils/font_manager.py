from PyQt6.QtWidgets import QWidget, QApplication

class FontManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.relative_font_widgets = []
            cls._instance.font_update_callbacks = []  
        return cls._instance

    def get_relative_style(self, widget: QWidget, size_difference: int = 0) -> str:
        """
        Returns a stylesheet with the relative font size while preserving existing styles
        
        Args:
            widget: The widget to modify
            size_difference: Points to add/subtract from base font size
        """
        app_font_size = QApplication.instance().font().pointSize()
        relative_size = app_font_size + size_difference
        
        # Get the widget's class name (e.g., 'QLabel')
        widget_type = widget.__class__.__name__
        
        # Get current stylesheet to preserve other styles
        current_style = widget.styleSheet()
        
        return current_style + f"""
            {widget_type} {{
                font-size: {relative_size}pt;
            }}
        """

    def add_relative_font_widget(self, widget: QWidget, size_difference: int = 0):
        """Keep track of widgets that need relative font updates"""
        self.relative_font_widgets.append((widget, size_difference))
        widget.setStyleSheet(self.get_relative_style(widget, size_difference))

    def update_all_relative_fonts(self):
        """Update all tracked widgets when app font changes"""
        for widget, size_difference in self.relative_font_widgets:
            widget.setStyleSheet(self.get_relative_style(widget, size_difference))
        
        # Call all registered callbacks
        for callback in self.font_update_callbacks:
            callback()

    def add_font_update_callback(self, callback):
        """Add a callback to be called when fonts are updated"""
        self.font_update_callbacks.append(callback)