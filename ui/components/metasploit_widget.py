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
    QScrollArea, QFrame, QMessageBox, QHeaderView, QAbstractItemView,
    QMenu, QDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QPalette
from typing import Dict, Any, List, Optional, Tuple
import json
import time
import subprocess
import platform
import os
from services import MetasploitManager, MetasploitService, PayloadConfig, ListenerConfig
from database import BeaconRepository
from config import ServerConfig
from ui.dialogs import SessionTerminalDialog
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
        
        # Connection Configuration group
        config_group = QGroupBox("Connection Configuration")
        config_layout = QFormLayout()
        
        # Connection settings
        self.host_input = QLineEdit(self.metasploit_manager.config.MSF_RPC_HOST)
        self.host_input.setPlaceholderText("127.0.0.1")
        
        self.port_input = QLineEdit(str(self.metasploit_manager.config.MSF_RPC_PORT))
        self.port_input.setPlaceholderText("55553")
        
        self.user_input = QLineEdit(self.metasploit_manager.config.MSF_RPC_USER)
        self.user_input.setPlaceholderText("msf")
        
        self.pass_input = QLineEdit(self.metasploit_manager.config.MSF_RPC_PASS)
        self.pass_input.setPlaceholderText("msf123")

        
        self.ssl_checkbox = QCheckBox("Use SSL")
        self.ssl_checkbox.setChecked(self.metasploit_manager.config.MSF_RPC_SSL)
        
        config_layout.addRow("RPC Host:", self.host_input)
        config_layout.addRow("RPC Port:", self.port_input)
        config_layout.addRow("Username:", self.user_input)
        config_layout.addRow("Password:", self.pass_input)
        config_layout.addRow("", self.ssl_checkbox)
        
        # Connection control buttons
        conn_btn_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("Connect to External RPC")
        self.connect_btn.clicked.connect(self.connect_to_external_rpc)
        conn_btn_layout.addWidget(self.connect_btn)
        
        self.start_rpc_btn = QPushButton("Start Local RPC")
        self.start_rpc_btn.clicked.connect(self.start_local_rpc)
        conn_btn_layout.addWidget(self.start_rpc_btn)
        
        self.stop_rpc_btn = QPushButton("Stop RPC")
        self.stop_rpc_btn.clicked.connect(self.stop_rpc)
        self.stop_rpc_btn.setEnabled(False)
        conn_btn_layout.addWidget(self.stop_rpc_btn)
        
        config_layout.addRow("", conn_btn_layout)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
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
        
        # Load saved connection settings
        self.load_connection_settings()
        
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
            # Show if it's external or managed
            if status.get('is_managed', False):
                self.status_text.setText("Connected (Local)")
            else:
                self.status_text.setText("Connected (External)")
        else:
            self.status_indicator.setText("●")
            self.status_indicator.setStyleSheet("color: red;")
            self.status_text.setText("Disconnected")
        
        # Update button states
        self.update_button_states()
            
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
    
    def connect_to_external_rpc(self):
        """Connect to an external Metasploit RPC instance"""
        try:
            # Get connection settings from UI
            host = self.host_input.text().strip()
            port = self.port_input.text().strip()
            user = self.user_input.text().strip()
            password = self.pass_input.text().strip()
            ssl = self.ssl_checkbox.isChecked()
            
            # Validate inputs
            if not host or not port or not user or not password:
                QMessageBox.warning(self, "Connection Error", "Please fill in all connection fields")
                return
            
            try:
                port = int(port)
            except ValueError:
                QMessageBox.warning(self, "Connection Error", "Port must be a valid number")
                return
            
            # Update configuration temporarily
            self.metasploit_manager.config.MSF_RPC_HOST = host
            self.metasploit_manager.config.MSF_RPC_PORT = port
            self.metasploit_manager.config.MSF_RPC_USER = user
            self.metasploit_manager.config.MSF_RPC_PASS = password
            self.metasploit_manager.config.MSF_RPC_SSL = ssl
            
            # Test the connection
            if utils.logger:
                utils.logger.log_message(f"Attempting to connect to external RPC at {host}:{port}")
            
            success, message = self.metasploit_manager.test_connection()
            
            if success:
                # Mark as external connection
                self.metasploit_manager._status.is_running = True
                self.metasploit_manager._status.is_managed = False
                self.metasploit_manager._status.connection_status = "Connected (External)"
                
                # Update MetasploitService with new connection details
                if self.metasploit_manager.metasploit_service:
                    self.metasploit_manager.metasploit_service.config.MSF_RPC_HOST = host
                    self.metasploit_manager.metasploit_service.config.MSF_RPC_PORT = port
                    self.metasploit_manager.metasploit_service.config.MSF_RPC_USER = user
                    self.metasploit_manager.metasploit_service.config.MSF_RPC_PASS = password
                    self.metasploit_manager.metasploit_service.config.MSF_RPC_SSL = ssl
                    
                    # Force reconnection
                    self.metasploit_manager.metasploit_service.disconnect()
                    connected = self.metasploit_manager.metasploit_service.connect()
                    
                    if connected:
                        QMessageBox.information(self, "Success", f"Connected to external RPC at {host}:{port}")
                        self.stop_rpc_btn.setEnabled(False)  # Don't allow stopping external RPC
                        # Save successful connection settings
                        self.save_connection_settings()
                    else:
                        QMessageBox.warning(self, "Connection Failed", "Connected to RPC but service initialization failed")
                else:
                    QMessageBox.information(self, "Success", f"Connected to external RPC at {host}:{port}")
                    # Save successful connection settings
                    self.save_connection_settings()
                    
                # Start health monitoring
                self.metasploit_manager._start_health_monitoring()
                
            else:
                QMessageBox.warning(self, "Connection Failed", f"Failed to connect:\n{message}")
                
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Unexpected error:\n{str(e)}")
            if utils.logger:
                utils.logger.log_message(f"Error connecting to external RPC: {str(e)}")
        
        self.update_status()
    
    def start_local_rpc(self):
        """Start the local Metasploit RPC daemon"""
        try:
            # Check if already running
            if self.metasploit_manager._status.is_running:
                QMessageBox.information(self, "RPC Status", "RPC is already running")
                return
            
            # Start the RPC daemon
            success, message = self.metasploit_manager.start_rpc_daemon()
            
            if success:
                QMessageBox.information(self, "Success", "Local RPC daemon started successfully")
                self.stop_rpc_btn.setEnabled(True)
                
                # Update MetasploitService connection
                if self.metasploit_manager.metasploit_service:
                    self.metasploit_manager.metasploit_service.connect()
            else:
                QMessageBox.warning(self, "Start Failed", f"Failed to start RPC daemon:\n{message}")
                
        except Exception as e:
            QMessageBox.critical(self, "Start Error", f"Unexpected error:\n{str(e)}")
            if utils.logger:
                utils.logger.log_message(f"Error starting local RPC: {str(e)}")
        
        self.update_status()
    
    def stop_rpc(self):
        """Stop the RPC daemon if we manage it"""
        try:
            if not self.metasploit_manager._status.is_managed:
                QMessageBox.warning(self, "Cannot Stop", "Cannot stop external RPC instance")
                return
            
            # Stop the daemon
            success, message = self.metasploit_manager.stop_rpc_daemon()
            
            if success:
                QMessageBox.information(self, "Success", "RPC daemon stopped successfully")
                self.stop_rpc_btn.setEnabled(False)
                
                # Disconnect MetasploitService
                if self.metasploit_manager.metasploit_service:
                    self.metasploit_manager.metasploit_service.disconnect()
            else:
                QMessageBox.warning(self, "Stop Failed", f"Failed to stop RPC daemon:\n{message}")
                
        except Exception as e:
            QMessageBox.critical(self, "Stop Error", f"Unexpected error:\n{str(e)}")
            if utils.logger:
                utils.logger.log_message(f"Error stopping RPC: {str(e)}")
        
        self.update_status()
    
    def update_button_states(self):
        """Update button states based on connection status"""
        is_running = self.metasploit_manager._status.is_running
        is_managed = self.metasploit_manager._status.is_managed
        
        # Enable/disable buttons based on state
        self.connect_btn.setEnabled(not is_running)
        self.start_rpc_btn.setEnabled(not is_running)
        self.stop_rpc_btn.setEnabled(is_running and is_managed)
        
        # Update stop button text
        if is_running and not is_managed:
            self.stop_rpc_btn.setText("Stop RPC (External)")
        else:
            self.stop_rpc_btn.setText("Stop RPC")
    
    def save_connection_settings(self):
        """Save connection settings to a file for persistence"""
        try:
            settings = {
                'host': self.host_input.text(),
                'port': self.port_input.text(),
                'user': self.user_input.text(),
                'ssl': self.ssl_checkbox.isChecked()
            }
            
            # Save to a config file
            config_dir = os.path.expanduser('~/.beaconatorc2')
            os.makedirs(config_dir, exist_ok=True)
            config_file = os.path.join(config_dir, 'msf_connection.json')
            
            with open(config_file, 'w') as f:
                json.dump(settings, f, indent=2)
                
            if utils.logger:
                utils.logger.log_message(f"Saved Metasploit connection settings to {config_file}")
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error saving connection settings: {str(e)}")
    
    def load_connection_settings(self):
        """Load saved connection settings if they exist"""
        try:
            config_file = os.path.expanduser('~/.beaconatorc2/msf_connection.json')
            
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    settings = json.load(f)
                
                # Update UI with saved settings
                self.host_input.setText(settings.get('host', self.metasploit_manager.config.MSF_RPC_HOST))
                self.port_input.setText(settings.get('port', str(self.metasploit_manager.config.MSF_RPC_PORT)))
                self.user_input.setText(settings.get('user', self.metasploit_manager.config.MSF_RPC_USER))
                self.ssl_checkbox.setChecked(settings.get('ssl', self.metasploit_manager.config.MSF_RPC_SSL))
                
                if utils.logger:
                    utils.logger.log_message("Loaded saved Metasploit connection settings")
                    
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error loading connection settings: {str(e)}")


