from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
                             QLineEdit, QSpinBox, QComboBox, QCheckBox, QTextEdit, QPushButton,
                             QLabel, QWidget, QMessageBox, QDialogButtonBox, QScrollArea, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from services.receivers import ReceiverConfig, ReceiverType, get_receiver_manager
from services.receivers.encoding_strategies import get_available_encodings
import uuid

class ReceiverConfigDialog(QDialog):
    """Dialog for creating/editing receiver configurations"""
    
    def __init__(self, config: ReceiverConfig = None, parent=None):
        super().__init__(parent)
        self.config = config or ReceiverConfig()
        self.is_editing = config is not None
        
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("Edit Receiver" if self.is_editing else "Add New Receiver")
        self.setModal(True)
        self.setMinimumSize(500, 700)
        
        # Add border and styling to distinguish from main application while matching dark theme
        self.setStyleSheet("""
            QDialog {
                border: 2px solid #888888;
                background-color: rgb(53, 53, 53);
            }
            QLineEdit, QSpinBox, QComboBox, QTextEdit {
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 3px;
                background-color: rgb(35, 35, 35);
                color: white;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #888888;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Create a single form with organized sections
        self.create_consolidated_form(layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
    def create_consolidated_form(self, main_layout):
        """Create a single consolidated form with all settings"""
        # Create a scrollable area for the form
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        form_widget = QWidget()
        form_layout = QVBoxLayout()
        form_layout.setSpacing(20)
        form_layout.setContentsMargins(20, 20, 20, 20)
        
        # Basic Information Section
        basic_content = QWidget()
        basic_content_layout = QVBoxLayout()
        basic_content_layout.setContentsMargins(0, 0, 0, 0)
        
        basic_title = QLabel("Basic Information")
        basic_title.setStyleSheet("font-weight: bold; color: white; margin-bottom: 5px;")
        basic_content_layout.addWidget(basic_title)
        
        basic_group = QGroupBox()
        basic_group.setStyleSheet("QGroupBox { border: 1px solid #666666; border-radius: 5px; background-color: rgb(35, 35, 35); }")
        basic_layout = QFormLayout()
        basic_layout.setSpacing(10)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter receiver name")
        basic_layout.addRow("Name:", self.name_edit)
        
        self.type_combo = QComboBox()
        self.populate_receiver_types()
        
        basic_layout.addRow("Type:", self.type_combo)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText("Optional description")
        basic_layout.addRow("Description:", self.description_edit)
        
        basic_group.setLayout(basic_layout)
        basic_content_layout.addWidget(basic_group)
        basic_content.setLayout(basic_content_layout)
        form_layout.addWidget(basic_content)
        
        # Network Configuration Section
        network_content = QWidget()
        network_content_layout = QVBoxLayout()
        network_content_layout.setContentsMargins(0, 0, 0, 0)
        
        network_title = QLabel("Network Configuration")
        network_title.setStyleSheet("font-weight: bold; color: white; margin-bottom: 5px;")
        network_content_layout.addWidget(network_title)
        
        network_group = QGroupBox()
        network_group.setStyleSheet("QGroupBox { border: 1px solid #666666; border-radius: 5px; background-color: rgb(35, 35, 35); }")
        network_layout = QFormLayout()
        network_layout.setSpacing(10)
        
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("0.0.0.0 (all interfaces)")
        network_layout.addRow("Host/Interface:", self.host_edit)
        
        self.port_edit = QLineEdit()
        self.port_edit.setText("5074")
        self.port_edit.setPlaceholderText("1-65535")
        network_layout.addRow("Port:", self.port_edit)
        
        self.buffer_size_edit = QLineEdit()
        self.buffer_size_edit.setText("1048576")
        self.buffer_size_edit.setPlaceholderText("Buffer size in bytes (e.g., 1048576)")
        network_layout.addRow("Buffer Size:", self.buffer_size_edit)
        
        self.timeout_edit = QLineEdit()
        self.timeout_edit.setText("30")
        self.timeout_edit.setPlaceholderText("Timeout in seconds (5-300)")
        network_layout.addRow("Connection Timeout:", self.timeout_edit)
        
        network_group.setLayout(network_layout)
        network_content_layout.addWidget(network_group)
        network_content.setLayout(network_content_layout)
        form_layout.addWidget(network_content)
        
        # Encoding Configuration Section
        encoding_content = QWidget()
        encoding_content_layout = QVBoxLayout()
        encoding_content_layout.setContentsMargins(0, 0, 0, 0)
        
        encoding_title = QLabel("Encoding Configuration")
        encoding_title.setStyleSheet("font-weight: bold; color: white; margin-bottom: 5px;")
        encoding_content_layout.addWidget(encoding_title)
        
        encoding_group = QGroupBox()
        encoding_group.setStyleSheet("QGroupBox { border: 1px solid #666666; border-radius: 5px; background-color: rgb(35, 35, 35); }")
        encoding_layout = QVBoxLayout()
        encoding_layout.setSpacing(10)
        
        # Encoding type selection
        encoding_form = QFormLayout()
        self.encoding_combo = QComboBox()
        available_encodings = get_available_encodings()
        for key, name in available_encodings.items():
            self.encoding_combo.addItem(name, key)
        self.encoding_combo.currentTextChanged.connect(self.on_encoding_changed)
        encoding_form.addRow("Encoding Type:", self.encoding_combo)
        encoding_layout.addLayout(encoding_form)
        
        # Encoding configuration section
        self.encoding_config_layout = QFormLayout()
        encoding_layout.addLayout(self.encoding_config_layout)
        
        # Initialize encoding config widgets
        self.encoding_config_widgets = {}
        self.update_encoding_config_ui()
        
        encoding_group.setLayout(encoding_layout)
        encoding_content_layout.addWidget(encoding_group)
        encoding_content.setLayout(encoding_content_layout)
        form_layout.addWidget(encoding_content)
        
        # Advanced Settings Section
        advanced_content = QWidget()
        advanced_content_layout = QVBoxLayout()
        advanced_content_layout.setContentsMargins(0, 0, 0, 0)
        
        advanced_title = QLabel("Advanced Settings")
        advanced_title.setStyleSheet("font-weight: bold; color: white; margin-bottom: 5px;")
        advanced_content_layout.addWidget(advanced_title)
        
        advanced_group = QGroupBox()
        advanced_group.setStyleSheet("QGroupBox { border: 1px solid #666666; border-radius: 5px; background-color: rgb(35, 35, 35); }")
        advanced_layout = QFormLayout()
        advanced_layout.setSpacing(10)
        
        self.max_connections_edit = QLineEdit()
        self.max_connections_edit.setText("100")
        self.max_connections_edit.setPlaceholderText("Max concurrent connections (1-1000)")
        advanced_layout.addRow("Max Connections:", self.max_connections_edit)
        
        self.conn_timeout_edit = QLineEdit()
        self.conn_timeout_edit.setText("300")
        self.conn_timeout_edit.setPlaceholderText("Connection timeout in seconds (60-3600)")
        advanced_layout.addRow("Connection Timeout:", self.conn_timeout_edit)
        
        self.keep_alive_check = QCheckBox("Enable keep-alive")
        self.keep_alive_check.setChecked(True)
        advanced_layout.addRow("", self.keep_alive_check)
        
        advanced_group.setLayout(advanced_layout)
        advanced_content_layout.addWidget(advanced_group)
        advanced_content.setLayout(advanced_content_layout)
        form_layout.addWidget(advanced_content)
        
        # Startup Options Section
        startup_content = QWidget()
        startup_content_layout = QVBoxLayout()
        startup_content_layout.setContentsMargins(0, 0, 0, 0)
        
        startup_title = QLabel("Startup Options")
        startup_title.setStyleSheet("font-weight: bold; color: white; margin-bottom: 5px;")
        startup_content_layout.addWidget(startup_title)
        
        startup_group = QGroupBox()
        startup_group.setStyleSheet("QGroupBox { border: 1px solid #666666; border-radius: 5px; background-color: rgb(35, 35, 35); }")
        startup_layout = QFormLayout()
        startup_layout.setSpacing(10)
        
        self.auto_start_check = QCheckBox("Start automatically when application launches")
        startup_layout.addRow("Auto-start:", self.auto_start_check)
        
        startup_group.setLayout(startup_layout)
        startup_content_layout.addWidget(startup_group)
        startup_content.setLayout(startup_content_layout)
        form_layout.addWidget(startup_content)
        
        form_widget.setLayout(form_layout)
        scroll_area.setWidget(form_widget)
        main_layout.addWidget(scroll_area)
    
    def populate_receiver_types(self):
        """Populate receiver types from registry"""
        try:
            # Get receiver manager and supported types from registry
            manager = get_receiver_manager()
            supported_types = manager.get_supported_receiver_types()
            
            # Clear existing items
            self.type_combo.clear()
            
            # Add supported receiver types with descriptions
            for receiver_type in supported_types:
                info = manager.get_receiver_type_info(receiver_type)
                description = info.get('description', '') if info else ''
                
                # Create display name
                display_name = receiver_type.value.upper()
                
                # Add item to combo box
                self.type_combo.addItem(display_name, receiver_type.value)
                
                # Add description as tooltip if available
                if description:
                    index = self.type_combo.count() - 1
                    self.type_combo.setItemData(index, description, Qt.ItemDataRole.ToolTipRole)
                    
        except Exception as e:
            # Fallback to hardcoded types if registry fails
            print(f"Warning: Failed to load receiver types from registry: {e}")
            self.populate_fallback_types()
    
    def populate_fallback_types(self):
        """Fallback method to populate receiver types if registry fails"""
        fallback_types = [
            (ReceiverType.TCP, "TCP socket receiver"),
            (ReceiverType.UDP, "UDP datagram receiver"), 
            (ReceiverType.SMB, "SMB named pipe receiver"),
            (ReceiverType.HTTP, "HTTP REST receiver"),
            (ReceiverType.METASPLOIT, "Metasploit framework receiver")
        ]
        
        self.type_combo.clear()
        
        for receiver_type, description in fallback_types:
            display_name = receiver_type.value.upper()
            self.type_combo.addItem(display_name, receiver_type.value)
            
            # Add description as tooltip
            index = self.type_combo.count() - 1
            self.type_combo.setItemData(index, description, Qt.ItemDataRole.ToolTipRole)
        
    def on_encoding_changed(self):
        """Handle encoding type change"""
        self.update_encoding_config_ui()
        
    def update_encoding_config_ui(self):
        """Update encoding configuration UI based on selected type"""
        # Clear existing widgets
        for widget in self.encoding_config_widgets.values():
            widget.setParent(None)
        self.encoding_config_widgets.clear()
        
        # Clear layout
        while self.encoding_config_layout.count():
            item = self.encoding_config_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                
        # Get selected encoding type
        encoding_type = self.encoding_combo.currentData()
        
        if encoding_type == "xor":
            # XOR key configuration
            key_edit = QLineEdit()
            key_edit.setPlaceholderText("Enter XOR key")
            key_edit.setText("default_key")
            self.encoding_config_widgets["key"] = key_edit
            self.encoding_config_layout.addRow("XOR Key:", key_edit)
            
        elif encoding_type == "rot":
            # ROT shift configuration
            shift_edit = QLineEdit()
            shift_edit.setText("13")
            shift_edit.setPlaceholderText("Shift value (1-255)")
            self.encoding_config_widgets["shift"] = shift_edit
            self.encoding_config_layout.addRow("ROT Shift:", shift_edit)
            
        else:
            # Plain text or Base64 - no configuration needed
            info_label = QLabel("No additional configuration required for this encoding type.")
            info_label.setStyleSheet("color: #888888; font-style: italic;")
            self.encoding_config_layout.addRow(info_label)
            
    def load_config(self):
        """Load configuration into UI"""
        if not self.config:
            return
            
        # Basic settings
        self.name_edit.setText(self.config.name)
        self.description_edit.setPlainText(self.config.description)
        self.auto_start_check.setChecked(self.config.auto_start)
        
        # Set receiver type (handle both string and enum safely)
        if isinstance(self.config.receiver_type, str):
            receiver_type_value = self.config.receiver_type
        else:
            receiver_type_value = self.config.receiver_type.value
            
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == receiver_type_value:
                self.type_combo.setCurrentIndex(i)
                break
                
        # Network settings
        self.host_edit.setText(self.config.host)
        self.port_edit.setText(str(self.config.port))
        self.buffer_size_edit.setText(str(self.config.buffer_size))
        self.timeout_edit.setText(str(self.config.timeout))
        
        # Encoding settings
        for i in range(self.encoding_combo.count()):
            if self.encoding_combo.itemData(i) == self.config.encoding_type:
                self.encoding_combo.setCurrentIndex(i)
                break
        self.update_encoding_config_ui()
        
        # Load encoding config
        for key, value in self.config.encoding_config.items():
            if key in self.encoding_config_widgets:
                widget = self.encoding_config_widgets[key]
                if hasattr(widget, 'setText'):
                    widget.setText(str(value))
                elif hasattr(widget, 'setValue'):
                    widget.setValue(int(value))
                    
        # Advanced settings
        self.max_connections_edit.setText(str(self.config.max_connections))
        self.conn_timeout_edit.setText(str(self.config.connection_timeout))
        self.keep_alive_check.setChecked(self.config.keep_alive)
        
    def get_config(self) -> ReceiverConfig:
        """Get configuration from UI"""
        # Create new config or update existing
        if self.is_editing:
            config = self.config
        else:
            config = ReceiverConfig()
            config.receiver_id = str(uuid.uuid4())
            
        # Basic settings
        config.name = self.name_edit.text().strip()
        config.description = self.description_edit.toPlainText().strip()
        config.enabled = True  # All receivers are enabled by default
        config.auto_start = self.auto_start_check.isChecked()
        
        # Handle receiver type conversion safely
        try:
            current_data = self.type_combo.currentData()
            if isinstance(current_data, str):
                config.receiver_type = ReceiverType(current_data)
            else:
                config.receiver_type = current_data
        except ValueError:
            # Fallback to TCP if conversion fails
            config.receiver_type = ReceiverType.TCP
        
        # Network settings
        config.host = self.host_edit.text().strip() or "0.0.0.0"
        config.port = int(self.port_edit.text() or "5074")
        config.buffer_size = int(self.buffer_size_edit.text() or "1048576")
        config.timeout = int(self.timeout_edit.text() or "30")
        
        # Encoding settings
        config.encoding_type = self.encoding_combo.currentData()
        config.encoding_config = {}
        
        for key, widget in self.encoding_config_widgets.items():
            if hasattr(widget, 'text'):
                config.encoding_config[key] = widget.text()
            elif hasattr(widget, 'value'):
                config.encoding_config[key] = widget.value()
                
        # Advanced settings
        config.max_connections = int(self.max_connections_edit.text() or "100")
        config.connection_timeout = int(self.conn_timeout_edit.text() or "300")
        config.keep_alive = self.keep_alive_check.isChecked()
        
        return config
        
    def accept(self):
        """Validate and accept the dialog"""
        config = self.get_config()
        
        # Validate configuration
        is_valid, error = config.validate()
        if not is_valid:
            QMessageBox.warning(self, "Invalid Configuration", error)
            return
            
        super().accept()