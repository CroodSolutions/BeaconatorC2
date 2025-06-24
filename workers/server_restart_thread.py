import threading
from PyQt6.QtCore import QThread, pyqtSignal

class ServerRestartThread(QThread):
    finished = pyqtSignal(bool)  # Signal to indicate success/failure

    def __init__(self, server_manager, new_port):
        super().__init__()
        self.server_manager = server_manager
        self.new_port = new_port

    def run(self):
        import utils  # Import here to avoid circular imports
        try:
            if utils.logger:
                utils.logger.log_message(f"[DEBUG] Starting port change process from {self.server_manager.config.COMBINED_PORT} to {self.new_port}")
            
            # Set shutdown flag and stop current server
            if utils.logger:
                utils.logger.log_message("[DEBUG] Setting shutdown flag")
            self.server_manager._shutdown.set()
            
            if self.server_manager.server:
                if utils.logger:
                    utils.logger.log_message("[DEBUG] Calling server.shutdown()")
                self.server_manager.server.shutdown()
                if utils.logger:
                    utils.logger.log_message("[DEBUG] Calling server.server_close()")
                self.server_manager.server.server_close()
            
            # Update port
            if utils.logger:
                utils.logger.log_message(f"[DEBUG] Updating COMBINED_PORT to {self.new_port}")
            self.server_manager.config.COMBINED_PORT = self.new_port
            
            # Clear shutdown flag for new server
            if utils.logger:
                utils.logger.log_message("[DEBUG] Clearing shutdown flag")
            self.server_manager._shutdown.clear()
            
            # Create and start new server
            if utils.logger:
                utils.logger.log_message("[DEBUG] Creating new server")
            self.server_manager.server = self.server_manager._create_server()
            
            # Start new server thread
            if utils.logger:
                utils.logger.log_message("[DEBUG] Starting new server thread")
            self.server_manager.server_thread = threading.Thread(
                target=self.server_manager._run_server,
                daemon=True,
                name="ServerThread"
            )
            self.server_manager.server_thread.start()
            
            if utils.logger:
                utils.logger.log_message(f"[DEBUG] Server restart process complete on port {self.new_port}")
            self.finished.emit(True)
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"[DEBUG] Error during restart: {str(e)}")
            self.finished.emit(False)