import shutil
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                            QHeaderView, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt
from database import BeaconRepository
from utils import FontManager

class FileTransferWidget(QWidget):
    """Widget for handling file transfers"""
    def __init__(self, beacon_repository: BeaconRepository):
        super().__init__()
        self.beacon_repository = beacon_repository
        self.current_beacon_id = None
        
        # Try to use FontManager, but don't fail if it's not available
        try:
            FontManager().add_relative_font_widget(self, 0)
        except:
            pass
            
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Request from Agent
        top_group = QGroupBox("Request from Agent")
        top_layout = QHBoxLayout()
        
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("File path")
        self.file_path_input.setToolTip(
            "Enter the full file path as it appears on the target system\n"
            "Example: C:\\Users\\Administrator\\Documents\\file.txt"
        )
        self.request_btn = QPushButton("Request")
        self.request_btn.clicked.connect(self.request_file)
        
        top_layout.addWidget(self.file_path_input)
        top_layout.addWidget(self.request_btn)
        top_group.setLayout(top_layout)
        
        # Send to Agent
        bottom_group = QGroupBox("Send to Agent")
        bottom_layout = QVBoxLayout()
        
        # Add button row for file operations
        button_layout = QHBoxLayout()
        self.browse_btn = QPushButton("Browse Files...")
        self.browse_btn.clicked.connect(self.browse_files)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_files)
        self.transfer_btn = QPushButton("Send")
        self.transfer_btn.clicked.connect(self.transfer_file)
        
        button_layout.addWidget(self.browse_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.transfer_btn)
        
        # Create file list table
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(3)
        self.file_table.setHorizontalHeaderLabels(["Name", "Size", "Type"])
        self.file_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.file_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Set up the header and column sizes
        header = self.file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        
        # Set minimum widths for the fixed columns
        self.file_table.setColumnWidth(1, 100)
        self.file_table.setColumnWidth(2, 80)
        
        # Add widgets to bottom layout
        bottom_layout.addLayout(button_layout)
        bottom_layout.addWidget(self.file_table)
        bottom_group.setLayout(bottom_layout)

        # Add styles
        base_style = top_group.styleSheet()
        style = """ 
            QGroupBox {
                background: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #424242, stop:1 #232323);
            }
            QGroupBox::title {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #232323);                
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding-left: 2000px;
                padding-right: 2000px;
            }
        """
        top_group.setStyleSheet(base_style + style)
        bottom_group.setStyleSheet(base_style + style)
        
        # Add both sections to main layout
        layout.addWidget(top_group)
        layout.addWidget(bottom_group)
        self.setLayout(layout)
        
        self.refresh_files()

    def get_file_size_str(self, size_in_bytes: int) -> str:
        """Convert file size to human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_in_bytes < 1024:
                return f"{size_in_bytes:.1f} {unit}"
            size_in_bytes /= 1024
        return f"{size_in_bytes:.1f} TB"

    def get_file_type(self, filename: str) -> str:
        """Get file type description"""
        ext = Path(filename).suffix.lower()
        return ext[1:].upper() if ext else "File"

    def refresh_files(self):
        """Refresh the file list table"""
        self.file_table.setRowCount(0)
        try:
            from config import ServerConfig
            config = ServerConfig()
            files = Path(config.FILES_FOLDER).glob('*')
            for file_path in files:
                if file_path.is_file():  # Only show files, not directories
                    row = self.file_table.rowCount()
                    self.file_table.insertRow(row)
                    
                    # File name
                    self.file_table.setItem(row, 0, QTableWidgetItem(file_path.name))
                    
                    # File size
                    size = file_path.stat().st_size
                    size_item = QTableWidgetItem(self.get_file_size_str(size))
                    size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.file_table.setItem(row, 1, size_item)
                    
                    # File type
                    type_item = QTableWidgetItem(self.get_file_type(file_path.name))
                    type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.file_table.setItem(row, 2, type_item)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading files: {str(e)}")

    def browse_files(self):
        """Open system file browser"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Send",
            str(Path.home()),  # Start in user's home directory
            "All Files (*.*)"
        )
        
        if file_path:
            try:
                from config import ServerConfig
                config = ServerConfig()
                
                # Copy selected file to files folder
                source_path = Path(file_path)
                dest_path = Path(config.FILES_FOLDER) / source_path.name
                
                # Ask for confirmation if file already exists
                if dest_path.exists():
                    reply = QMessageBox.question(
                        self,
                        "File Exists",
                        f"File {source_path.name} already exists. Replace it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return
                
                shutil.copy2(file_path, dest_path)
                self.refresh_files()
                
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error copying file: {str(e)}")

    def transfer_file(self):
        """Transfer selected file to agent"""
        if not self.current_beacon_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        selected_items = self.file_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "No file selected!")
            return

        filename = self.file_table.item(selected_items[0].row(), 0).text()
        try:
            from config import ServerConfig
            config = ServerConfig()
            source_path = Path(config.FILES_FOLDER) / filename
            
            if not source_path.exists():
                QMessageBox.warning(self, "Error", "File not found")
                return
            
            # Schedule download command
            agent = self.beacon_repository.get_beacon(self.current_beacon_id)
            if agent:
                # Quote filename if it contains spaces or special characters
                if ' ' in filename or '"' in filename or "'" in filename:
                    quoted_filename = f'"{filename}"'
                else:
                    quoted_filename = filename
                self.beacon_repository.update_beacon_command(
                    self.current_beacon_id,
                    f"download_file {quoted_filename}"
                )
                QMessageBox.information(
                    self,
                    "Success", 
                    f"File transfer scheduled for agent {self.current_beacon_id}"
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Transfer error: {str(e)}")

    def request_file(self):
        """Request file from agent"""
        if not self.current_beacon_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        file_path = self.file_path_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "Warning", "Please enter a file path!")
            return

        try:
            # Schedule upload command
            agent = self.beacon_repository.get_beacon(self.current_beacon_id)
            if agent:
                # Quote file path if it contains spaces or special characters
                if ' ' in file_path or '"' in file_path or "'" in file_path:
                    quoted_file_path = f'"{file_path}"'
                else:
                    quoted_file_path = file_path
                self.beacon_repository.update_beacon_command(
                    self.current_beacon_id,
                    f"upload_file {quoted_file_path}"
                )
                QMessageBox.information(
                    self,
                    "Success", 
                    f"File request scheduled for agent {self.current_beacon_id}"
                )
                # Clear the input field after successful request
                self.file_path_input.clear()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Request error: {str(e)}")

    def set_agent(self, beacon_id: str):
        self.current_beacon_id = beacon_id
    
    def set_beacon(self, beacon_id: str):
        """Set the current beacon ID - delegates to set_agent for compatibility"""
        self.set_agent(beacon_id)