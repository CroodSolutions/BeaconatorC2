from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QFrame, QGridLayout, QSizePolicy, QMessageBox,
                             QAbstractItemView, QDialog, QProgressBar)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from utils import FontManager
from services.receivers import ReceiverManager, ReceiverConfig, ReceiverType
from .receiver_config_dialog import ReceiverConfigDialog
import threading
import time

class ReceiverOperationWorker(QThread):
    """Worker thread for receiver operations"""
    operation_completed = pyqtSignal(str, str, bool, str)  # receiver_id, operation, success, message
    
    def __init__(self, receiver_manager, operation, receiver_id, config=None):
        super().__init__()
        self.receiver_manager = receiver_manager
        self.operation = operation
        self.receiver_id = receiver_id
        self.config = config
        
    def run(self):
        try:
            if self.operation == "start":
                success = self.receiver_manager.start_receiver(self.receiver_id)
                message = "Receiver started successfully!" if success else "Failed to start receiver."
            elif self.operation == "stop":
                success = self.receiver_manager.stop_receiver(self.receiver_id)
                message = "Receiver stopped successfully!" if success else "Failed to stop receiver."
            elif self.operation == "restart":
                success = self.receiver_manager.restart_receiver(self.receiver_id)
                message = "Receiver restarted successfully!" if success else "Failed to restart receiver."
            elif self.operation == "remove":
                success = self.receiver_manager.remove_receiver(self.receiver_id)
                message = "Receiver removed successfully!" if success else "Failed to remove receiver."
            elif self.operation == "update":
                success = self.receiver_manager.update_receiver_config(self.receiver_id, self.config)
                message = "Receiver updated successfully!" if success else "Failed to update receiver."
            else:
                success = False
                message = f"Unknown operation: {self.operation}"
                
            self.operation_completed.emit(self.receiver_id, self.operation, success, message)
            
        except Exception as e:
            self.operation_completed.emit(self.receiver_id, self.operation, False, str(e))

