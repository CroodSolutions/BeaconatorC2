"""
Dynamic Metasploit Integration Widget

Provides an interactive interface for:
- Real-time payload discovery and search
- Dynamic parameter configuration 
- Listener management
- Session monitoring
- Live connection status
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QGroupBox, 
    QLineEdit, QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
    QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QTextEdit,
    QLabel, QProgressBar, QTableWidget, QTableWidgetItem, QSplitter,
    QScrollArea, QFrame, QMessageBox, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QPalette
from typing import Dict, Any, List, Optional, Tuple
import json
import time
import subprocess
import platform
from services import MetasploitManager, MetasploitService, PayloadConfig, ListenerConfig
from database import BeaconRepository
from config import ServerConfig
from utils.helpers import save_payload_to_disk
import utils


class PayloadDiscoveryWorker(QThread):
    """Background worker for discovering Metasploit payloads"""
    payloads_discovered = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, metasploit_service: MetasploitService, platform_filter: str = None):
        super().__init__()
        self.metasploit_service = metasploit_service
        self.platform_filter = platform_filter
        
    def run(self):
        try:
            payloads = self.metasploit_service.list_payloads(self.platform_filter)
            self.payloads_discovered.emit(payloads)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ModuleOptionsWorker(QThread):
    """Background worker for fetching module options"""
    options_discovered = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, metasploit_service: MetasploitService, module_name: str):
        super().__init__()
        self.metasploit_service = metasploit_service
        self.module_name = module_name
        
    def run(self):
        try:
            options = self.metasploit_service.get_payload_info(self.module_name)
            self.options_discovered.emit(options)
        except Exception as e:
            self.error_occurred.emit(str(e))


class DynamicParameterWidget(QWidget):
    """Dynamic parameter input widget based on Metasploit module options"""
    
    def __init__(self, option_name: str, option_info: dict, parent=None):
        super().__init__(parent)
        self.option_name = option_name
        self.option_info = option_info
        self.input_widget = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create input widget based on option type and constraints
        option_type = self.option_info.get('type', 'string').lower()
        default_value = self.option_info.get('default', '')
        required = self.option_info.get('required', False)
        description = self.option_info.get('desc', '')
        
        if option_type in ['bool', 'boolean']:
            self.input_widget = QCheckBox()
            if default_value:
                self.input_widget.setChecked(str(default_value).lower() in ['true', '1', 'yes'])
                
        elif option_type in ['int', 'integer']:
            self.input_widget = QSpinBox()
            self.input_widget.setRange(-999999, 999999)
            if default_value:
                try:
                    self.input_widget.setValue(int(default_value))
                except:
                    pass
                    
        elif option_type == 'enum':
            self.input_widget = QComboBox()
            enums = self.option_info.get('enums', [])
            if enums:
                self.input_widget.addItems(enums)
                if default_value and default_value in enums:
                    self.input_widget.setCurrentText(default_value)
                    
        else:  # String/text input
            self.input_widget = QLineEdit()
            if default_value:
                self.input_widget.setText(str(default_value))
            if description:
                # Set shorter placeholder text but full description in tooltip
                short_desc = description[:50] + "..." if len(description) > 50 else description
                self.input_widget.setPlaceholderText(short_desc)
        
        # Set tooltip with full description for all widget types
        if description and hasattr(self.input_widget, 'setToolTip'):
            self.input_widget.setToolTip(description)
        
        # Style required fields
        if required:
            self.input_widget.setStyleSheet("border: 1px solid orange;")
            
        layout.addWidget(self.input_widget)
        self.setLayout(layout)
        
    def get_value(self):
        """Get the current value from the input widget"""
        if isinstance(self.input_widget, QCheckBox):
            return self.input_widget.isChecked()
        elif isinstance(self.input_widget, QSpinBox):
            return self.input_widget.value()
        elif isinstance(self.input_widget, QComboBox):
            return self.input_widget.currentText()
        elif isinstance(self.input_widget, QLineEdit):
            return self.input_widget.text()
        else:
            return ""
    
    def set_value(self, value):
        """Set the value of the input widget"""
        if isinstance(self.input_widget, QCheckBox):
            self.input_widget.setChecked(bool(value))
        elif isinstance(self.input_widget, QSpinBox):
            self.input_widget.setValue(int(value) if value else 0)
        elif isinstance(self.input_widget, QComboBox):
            self.input_widget.setCurrentText(str(value))
        elif isinstance(self.input_widget, QLineEdit):
            self.input_widget.setText(str(value))


class StatusTab(QWidget):
    """Tab for Metasploit connection status and diagnostics"""
    
    def __init__(self, metasploit_manager: MetasploitManager):
        super().__init__()
        self.metasploit_manager = metasploit_manager
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Connection status section
        status_group = QGroupBox("Connection Status")
        status_layout = QVBoxLayout()
        
        # Status indicator row
        status_row = QHBoxLayout()
        self.status_label = QLabel("Status:")
        self.status_indicator = QLabel("●")
        self.status_text = QLabel("Checking...")
        
        status_row.addWidget(self.status_label)
        status_row.addWidget(self.status_indicator)
        status_row.addWidget(self.status_text)
        status_row.addStretch()
        
        # Buttons
        refresh_btn = QPushButton("Refresh Connection")
        refresh_btn.clicked.connect(self.refresh_connection)
        status_row.addWidget(refresh_btn)
        
        diagnose_btn = QPushButton("Run Diagnostics")
        diagnose_btn.clicked.connect(self.run_diagnostics)
        status_row.addWidget(diagnose_btn)
        
        status_layout.addLayout(status_row)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Installation info section
        install_group = QGroupBox("Installation Information")
        install_layout = QFormLayout()
        
        self.install_status_label = QLabel("Unknown")
        self.install_path_label = QLabel("Not found")
        self.rpc_host_label = QLabel("")
        self.rpc_port_label = QLabel("")
        self.framework_version_label = QLabel("Unknown")
        self.database_status_label = QLabel("Unknown")
        
        install_layout.addRow("Installation Status:", self.install_status_label)
        install_layout.addRow("Daemon Path:", self.install_path_label)
        install_layout.addRow("RPC Host:", self.rpc_host_label)
        install_layout.addRow("RPC Port:", self.rpc_port_label)
        install_layout.addRow("Framework Version:", self.framework_version_label)
        install_layout.addRow("Database Status:", self.database_status_label)
        
        install_group.setLayout(install_layout)
        layout.addWidget(install_group)
        
        # Add stretch to push content to top
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Start status updates
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # Update every 5 seconds
        self.update_status()
        
    def update_status(self):
        """Update connection status display"""
        if not self.metasploit_manager:
            self.status_indicator.setText("●")
            self.status_indicator.setStyleSheet("color: red;")
            self.status_text.setText("No Metasploit manager")
            return
            
        status = self.metasploit_manager.get_status_info()
        
        # Update RPC connection info
        self.rpc_host_label.setText(status.get('rpc_host', 'Unknown'))
        self.rpc_port_label.setText(str(status.get('rpc_port', 'Unknown')))
        
        # Check installation status
        if not status.get('installation_found', False):
            self.status_indicator.setText("●")
            self.status_indicator.setStyleSheet("color: red;")
            self.status_text.setText("Metasploit not installed")
            self.install_status_label.setText("Not Found")
            self.install_path_label.setText(status.get('installation_error', 'Unknown error'))
            return
        else:
            self.install_status_label.setText("Found")
            self.install_path_label.setText(status.get('installation_path', 'Unknown'))
        
        # Update connection status
        if status['is_running']:
            self.status_indicator.setText("●")
            self.status_indicator.setStyleSheet("color: green;")
            self.status_text.setText("Connected")
        else:
            self.status_indicator.setText("●")
            self.status_indicator.setStyleSheet("color: red;")
            self.status_text.setText("Disconnected")
            
    def refresh_connection(self):
        """Manually refresh connection"""
        if self.metasploit_manager:
            # First check installation
            status = self.metasploit_manager.get_status_info()
            if not status.get('installation_found', False):
                install_error = status.get('installation_error', 'Unknown installation error')
                QMessageBox.warning(self, "Installation Check", f"Metasploit Framework not found:\n\n{install_error}")
                self.update_status()
                return
                
            # Test connection
            success, message = self.metasploit_manager.test_connection()
            if not success:
                QMessageBox.warning(self, "Connection Test", f"Connection failed:\n{message}")
        self.update_status()
    
    def run_diagnostics(self):
        """Run comprehensive Metasploit diagnostics"""
        if not self.metasploit_manager:
            QMessageBox.warning(self, "Diagnostics", "No Metasploit manager available")
            return
            
        # Check if Metasploit service is available
        metasploit_service = self.metasploit_manager.metasploit_service
        if not metasploit_service:
            QMessageBox.warning(self, "Diagnostics", "Metasploit service not available")
            return
        
        try:
            # Run diagnostics
            diagnostics = metasploit_service.diagnose_connection()
            
            # Parse results and update UI
            if 'error' in diagnostics:
                QMessageBox.critical(self, "Diagnostics Failed", f"Diagnostic check failed:\n{diagnostics['error']}")
                return
            
            # Update status labels with diagnostic info
            if diagnostics.get('core_version'):
                version = diagnostics['core_version'].get('version', 'Unknown')
                self.framework_version_label.setText(version)
            
            if diagnostics.get('db_status'):
                db_driver = diagnostics['db_status'].get('driver', 'Unknown')
                self.database_status_label.setText(f"Connected ({db_driver})")
            
            # Show diagnostic results
            if diagnostics.get('errors'):
                error_list = '\n'.join([f"• {error}" for error in diagnostics['errors']])
                QMessageBox.warning(self, "Diagnostic Issues Found", 
                                  f"The following issues were detected:\n\n{error_list}\n\n"
                                  "These issues may prevent normal Metasploit operations.")
            else:
                QMessageBox.information(self, "Diagnostics Complete", 
                                      "All diagnostic checks passed successfully!")
                
        except Exception as e:
            QMessageBox.critical(self, "Diagnostics Error", f"Failed to run diagnostics:\n{str(e)}")
        
        # Refresh the status display
        self.update_status()


class PayloadGeneratorTab(QWidget):
    """Tab for payload generation and delivery"""
    
    payload_generated = pyqtSignal(str, bytes)  # filename, data
    delivery_requested = pyqtSignal(str, dict)  # beacon_id, config
    
    def __init__(self, metasploit_manager: MetasploitManager, beacon_repository: BeaconRepository):
        super().__init__()
        self.metasploit_manager = metasploit_manager
        self.beacon_repository = beacon_repository
        self.metasploit_service = metasploit_manager.metasploit_service if metasploit_manager else None
        self.current_module_options = {}
        self.parameter_widgets = {}
        self.discovery_worker = None
        self.options_worker = None
        self.config = ServerConfig()
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Main content splitter (removed status frame)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel: Module selection
        left_panel = self.create_module_selection_panel()
        splitter.addWidget(left_panel)
        
        # Right panel: Configuration and actions
        right_panel = self.create_configuration_panel()
        splitter.addWidget(right_panel)
        
        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        
        self.setLayout(layout)
        
        # Start initial payload discovery
        self.refresh_payloads()
    
    def get_formats_for_payload(self, payload_name: str) -> list:
        """Get appropriate formats based on payload platform/type"""
        if not payload_name:
            return ["exe", "raw", "hex"]
        
        payload_lower = payload_name.lower()
        
        # Windows payloads
        if any(platform in payload_lower for platform in ['windows', 'win']):
            return ["exe", "dll", "msi", "raw", "hex", "powershell"]
        
        # Linux payloads
        elif any(platform in payload_lower for platform in ['linux', 'unix']):
            return ["elf", "raw", "hex"]
        
        # Python payloads
        elif 'python' in payload_lower:
            return ["py", "raw"]
        
        # PHP payloads
        elif 'php' in payload_lower:
            return ["raw"]
        
        # Java payloads
        elif 'java' in payload_lower:
            return ["jar", "war", "raw"]
        
        # Android payloads
        elif 'android' in payload_lower:
            return ["apk", "raw"]
        
        # macOS payloads
        elif any(platform in payload_lower for platform in ['osx', 'macos']):
            return ["macho", "raw", "hex"]
        
        # Generic/multi-platform payloads
        else:
            return ["raw", "hex", "exe"]
        
        
    def create_module_selection_panel(self):
        """Create payload/module selection panel"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Search and filter
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.textChanged.connect(self.filter_payloads)
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_input)
        
        self.platform_filter = QComboBox()
        self.platform_filter.addItems(["All Platforms", "Windows", "Linux", "macOS", "Python", "PHP", "Java"])
        self.platform_filter.currentTextChanged.connect(self.on_platform_changed)
        search_layout.addWidget(QLabel("Platform:"))
        search_layout.addWidget(self.platform_filter)
        
        layout.addLayout(search_layout)
        
        # Payload tree
        self.payload_tree = QTreeWidget()
        self.payload_tree.setHeaderLabels(["Payload Module"])
        self.payload_tree.itemSelectionChanged.connect(self.on_payload_selected)
        layout.addWidget(self.payload_tree)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Payloads")
        refresh_btn.clicked.connect(self.refresh_payloads)
        layout.addWidget(refresh_btn)
        
        widget.setLayout(layout)
        return widget
        
    def create_configuration_panel(self):
        """Create configuration panel"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Module info
        info_group = QGroupBox("Module Information")
        info_layout = QVBoxLayout()
        
        self.module_name_label = QLabel("No module selected")
        self.module_name_label.setFont(QFont("", 10, QFont.Weight.Bold))
        info_layout.addWidget(self.module_name_label)
        
        self.module_desc_label = QLabel("")
        self.module_desc_label.setWordWrap(True)
        info_layout.addWidget(self.module_desc_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Parameters scroll area
        self.params_group = QGroupBox("Parameters")
        self.params_scroll = QScrollArea()
        self.params_widget = QWidget()
        self.params_layout = QFormLayout()
        self.params_widget.setLayout(self.params_layout)
        self.params_scroll.setWidget(self.params_widget)
        self.params_scroll.setWidgetResizable(True)
        self.params_group_layout = QVBoxLayout()
        self.params_group_layout.addWidget(self.params_scroll)
        self.params_group.setLayout(self.params_group_layout)
        layout.addWidget(self.params_group)
        
        # Output options
        output_options_group = QGroupBox("Output Options")
        output_options_layout = QFormLayout()
        
        # Format selection
        self.format_combo = QComboBox()
        self.format_combo.addItems(["exe", "raw", "hex"])  # Default formats
        self.format_combo.setToolTip("Select the output format for the generated payload")
        output_options_layout.addRow("Format:", self.format_combo)
        
        output_options_group.setLayout(output_options_layout)
        layout.addWidget(output_options_group)
        
        # Save options
        save_options_group = QGroupBox("Save Options")
        save_options_layout = QVBoxLayout()
        
        self.auto_save_checkbox = QCheckBox("Automatically save generated payloads")
        self.auto_save_checkbox.setChecked(self.config.PAYLOAD_AUTO_SAVE)
        self.auto_save_checkbox.setToolTip("Save payloads to disk when generated")
        save_options_layout.addWidget(self.auto_save_checkbox)
        
        save_options_group.setLayout(save_options_layout)
        layout.addWidget(save_options_group)
        
        # Actions
        actions_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("Generate Payload")
        self.generate_btn.clicked.connect(self.generate_payload)
        self.generate_btn.setEnabled(False)
        actions_layout.addWidget(self.generate_btn)
        
        self.deliver_btn = QPushButton("Deliver Payload")
        self.deliver_btn.clicked.connect(self.generate_and_deliver)
        self.deliver_btn.setEnabled(False)
        actions_layout.addWidget(self.deliver_btn)
        
        # Add folder button
        self.open_folder_btn = QPushButton("Open Payloads Folder")
        self.open_folder_btn.clicked.connect(self.open_payloads_folder)
        self.open_folder_btn.setEnabled(self.config.PAYLOAD_STORAGE_ENABLED)
        actions_layout.addWidget(self.open_folder_btn)
        
        layout.addLayout(actions_layout)
        
        widget.setLayout(layout)
        return widget
        
    def refresh_payloads(self):
        """Refresh payload list from Metasploit"""
        if not self.metasploit_service:
            return
            
        # Check if Metasploit is installed
        if self.metasploit_manager:
            status = self.metasploit_manager.get_status_info()
            if not status.get('installation_found', False):
                self.payload_tree.clear()
                error_item = QTreeWidgetItem(["Metasploit Framework not installed", "", ""])
                self.payload_tree.addTopLevelItem(error_item)
                return
            
        # Show loading
        self.payload_tree.clear()
        loading_item = QTreeWidgetItem(["Loading payloads...", "", ""])
        self.payload_tree.addTopLevelItem(loading_item)
        
        # Get platform filter
        platform = self.platform_filter.currentText()
        platform_filter = None if platform == "All Platforms" else platform.lower()
        
        # Start discovery worker
        if self.discovery_worker:
            self.discovery_worker.quit()
            self.discovery_worker.wait()
            
        self.discovery_worker = PayloadDiscoveryWorker(self.metasploit_service, platform_filter)
        self.discovery_worker.payloads_discovered.connect(self.on_payloads_discovered)
        self.discovery_worker.error_occurred.connect(self.on_discovery_error)
        self.discovery_worker.start()
        
    def on_payloads_discovered(self, payloads: List[str]):
        """Handle discovered payloads"""
        self.payload_tree.clear()
        
        # Organize payloads by category
        categories = {}
        for payload in payloads:
            parts = payload.split('/')
            if len(parts) >= 2:
                category = parts[0]
                if category not in categories:
                    categories[category] = []
                categories[category].append(payload)
                
        # Populate tree
        for category, category_payloads in sorted(categories.items()):
            category_item = QTreeWidgetItem([category.title(), "", f"{len(category_payloads)} payloads"])
            category_item.setExpanded(False)
            
            for payload in sorted(category_payloads):
                payload_item = QTreeWidgetItem([payload, category, ""])
                category_item.addChild(payload_item)
                
            self.payload_tree.addTopLevelItem(category_item)
            
        # Apply current search filter
        self.filter_payloads()
        
    def on_discovery_error(self, error: str):
        """Handle payload discovery error"""
        self.payload_tree.clear()
        error_item = QTreeWidgetItem([f"Error: {error}", "", ""])
        self.payload_tree.addTopLevelItem(error_item)
        
    def filter_payloads(self):
        """Filter payloads based on search text"""
        search_text = self.search_input.text().lower()
        
        for i in range(self.payload_tree.topLevelItemCount()):
            category_item = self.payload_tree.topLevelItem(i)
            category_visible = False
            
            for j in range(category_item.childCount()):
                payload_item = category_item.child(j)
                payload_name = payload_item.text(0).lower()
                
                visible = not search_text or search_text in payload_name
                payload_item.setHidden(not visible)
                
                if visible:
                    category_visible = True
                    
            category_item.setHidden(not category_visible)
            
    def on_platform_changed(self):
        """Handle platform filter change"""
        self.refresh_payloads()
        
    def on_payload_selected(self):
        """Handle payload selection"""
        selected_items = self.payload_tree.selectedItems()
        if not selected_items:
            self.clear_configuration()
            return
            
        item = selected_items[0]
        
        # Skip category items
        if item.childCount() > 0:
            self.clear_configuration()
            return
            
        payload_name = item.text(0)
        self.load_payload_options(payload_name)
        
    def load_payload_options(self, payload_name: str):
        """Load options for selected payload"""
        self.module_name_label.setText(payload_name)
        self.module_desc_label.setText("Loading options...")
        
        # Update format options based on payload platform
        self.update_format_options(payload_name)
        
        # Clear current parameters
        self.clear_parameters()
        
        # Start options discovery
        if self.options_worker:
            self.options_worker.quit()
            self.options_worker.wait()
            
        self.options_worker = ModuleOptionsWorker(self.metasploit_service, payload_name)
        self.options_worker.options_discovered.connect(self.on_options_discovered)
        self.options_worker.error_occurred.connect(self.on_options_error)
        self.options_worker.start()
    
    def update_format_options(self, payload_name: str):
        """Update format dropdown based on selected payload"""
        # Store current selection
        current_format = self.format_combo.currentText()
        
        # Get new format options
        new_formats = self.get_formats_for_payload(payload_name)
        
        # Update combo box
        self.format_combo.clear()
        self.format_combo.addItems(new_formats)
        
        # Try to restore previous selection if still available
        if current_format in new_formats:
            self.format_combo.setCurrentText(current_format)
        # Otherwise select the first (most appropriate) option
        elif new_formats:
            self.format_combo.setCurrentIndex(0)
        
    def on_options_discovered(self, module_info: dict):
        """Handle discovered module options"""
        self.current_module_options = module_info
        
        description = module_info.get('description', 'No description available')
        self.module_desc_label.setText(description)
        
        # Clear any error styling
        self.module_desc_label.setStyleSheet("")
        
        # Add parameters
        options = module_info.get('options', {})
        
        # Create parameter widgets
        for option_name, option_info in options.items():
            if option_name.upper() in ['VERBOSE', 'WORKSPACE']:
                continue  # Skip internal options
                
            param_widget = DynamicParameterWidget(option_name, option_info)
            self.parameter_widgets[option_name] = param_widget
            
            # Create label with required indicator
            label_text = option_name
            if option_info.get('required', False):
                label_text += " *"
                
            self.params_layout.addRow(label_text, param_widget)
            
        # Enable action buttons
        self.generate_btn.setEnabled(True)
        self.deliver_btn.setEnabled(True)
        
    def on_options_error(self, error: str):
        """Handle options discovery error"""
        # Parse error message to provide user-friendly feedback
        if "Module not found:" in error:
            # Extract suggestions from error message if available
            if "Did you mean:" in error:
                error_parts = error.split("Did you mean:")
                base_error = error_parts[0].strip()
                suggestions = error_parts[1].strip() if len(error_parts) > 1 else ""
                error_text = f"{base_error}\n\nSuggested alternatives: {suggestions}"
            else:
                error_text = f"Payload not found. Please check the payload name and try again."
        elif "session timeout" in error.lower() or "session may have expired" in error.lower():
            error_text = "Metasploit session has expired. The connection will be automatically restored on the next operation."
        elif "not installed" in error.lower():
            error_text = "Metasploit Framework is not installed or not accessible."
        elif "connection" in error.lower():
            error_text = "Cannot connect to Metasploit RPC. Please check if Metasploit is running."
        else:
            error_text = f"Error loading options: {error}"
        
        self.module_desc_label.setText(error_text)
        self.module_desc_label.setStyleSheet("color: #ff6b6b; font-style: italic;")
        
    def clear_configuration(self):
        """Clear module configuration"""
        self.module_name_label.setText("No module selected")
        self.module_desc_label.setText("")
        self.clear_parameters()
        self.generate_btn.setEnabled(False)
        self.deliver_btn.setEnabled(False)
        
        # Reset format dropdown to default options
        self.format_combo.clear()
        self.format_combo.addItems(["exe", "raw", "hex"])
        
    def clear_parameters(self):
        """Clear parameter widgets"""
        for widget in self.parameter_widgets.values():
            widget.setParent(None)
        self.parameter_widgets.clear()
        
        # Clear layout
        while self.params_layout.count():
            child = self.params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def get_payload_config(self) -> PayloadConfig:
        """Build payload configuration from UI"""
        payload_type = self.module_name_label.text()
        
        # Get parameter values from UI widgets (only for parameters that exist in the module)
        params = {}
        for option_name, widget in self.parameter_widgets.items():
            value = widget.get_value()
            # Only include non-empty values or explicitly set parameters
            if value or option_name in ['LHOST', 'LPORT', 'Format']:
                params[option_name] = value
        
        # Only use LHOST/LPORT if they actually exist in the module parameters
        lhost = params.get('LHOST') if 'LHOST' in self.parameter_widgets else '127.0.0.1'
        lport_value = params.get('LPORT', 4444) if 'LPORT' in self.parameter_widgets else 4444
        try:
            lport = int(lport_value) if lport_value else 4444
        except (ValueError, TypeError):
            lport = 4444
        
        # Get selected format from UI, with fallback to module Format parameter or 'exe'
        selected_format = self.format_combo.currentText()
        module_format = params.get('Format')
        final_format = selected_format or module_format or 'exe'
        
        return PayloadConfig(
            payload_type=payload_type,
            lhost=lhost,
            lport=lport,
            format=final_format,
            encoder=params.get('Encoder') if params.get('Encoder') != 'none' else None,
            iterations=int(params.get('Iterations', 1)) if params.get('Iterations') else 1
        )
        
    def generate_payload(self):
        """Generate payload without delivery"""
        try:
            config = self.get_payload_config()
            success, payload_data, error = self.metasploit_service.generate_payload(config)
            
            if success:
                filename = f"{config.payload_type.replace('/', '_')}.{config.format}"
                
                # Handle payload storage
                storage_message = ""
                if self.auto_save_checkbox.isChecked() and self.config.PAYLOAD_STORAGE_ENABLED:
                    # Prepare metadata
                    metadata = {
                        'lhost': config.lhost,
                        'lport': config.lport,
                        'encoder': config.encoder,
                        'iterations': config.iterations,
                        'template': config.template,
                        'badchars': config.badchars,
                        'platform': config.platform,
                        'arch': config.arch
                    }
                    
                    # Save to disk
                    saved, file_path, save_error = save_payload_to_disk(
                        self.config, config.payload_type, config.format, payload_data, metadata
                    )
                    
                    if saved:
                        storage_message = f"\nSaved to: {file_path}"
                    else:
                        storage_message = f"\nSave failed: {save_error}"
                
                # Emit signal for any other handlers
                self.payload_generated.emit(filename, payload_data)
                
                # Show success message
                message = f"Payload generated: {len(payload_data)} bytes{storage_message}"
                QMessageBox.information(self, "Success", message)
            else:
                # Parse error message for better user feedback
                if "Module not found:" in error:
                    if "Did you mean:" in error:
                        QMessageBox.warning(self, "Payload Not Found", 
                                          f"The specified payload was not found.\n\n{error}")
                    else:
                        QMessageBox.warning(self, "Payload Not Found", 
                                          f"The payload '{config.payload_type}' was not found.\n\n"
                                          "Please check the payload name or select a different payload.")
                elif "session timeout" in error.lower() or "session may have expired" in error.lower():
                    QMessageBox.information(self, "Session Restored", 
                                          "Metasploit session has been automatically restored.\n"
                                          "Please try generating the payload again.")
                elif "Connection error" in error:
                    QMessageBox.critical(self, "Connection Error", 
                                       f"Cannot connect to Metasploit:\n{error}\n\n"
                                       "Please ensure Metasploit is running and accessible.")
                else:
                    QMessageBox.warning(self, "Generation Failed", f"Failed to generate payload:\n{error}")
                
        except Exception as e:
            error_str = str(e)
            if "Module not found:" in error_str:
                QMessageBox.warning(self, "Payload Not Found", 
                                  f"The specified payload was not found:\n{error_str}")
            elif "session timeout" in error_str.lower() or "session may have expired" in error_str.lower():
                QMessageBox.information(self, "Session Restored", 
                                      "Metasploit session has been automatically restored.\n"
                                      "Please try generating the payload again.")
            elif "connection" in error_str.lower():
                QMessageBox.critical(self, "Connection Error", 
                                   f"Cannot connect to Metasploit:\n{error_str}")
            else:
                QMessageBox.critical(self, "Error", f"Error generating payload:\n{error_str}")
            
    def generate_and_deliver(self):
        """Generate and deliver payload to selected beacon"""
        # This would open a beacon selection dialog
        # For now, show a placeholder message
        QMessageBox.information(self, "Delivery", "Beacon selection and delivery will be implemented next!")
    
    def open_payloads_folder(self):
        """Open the payloads folder in the system file manager"""
        try:
            from pathlib import Path
            payloads_path = Path(self.config.PAYLOADS_FOLDER)
            
            # Create directory if it doesn't exist
            payloads_path.mkdir(parents=True, exist_ok=True)
            
            # Open folder based on platform
            system = platform.system().lower()
            if system == "windows":
                subprocess.run(["explorer", str(payloads_path)], check=True)
            elif system == "darwin":  # macOS
                subprocess.run(["open", str(payloads_path)], check=True)
            else:  # Linux and others
                subprocess.run(["xdg-open", str(payloads_path)], check=True)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open payloads folder:\n{str(e)}")


class MetasploitWidget(QTabWidget):
    """Main Metasploit integration widget with multiple tabs"""
    
    def __init__(self, metasploit_manager: MetasploitManager = None, beacon_repository: BeaconRepository = None):
        super().__init__()
        self.metasploit_manager = metasploit_manager
        self.beacon_repository = beacon_repository
        self.setup_ui()
        
    def setup_ui(self):
        # Payload Generator tab
        self.payload_tab = PayloadGeneratorTab(self.metasploit_manager, self.beacon_repository)
        self.addTab(self.payload_tab, "Payload Generator")
        
        # Placeholder tabs for now
        placeholder1 = QLabel("Listener Management\n(Coming Soon)")
        placeholder1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addTab(placeholder1, "Listeners")
        
        placeholder2 = QLabel("Session Management\n(Coming Soon)")
        placeholder2.setAlignment(Qt.AlignmentFlag.AlignCenter)  
        self.addTab(placeholder2, "Sessions")
        
        # Status tab
        self.status_tab = StatusTab(self.metasploit_manager)
        self.addTab(self.status_tab, "Status")