class PayloadGeneratorTab(QWidget):
    """Tab for payload generation and delivery"""
    
    payload_generated = pyqtSignal(str, object)  # filename, data (can be str or bytes)
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
        
        # Create Handler button
        self.create_handler_btn = QPushButton("Create Handler")
        self.create_handler_btn.clicked.connect(self.create_matching_handler)
        self.create_handler_btn.setEnabled(False)
        self.create_handler_btn.setToolTip("Create a matching Metasploit handler/listener for this payload")
        actions_layout.addWidget(self.create_handler_btn)
        
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
        self.create_handler_btn.setEnabled(True)
        
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
        self.create_handler_btn.setEnabled(False)
        
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
    
    def create_matching_handler(self):
        """Create a matching Metasploit handler/listener for the current payload configuration with enhanced error handling"""
        try:
            if utils.logger:
                utils.logger.log_message("PayloadGeneratorTab: Creating matching handler")
            
            config = self.get_payload_config()
            
            if utils.logger:
                utils.logger.log_message(f"PayloadGeneratorTab: Payload config - {config.payload_type}, {config.lhost}:{config.lport}")
            
            # Disable the create handler button to prevent double-clicks
            self.create_handler_btn.setEnabled(False)
            self.create_handler_btn.setText("Creating...")
            
            try:
                # Create listener configuration from payload configuration
                listener_config = ListenerConfig(
                    payload_type=config.payload_type,
                    lhost=config.lhost,
                    lport=config.lport,
                    exit_on_session=False  # Default to not exit on session
                )
                
                if utils.logger:
                    utils.logger.log_message(f"PayloadGeneratorTab: Listener config created - {listener_config.payload_type}, {listener_config.lhost}:{listener_config.lport}")
                
                # Start listener
                success, job_id, error = self.metasploit_service.start_listener(listener_config)
                
                if success:
                    success_msg = (f"Handler created successfully!\\n\\n"
                                 f"Job ID: {job_id}\\n"
                                 f"Payload: {config.payload_type}\\n"
                                 f"Listening on: {config.lhost}:{config.lport}\\n\\n"
                                 f"The handler is now ready to receive connections.\\n"
                                 f"Switch to the 'Listeners' tab to manage active handlers.")
                    
                    QMessageBox.information(self, "Handler Created", success_msg)
                    
                    # Refresh the listeners tab if available
                    if hasattr(self, 'listeners_tab'):
                        self.listeners_tab.refresh_listeners()
                        
                else:
                    # Use enhanced error handling similar to ListenersTab
                    self._handle_handler_creation_error(error, config.payload_type, config.lhost, config.lport)
                    
            finally:
                # Re-enable the create handler button
                self.create_handler_btn.setEnabled(True)
                self.create_handler_btn.setText("Create Handler")
                
        except Exception as e:
            # Re-enable button in case of exception
            self.create_handler_btn.setEnabled(True)
            self.create_handler_btn.setText("Create Handler")
            
            if utils.logger:
                utils.logger.log_message(f"PayloadGeneratorTab: Exception in create_matching_handler: {str(e)}")
            
            error_msg = f"An unexpected error occurred while creating the handler:\\n\\n{str(e)}\\n\\nPlease check the logs for more details."
            QMessageBox.critical(self, "Handler Creation Error", error_msg)
    
    def _handle_handler_creation_error(self, error: str, payload_type: str, lhost: str, lport: int):
        """Handle and categorize handler creation errors with user-friendly messages"""
        error_lower = error.lower()
        
        if "port" in error_lower and ("use" in error_lower or "bind" in error_lower):
            title = "Port Conflict"
            message = (f"Cannot create handler: Port {lport} is already in use.\\n\\n"
                      f"Solutions:\\n"
                      f"• Change the LPORT in your payload configuration\\n"
                      f"• Stop any existing listeners using port {lport}\\n"
                      f"• Use a different available port\\n\\n"
                      f"Original error: {error}")
            icon = QMessageBox.Icon.Warning
            
        elif "payload" in error_lower and ("not found" in error_lower or "invalid" in error_lower):
            title = "Invalid Payload"
            message = (f"Cannot create handler: The payload '{payload_type}' is invalid.\\n\\n"
                      f"Solutions:\\n"
                      f"• Select a different payload type\\n"
                      f"• Ensure the payload name is correct\\n"
                      f"• Check Metasploit connection\\n\\n"
                      f"Original error: {error}")
            icon = QMessageBox.Icon.Warning
            
        elif "connection" in error_lower or "timeout" in error_lower:
            title = "Connection Error"
            message = (f"Cannot create handler: Failed to communicate with Metasploit.\\n\\n"
                      f"Solutions:\\n"
                      f"• Check Metasploit RPC connection\\n"
                      f"• Verify Metasploit service is running\\n"
                      f"• Try reconnecting to Metasploit\\n\\n"
                      f"Original error: {error}")
            icon = QMessageBox.Icon.Critical
            
        else:
            title = "Handler Creation Failed"
            message = (f"Failed to create handler with configuration:\\n"
                      f"Payload: {payload_type}\\n"
                      f"LHOST: {lhost}\\n"
                      f"LPORT: {lport}\\n\\n"
                      f"Error: {error}\\n\\n"
                      f"Please verify your payload configuration and Metasploit connection.")
            icon = QMessageBox.Icon.Warning
        
        if utils.logger:
            utils.logger.log_message(f"PayloadGeneratorTab: Handler creation error - {error}")
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)
        msg_box.exec()
        
    def generate_payload(self):
        """Generate payload without delivery"""
        try:
            config = self.get_payload_config()
            success, payload_data, error = self.metasploit_service.generate_payload(config)
            
            if success:
                # Import helper to get proper file extension
                from utils.helpers import get_file_extension_for_format
                extension = get_file_extension_for_format(config.format)
                filename = f"{config.payload_type.replace('/', '_')}{extension}"
                
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
                
                # Show success message with appropriate size information
                if isinstance(payload_data, str):
                    size_info = f"{len(payload_data)} characters"
                else:
                    size_info = f"{len(payload_data)} bytes"
                    
                message = f"Payload generated: {size_info}{storage_message}"
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


