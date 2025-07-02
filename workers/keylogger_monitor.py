from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from database import BeaconRepository

class KeyLoggerOutputMonitor(QThread):
    """Monitor KeyLogger output from a specific beacon"""
    output_received = pyqtSignal(str)
    
    def __init__(self, beacon_id: str, beacon_repository: BeaconRepository, config):
        super().__init__()
        self.beacon_id = beacon_id
        self.beacon_repository = beacon_repository
        self.running = True
        self.output_file = Path(config.LOGS_FOLDER) / f"keylogger_output_{beacon_id}.txt"
        self.last_content = None

    def run(self):
        import utils  # Import here to avoid circular imports
        while self.running:
            try:
                if self.output_file.exists():
                    with open(self.output_file, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                        if content and content != self.last_content:
                            self.last_content = content
                            self.output_received.emit(content)
                                
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Error reading output file: {e}")
            self.msleep(100)

    def stop(self):
        self.running = False