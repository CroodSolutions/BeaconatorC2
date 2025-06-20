from PyQt6.QtCore import QThread, pyqtSignal
from database import AgentRepository

class AgentUpdateWorker(QThread):
    """Background worker to update agent statuses"""
    agent_updated = pyqtSignal(list)

    def __init__(self, agent_repository: AgentRepository):
        super().__init__()
        self.agent_repository = agent_repository
        self._running = True  # Add running flag

    def run(self):
        import utils  # Import here to avoid circular imports
        while self._running:  # Use running flag
            try:
                agents = self.agent_repository.get_all_agents()
                self.agent_updated.emit([agent.to_dict() for agent in agents])
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Error updating agents: {e}")
            self.msleep(1000)  # 1 second delay

    def stop(self):  # Implement stop method
        self._running = False
        self.wait()  # Wait for the thread to finish