"""
Session Terminal Dialog

Provides a pseudo-terminal interface for interacting with Metasploit sessions.
Supports both Meterpreter and shell sessions with command history and proper formatting.
"""

import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit, 
                             QLineEdit, QLabel, QFrame, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QKeyEvent, QTextCharFormat, QColor

from services.metasploit_service import MetasploitService


class CommandExecutor(QThread):
    """Thread for executing commands without blocking the UI"""
    
    output_received = pyqtSignal(str, str)  # output, error
    command_complete = pyqtSignal()
    
    def __init__(self, metasploit_service: MetasploitService, session_id: str, command: str):
        super().__init__()
        self.metasploit_service = metasploit_service
        self.session_id = session_id
        self.command = command
        
    def run(self):
        """Execute the command and emit results"""
        try:
            print(f"CommandExecutor: Executing command '{self.command}' on session {self.session_id}")
            result = self.metasploit_service.execute_session_command(self.session_id, self.command)
            print(f"CommandExecutor: Result: {result}")
            
            if result.get('success', False):
                output = result.get('output', '')
                print(f"CommandExecutor: Success, output length: {len(output)}")
                self.output_received.emit(output, "")
            else:
                error = result.get('error', 'Command failed')
                print(f"CommandExecutor: Error: {error}")
                self.output_received.emit("", error)
                
        except Exception as e:
            print(f"CommandExecutor: Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            self.output_received.emit("", f"Error executing command: {str(e)}")
        
        print("CommandExecutor: Emitting command_complete")
        self.command_complete.emit()


class SessionTerminalDialog(QDialog):
    """Interactive terminal dialog for Metasploit sessions"""
    
    def __init__(self, metasploit_service: MetasploitService, session_id: str, session_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        
        self.metasploit_service = metasploit_service
        # Convert session_id to int for Metasploit RPC calls
        self.session_id = int(session_id) if str(session_id).isdigit() else session_id
        self.session_info = session_info
        self.session_type = session_info.get('type', '').lower()
        
        # Command history management
        self.command_history: List[str] = []
        self.history_index: int = -1
        
        # State
        self.command_in_progress = False
        self.current_executor: Optional[CommandExecutor] = None
        
        # Setup UI
        self.setup_ui()
        self.setup_styling()
        self.show_welcome_message()
        
        # Focus on input
        self.command_input.setFocus()
        
    def setup_ui(self):
        """Setup the terminal dialog UI"""
        self.setWindowTitle(f"Session Terminal - {self.session_id}")
        self.setModal(False)  # Allow interaction with main window
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        layout = QVBoxLayout()
        
        # Session info header
        self.create_session_header(layout)
        
        # Terminal output area
        self.output_display = QPlainTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setFont(QFont("Consolas", 10))
        self.output_display.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.output_display)
        
        # Command input area
        input_layout = QHBoxLayout()
        
        # Prompt label
        prompt_text = "meterpreter> " if 'meterpreter' in self.session_type else "shell> "
        self.prompt_label = QLabel(prompt_text)
        self.prompt_label.setFont(QFont("Consolas", 10))
        input_layout.addWidget(self.prompt_label)
        
        # Command input
        self.command_input = QLineEdit()
        self.command_input.setFont(QFont("Consolas", 10))
        self.command_input.returnPressed.connect(self.execute_command)
        input_layout.addWidget(self.command_input)
        
        # Execute button
        self.execute_btn = QPushButton("Execute")
        self.execute_btn.clicked.connect(self.execute_command)
        input_layout.addWidget(self.execute_btn)
        
        layout.addLayout(input_layout)
        
        # Status bar
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
    def create_session_header(self, layout):
        """Create session information header"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_layout = QHBoxLayout(header_frame)
        
        # Session details
        session_details = f"Session ID: {self.session_id} | "
        session_details += f"Type: {self.session_info.get('type', 'Unknown')} | "
        session_details += f"Target: {self.session_info.get('target_host', 'Unknown')} | "
        session_details += f"Platform: {self.session_info.get('platform', 'Unknown')}"
        
        header_label = QLabel(session_details)
        header_label.setFont(QFont("Arial", 9))
        header_layout.addWidget(header_label)
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_terminal)
        header_layout.addWidget(clear_btn)
        
        layout.addWidget(header_frame)
        
    def setup_styling(self):
        """Setup dark theme styling for terminal"""
        self.setStyleSheet("""
            QDialog {
                background-color: rgb(30, 30, 30);
                color: white;
            }
            QPlainTextEdit {
                background-color: rgb(20, 20, 20);
                color: #00ff00;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 5px;
                selection-background-color: #4a4a4a;
            }
            QLineEdit {
                background-color: rgb(35, 35, 35);
                color: white;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 3px;
            }
            QLineEdit:focus {
                border: 1px solid #888888;
            }
            QLabel {
                color: #cccccc;
            }
            QPushButton {
                background-color: rgb(45, 45, 45);
                color: white;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 5px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: rgb(55, 55, 55);
            }
            QPushButton:pressed {
                background-color: rgb(35, 35, 35);
            }
            QPushButton:disabled {
                background-color: rgb(25, 25, 25);
                color: #666666;
            }
            QFrame {
                background-color: rgb(40, 40, 40);
                border: 1px solid #555555;
                border-radius: 3px;
            }
        """)
        
    def show_welcome_message(self):
        """Show initial welcome message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        session_type_display = self.session_info.get('type', 'Unknown')
        target = self.session_info.get('target_host', 'Unknown')
        
        welcome_msg = f"[{timestamp}] Connected to {session_type_display} session {self.session_id} on {target}\n"
        welcome_msg += f"Session Type: {session_type_display}\n"
        
        if 'meterpreter' in self.session_type:
            welcome_msg += "Available commands: help, sysinfo, getuid, ps, shell, upload, download, etc.\n"
        else:
            welcome_msg += "Shell session - enter system commands directly\n"
            
        welcome_msg += "Use 'help' for available commands or Ctrl+L to clear terminal\n"
        welcome_msg += "-" * 60 + "\n\n"
        
        self.append_output(welcome_msg, is_system=True)
        
    def keyPressEvent(self, event: QKeyEvent):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key.Key_Up:
            self.navigate_history(-1)
        elif event.key() == Qt.Key.Key_Down:
            self.navigate_history(1)
        elif event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_L:
            self.clear_terminal()
        else:
            super().keyPressEvent(event)
            
    def navigate_history(self, direction: int):
        """Navigate through command history"""
        if not self.command_history:
            return
            
        self.history_index += direction
        
        # Clamp to valid range
        if self.history_index < 0:
            self.history_index = 0
        elif self.history_index >= len(self.command_history):
            self.history_index = len(self.command_history) - 1
            
        if 0 <= self.history_index < len(self.command_history):
            self.command_input.setText(self.command_history[self.history_index])
            
    def execute_command(self):
        """Execute the current command"""
        if self.command_in_progress:
            return
            
        command = self.command_input.text().strip()
        if not command:
            return
            
        # Add to history
        if command not in self.command_history or self.command_history[-1] != command:
            self.command_history.append(command)
            
        # Reset history index
        self.history_index = len(self.command_history)
        
        # Show command in output
        prompt = "meterpreter> " if 'meterpreter' in self.session_type else "shell> "
        self.append_output(f"{prompt}{command}\n", is_input=True)
        
        # Clear input
        self.command_input.clear()
        
        # Handle local commands
        if command.lower() in ['clear', 'cls']:
            self.clear_terminal()
            return
        elif command.lower() == 'exit':
            self.close()
            return
        elif command.lower() == 'history':
            self.show_command_history()
            return
            
        # Execute remote command
        self.execute_remote_command(command)
        
    def execute_remote_command(self, command: str):
        """Execute command on the remote session"""
        # Clean up any existing executor first
        if self.current_executor and self.current_executor.isRunning():
            self.current_executor.terminate()
            self.current_executor.wait(1000)  # Wait up to 1 second
            
        self.command_in_progress = True
        self.execute_btn.setEnabled(False)
        self.status_label.setText("Executing command...")
        
        # Create and start executor thread
        self.current_executor = CommandExecutor(self.metasploit_service, self.session_id, command)
        self.current_executor.output_received.connect(self.on_command_output)
        self.current_executor.command_complete.connect(self.on_command_complete)
        self.current_executor.finished.connect(self.current_executor.deleteLater)  # Clean up thread
        self.current_executor.start()
        
    def on_command_output(self, output: str, error: str):
        """Handle command output"""
        if output:
            self.append_output(output, is_output=True)
        if error:
            self.append_output(f"Error: {error}\n", is_error=True)
            
    def on_command_complete(self):
        """Handle command completion"""
        self.command_in_progress = False
        self.execute_btn.setEnabled(True)
        self.status_label.setText("Ready")
        self.current_executor = None
        
        # Add newline for readability
        self.append_output("\n")
        
    def append_output(self, text: str, is_input: bool = False, is_output: bool = False, 
                     is_error: bool = False, is_system: bool = False):
        """Append text to output display with appropriate formatting"""
        cursor = self.output_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Create format for different text types
        char_format = QTextCharFormat()
        
        if is_input:
            char_format.setForeground(QColor(255, 255, 255))  # White for input
        elif is_error:
            char_format.setForeground(QColor(255, 100, 100))  # Red for errors
        elif is_system:
            char_format.setForeground(QColor(150, 150, 255))  # Light blue for system messages
        else:
            char_format.setForeground(QColor(0, 255, 0))      # Green for output
            
        # Insert text with formatting
        cursor.insertText(text, char_format)
        
        # Auto-scroll to bottom
        self.output_display.setTextCursor(cursor)
        self.output_display.ensureCursorVisible()
        
    def show_command_history(self):
        """Show command history"""
        if not self.command_history:
            self.append_output("No commands in history\n", is_system=True)
            return
            
        history_text = "Command History:\n"
        for i, cmd in enumerate(self.command_history[-10:], 1):  # Show last 10 commands
            history_text += f"  {i}. {cmd}\n"
        history_text += "\n"
        
        self.append_output(history_text, is_system=True)
        
    def clear_terminal(self):
        """Clear the terminal output"""
        self.output_display.clear()
        self.show_welcome_message()
        
    def closeEvent(self, event):
        """Handle dialog close"""
        # Always clean up threads, whether command is in progress or not
        if self.current_executor:
            if self.command_in_progress:
                reply = QMessageBox.question(
                    self, 
                    "Command in Progress", 
                    "A command is currently executing. Close anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    event.ignore()
                    return
            
            # Properly terminate and clean up executor thread
            if self.current_executor.isRunning():
                self.current_executor.quit()  # Try graceful quit first
                if not self.current_executor.wait(2000):  # Wait 2 seconds
                    self.current_executor.terminate()  # Force terminate if needed
                    self.current_executor.wait(1000)  # Wait for termination
                    
        event.accept()