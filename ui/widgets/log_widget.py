import re
from PyQt6.QtWidgets import QTextEdit, QSizePolicy
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from utils import FontManager

class LogWidget(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setPlaceholderText("Logs will appear here...")
        
        # Set size policy to control expansion behavior
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(100)
        
        # Set monospace font for better log readability
        font = QFont("Source Code Pro", 9)
        FontManager().add_relative_font_widget(self, 0)
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        self.setFont(font)

        base_style = self.styleSheet()
        self.setStyleSheet(base_style + """
            QTextEdit {
                background-color: #121212;
                color: #ffffff;
                border: none;
                font-size: 12pt;
            }
        """)

        # Initialize syntax highlighter
        self.highlighter = LogHighlighter(self.document())
        self.level_colors = {
            'ERROR': '#ff6b6b',
            'WARNING': '#ffd93d',
            'INFO': '#ffffff',
            'DEBUG': '#6bff6b'
        }

    @pyqtSlot(str)
    def append_log(self, message: str):
        """Append a log message to the widget"""
        self.append(message)
        
        # Auto-scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

class LogHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Enhanced color scheme
        self.colors = {
            'timestamp': '#8BE9FD',  # Light blue for timestamps
            'event_type': '#FFB86C',  # Pink for event types (Agent Registration, File Transfer, etc)
            'beacon_id': '#50FA7B',    # Green for agent IDs
            'status': {
                'success': '#50FA7B',  # Green for success messages
                'error': '#FF5555',    # Red for errors
                'warning': '#FFB86C',  # Orange for warnings
                'info': '#F8F8F2'      # White for info
            },
            'file_info': '#BD93F9',   # Purple for file names and sizes
            'progress': '#F1FA8C',     # Yellow for progress indicators
            'network': '#8BE9FD',      # Light blue for network addresses/ports
            'separator': '#6272A4'     # Soft purple for separators
        }
        
        # Create format patterns
        self.highlighting_rules = []
        
        # Timestamp
        timestamp_format = QTextCharFormat()
        timestamp_format.setForeground(QColor(self.colors['timestamp']))
        font = QFont("Source Code Pro", 8)
        timestamp_format.setFont(font)
        self.highlighting_rules.append(
            (re.compile(r'\[\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\]'),
             timestamp_format)
        )
        
        # Event types
        event_format = QTextCharFormat()
        event_format.setForeground(QColor(self.colors['event_type']))
        self.highlighting_rules.append(
            (re.compile(r'(?:Agent Registration|Beacon Registration|File Transfer|Command Output|Command Scheduled|Command|Connection|Received|Check In|Metadata Extracted|Encoded file)(?=:)'),
             event_format)
        )

        # command types
        command_format = QTextCharFormat()
        command_format.setForeground(QColor(self.colors['beacon_id']))  # Using the same green as agent IDs
        self.highlighting_rules.append(
            (re.compile(r'(?<=: )(request_action|execute_command|download_file|upload_file|execute_module|command_output)(?=\|)'),
            command_format)
        )
        
        # Agent IDs (8-character)
        agent_format = QTextCharFormat()
        agent_format.setForeground(QColor(self.colors['beacon_id']))
        self.highlighting_rules.append(
            (re.compile(r'[a-f0-9]{8}'),
             agent_format)
        )
        
        # File information
        file_format = QTextCharFormat()
        file_format.setForeground(QColor(self.colors['file_info']))
        self.highlighting_rules.append(
            (re.compile(r'(?<=: )[\w.-]+\.(txt|exe|dll|py|json|log|cfg)(?=\s\(|\s-|$)'),  # Matches only filenames with extensions
            file_format)
        )
        
        # Progress and sizes
        progress_format = QTextCharFormat()
        progress_format.setForeground(QColor(self.colors['progress']))
        self.highlighting_rules.append(
            (re.compile(r'\d+(?:\.\d+)?\s*(?:KB|MB|bytes)|\d+%'),
             progress_format)
        )
        
        # Error messages
        error_format = QTextCharFormat()
        error_format.setForeground(QColor(self.colors['status']['error']))
        self.highlighting_rules.append(
            (re.compile(r'(?:Error|Failed|failed|error):.*$'),
             error_format)
        )
        
        # Network addresses
        network_format = QTextCharFormat()
        network_format.setForeground(QColor(self.colors['network']))
        self.highlighting_rules.append(
            (re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?'),
             network_format)
        )
        
        # Separators
        separator_format = QTextCharFormat()
        separator_format.setForeground(QColor(self.colors['separator']))
        self.highlighting_rules.append(
            (re.compile(r'(?<=[a-z_])\|(?=[a-f0-9]{8})|(?<=[a-f0-9]{8})\s-\s'),  # Only match pipe between command and agent ID, or dash after agent ID
            separator_format)
        )
                # Store the command output format separately since we'll handle it differently
        self.command_output_format = QTextCharFormat()
        self.command_output_format.setFont(QFont("Source Code Pro", 6))

    def highlightBlock(self, text):
        # Check if this block is a command output line or continuation
        if text.startswith('command_output|'):
            # Format the entire line including the command_output|agentid| part
            self.setFormat(0, len(text), self.command_output_format)
        else:
            previous_block = self.currentBlock().previous()
            if previous_block.isValid():
                previous_text = previous_block.text()
                if (previous_text.startswith('command_output|') or
                    (not text.startswith('[') and
                     not any(text.startswith(cmd) for cmd in ['Agent', 'Beacon', 'File', 'Command', 'Connection', 'Received', 'Check', 'Metadata', 'Encoded']))):
                    self.setFormat(0, len(text), self.command_output_format)
                else:
                    # Apply regular rules
                    for pattern, format in self.highlighting_rules:
                        for match in pattern.finditer(text):
                            start, end = match.span()
                            self.setFormat(start, end - start, format)
