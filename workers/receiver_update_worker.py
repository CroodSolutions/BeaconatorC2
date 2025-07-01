from PyQt6.QtCore import QThread, pyqtSignal
from services.receivers import ReceiverManager

class ReceiverUpdateWorker(QThread):
    """Background worker to update receiver statistics"""
    receiver_stats_updated = pyqtSignal()

    def __init__(self, receiver_manager: ReceiverManager):
        super().__init__()
        self.receiver_manager = receiver_manager
        self._running = True

    def run(self):
        import utils  # Import here to avoid circular imports
        while self._running:
            try:
                # Trigger stats update for all receivers
                self.receiver_manager._update_all_stats()
                # Emit signal to update UI
                self.receiver_stats_updated.emit()
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Error updating receiver stats: {e}")
            self.msleep(2000)  # 2 second delay (same as original timer)

    def stop(self):
        """Stop the worker thread"""
        self._running = False
        self.wait()  # Wait for the thread to finish