import sys
from pathlib import Path
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QApplication, QSplitter, QStackedWidget, QStackedLayout, QTabWidget, QLabel)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon, QFontDatabase

from config import ConfigManager
from services.receivers import ReceiverManager
from services.command_processor import CommandProcessor
from services.file_transfer import FileTransferService
from services import MetasploitManager
from database import BeaconRepository
from utils import DocumentationManager
from workers import BeaconUpdateWorker, ReceiverUpdateWorker
from .components import (BeaconTableWidget, CommandWidget, NavigationMenu,
                        FileTransferWidget, SettingsPage, DocumentationPanel, BeaconSettingsWidget, ReceiversWidget, MetasploitWidget, AssetMapCanvas, BeaconMetadataPanel)
from .widgets import LogWidget, OutputDisplay, KeyLoggerDisplay
from services import SchemaService
from services.workflows.trigger_service import TriggerService
import utils

class MainWindow(QMainWindow):
    def __init__(self, beacon_repository: BeaconRepository, command_processor: CommandProcessor, 
                 file_transfer_service: FileTransferService, receiver_manager: ReceiverManager = None,
                 metasploit_manager: MetasploitManager = None):
        super().__init__()
        self.beacon_repository = beacon_repository
        self.command_processor = command_processor
        self.file_transfer_service = file_transfer_service
        self.receiver_manager = receiver_manager
        self.metasploit_manager = metasploit_manager
        self.config_manager = ConfigManager()
        self.beacon_update_worker = None
        self.receiver_update_worker = None
        self.schema_service = SchemaService()
        
        # Initialize trigger service (will be passed to workflow editor)
        self.trigger_service = None  # Will be initialized after workflow components
        
        # Store tab widget references for dynamic management
        self.tab_widgets = {}
        self.right_panel = None
        
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
        self.doc_panel.set_content("--- Introduction ---")
        container_layout.addWidget(self.doc_panel)

        # Set layout for container
        content_container.setLayout(container_layout)
        main_layout.addWidget(content_container)

        # Create content pages
        self.setup_beacons_page()
        self.setup_receivers_page()
        self.setup_workflows_page()
        self.setup_asset_map_page()
        self.setup_settings_page()
        self.setup_metasploit_page()

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
        left_splitter.setSizes([290, 310])  # Set initial sizes for vertical splitter
        left_splitter.setStretchFactor(0, 1)  # Table gets more space
        left_splitter.setStretchFactor(1, 0)  # Log gets less space
        
        left_layout.addWidget(left_splitter)
        left_widget.setLayout(left_layout)
        
        # Create right panel with tabs
        self.right_panel = QTabWidget()
        self.right_panel.setMinimumWidth(600)  # Ensure minimum width for command column
        
        # Create all tab widgets and store references
        self.create_tab_widgets()
        
        # Add always-visible tabs
        self.add_always_visible_tabs()
        
        # Add conditional tabs (initially hidden)
        self.add_conditional_tabs()
        
        # Add widgets to main splitter
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(self.right_panel)
        
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
    
    def create_tab_widgets(self):
        """Create all tab widgets and store references"""
        # Always visible tabs
        self.command_widget = CommandWidget(self.beacon_repository, self.doc_panel)
        # Establish bidirectional reference between doc panel and command widget
        self.doc_panel.command_widget = self.command_widget
        self.tab_widgets['modules'] = self.command_widget
        
        self.beacon_settings_widget = BeaconSettingsWidget(self.beacon_repository)
        self.beacon_settings_widget.schema_applied.connect(self.command_widget.on_schema_applied)
        self.tab_widgets['beacon_settings'] = self.beacon_settings_widget
        
        # Conditional tabs
        self.file_transfer_widget = FileTransferWidget(self.beacon_repository)
        self.tab_widgets['file_transfer'] = self.file_transfer_widget
        
        self.keylogger_display = KeyLoggerDisplay(self.beacon_repository)
        self.tab_widgets['keylogger'] = self.keylogger_display
        
        # Metasploit widget is now handled by navigation menu (setup_metasploit_page)
    
    def add_always_visible_tabs(self):
        """Add tabs that are always visible"""
        self.right_panel.addTab(self.tab_widgets['modules'], "Modules")
        self.right_panel.addTab(self.tab_widgets['beacon_settings'], "Beacon Settings")
        
        # Metasploit is now in navigation menu, not tabs
    
    def add_conditional_tabs(self):
        """Add conditional tabs (initially all shown for backward compatibility)"""
        # Show all conditional tabs initially for backward compatibility
        self.right_panel.addTab(self.tab_widgets['file_transfer'], "File Transfer")
        self.right_panel.addTab(self.tab_widgets['keylogger'], "KeyLogger")
    
    def get_beacon_schema(self, beacon_id: str):
        """Get schema for a beacon"""
        try:
            beacon = self.beacon_repository.get_beacon(beacon_id)
            if beacon and beacon.schema_file:
                return self.schema_service.get_schema(beacon.schema_file)
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error getting beacon schema: {e}")
        return None
    
    def update_beacon_tabs(self, beacon_id: str):
        """Update tab visibility based on beacon capabilities"""
        if not beacon_id:
            # No beacon selected - reset to default state
            self.reset_tabs_to_default()
            return
            
        schema = self.get_beacon_schema(beacon_id)
        
        if schema and schema.beacon_info:
            # Update file transfer tab
            self.toggle_tab_visibility('file_transfer', schema.beacon_info.file_transfer_supported)
            
            # Update keylogger tab
            self.toggle_tab_visibility('keylogger', schema.beacon_info.keylogger_supported)
        else:
            # No schema or schema info - show all tabs for backward compatibility
            self.toggle_tab_visibility('file_transfer', True)
            self.toggle_tab_visibility('keylogger', True)
    
    def reset_tabs_to_default(self):
        """Reset tabs to default state when no beacon is selected"""
        # Enable all conditional tabs by default
        self.toggle_tab_visibility('file_transfer', True)
        self.toggle_tab_visibility('keylogger', True)
    
    def toggle_tab_visibility(self, tab_key: str, show: bool):
        """Show or hide a tab based on beacon capabilities"""
        if tab_key not in self.tab_widgets:
            return
        
        widget = self.tab_widgets[tab_key]
        tab_title = {
            'file_transfer': 'File Transfer',
            'keylogger': 'KeyLogger'
        }.get(tab_key, tab_key.title())
        
        # Find current index of the tab
        current_index = -1
        for i in range(self.right_panel.count()):
            if self.right_panel.widget(i) == widget:
                current_index = i
                break
        
        if show and current_index == -1:
            # Add tab if it should be shown but isn't present
            insert_index = self._get_tab_insert_position(tab_key)
            self.right_panel.insertTab(insert_index, widget, tab_title)
            
        elif not show and current_index != -1:
            # Remove tab completely for cleaner UI
            self.right_panel.removeTab(current_index)
    
    def _get_tab_insert_position(self, tab_key: str) -> int:
        """Get the correct position to insert a tab to maintain proper ordering"""
        # Desired tab order: Modules, File Transfer, KeyLogger, Beacon Settings
        tab_order = ['modules', 'file_transfer', 'keylogger', 'beacon_settings']
        
        try:
            target_position = tab_order.index(tab_key)
        except ValueError:
            # Unknown tab, add at end
            return self.right_panel.count()
        
        # Find the position by checking existing tabs
        for i in range(self.right_panel.count()):
            current_widget = self.right_panel.widget(i)
            # Find which tab this widget represents
            for existing_key, existing_widget in self.tab_widgets.items():
                if current_widget == existing_widget:
                    try:
                        existing_position = tab_order.index(existing_key)
                        if existing_position > target_position:
                            return i
                    except ValueError:
                        continue
                    break
        
        # If we didn't find a position, add at the end
        return self.right_panel.count()

    def setup_receivers_page(self):
        """Create the receivers page"""
        # Pass receiver_manager if available, otherwise ReceiversWidget will create its own
        if self.receiver_manager:
            self.receivers_page = ReceiversWidget(self.command_processor, self.file_transfer_service, self.receiver_manager)
        else:
            self.receivers_page = ReceiversWidget(self.command_processor, self.file_transfer_service)
        self.content_stack.addWidget(self.receivers_page)

    def setup_workflows_page(self):
        """Create the workflows page"""
        from .workflows import WorkflowEditor
        
        self.workflows_page = WorkflowEditor(
            schema_service=self.schema_service,
            beacon_repository=self.beacon_repository,
            command_processor=self.command_processor
        )
        
        # Initialize trigger service now that workflow components are created
        from services.workflows.workflow_service import WorkflowService
        from services.workflows.workflow_engine import WorkflowEngine
        
        workflow_service = WorkflowService(
            self.schema_service,
            self.beacon_repository,
            self.command_processor
        )
        workflow_engine = WorkflowEngine(
            workflow_service,
            self.schema_service,
            self.beacon_repository,
            self.command_processor
        )
        
        self.trigger_service = TriggerService(
            self.beacon_repository,
            workflow_service,
            workflow_engine
        )
        
        # Pass trigger service to workflow editor
        self.workflows_page.set_trigger_service(self.trigger_service)
        
        # Connect beacon events to trigger evaluation
        if hasattr(self.beacon_repository, 'beacon_connected'):
            self.beacon_repository.beacon_connected.connect(
                lambda beacon_info: self.trigger_service.evaluate_beacon_event(beacon_info, 'connection')
            )
            print("[TRIGGER DEBUG] Connected beacon_connected signal to trigger service")
        
        # Also connect status change events
        if hasattr(self.beacon_repository, 'beacon_status_changed'):
            self.beacon_repository.beacon_status_changed.connect(
                lambda beacon_info: self.trigger_service.evaluate_beacon_event(beacon_info, 'status')
            )
            print("[TRIGGER DEBUG] Connected beacon_status_changed signal to trigger service")
        else:
            print("[TRIGGER DEBUG] WARNING: beacon_repository doesn't have beacon_status_changed signal")
        
        # Start trigger monitoring
        self.trigger_service.start_monitoring()

        self.content_stack.addWidget(self.workflows_page)

    def setup_asset_map_page(self):
        """Create the asset map page"""
        asset_map_widget = QWidget()
        main_layout = QVBoxLayout(asset_map_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create horizontal layout for canvas and metadata panel
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Create the asset map canvas with beacon repository for command execution
        self.asset_map_canvas = AssetMapCanvas(beacon_repository=self.beacon_repository)
        content_layout.addWidget(self.asset_map_canvas)

        # Create metadata panel (starts hidden)
        self.beacon_metadata_panel = BeaconMetadataPanel()
        self.beacon_metadata_panel.set_beacon_repository(self.beacon_repository)
        content_layout.addWidget(self.beacon_metadata_panel)

        main_layout.addLayout(content_layout)

        # Connect signals
        self.asset_map_canvas.node_selected.connect(self._on_asset_map_node_selected)
        self.beacon_metadata_panel.panel_closed.connect(self.asset_map_canvas.update)

        # Populate initial data
        self._populate_asset_map()

        # Note: Signal connections will be made in start_background_workers()
        # after workers are initialized

        asset_map_widget.setLayout(main_layout)
        self.content_stack.addWidget(asset_map_widget)

    def _populate_asset_map(self):
        """Populate the asset map with current beacon and receiver data"""
        # Get all beacons
        beacons = self.beacon_repository.get_all_beacons()

        # Get all receivers
        receivers = []
        if self.receiver_manager:
            receivers = list(self.receiver_manager.get_all_receivers().values())

        # Populate the canvas
        self.asset_map_canvas.populate_from_data(beacons, receivers)

    def _refresh_asset_map(self):
        """Refresh the asset map with updated data"""
        # Only refresh if we're on the asset map page to avoid unnecessary updates
        if self.content_stack.currentIndex() == 3:  # Asset map index
            beacons = self.beacon_repository.get_all_beacons()
            receivers = []
            if self.receiver_manager:
                receivers = list(self.receiver_manager.get_all_receivers().values())

            self.asset_map_canvas.refresh_from_data(beacons, receivers)

    def _on_asset_map_node_selected(self, node):
        """Handle node selection in asset map"""
        # Only show metadata panel for beacon nodes
        if node.node_type == "beacon":
            beacon_id = node.asset_data.get('beacon_id')
            if beacon_id:
                self.beacon_metadata_panel.show_beacon(beacon_id)

    def setup_settings_page(self):
        """Create the settings page"""
        self.settings_page = SettingsPage(self.config_manager)
        self.content_stack.addWidget(self.settings_page)
    
    def setup_metasploit_page(self):
        """Create the Metasploit RPC page"""
        if self.metasploit_manager:
            # Create main widget container
            metasploit_widget = QWidget()
            layout = QVBoxLayout(metasploit_widget)
            
            # Create and add the Metasploit widget
            self.metasploit_page_widget = MetasploitWidget(self.metasploit_manager, self.beacon_repository)
            layout.addWidget(self.metasploit_page_widget)
            
            metasploit_widget.setLayout(layout)
            self.content_stack.addWidget(metasploit_widget)
        else:
            # Create a placeholder if Metasploit manager not available
            placeholder = QWidget()
            layout = QVBoxLayout(placeholder)
            
            label = QLabel("Metasploit integration is not available")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            
            placeholder.setLayout(layout)
            self.content_stack.addWidget(placeholder)


    def start_background_workers(self):
        """Start background workers for updating beacon status"""
        # Start beacon update worker
        self.beacon_update_worker = BeaconUpdateWorker(self.beacon_repository)
        self.beacon_update_worker.beacon_updated.connect(self.beacon_table.update_beacons)
        self.beacon_update_worker.beacon_updated.connect(self._refresh_asset_map)
        self.beacon_update_worker.start()

        # Start receiver update worker if receiver manager is available
        if self.receiver_manager:
            self.receiver_update_worker = ReceiverUpdateWorker(self.receiver_manager)
            self.receiver_update_worker.receiver_stats_updated.connect(self.receivers_page.refresh_receivers_table)
            self.receiver_update_worker.receiver_stats_updated.connect(self.receivers_page.update_summary_stats)
            self.receiver_update_worker.receiver_stats_updated.connect(self._refresh_asset_map)
            self.receiver_update_worker.start()

        # Connect logger to log widget
        if utils.logger:
            utils.logger.new_log.connect(self.log_widget.append_log)

    def on_nav_changed(self, page_id: str):
        """Handle navigation menu changes"""
        self.nav_menu.set_current_page(page_id)

        if page_id == "beacons":
            self.content_stack.setCurrentIndex(0)
        elif page_id == "receivers":
            self.content_stack.setCurrentIndex(1)
        elif page_id == "workflows":
            self.content_stack.setCurrentIndex(2)
        elif page_id == "asset_map":
            self.content_stack.setCurrentIndex(3)
            # Refresh asset map when navigating to it
            self._refresh_asset_map()
        elif page_id == "settings":
            self.content_stack.setCurrentIndex(4)
        elif page_id == "metasploit":
            self.content_stack.setCurrentIndex(5)

    def toggle_documentation(self, show: bool):
        """Toggle the documentation panel"""
        if show:
            self.doc_panel.show_panel()
        else:
            self.doc_panel.hide_panel()

    def on_beacon_selected(self, beacon_id: str):
        """Handle beacon selection with optimized async updates"""
        # Update tab visibility based on beacon capabilities
        self.update_beacon_tabs(beacon_id)
        
        # Fast operations first (minimal delay)
        self.file_transfer_widget.set_beacon(beacon_id)
        
        # Defer heavy operations to next event loop cycle
        # This prevents blocking the UI thread
        QTimer.singleShot(0, lambda: self._update_beacon_widgets_async(beacon_id))
    
    def _update_beacon_widgets_async(self, beacon_id: str):
        """Update heavy widgets asynchronously to avoid blocking selection"""
        # Update widgets in order of priority/speed
        
        # 1. Command widget (needs schema but used most frequently)
        self.command_widget.set_beacon(beacon_id)
        
        # 2. Settings widget (shares schema cache with command widget)
        self.beacon_settings_widget.set_beacon(beacon_id)
        
        # 3. Keylogger last (involves thread operations)
        self.keylogger_display.set_beacon(beacon_id)

    def on_command_sent(self, beacon_id: str, command: str):
        """Handle command being sent to beacon"""
        if utils.logger:
            utils.logger.log_message(f"Command sent to {beacon_id}: {command}")

    def closeEvent(self, event):
        """Handle window close event"""
        # Stop background workers
        if self.beacon_update_worker:
            self.beacon_update_worker.stop()
        
        if self.receiver_update_worker:
            self.receiver_update_worker.stop()
        
        # Cleanup widgets
        if hasattr(self, 'keylogger_display'):
            self.keylogger_display.cleanup()
        
        # Accept the close event
        event.accept()
