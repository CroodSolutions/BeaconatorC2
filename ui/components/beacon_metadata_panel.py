#!/usr/bin/env python3
"""
Beacon Metadata Panel - Simple panel for displaying beacon metadata from asset map
No animations - just simple show/hide for reliability
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
                            QFrame, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from datetime import datetime


class BeaconMetadataPanel(QWidget):
    """Simple panel that displays beacon information and metadata"""

    # Signals
    panel_closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_beacon_id = None
        self.beacon_repository = None

        self.setup_ui()
        self.hide()  # Start hidden

    def set_beacon_repository(self, repository):
        """Set the beacon repository for fetching data"""
        self.beacon_repository = repository

    def setup_ui(self):
        """Setup the panel UI"""
        self.setFixedWidth(400)
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: #e0e0e0;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Header with close button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 5)

        self.title_label = QLabel("Beacon Details")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        close_btn = QPushButton("×")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                border: none;
                border-radius: 3px;
                font-size: 18px;
                font-weight: bold;
                color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        close_btn.clicked.connect(self.close_panel)
        header_layout.addWidget(close_btn)

        layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("background-color: #444444;")
        layout.addWidget(separator)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #2b2b2b;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 5px;
            }
        """)

        # Content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(8)
        self.content_widget.setLayout(self.content_layout)

        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)

        self.setLayout(layout)

    def show_beacon(self, beacon_id: str):
        """Show the panel with beacon information"""
        self.current_beacon_id = beacon_id

        if not self.beacon_repository:
            return

        # Get beacon data
        beacon = self.beacon_repository.get_beacon(beacon_id)
        if not beacon:
            return

        # Get metadata
        metadata = self.beacon_repository.get_beacon_metadata_with_details(beacon_id)

        # Clear existing content
        self.clear_content()

        # Add beacon basic info
        self.add_section_header("Basic Information")
        self.add_field("Beacon ID", beacon_id)
        self.add_field("Computer Name", beacon.computer_name)

        # Status with color
        status_widget = self.create_status_widget(beacon.status)
        self.add_field_widget("Status", status_widget)

        if beacon.ip_address:
            self.add_field("IP Address", beacon.ip_address)

        # Last check-in with formatting
        if beacon.last_checkin:
            if isinstance(beacon.last_checkin, datetime):
                checkin_str = beacon.last_checkin.strftime("%Y-%m-%d %H:%M:%S")
            else:
                checkin_str = str(beacon.last_checkin)
        else:
            checkin_str = "Never"
        self.add_field("Last Check-in", checkin_str)

        if beacon.receiver_id:
            self.add_field("Receiver", beacon.receiver_id, wrap=True)

        if beacon.schema_file:
            self.add_field("Schema", beacon.schema_file, wrap=True)

        # Pending command
        if beacon.pending_command:
            self.add_field("Pending Command", beacon.pending_command, wrap=True)

        # Metadata section
        if metadata:
            self.add_section_header("Collected Metadata")

            # Display all metadata without category grouping
            for item in metadata:
                self.add_metadata_field(item)

        else:
            self.add_section_header("Collected Metadata")
            empty_label = QLabel("No metadata collected yet")
            empty_label.setStyleSheet("color: #888888; font-style: italic; padding: 10px;")
            self.content_layout.addWidget(empty_label)

        self.content_layout.addStretch()

        # Show the panel
        self.show()

    def add_metadata_field(self, metadata_item: dict):
        """Add a metadata field with optional source info"""
        # Main key:value layout
        field_widget = QWidget()
        field_layout = QVBoxLayout()
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(2)

        # Key:Value horizontal layout
        kv_layout = QHBoxLayout()
        kv_layout.setContentsMargins(0, 0, 0, 0)
        kv_layout.setSpacing(8)

        # Label (key)
        label = metadata_item['key'].replace('_', ' ').title()
        label_widget = QLabel(label + ":")
        label_font = QFont()
        label_font.setBold(True)
        label_widget.setFont(label_font)
        label_widget.setStyleSheet("color: #b0b0b0;")
        label_widget.setMinimumWidth(120)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        kv_layout.addWidget(label_widget)

        # Value
        value_widget = QLabel(str(metadata_item['value']))
        value_widget.setWordWrap(True)
        value_widget.setStyleSheet("color: #ffffff;")
        value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        kv_layout.addWidget(value_widget, 1)

        field_layout.addLayout(kv_layout)

        # Source and timestamp (small text, indented below)
        if metadata_item.get('source_command') or metadata_item.get('collected_at'):
            info_parts = []
            if metadata_item.get('source_command'):
                info_parts.append(f"from: {metadata_item['source_command']}")
            if metadata_item.get('collected_at'):
                timestamp = metadata_item['collected_at']
                if isinstance(timestamp, datetime):
                    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    timestamp_str = str(timestamp)
                info_parts.append(f"at: {timestamp_str}")

            info_label = QLabel(" | ".join(info_parts))
            info_label.setWordWrap(True)
            info_label.setStyleSheet("color: #666666; font-size: 9px; margin-left: 128px;")
            field_layout.addWidget(info_label)

        field_widget.setLayout(field_layout)
        self.content_layout.addWidget(field_widget)

    def add_section_header(self, title: str):
        """Add a section header"""
        header = QLabel(title)
        header.setStyleSheet("""
            font-weight: bold;
            font-size: 11px;
            color: #cccccc;
            margin-top: 10px;
            margin-bottom: 5px;
            padding: 5px;
            background-color: #353535;
            border-radius: 3px;
        """)
        self.content_layout.addWidget(header)

    def add_field(self, label: str, value: str, wrap: bool = False):
        """Add a labeled field to the content"""
        field_widget = QWidget()
        field_layout = QHBoxLayout()
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(8)

        # Label
        label_widget = QLabel(label + ":")
        label_font = QFont()
        label_font.setBold(True)
        label_widget.setFont(label_font)
        label_widget.setStyleSheet("color: #b0b0b0;")
        label_widget.setMinimumWidth(120)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        field_layout.addWidget(label_widget)

        # Value
        value_widget = QLabel(str(value))
        if wrap:
            value_widget.setWordWrap(True)
        value_widget.setStyleSheet("color: #ffffff;")
        value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        field_layout.addWidget(value_widget, 1)

        field_widget.setLayout(field_layout)
        self.content_layout.addWidget(field_widget)

    def add_field_widget(self, label: str, widget: QWidget):
        """Add a labeled field with a custom widget"""
        field_container = QWidget()
        field_layout = QHBoxLayout()
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(8)

        # Label
        label_widget = QLabel(label + ":")
        label_font = QFont()
        label_font.setBold(True)
        label_widget.setFont(label_font)
        label_widget.setStyleSheet("color: #b0b0b0;")
        label_widget.setMinimumWidth(120)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        field_layout.addWidget(label_widget)

        # Custom widget
        field_layout.addWidget(widget, 1)

        field_container.setLayout(field_layout)
        self.content_layout.addWidget(field_container)

    def create_status_widget(self, status: str) -> QLabel:
        """Create a styled status label with color"""
        status_label = QLabel(status.upper())
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if status in ("online", "running"):
            color = "#32C832"  # Green
            bg_color = "#1a3d1a"
        elif status in ("offline", "stopped"):
            color = "#C83232"  # Red
            bg_color = "#3d1a1a"
        else:
            color = "#888888"  # Gray
            bg_color = "#2a2a2a"

        status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background-color: {bg_color};
                border: 1px solid {color};
                border-radius: 3px;
                padding: 3px 8px;
                font-weight: bold;
            }}
        """)

        return status_label

    def clear_content(self):
        """Clear all content widgets"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def close_panel(self):
        """Close the panel"""
        self.hide()
        self.current_beacon_id = None
        self.panel_closed.emit()
