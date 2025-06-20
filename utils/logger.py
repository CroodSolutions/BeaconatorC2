import logging
import sys
import ctypes
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from PyQt6.QtCore import QObject, pyqtSignal

class Logger(QObject):
    new_log = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setup_file_logger()
        
    def setup_file_logger(self):
        log_path = Path(self.config.LOGS_FOLDER) / "manager.log"
        
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

def setup_taskbar_icon(config):
    """Setup taskbar icon for Windows"""
    if sys.platform == 'win32':
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(config.APP_ID)
        except Exception as e:
            print(f"Failed to set taskbar icon: {e}")

# Global logger instance - will be initialized in main
logger = None