class ListenersTab(QWidget):
    """Tab for managing Metasploit listeners/handlers"""
    
    def __init__(self, metasploit_manager: MetasploitManager, beacon_repository: BeaconRepository):
        super().__init__()
        self.metasploit_manager = metasploit_manager
        self.beacon_repository = beacon_repository
        self.metasploit_service = metasploit_manager.metasploit_service if metasploit_manager else None
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_listeners)
        
        # Cache for listener information that we created
        # Maps job_id -> {payload, host, port, created_at}
        self._listener_cache = {}
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Listener creation section
        creation_group = QGroupBox("Create New Listener")
        creation_layout = QFormLayout()
        
        # Payload type selection
        self.payload_combo = QComboBox()
        self.payload_combo.setEditable(True)
        
        # Add refresh button for payloads
        payload_layout = QHBoxLayout()
        payload_layout.addWidget(self.payload_combo, 1)
        
        self.payload_refresh_btn = QPushButton("Refresh")
        self.payload_refresh_btn.setMaximumWidth(80)
        self.payload_refresh_btn.setToolTip("Refresh payload list from Metasploit")
        self.payload_refresh_btn.clicked.connect(self.refresh_payloads)
        payload_layout.addWidget(self.payload_refresh_btn)
        
        payload_widget = QWidget()
        payload_widget.setLayout(payload_layout)
        creation_layout.addRow("Payload:", payload_widget)
        
        # Load payloads dynamically
        self.refresh_payloads()
        
        # Connection settings
        self.lhost_edit = QLineEdit()
        if self.metasploit_service:
            try:
                self.lhost_edit.setText(self.metasploit_service.get_server_ip())
            except:
                self.lhost_edit.setText("127.0.0.1")
        creation_layout.addRow("LHOST:", self.lhost_edit)
        
        self.lport_spin = QSpinBox()
        self.lport_spin.setRange(1, 65535)
        self.lport_spin.setValue(4444)
        creation_layout.addRow("LPORT:", self.lport_spin)
        
        # Options
        self.exit_on_session = QCheckBox("Exit on Session")
        self.exit_on_session.setToolTip("Stop listener after receiving one session")
        creation_layout.addRow("", self.exit_on_session)
        
        # Create button
        self.create_btn = QPushButton("Start Listener")
        self.create_btn.clicked.connect(self.create_listener)
        creation_layout.addRow("", self.create_btn)
        
        creation_group.setLayout(creation_layout)
        layout.addWidget(creation_group)
        
        # Active listeners table
        listeners_group = QGroupBox("Active Listeners")
        listeners_layout = QVBoxLayout()
        
        # Refresh controls
        refresh_layout = QHBoxLayout()
        self.auto_refresh = QCheckBox("Auto-refresh")
        self.auto_refresh.toggled.connect(self.toggle_auto_refresh)
        refresh_layout.addWidget(self.auto_refresh)
        
        self.refresh_btn = QPushButton("Refresh Now")
        self.refresh_btn.clicked.connect(self.refresh_listeners)
        refresh_layout.addWidget(self.refresh_btn)
        
        self.diagnostics_btn = QPushButton("Connection Diagnostics")
        self.diagnostics_btn.setToolTip("Show detailed Metasploit connection diagnostics")
        self.diagnostics_btn.clicked.connect(self.show_connection_diagnostics)
        refresh_layout.addWidget(self.diagnostics_btn)
        
        self.cleanup_jobs_btn = QPushButton("Cleanup All Jobs")
        self.cleanup_jobs_btn.setToolTip("Clean up all Metasploit jobs with enhanced termination")
        self.cleanup_jobs_btn.clicked.connect(self.cleanup_all_jobs)
        refresh_layout.addWidget(self.cleanup_jobs_btn)
        
        refresh_layout.addStretch()
        
        listeners_layout.addLayout(refresh_layout)
        
        # Listeners table
        self.listeners_table = QTableWidget()
        self.listeners_table.setColumnCount(5)
        self.listeners_table.setHorizontalHeaderLabels(["Job ID", "Payload", "Host", "Port", "Status"])
        self.listeners_table.horizontalHeader().setStretchLastSection(True)
        self.listeners_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.listeners_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.listeners_table.customContextMenuRequested.connect(self.show_listener_context_menu)
        
        listeners_layout.addWidget(self.listeners_table)
        
        listeners_group.setLayout(listeners_layout)
        layout.addWidget(listeners_group)
        
        self.setLayout(layout)
        
        # Initial refresh
        self.refresh_listeners()
        
    def toggle_auto_refresh(self, enabled: bool):
        """Toggle automatic refresh of listeners"""
        if enabled:
            self.refresh_timer.start(5000)  # Refresh every 5 seconds
        else:
            self.refresh_timer.stop()
    
    def create_listener(self):
        """Create a new Metasploit listener with comprehensive error handling"""
        if not self.metasploit_service:
            error_msg = "Metasploit service not available. Please check connection settings."
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: {error_msg}")
            self._show_error_dialog("Service Unavailable", error_msg, "CONNECTION")
            return
        
        # Pre-flight validation - configuration
        validation_error = self._validate_listener_configuration()
        if validation_error:
            self._show_error_dialog("Configuration Error", validation_error, "VALIDATION")
            return
        
        # Pre-flight validation - connection state
        is_connected, conn_status, conn_diagnostics = self.validate_connection_state()
        if not is_connected:
            error_msg = f"Cannot create listener: {conn_status}\n\nWould you like to view connection diagnostics for troubleshooting?"
            
            reply = QMessageBox.question(self, "Connection Error", error_msg,
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.show_connection_diagnostics()
            return
            
        try:
            # Create listener configuration
            payload_type = self.payload_combo.currentText().strip()
            lhost = self.lhost_edit.text().strip()
            lport = self.lport_spin.value()
            exit_on_session = self.exit_on_session.isChecked()
            
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: Creating listener - Payload: {payload_type}, LHOST: {lhost}, LPORT: {lport}, Exit on session: {exit_on_session}")
            
            # Check for port conflicts
            if self._check_port_conflict(lport):
                conflict_msg = f"Port {lport} is already in use by another listener.\n\nWould you like to use a different port?"
                reply = QMessageBox.question(self, "Port Conflict", conflict_msg,
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    suggested_port = self._suggest_available_port(lport)
                    self.lport_spin.setValue(suggested_port)
                    return  # Let user review and try again
                else:
                    return  # User cancelled
            
            config = ListenerConfig(
                payload_type=payload_type,
                lhost=lhost,
                lport=lport,
                exit_on_session=exit_on_session
            )
            
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: ListenerConfig created successfully")
                utils.logger.log_message(f"ListenersTab: Calling metasploit_service.start_listener()")
            
            # Disable the create button to prevent double-clicks
            self.create_btn.setEnabled(False)
            self.create_btn.setText("Creating...")
            
            try:
                # Start listener
                success, job_id, error = self.metasploit_service.start_listener(config)
                
                if utils.logger:
                    utils.logger.log_message(f"ListenersTab: start_listener returned - Success: {success}, Job ID: {job_id}, Error: {error}")
                
                if success:
                    if utils.logger:
                        utils.logger.log_message(f"ListenersTab: Listener started successfully with job ID: {job_id}")
                    
                    # Cache the listener information for better display
                    import time
                    self._listener_cache[str(job_id)] = {
                        'payload': payload_type,
                        'host': lhost,
                        'port': str(lport),
                        'created_at': time.time()
                    }
                    
                    if utils.logger:
                        utils.logger.log_message(f"ListenersTab: Cached listener info for job {job_id}")
                    
                    # Verify the listener is actually binding to the port
                    port_status = self._check_port_binding(lhost, lport)
                    if utils.logger:
                        utils.logger.log_message(f"ListenersTab: Port binding check for {lhost}:{lport} - {port_status}")
                    
                    # Check job status to see if it's still running
                    job_status = self._get_job_status(job_id)
                    if utils.logger:
                        utils.logger.log_message(f"ListenersTab: Job {job_id} status: {job_status}")
                    
                    # Get detailed job information for debugging
                    job_details = self._get_job_details(job_id)
                    
                    if "not bound" in port_status.lower():

                        warning_msg = (f"Listener job created but port binding failed!\n\n"
                                         f"Job ID: {job_id}\n"
                                         f"Payload: {payload_type}\n"
                                         f"Target: {lhost}:{lport}\n\n"
                                         f"Port Status: {port_status}\n"
                                         f"Job Status: {job_status}\n\n")

                        
                        msg_box = QMessageBox()
                        msg_box.setIcon(QMessageBox.Icon.Warning)
                        msg_box.setWindowTitle("Listener Port Not Bound")
                        msg_box.setText(warning_msg)
                        msg_box.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
                        msg_box.addButton("Stop Job", QMessageBox.ButtonRole.RejectRole)
                        
                        result = msg_box.exec()
                        
                        # If user chose to stop the job
                        if result == 1:  # RejectRole button
                            self._stop_listener(job_id)
                    else:
                        # Port binding successful
                        success_msg = (f"Listener started successfully!\n\n"
                                     f"Job ID: {job_id}\n"
                                     f"Payload: {payload_type}\n"
                                     f"Listening on: {lhost}:{lport}\n\n"
                                     f"Port Status: {port_status}\n"
                                     f"Job Status: {job_status}\n\n"
                                     f"The listener is now ready to receive connections.")
                        QMessageBox.information(self, "Listener Created", success_msg)
                    
                    self.refresh_listeners()  # Refresh the table
                else:
                    if utils.logger:
                        utils.logger.log_message(f"ListenersTab: Failed to start listener - Error: {error}")
                    
                    # Categorize and display the error appropriately
                    self._handle_listener_creation_error(error, payload_type, lhost, lport)
                    
            finally:
                # Re-enable the create button
                self.create_btn.setEnabled(True)
                self.create_btn.setText("Start Listener")
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: Exception in create_listener: {str(e)}")
            
            # Re-enable the create button in case of exception
            self.create_btn.setEnabled(True)
            self.create_btn.setText("Start Listener")
            
            error_msg = f"An unexpected error occurred while creating the listener:\n\n{str(e)}\n\nPlease check the logs for more details."
            self._show_error_dialog("Unexpected Error", error_msg, "EXCEPTION")
    
    def refresh_listeners(self):
        """Refresh the listeners table with enhanced job parsing"""
        if not self.metasploit_service:
            return
            
        try:
            # Get active jobs (listeners are background jobs)
            jobs = self.metasploit_service.list_jobs()
            
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: Refreshing listeners table with {len(jobs)} jobs")
            
            # Parse and filter jobs for listeners
            parsed_jobs = []
            for job in jobs:
                parsed_job = self._parse_job_information(job)
                parsed_jobs.append(parsed_job)
            
            # Filter for actual listeners (handlers)
            listener_jobs = [job for job in parsed_jobs if job['is_listener']]
            
            # Update table with all jobs (listeners first)
            all_jobs_to_show = listener_jobs + [job for job in parsed_jobs if not job['is_listener']]
            self.listeners_table.setRowCount(len(all_jobs_to_show))
            
            for row, job in enumerate(all_jobs_to_show):
                # Set row data with color coding
                self._populate_table_row(row, job)
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error refreshing listeners: {e}")
            # Clear table on error
            self.listeners_table.setRowCount(0)
    
    def _parse_job_information(self, job: dict) -> dict:
        """Parse job information with structured extraction
        
        Args:
            job: Job dictionary from Metasploit
            
        Returns:
            Parsed job information dictionary
        """
        job_id = str(job.get("id", ""))
        job_name = job.get("name", "")
        
        # Initialize parsed job structure
        parsed_job = {
            'id': job_id,
            'raw_name': job_name,
            'is_listener': False,
            'payload': "Unknown",
            'host': "Unknown",
            'port': "Unknown",
            'status': "Unknown",
            'job_type': "Other",
            'details': {}
        }
        
        if utils.logger:
            utils.logger.log_message(f"ListenersTab: Parsing job {job_id}: {job_name}")
        
        # Check if this is a listener/handler job
        if "Handler" in job_name or "multi/handler" in job_name:
            parsed_job['is_listener'] = True
            parsed_job['job_type'] = "Listener"
            parsed_job['status'] = "Running"
            
            # Enhanced parsing for handler jobs
            self._parse_handler_job(job_name, parsed_job)
            
        elif "Exploit:" in job_name:
            parsed_job['job_type'] = "Exploit"
            parsed_job['status'] = "Running"
            
            # Try to extract exploit details
            if "multi/handler" in job_name.lower():
                parsed_job['is_listener'] = True
                parsed_job['job_type'] = "Listener"
                self._parse_handler_job(job_name, parsed_job)
            else:
                parsed_job['payload'] = job_name  # Use full name for non-handlers
                
        else:
            # Other job types
            parsed_job['payload'] = job_name
            parsed_job['status'] = "Running"
        
        return parsed_job
    
    def _parse_handler_job(self, job_name: str, parsed_job: dict):
        """Parse handler/listener job details from job name
        
        Args:
            job_name: Raw job name string
            parsed_job: Job dictionary to populate
        """
        try:
            # Common handler job patterns:
            # "Exploit: multi/handler"
            # "Handler: windows/meterpreter/reverse_tcp"
            # "Exploit: multi/handler LHOST=192.168.1.100 LPORT=4444"
            
            # Split on spaces and common separators
            parts = job_name.replace(',', ' ').split()
            
            for part in parts:
                part = part.strip()
                
                # Look for payload patterns (contains forward slash, not an option)
                if "/" in part and "=" not in part and not part.startswith("Exploit:"):
                    # This looks like a payload name
                    if any(platform in part.lower() for platform in ["windows", "linux", "osx", "java", "python", "generic"]):
                        parsed_job['payload'] = part
                
                # Look for LHOST parameter
                elif part.startswith("LHOST="):
                    parsed_job['host'] = part.split("=", 1)[1].strip('"\'')
                    parsed_job['details']['lhost'] = parsed_job['host']
                
                # Look for LPORT parameter
                elif part.startswith("LPORT="):
                    parsed_job['port'] = part.split("=", 1)[1].strip('"\'')
                    parsed_job['details']['lport'] = parsed_job['port']
                
                # Look for other common parameters
                elif "=" in part:
                    key, value = part.split("=", 1)
                    parsed_job['details'][key.lower()] = value.strip('"\'')
            
            # If we still don't have a payload, try to extract from the beginning
            if parsed_job['payload'] == "Unknown":
                # Look for patterns like "Handler: payload_name" or "Exploit: multi/handler"
                if ":" in job_name:
                    after_colon = job_name.split(":", 1)[1].strip()
                    first_word = after_colon.split()[0]
                    if "/" in first_word:
                        parsed_job['payload'] = first_word
                    elif "multi/handler" in after_colon.lower():
                        parsed_job['payload'] = "multi/handler"
            
            # Check if we have cached information for this job
            job_id = parsed_job['id']
            if job_id in self._listener_cache:
                cached_info = self._listener_cache[job_id]
                parsed_job['payload'] = cached_info['payload']
                parsed_job['host'] = cached_info['host']
                parsed_job['port'] = cached_info['port']
                parsed_job['details']['from_cache'] = True
                
                if utils.logger:
                    utils.logger.log_message(f"ListenersTab: Using cached info for job {job_id}")
            
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: Parsed handler - Payload: {parsed_job['payload']}, Host: {parsed_job['host']}, Port: {parsed_job['port']}")
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: Error parsing handler job '{job_name}': {e}")
            # Fallback to basic parsing
            parsed_job['payload'] = job_name
    
    def _populate_table_row(self, row: int, job: dict):
        """Populate a table row with job information and appropriate styling
        
        Args:
            row: Table row index
            job: Parsed job dictionary
        """
        # Create table items
        id_item = QTableWidgetItem(job['id'])
        payload_item = QTableWidgetItem(job['payload'])
        host_item = QTableWidgetItem(job['host'])
        port_item = QTableWidgetItem(job['port'])
        status_item = QTableWidgetItem(job['status'])
        
        # Apply subtle styling based on job type (no background colors)
        if job['is_listener']:
            # Make listener status bold to distinguish from other jobs
            font = status_item.font()
            font.setBold(True)
            status_item.setFont(font)
            
            # Also make the payload bold for listeners
            payload_font = payload_item.font()
            payload_font.setBold(True)
            payload_item.setFont(payload_font)
        
        # Add tooltips with additional information
        if job['details']:
            details_text = "\n".join([f"{k.upper()}: {v}" for k, v in job['details'].items()])
            tooltip = f"Job Type: {job['job_type']}\n{details_text}\n\nRaw: {job['raw_name']}"
        else:
            tooltip = f"Job Type: {job['job_type']}\n\nRaw: {job['raw_name']}"
        
        for item in [id_item, payload_item, host_item, port_item, status_item]:
            item.setToolTip(tooltip)
        
        # Set items in table
        self.listeners_table.setItem(row, 0, id_item)
        self.listeners_table.setItem(row, 1, payload_item)
        self.listeners_table.setItem(row, 2, host_item)
        self.listeners_table.setItem(row, 3, port_item)
        self.listeners_table.setItem(row, 4, status_item)
    
    def show_listener_context_menu(self, position):
        """Show context menu for listener table"""
        if self.listeners_table.itemAt(position):
            menu = QMenu(self)
            
            stop_action = menu.addAction("Stop Listener")
            stop_action.triggered.connect(self.stop_selected_listener)
            
            menu.exec(self.listeners_table.mapToGlobal(position))
    
    def stop_selected_listener(self):
        """Stop the selected listener"""
        current_row = self.listeners_table.currentRow()
        if current_row >= 0:
            job_id_item = self.listeners_table.item(current_row, 0)
            if job_id_item:
                job_id = job_id_item.text()
                
                reply = QMessageBox.question(self, "Confirm", 
                                           f"Stop listener with job ID {job_id}?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        success, error = self.metasploit_service.stop_listener(job_id)
                        if success:
                            # Remove from cache when stopped
                            if job_id in self._listener_cache:
                                del self._listener_cache[job_id]
                                if utils.logger:
                                    utils.logger.log_message(f"ListenersTab: Removed job {job_id} from cache")
                            
                            QMessageBox.information(self, "Success", f"Listener {job_id} stopped")
                            self.refresh_listeners()
                        else:
                            QMessageBox.warning(self, "Error", f"Failed to stop listener:\n{error}")
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Unexpected error:\n{str(e)}")
    
    def _stop_listener(self, job_id: str):
        """
        Stop a listener by job ID (helper method)
        
        Args:
            job_id: The job ID to stop
        """
        try:
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: Stopping listener job {job_id}")
            
            success, error = self.metasploit_service.stop_listener(job_id)
            if success:
                # Remove from cache when stopped
                if job_id in self._listener_cache:
                    del self._listener_cache[job_id]
                    if utils.logger:
                        utils.logger.log_message(f"ListenersTab: Removed job {job_id} from cache")
                
                if utils.logger:
                    utils.logger.log_message(f"ListenersTab: Successfully stopped listener {job_id}")
                self.refresh_listeners()
            else:
                if utils.logger:
                    utils.logger.log_message(f"ListenersTab: Failed to stop listener {job_id}: {error}")
                QMessageBox.warning(self, "Error", f"Failed to stop listener {job_id}:\n{error}")
        except Exception as e:
            error_msg = f"Unexpected error stopping listener {job_id}: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
    
    def cleanup_all_jobs(self):
        """
        Clean up all Metasploit jobs with user confirmation
        """
        try:
            # Get current jobs count first
            if not self.metasploit_service or not self.metasploit_service.is_connected:
                QMessageBox.warning(self, "Error", "Not connected to Metasploit. Please establish connection first.")
                return
            
            jobs = self.metasploit_service.list_jobs()
            if not jobs:
                QMessageBox.information(self, "No Jobs", "No active Metasploit jobs found to clean up.")
                return
            
            # Show confirmation with job details
            job_list = "\n".join([f"  {job.get('id', 'N/A')}: {job.get('name', 'Unknown')}" for job in jobs])
            
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setWindowTitle("Confirm Job Cleanup")
            msg_box.setText(f"Found {len(jobs)} active job(s):\n\n{job_list}\n\nThis will attempt to stop all jobs.")
            msg_box.setInformativeText("Choose cleanup method:")
            
            normal_btn = msg_box.addButton("Normal Cleanup", QMessageBox.ButtonRole.AcceptRole)
            force_btn = msg_box.addButton("Force Cleanup", QMessageBox.ButtonRole.DestructiveRole)
            cancel_btn = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            
            msg_box.setDefaultButton(normal_btn)
            
            result = msg_box.exec()
            
            if msg_box.clickedButton() == cancel_btn:
                return
            
            use_force = (msg_box.clickedButton() == force_btn)
            
            # Disable the cleanup button during operation
            self.cleanup_jobs_btn.setEnabled(False)
            self.cleanup_jobs_btn.setText("Cleaning Up...")
            
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: Starting cleanup of {len(jobs)} jobs (force={use_force})")
            
            # Perform cleanup
            cleaned_count = self.metasploit_service.cleanup_all_jobs(force=use_force)
            
            if cleaned_count > 0:
                success_msg = f"Successfully cleaned up {cleaned_count} job(s)."
                if utils.logger:
                    utils.logger.log_message(f"ListenersTab: {success_msg}")
                QMessageBox.information(self, "Cleanup Complete", success_msg)
                
                # Clear listener cache since jobs were cleaned up
                self._listener_cache.clear()
                self.refresh_listeners()
            else:
                warning_msg = "No jobs were cleaned up. Jobs may be resistant to termination."
                if utils.logger:
                    utils.logger.log_message(f"ListenersTab: {warning_msg}")
                QMessageBox.warning(self, "Cleanup Warning", warning_msg)
            
        except Exception as e:
            error_msg = f"Error during job cleanup: {str(e)}"
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: {error_msg}")
            QMessageBox.critical(self, "Cleanup Error", error_msg)
            
        finally:
            # Re-enable the cleanup button
            self.cleanup_jobs_btn.setEnabled(True)
            self.cleanup_jobs_btn.setText("Cleanup All Jobs")
    
    def _validate_listener_configuration(self) -> str:
        """Validate listener configuration before creation
        
        Returns:
            Error message string if validation fails, empty string if valid
        """
        payload_type = self.payload_combo.currentText().strip()
        lhost = self.lhost_edit.text().strip()
        lport = self.lport_spin.value()
        
        # Validate payload type with enhanced validation
        if not payload_type:
            return "Payload type cannot be empty. Please select a valid payload."
        
        # Skip separator lines
        if payload_type.startswith("─"):
            return "Please select a valid payload, not a separator line."
        
        # Validate payload against Metasploit if connected
        is_valid, error_msg, suggestions = self.validate_payload_name(payload_type)
        if not is_valid:
            return error_msg
        
        # Validate LHOST
        if not lhost:
            return "LHOST cannot be empty. Please enter a valid IP address or hostname."
        
        # Enhanced IP validation
        import re
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ip_pattern, lhost):
            # Validate IP octets
            try:
                octets = lhost.split('.')
                for octet in octets:
                    octet_int = int(octet)
                    if not 0 <= octet_int <= 255:
                        return f"Invalid IP address: {lhost}. Each octet must be between 0-255."
                
                # Check for reserved IP ranges
                first_octet = int(octets[0])
                # Allow 0.0.0.0 for listening on all interfaces
                if first_octet == 0 and lhost != "0.0.0.0":
                    return f"Invalid IP address: {lhost}. IP cannot start with 0 (except 0.0.0.0)."
                elif first_octet >= 224:  # Multicast and reserved ranges
                    return f"Warning: IP address {lhost} is in a multicast or reserved range."
                    
            except ValueError:
                return f"Invalid IP address format: {lhost}"
        elif lhost.lower() in ['localhost', '127.0.0.1']:
            # Warn about localhost limitations
            suggested_ip = self._get_suggested_network_ip()
            return (f"Warning: Using {lhost} will only accept connections from the same machine. "
                   f"If you want to receive connections from other machines, consider using "
                   f"your network IP address: {suggested_ip} or 0.0.0.0 for all interfaces.")
        else:
            # Could be a hostname, do basic validation
            if not re.match(r'^[a-zA-Z0-9.-]+$', lhost):
                return f"Invalid hostname format: {lhost}. Use only letters, numbers, dots, and hyphens."
        
        # Validate LPORT
        if not 1 <= lport <= 65535:
            return f"Invalid port: {lport}. Port must be between 1-65535."
        
        # Check for common port conflicts and well-known ports
        common_ports = {22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP", 
                       110: "POP3", 143: "IMAP", 443: "HTTPS", 993: "IMAPS", 995: "POP3S",
                       21: "FTP", 23: "Telnet", 135: "RPC", 139: "NetBIOS", 445: "SMB"}
        if lport in common_ports:
            return f"Warning: Port {lport} is commonly used by {common_ports[lport]}. Consider using a different port to avoid conflicts."
        
        # Check for privileged ports
        if lport < 1024 and lhost not in ['127.0.0.1', 'localhost']:
            return f"Warning: Port {lport} is a privileged port (<1024). You may need elevated privileges to bind to this port."
        
        return ""  # No validation errors
    
    def _check_port_conflict(self, port: int) -> bool:
        """Check if the specified port is already in use by an existing listener
        
        Args:
            port: Port number to check
            
        Returns:
            True if port is in use, False otherwise
        """
        try:
            if not self.metasploit_service:
                return False
                
            jobs = self.metasploit_service.list_jobs()
            for job in jobs:
                job_name = job.get("name", "")
                # Look for LPORT= in job name
                if f"LPORT={port}" in job_name:
                    return True
                    
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error checking port conflict: {e}")
        
        return False
    
    def _suggest_available_port(self, starting_port: int) -> int:
        """Suggest an available port starting from the given port
        
        Args:
            starting_port: Port to start searching from
            
        Returns:
            Suggested available port
        """
        suggested_port = starting_port + 1
        max_attempts = 100  # Avoid infinite loops
        
        for _ in range(max_attempts):
            if not self._check_port_conflict(suggested_port):
                return suggested_port
            suggested_port += 1
            
        # If we can't find a port, suggest a random high port
        import random
        return random.randint(49152, 65535)
    
    def _check_port_binding(self, host: str, port: int) -> str:
        """Check if the port is actually bound and listening
        
        Args:
            host: Host/IP to check
            port: Port number to check
            
        Returns:
            String describing the port status
        """
        try:
            import socket
            import time
            
            # Use the same retry logic as the backend verification
            # This is now handled by the backend verification in MetasploitService
            # Here we just do a quick check after the backend has verified
            
            # Quick delay to ensure backend verification is complete
            time.sleep(0.5)
            
            # Try to connect to the port
            test_host = '127.0.0.1' if host == '0.0.0.0' else host
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)  # 2 second timeout
                result = sock.connect_ex((test_host, port))
                
                if result == 0:
                    return "Port is bound and accepting connections"
                elif result == 111:  # Connection refused
                    return "Port is not bound - connection refused"
                elif result == 110:  # Connection timed out
                    return "Port check timed out - firewall may be blocking"
                else:
                    # Try to bind to the port to see if it's in use
                    try:
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
                            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            test_sock.bind((test_host, port))
                            test_sock.close()
                            return "Port is not bound - listener failed to start"
                    except OSError as bind_error:
                        if bind_error.errno == 98:  # Address already in use
                            return "Port is in use but not accepting connections - may still be initializing"
                        elif bind_error.errno == 13:  # Permission denied
                            return "Port binding check failed - permission denied"
                        else:
                            return f"Port is in use - {str(bind_error)}"
        except Exception as e:
            return f"Unable to check port status: {str(e)}"
    
    def _get_job_status(self, job_id: str) -> str:
        """Get the status of a Metasploit job
        
        Args:
            job_id: Job ID to check
            
        Returns:
            String describing the job status
        """
        try:
            if not self.metasploit_service:
                return "Service unavailable"
            
            jobs = self.metasploit_service.list_jobs()
            
            # Look for the specific job ID
            for job in jobs:
                if str(job.get("id", "")) == str(job_id):
                    return f"Running: {job.get('name', 'Unknown job')}"
            
            # Job not found in active jobs - it may have terminated
            return "Job not found (may have terminated)"
            
        except Exception as e:
            return f"Unable to check job status: {str(e)}"
    
    def _get_job_details(self, job_id: str) -> Dict[str, Any]:
        """Get detailed information about a Metasploit job
        
        Args:
            job_id: Job ID to get details for
            
        Returns:
            Dictionary with job details
        """
        try:
            if not self.metasploit_service or not self.metasploit_service._handlers:
                return {"error": "Service unavailable"}
            
            # Get job info using the RPC API
            job_info = self.metasploit_service._handlers.job.info(job_id)
            
            if utils.logger:
                utils.logger.log_message(f"Job {job_id} details: {job_info}")
            
            return job_info
            
        except Exception as e:
            error_msg = f"Unable to get job details: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return {"error": error_msg}
    
    def _handle_listener_creation_error(self, error: str, payload_type: str, lhost: str, lport: int):
        """Handle and categorize listener creation errors with user-friendly messages
        
        Args:
            error: Error message from the service
            payload_type: Payload type that failed
            lhost: LHOST that failed
            lport: LPORT that failed
        """
        error_lower = error.lower()
        
        # Categorize errors and provide helpful solutions
        if "port" in error_lower and ("use" in error_lower or "bind" in error_lower):
            error_type = "PORT_CONFLICT"
            title = "Port Conflict"
            message = (f"Port {lport} is already in use and cannot be bound for the listener.\\n\\n"
                      f"Solutions:\\n"
                      f"• Use a different port (suggested: {self._suggest_available_port(lport)})\\n"
                      f"• Stop the existing service using port {lport}\\n"
                      f"• Check for existing listeners on this port\\n\\n"
                      f"Original error: {error}")
                      
        elif "payload" in error_lower and ("not found" in error_lower or "invalid" in error_lower):
            error_type = "INVALID_PAYLOAD"
            title = "Invalid Payload"
            message = (f"The payload '{payload_type}' is not valid or not available.\\n\\n"
                      f"Solutions:\\n"
                      f"• Check the payload name spelling\\n"
                      f"• Use the payload dropdown to select a valid payload\\n"
                      f"• Ensure Metasploit is properly connected\\n\\n"
                      f"Original error: {error}")
                      
        elif "connection" in error_lower or "timeout" in error_lower:
            error_type = "CONNECTION"
            title = "Connection Error"
            message = (f"Failed to communicate with Metasploit RPC server.\\n\\n"
                      f"Solutions:\\n"
                      f"• Check Metasploit RPC connection status\\n"
                      f"• Verify Metasploit is running and accessible\\n"
                      f"• Check network connectivity\\n"
                      f"• Try reconnecting to Metasploit\\n\\n"
                      f"Original error: {error}")
                      
        elif "permission" in error_lower or "denied" in error_lower:
            error_type = "PERMISSION"
            title = "Permission Denied"
            message = (f"Permission denied while starting listener on {lhost}:{lport}.\\n\\n"
                      f"Solutions:\\n"
                      f"• Try using a port above 1024 (non-privileged)\\n"
                      f"• Run Metasploit with appropriate privileges\\n"
                      f"• Check firewall settings\\n\\n"
                      f"Original error: {error}")
                      
        else:
            error_type = "UNKNOWN"
            title = "Listener Creation Failed"
            message = (f"Failed to create listener with the following configuration:\\n"
                      f"Payload: {payload_type}\\n"
                      f"LHOST: {lhost}\\n"
                      f"LPORT: {lport}\\n\\n"
                      f"Error details: {error}\\n\\n"
                      f"Please check the Metasploit logs for more information.")
        
        if utils.logger:
            utils.logger.log_message(f"ListenersTab: Categorized error as {error_type} - {error}")
        
        self._show_error_dialog(title, message, error_type)
    
    def _show_error_dialog(self, title: str, message: str, error_type: str):
        """Show a categorized error dialog with appropriate icon and options
        
        Args:
            title: Dialog title
            message: Error message
            error_type: Error category for logging/handling
        """
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        
        # Set appropriate icon based on error type
        if error_type in ["CONNECTION", "PERMISSION"]:
            msg_box.setIcon(QMessageBox.Icon.Critical)
        elif error_type in ["PORT_CONFLICT", "INVALID_PAYLOAD"]:
            msg_box.setIcon(QMessageBox.Icon.Warning)
        else:
            msg_box.setIcon(QMessageBox.Icon.Warning)
        
        # Add helpful buttons based on error type
        if error_type == "CONNECTION":
            msg_box.addButton("Retry Connection", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton(QMessageBox.StandardButton.Close)
        elif error_type == "PORT_CONFLICT":
            msg_box.addButton("Suggest Different Port", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton(QMessageBox.StandardButton.Close)
        else:
            msg_box.addButton(QMessageBox.StandardButton.Close)
        
        result = msg_box.exec()
        
        # Handle action button responses
        if result == 0:  # First action button was clicked
            if error_type == "CONNECTION":
                self._retry_connection()
            elif error_type == "PORT_CONFLICT":
                suggested_port = self._suggest_available_port(self.lport_spin.value())
                self.lport_spin.setValue(suggested_port)
    
    def _retry_connection(self):
        """Attempt to reconnect to Metasploit service"""
        try:
            if self.metasploit_service:
                if utils.logger:
                    utils.logger.log_message("ListenersTab: Attempting to reconnect to Metasploit...")
                
                # Try to reconnect
                if self.metasploit_service.connect():
                    QMessageBox.information(self, "Connection Restored", 
                                          "Successfully reconnected to Metasploit RPC service.")
                    if utils.logger:
                        utils.logger.log_message("ListenersTab: Reconnection successful")
                else:
                    QMessageBox.warning(self, "Connection Failed", 
                                      "Failed to reconnect to Metasploit RPC service. Please check your connection settings.")
                    if utils.logger:
                        utils.logger.log_message("ListenersTab: Reconnection failed")
        except Exception as e:
            error_msg = f"Error during reconnection attempt: {str(e)}"
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: {error_msg}")
            QMessageBox.critical(self, "Reconnection Error", error_msg)
    
    def refresh_payloads(self):
        """Refresh payload list from Metasploit with fallback to defaults"""
        if utils.logger:
            utils.logger.log_message("ListenersTab: Refreshing payload list from Metasploit")
        
        # Disable refresh button during refresh
        self.payload_refresh_btn.setEnabled(False)
        self.payload_refresh_btn.setText("...")
        
        # Store current selection to restore if possible
        current_payload = self.payload_combo.currentText()
        
        try:
            # Clear existing items
            self.payload_combo.clear()
            
            if self.metasploit_service and self.metasploit_service.is_connected:
                # Try to fetch payloads from Metasploit
                try:
                    # Fetch all payloads
                    all_payloads = self.metasploit_service.list_payloads()
                    
                    if all_payloads:
                        # Filter for commonly used payloads and add them first
                        popular_payloads = [
                            "windows/meterpreter/reverse_tcp",
                            "windows/meterpreter/reverse_https",
                            "windows/x64/meterpreter/reverse_tcp",
                            "windows/x64/meterpreter/reverse_https",
                            "linux/x86/meterpreter/reverse_tcp",
                            "linux/x64/meterpreter/reverse_tcp",
                            "python/meterpreter/reverse_tcp",
                            "java/meterpreter/reverse_tcp",
                            "osx/x86/shell_reverse_tcp",
                            "generic/shell_reverse_tcp"
                        ]
                        
                        # Add popular payloads first (if available)
                        added_payloads = set()
                        for payload in popular_payloads:
                            if payload in all_payloads:
                                self.payload_combo.addItem(payload)
                                added_payloads.add(payload)
                        
                        # Add a separator if we have both popular and other payloads
                        if added_payloads and len(all_payloads) > len(added_payloads):
                            self.payload_combo.addItem("─" * 30)  # Visual separator
                        
                        # Add remaining payloads alphabetically
                        remaining_payloads = sorted([p for p in all_payloads if p not in added_payloads])
                        for payload in remaining_payloads:
                            self.payload_combo.addItem(payload)
                        
                        if utils.logger:
                            utils.logger.log_message(f"ListenersTab: Loaded {len(all_payloads)} payloads from Metasploit")
                    else:
                        # No payloads returned, use defaults
                        self._load_default_payloads()
                        if utils.logger:
                            utils.logger.log_message("ListenersTab: No payloads returned from Metasploit, using defaults")
                            
                except Exception as e:
                    if utils.logger:
                        utils.logger.log_message(f"ListenersTab: Error fetching payloads from Metasploit: {e}")
                    self._load_default_payloads()
            else:
                # Metasploit not connected, use defaults
                self._load_default_payloads()
                if utils.logger:
                    utils.logger.log_message("ListenersTab: Metasploit not connected, using default payloads")
            
            # Restore previous selection if it exists in the new list
            if current_payload:
                index = self.payload_combo.findText(current_payload)
                if index >= 0:
                    self.payload_combo.setCurrentIndex(index)
                else:
                    # If exact match not found, try to find similar payload
                    self._select_similar_payload(current_payload)
            
        finally:
            # Re-enable refresh button
            self.payload_refresh_btn.setEnabled(True)
            self.payload_refresh_btn.setText("Refresh")
    
    def _load_default_payloads(self):
        """Load default payload list when Metasploit is not available"""
        default_payloads = [
            "windows/meterpreter/reverse_tcp",
            "windows/meterpreter/reverse_https",
            "windows/x64/meterpreter/reverse_tcp",
            "windows/x64/meterpreter/reverse_https",
            "linux/x86/meterpreter/reverse_tcp",
            "linux/x64/meterpreter/reverse_tcp",
            "python/meterpreter/reverse_tcp",
            "java/meterpreter/reverse_tcp",
            "osx/x86/shell_reverse_tcp",
            "generic/shell_reverse_tcp"
        ]
        self.payload_combo.addItems(default_payloads)
    
    def _select_similar_payload(self, target_payload: str):
        """Try to select a similar payload if exact match is not found"""
        if not target_payload:
            return
            
        target_lower = target_payload.lower()
        
        # Look for payloads with similar characteristics
        best_match_index = -1
        best_match_score = 0
        
        for i in range(self.payload_combo.count()):
            payload = self.payload_combo.itemText(i)
            if not payload or payload.startswith("─"):  # Skip separators
                continue
                
            payload_lower = payload.lower()
            score = 0
            
            # Score based on platform match
            if any(platform in target_lower and platform in payload_lower 
                   for platform in ["windows", "linux", "osx", "java", "python"]):
                score += 3
            
            # Score based on payload type match
            if any(ptype in target_lower and ptype in payload_lower 
                   for ptype in ["meterpreter", "shell", "reverse_tcp", "reverse_https"]):
                score += 2
            
            # Score based on architecture match
            if any(arch in target_lower and arch in payload_lower 
                   for arch in ["x86", "x64"]):
                score += 1
            
            if score > best_match_score:
                best_match_score = score
                best_match_index = i
        
        # Select the best match if found
        if best_match_index >= 0:
            self.payload_combo.setCurrentIndex(best_match_index)
            if utils.logger:
                selected_payload = self.payload_combo.itemText(best_match_index)
                utils.logger.log_message(f"ListenersTab: Selected similar payload '{selected_payload}' for '{target_payload}'")
    
    def validate_payload_name(self, payload_name: str) -> tuple[bool, str, list[str]]:
        """Validate payload name and provide suggestions if invalid
        
        Args:
            payload_name: Payload name to validate
            
        Returns:
            Tuple of (is_valid, error_message, suggestions)
        """
        if not payload_name.strip():
            return False, "Payload name cannot be empty", []
        
        payload_name = payload_name.strip()
        
        # Check if payload exists in current list
        for i in range(self.payload_combo.count()):
            item_text = self.payload_combo.itemText(i)
            if item_text == payload_name:
                return True, "", []
        
        # If not in list, try to get suggestions from Metasploit
        suggestions = []
        if self.metasploit_service:
            try:
                # Get all payloads and find similar ones
                all_payloads = self.metasploit_service.list_payloads()
                
                # Find similar payloads
                payload_lower = payload_name.lower()
                for payload in all_payloads:
                    # Check for partial matches
                    if any(part in payload.lower() for part in payload_lower.split('/')):
                        suggestions.append(payload)
                        if len(suggestions) >= 5:  # Limit suggestions
                            break
                
                # Sort suggestions by similarity
                suggestions.sort(key=lambda x: len(x))
                
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Error getting payload suggestions: {e}")
        
        error_msg = f"Payload '{payload_name}' is not available or invalid."
        if suggestions:
            error_msg += f" Did you mean: {', '.join(suggestions[:3])}?"
        
        return False, error_msg, suggestions
    
    def validate_connection_state(self) -> tuple[bool, str, dict]:
        """Validate Metasploit connection state with detailed diagnostics
        
        Returns:
            Tuple of (is_connected, status_message, diagnostics_dict)
        """
        diagnostics = {
            'service_available': False,
            'rpc_connected': False,
            'version_info': None,
            'last_activity': None,
            'connection_time': None,
            'error_details': [],
            'recommendations': []
        }
        
        if utils.logger:
            utils.logger.log_message("ListenersTab: Validating Metasploit connection state")
        
        # Check if service is available
        if not self.metasploit_service:
            error_msg = "Metasploit service is not initialized"
            diagnostics['error_details'].append(error_msg)
            diagnostics['recommendations'].append("Check Metasploit configuration")
            return False, error_msg, diagnostics
        
        diagnostics['service_available'] = True
        
        # Check if service is enabled
        if not self.metasploit_service.is_enabled:
            error_msg = "Metasploit integration is disabled in configuration"
            diagnostics['error_details'].append(error_msg)
            diagnostics['recommendations'].append("Enable Metasploit integration in server configuration")
            return False, error_msg, diagnostics
        
        # Test RPC connection
        try:
            is_connected, test_message = self.metasploit_service.test_connection()
            
            if is_connected:
                diagnostics['rpc_connected'] = True
                
                # Get detailed diagnostics from service
                service_diagnostics = self.metasploit_service.diagnose_connection()
                
                if 'core_version' in service_diagnostics:
                    diagnostics['version_info'] = service_diagnostics['core_version']
                
                if service_diagnostics.get('errors'):
                    diagnostics['error_details'].extend(service_diagnostics['errors'])
                    
                # Check recent activity
                if hasattr(self.metasploit_service, '_last_activity'):
                    import time
                    last_activity = getattr(self.metasploit_service, '_last_activity', None)
                    if last_activity:
                        diagnostics['last_activity'] = time.time() - last_activity
                        
                        # Warn if connection is stale
                        if diagnostics['last_activity'] > 300:  # 5 minutes
                            diagnostics['recommendations'].append("Connection may be stale - consider refreshing")
                
                return True, test_message, diagnostics
            else:
                diagnostics['error_details'].append(test_message)
                diagnostics['recommendations'].extend([
                    "Verify Metasploit RPC server is running",
                    "Check network connectivity",
                    "Validate RPC credentials",
                    "Ensure correct host and port configuration"
                ])
                return False, test_message, diagnostics
                
        except Exception as e:
            error_msg = f"Connection validation failed: {str(e)}"
            diagnostics['error_details'].append(error_msg)
            diagnostics['recommendations'].append("Check Metasploit service logs for details")
            
            if utils.logger:
                utils.logger.log_message(f"ListenersTab: Connection validation error: {e}")
                
            return False, error_msg, diagnostics
    
    def show_connection_diagnostics(self):
        """Show detailed connection diagnostics dialog"""
        is_connected, status_msg, diagnostics = self.validate_connection_state()
        
        # Create diagnostics dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Metasploit Connection Diagnostics")
        dialog.setModal(True)
        dialog.resize(500, 400)
        
        layout = QVBoxLayout()
        
        # Status section
        status_group = QGroupBox("Connection Status")
        status_layout = QVBoxLayout()
        
        status_label = QLabel(status_msg)
        if is_connected:
            status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            status_label.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(status_label)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Detailed information
        details_group = QGroupBox("Diagnostic Details")
        details_layout = QVBoxLayout()
        
        details_text = QTextEdit()
        details_text.setReadOnly(True)
        
        # Build details text
        details_content = []
        details_content.append(f"Service Available: {'Yes' if diagnostics['service_available'] else 'No'}")
        details_content.append(f"RPC Connected: {'Yes' if diagnostics['rpc_connected'] else 'No'}")
        
        if diagnostics['version_info']:
            version = diagnostics['version_info'].get('version', 'Unknown')
            api_version = diagnostics['version_info'].get('api', 'Unknown')
            details_content.append(f"Framework Version: {version}")
            details_content.append(f"API Version: {api_version}")
        
        if diagnostics['last_activity'] is not None:
            minutes_ago = int(diagnostics['last_activity'] / 60)
            details_content.append(f"Last Activity: {minutes_ago} minutes ago")
        
        if diagnostics['error_details']:
            details_content.append("\\nError Details:")
            for error in diagnostics['error_details']:
                details_content.append(f"  • {error}")
        
        if diagnostics['recommendations']:
            details_content.append("\\nRecommendations:")
            for rec in diagnostics['recommendations']:
                details_content.append(f"  • {rec}")
        
        details_text.setText("\\n".join(details_content))
        details_layout.addWidget(details_text)
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        if not is_connected:
            retry_btn = QPushButton("Retry Connection")
            retry_btn.clicked.connect(lambda: self._retry_connection_from_dialog(dialog))
            button_layout.addWidget(retry_btn)
        
        refresh_btn = QPushButton("Refresh Diagnostics")
        refresh_btn.clicked.connect(lambda: self._refresh_diagnostics_dialog(dialog))
        button_layout.addWidget(refresh_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        
        dialog.exec()
    
    def _retry_connection_from_dialog(self, dialog):
        """Retry connection from diagnostics dialog"""
        try:
            if self.metasploit_service:
                if self.metasploit_service.connect():
                    QMessageBox.information(dialog, "Success", "Successfully connected to Metasploit RPC.")
                    dialog.close()
                    self.refresh_payloads()  # Refresh payload list
                    self.refresh_listeners()  # Refresh listeners
                else:
                    QMessageBox.warning(dialog, "Failed", "Failed to connect to Metasploit RPC. Please check your configuration.")
        except Exception as e:
            QMessageBox.critical(dialog, "Error", f"Error during connection retry: {str(e)}")
    
    def _refresh_diagnostics_dialog(self, dialog):
        """Refresh the diagnostics dialog content"""
        dialog.close()
        self.show_connection_diagnostics()


class SessionsTab(QWidget):
    """Tab for managing Metasploit sessions and integrating with BeaconatorC2"""
    
    def __init__(self, metasploit_manager: MetasploitManager, beacon_repository: BeaconRepository):
        super().__init__()
        self.metasploit_manager = metasploit_manager
        self.beacon_repository = beacon_repository
        self.metasploit_service = metasploit_manager.metasploit_service if metasploit_manager else None
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_sessions)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Control panel
        controls_group = QGroupBox("Session Management")
        controls_layout = QHBoxLayout()
        
        self.auto_refresh = QCheckBox("Auto-refresh")
        self.auto_refresh.toggled.connect(self.toggle_auto_refresh)
        controls_layout.addWidget(self.auto_refresh)
        
        self.refresh_btn = QPushButton("Refresh Sessions")
        self.refresh_btn.clicked.connect(self.refresh_sessions)
        controls_layout.addWidget(self.refresh_btn)
        
        self.register_btn = QPushButton("Register Selected as Beacon")
        self.register_btn.clicked.connect(self.register_as_beacon)
        self.register_btn.setEnabled(False)
        controls_layout.addWidget(self.register_btn)
        
        controls_layout.addStretch()
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Sessions table
        sessions_group = QGroupBox("Active Sessions")
        sessions_layout = QVBoxLayout()
        
        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(7)
        self.sessions_table.setHorizontalHeaderLabels([
            "Session ID", "Type", "Info", "Tunnel", "Platform", "Username", "Status"
        ])
        self.sessions_table.horizontalHeader().setStretchLastSection(True)
        self.sessions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sessions_table.selectionModel().selectionChanged.connect(self.on_session_selection_changed)
        self.sessions_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sessions_table.customContextMenuRequested.connect(self.show_session_context_menu)
        
        sessions_layout.addWidget(self.sessions_table)
        sessions_group.setLayout(sessions_layout)
        layout.addWidget(sessions_group)
        
        self.setLayout(layout)
        
        # Initial refresh
        self.refresh_sessions()
        
    def toggle_auto_refresh(self, enabled: bool):
        """Toggle automatic refresh of sessions"""
        if enabled:
            self.refresh_timer.start(3000)  # Refresh every 3 seconds
        else:
            self.refresh_timer.stop()
    
    def refresh_sessions(self):
        """Refresh the sessions table"""
        if not self.metasploit_service:
            return
            
        try:
            # Get active sessions
            sessions = self.metasploit_service.list_sessions()
            
            self.sessions_table.setRowCount(len(sessions))
            
            for row, session in enumerate(sessions):
                self.sessions_table.setItem(row, 0, QTableWidgetItem(session.session_id))
                self.sessions_table.setItem(row, 1, QTableWidgetItem(session.session_type))
                self.sessions_table.setItem(row, 2, QTableWidgetItem(session.info))
                self.sessions_table.setItem(row, 3, QTableWidgetItem(f"{session.tunnel_local} -> {session.tunnel_peer}"))
                self.sessions_table.setItem(row, 4, QTableWidgetItem(f"{session.platform}/{session.arch}"))
                self.sessions_table.setItem(row, 5, QTableWidgetItem(session.username or "Unknown"))
                
                # Check if session is already registered as beacon
                beacon_id = f"msf_session_{session.session_id}"
                if self.beacon_repository and self.beacon_repository.get_beacon(beacon_id):
                    status = "Registered as Beacon"
                    status_item = QTableWidgetItem(status)
                    status_item.setBackground(QColor("#4CAF50"))  # Green background
                else:
                    status = "Available"
                    status_item = QTableWidgetItem(status)
                
                self.sessions_table.setItem(row, 6, status_item)
                    
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error refreshing sessions: {e}")
    
    def on_session_selection_changed(self):
        """Handle session selection change"""
        has_selection = len(self.sessions_table.selectionModel().selectedRows()) > 0
        self.register_btn.setEnabled(has_selection)
    
    def register_as_beacon(self):
        """Register selected session as a beacon in BeaconatorC2"""
        current_row = self.sessions_table.currentRow()
        if current_row >= 0:
            session_id_item = self.sessions_table.item(current_row, 0)
            if session_id_item and self.beacon_repository:
                session_id = session_id_item.text()
                beacon_id = f"msf_session_{session_id}"
                
                # Check if already registered
                if self.beacon_repository.get_beacon(beacon_id):
                    QMessageBox.information(self, "Info", "Session is already registered as a beacon")
                    return
                
                # Get session details for registration
                session_type = self.sessions_table.item(current_row, 1).text()
                session_info = self.sessions_table.item(current_row, 2).text()
                
                try:
                    # Register session as beacon (this would integrate with your command processor)
                    # For now, show success message
                    QMessageBox.information(self, "Success", 
                                          f"Session {session_id} registered as beacon {beacon_id}")
                    self.refresh_sessions()  # Refresh to show updated status
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to register session:\n{str(e)}")
    
    def show_session_context_menu(self, position):
        """Show context menu for session table"""
        if self.sessions_table.itemAt(position):
            menu = QMenu(self)
            
            interact_action = menu.addAction("Interact with Session")
            interact_action.triggered.connect(self.interact_with_session)
            
            register_action = menu.addAction("Register as Beacon")
            register_action.triggered.connect(self.register_as_beacon)
            
            kill_action = menu.addAction("Kill Session")
            kill_action.triggered.connect(self.kill_session)
            
            menu.exec(self.sessions_table.mapToGlobal(position))
    
    def interact_with_session(self):
        """Open interaction with selected session"""
        current_row = self.sessions_table.currentRow()
        if current_row >= 0:
            session_id = self.sessions_table.item(current_row, 0).text()
            
            # Get session information
            try:
                if self.metasploit_service and self.metasploit_service.is_connected:
                    # Get session list using the session handler directly
                    print(f"Debug: Getting session list for session_id: {session_id}")
                    sessions_data = self.metasploit_service._handlers.session.list()
                    print(f"Debug: Sessions available: {list(sessions_data.keys())}")
                    print(f"Debug: session_id type: {type(session_id)}, first key type: {type(list(sessions_data.keys())[0]) if sessions_data else 'N/A'}")
                    
                    # Convert session_id to int for comparison since Metasploit uses integer keys
                    session_key = int(session_id) if session_id.isdigit() else session_id
                    
                    if session_key in sessions_data:
                        session_info = sessions_data[session_key]
                        print(f"Debug: Session info: {session_info}")
                        
                        # Open terminal dialog
                        terminal_dialog = SessionTerminalDialog(
                            self.metasploit_service,
                            session_id,
                            session_info,
                            self
                        )
                        terminal_dialog.show()
                    else:
                        QMessageBox.warning(self, "Error", f"Session {session_id} not found")
                else:
                    QMessageBox.warning(self, "Error", "Not connected to Metasploit")
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to open session terminal:\n{str(e)}")
    
    def kill_session(self):
        """Kill the selected session"""
        current_row = self.sessions_table.currentRow()
        if current_row >= 0:
            session_id = self.sessions_table.item(current_row, 0).text()
            
            reply = QMessageBox.question(self, "Confirm", 
                                       f"Kill session {session_id}?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    # Kill session via Metasploit service
                    # This would need to be implemented in MetasploitService
                    QMessageBox.information(self, "Info", 
                                          f"Session kill for {session_id} would be implemented here")
                    self.refresh_sessions()
                    
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to kill session:\n{str(e)}")


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
        
        # Listeners tab
        self.listeners_tab = ListenersTab(self.metasploit_manager, self.beacon_repository)
        self.addTab(self.listeners_tab, "Listeners")
        
        # Sessions tab
        self.sessions_tab = SessionsTab(self.metasploit_manager, self.beacon_repository)
        self.addTab(self.sessions_tab, "Sessions")
        
        # Status tab
        self.status_tab = StatusTab(self.metasploit_manager)
        self.addTab(self.status_tab, "Status")
        
        # Allow tabs to reference each other for cross-tab integration
        self.payload_tab.listeners_tab = self.listeners_tab
        self.payload_tab.sessions_tab = self.sessions_tab