class ReceiversWidget(QWidget):
    """Widget for managing and monitoring receiver instances"""
    
    def __init__(self, command_processor=None, file_transfer_service=None, receiver_manager=None):
        super().__init__()
        self.active_operations = {}  # Track ongoing operations by receiver_id
        self.command_processor = command_processor
        self.file_transfer_service = file_transfer_service
        
        # Use provided receiver manager or create a new one
        if receiver_manager:
            self.receiver_manager = receiver_manager
        else:
            # Initialize receiver manager
            self.receiver_manager = ReceiverManager(
                command_processor=command_processor,
                file_transfer_service=file_transfer_service
            )
        
        # Connect receiver manager signals
        self.receiver_manager.receiver_added.connect(self.refresh_receivers_table)
        self.receiver_manager.receiver_removed.connect(self.refresh_receivers_table)
        self.receiver_manager.receiver_status_changed.connect(self.on_receiver_status_changed)
        self.receiver_manager.receiver_stats_updated.connect(self.on_receiver_stats_updated)
        self.receiver_manager.error_occurred.connect(self.on_receiver_error)
        
        # Setup font management
        try:
            font_manager = FontManager()
            font_manager.add_relative_font_widget(self, 0)
        except:
            pass
            
        self.setup_ui()
        self.refresh_receivers_table()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Page title and controls
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Receiver Management")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Control buttons
        self.add_receiver_btn = QPushButton("Add Receiver")
        self.add_receiver_btn.clicked.connect(self.add_receiver)
        header_layout.addWidget(self.add_receiver_btn)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_receivers_table)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Receiver management table (direct table without container)
        self.receivers_table = self.create_receivers_table()
        layout.addWidget(self.receivers_table)
        
        # Summary statistics
        self.summary_group = self.create_summary_group()
        layout.addWidget(self.summary_group)
        
        layout.addStretch()
        self.setLayout(layout)
        
    def create_receivers_table(self):
        """Create receivers management table"""
        receivers_table = QTableWidget(0, 7)
        receivers_table.setHorizontalHeaderLabels([
            "Name", "Type", "Status", "Port", "Encoding", "Beacons", "Actions"
        ])
        
        # Configure table
        header = receivers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Type
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Status
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Port
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Encoding
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Beacons
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Actions

        
        receivers_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        receivers_table.setMinimumHeight(200)
        
        return receivers_table
        
    def create_summary_group(self):
        """Create summary statistics group"""
        group = QGroupBox("Summary Statistics")
        layout = QGridLayout()
        
        self.total_receivers_label = QLabel("Total Receivers:")
        self.total_receivers_value = QLabel("0")
        
        self.running_receivers_label = QLabel("Running:")
        self.running_receivers_value = QLabel("0")
        
        self.total_beacons_label = QLabel("Online Beacons:")
        self.total_beacons_value = QLabel("0")
        
        self.data_transferred_label = QLabel("Data Transferred:")
        self.data_transferred_value = QLabel("0 MB")
        
        layout.addWidget(self.total_receivers_label, 0, 0)
        layout.addWidget(self.total_receivers_value, 0, 1)
        layout.addWidget(self.running_receivers_label, 0, 2)
        layout.addWidget(self.running_receivers_value, 0, 3)
        layout.addWidget(self.total_beacons_label, 1, 0)
        layout.addWidget(self.total_beacons_value, 1, 1)
        layout.addWidget(self.data_transferred_label, 1, 2)
        layout.addWidget(self.data_transferred_value, 1, 3)
        
        group.setLayout(layout)
        return group
        
    def refresh_receivers_table(self, receiver_id=None):
        """Refresh the receivers table"""
        receivers = self.receiver_manager.get_all_receivers()
        configs = self.receiver_manager.get_receiver_configs()
        
        self.receivers_table.setRowCount(len(configs))
        
        for row, (rid, config) in enumerate(configs.items()):
            receiver = receivers.get(rid)
            
            # Name
            self.receivers_table.setItem(row, 0, QTableWidgetItem(config.name or "Unnamed"))
            
            # Type (handle both string and enum safely)
            if isinstance(config.receiver_type, str):
                type_display = config.receiver_type.upper()
            else:
                type_display = config.receiver_type.value.upper()
            self.receivers_table.setItem(row, 1, QTableWidgetItem(type_display))
            
            # Status
            if receiver:
                status = receiver.get_status_display()
                status_item = QTableWidgetItem(status)
                if receiver.status.name == "RUNNING":
                    status_item.setForeground(Qt.GlobalColor.green)
                elif receiver.status.name == "ERROR":
                    status_item.setForeground(Qt.GlobalColor.red)
                else:
                    status_item.setForeground(Qt.GlobalColor.gray)
            else:
                status_item = QTableWidgetItem("Not Created")
                status_item.setForeground(Qt.GlobalColor.gray)
            self.receivers_table.setItem(row, 2, status_item)
            
            # Port
            self.receivers_table.setItem(row, 3, QTableWidgetItem(str(config.port)))
            
            # Encoding
            encoding_display = config.encoding_type.title()
            if config.encoding_config:
                if config.encoding_type == "xor":
                    key = config.encoding_config.get("key", "default_key")
                    encoding_display += f" (Key: {key[:8]}...)" if len(key) > 8 else f" (Key: {key})"
                elif config.encoding_type == "rot":
                    shift = config.encoding_config.get("shift", 13)
                    encoding_display += f" (Shift: {shift})"
            self.receivers_table.setItem(row, 4, QTableWidgetItem(encoding_display))
            
            # Beacons (get online beacon count for this specific receiver)
            if self.receiver_manager and hasattr(self.receiver_manager, 'command_processor') and hasattr(self.receiver_manager.command_processor, 'beacon_repository'):
                beacon_count = str(self.receiver_manager.command_processor.beacon_repository.get_online_beacons_count_by_receiver(rid))
            else:
                beacon_count = "0"
            self.receivers_table.setItem(row, 5, QTableWidgetItem(beacon_count))
            
            # Actions (create button widget or loading widget)
            if rid in self.active_operations:
                # Show loading widget for ongoing operations
                operation = self.active_operations[rid]
                actions_widget = self.create_loading_widget(f"{operation.title()}...")
            else:
                # Show normal action buttons
                actions_widget = self.create_action_buttons(rid, receiver)
            self.receivers_table.setCellWidget(row, 6, actions_widget)
            
        # Store receiver IDs for reference
        self.receiver_ids = list(configs.keys())
    
    def create_loading_widget(self, text: str):
        """Create a loading widget with text"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        # Create a simple animated loading indicator using QProgressBar
        progress = QProgressBar()
        progress.setRange(0, 0)  # Indeterminate progress
        progress.setMaximumHeight(20)
        progress.setMaximumWidth(80)
        progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid grey;
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4A90E2;
                border-radius: 2px;
            }
        """)
        layout.addWidget(progress)
        
        # Add loading text
        label = QLabel(text)
        label.setStyleSheet("color: #4A90E2; font-style: italic;")
        layout.addWidget(label)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def start_receiver_operation(self, receiver_id: str, operation: str, config=None):
        """Start a receiver operation in background"""
        if receiver_id in self.active_operations:
            return  # Operation already in progress
            
        # Track the operation
        self.active_operations[receiver_id] = operation
        
        # Refresh table to show loading state
        self.refresh_receivers_table()
        
        # Start worker thread
        worker = ReceiverOperationWorker(self.receiver_manager, operation, receiver_id, config)
        worker.operation_completed.connect(self.on_operation_completed)
        worker.start()
        
        # Keep reference to prevent garbage collection
        if not hasattr(self, '_workers'):
            self._workers = []
        self._workers.append(worker)
    
    def on_operation_completed(self, receiver_id: str, operation: str, success: bool, message: str):
        """Handle completion of receiver operation"""
        # Remove from active operations
        if receiver_id in self.active_operations:
            del self.active_operations[receiver_id]
        
        # Refresh table to show normal buttons
        self.refresh_receivers_table()
        
        # Show result only for failures (success is implied by UI change)
        if not success:
            QMessageBox.warning(self, "Operation Failed", message)
        
        # Clean up worker reference
        sender = self.sender()
        if hasattr(self, '_workers') and sender in self._workers:
            self._workers.remove(sender)
    
    def create_action_buttons(self, receiver_id: str, receiver):
        """Create action buttons widget for a receiver row"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        # Edit button
        edit_btn = QPushButton("Edit")
        edit_btn.setMaximumHeight(25)
        edit_btn.clicked.connect(lambda: self.edit_receiver(receiver_id))
        layout.addWidget(edit_btn)
        
        # Start/Stop/Restart button
        if receiver and receiver.status.name == "RUNNING":
            # Stop button
            stop_btn = QPushButton("Stop")
            stop_btn.setMaximumHeight(25)
            stop_btn.clicked.connect(lambda: self.start_receiver_operation(receiver_id, "stop"))
            layout.addWidget(stop_btn)
            
            # Restart button  
            restart_btn = QPushButton("Restart")
            restart_btn.setMaximumHeight(25)
            restart_btn.clicked.connect(lambda: self.start_receiver_operation(receiver_id, "restart"))
            layout.addWidget(restart_btn)
        else:
            # Start button
            start_btn = QPushButton("Start")
            start_btn.setMaximumHeight(25)
            start_btn.clicked.connect(lambda: self.start_receiver_operation(receiver_id, "start"))
            layout.addWidget(start_btn)
        
        # Remove button
        remove_btn = QPushButton("Remove")
        remove_btn.setMaximumHeight(25)
        remove_btn.clicked.connect(lambda: self.confirm_remove_receiver(receiver_id))
        layout.addWidget(remove_btn)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
                
    def update_summary_stats(self):
        """Update summary statistics"""
        summary = self.receiver_manager.get_receiver_summary()
        
        self.total_receivers_value.setText(str(summary["total_receivers"]))
        self.running_receivers_value.setText(str(summary["running_receivers"]))
        
        # Get online beacon count from beacon repository
        if self.receiver_manager and hasattr(self.receiver_manager, 'command_processor') and hasattr(self.receiver_manager.command_processor, 'beacon_repository'):
            beacon_count = self.receiver_manager.command_processor.beacon_repository.get_online_beacons_count()
        else:
            beacon_count = 0
        self.total_beacons_value.setText(str(beacon_count))
        
        # Format data transferred
        total_bytes = summary["total_bytes_received"] + summary["total_bytes_sent"]
        if total_bytes >= 1048576:  # MB
            data_str = f"{total_bytes / 1048576:.1f} MB"
        elif total_bytes >= 1024:  # KB
            data_str = f"{total_bytes / 1024:.1f} KB"
        else:
            data_str = f"{total_bytes} bytes"
        self.data_transferred_value.setText(data_str)
        
            
    def add_receiver(self):
        """Add a new receiver"""
        dialog = ReceiverConfigDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            receiver_id = self.receiver_manager.create_receiver(config)
            if receiver_id:
                QMessageBox.information(self, "Success", f"Receiver '{config.name}' created successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to create receiver. Check the logs for details.")
                
    def edit_receiver(self, receiver_id: str):
        """Edit an existing receiver"""
        config = self.receiver_manager.get_receiver_config(receiver_id)
        if not config:
            QMessageBox.warning(self, "Error", "Receiver configuration not found.")
            return
            
        dialog = ReceiverConfigDialog(config, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_config = dialog.get_config()
            # Use background operation for updating
            self.start_receiver_operation(receiver_id, "update", updated_config.to_dict())
    
    def confirm_remove_receiver(self, receiver_id: str):
        """Confirm and remove a receiver"""
        config = self.receiver_manager.get_receiver_config(receiver_id)
        if not config:
            return
            
        reply = QMessageBox.question(
            self, "Confirm Removal", 
            f"Are you sure you want to remove receiver '{config.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.start_receiver_operation(receiver_id, "remove")
                
    def start_receiver(self, receiver_id: str):
        """Start a receiver"""
        if self.receiver_manager.start_receiver(receiver_id):
            QMessageBox.information(self, "Success", "Receiver started successfully!")
        else:
            QMessageBox.warning(self, "Error", "Failed to start receiver.")
            
    def stop_receiver(self, receiver_id: str):
        """Stop a receiver"""
        if self.receiver_manager.stop_receiver(receiver_id):
            QMessageBox.information(self, "Success", "Receiver stopped successfully!")
        else:
            QMessageBox.warning(self, "Error", "Failed to stop receiver.")
            
    def remove_receiver(self, receiver_id: str):
        """Remove a receiver"""
        config = self.receiver_manager.get_receiver_config(receiver_id)
        if not config:
            return
            
        reply = QMessageBox.question(
            self, "Confirm Removal", 
            f"Are you sure you want to remove receiver '{config.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.receiver_manager.remove_receiver(receiver_id):
                QMessageBox.information(self, "Success", "Receiver removed successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to remove receiver.")
                
        
    def on_receiver_status_changed(self, receiver_id: str, status: str):
        """Handle receiver status change"""
        self.refresh_receivers_table()
        
    def on_receiver_stats_updated(self, receiver_id: str):
        """Handle receiver stats update"""
        self.refresh_receivers_table()
        
    def on_receiver_error(self, receiver_id: str, error: str):
        """Handle receiver error"""
        if receiver_id:
            config = self.receiver_manager.get_receiver_config(receiver_id)
            receiver_name = config.name if config else receiver_id
            QMessageBox.warning(self, "Receiver Error", f"Error in receiver '{receiver_name}': {error}")
        else:
            QMessageBox.warning(self, "Receiver Manager Error", error)
            
    # Legacy method removed - services now passed directly to constructor