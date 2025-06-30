import threading
import time
from socketserver import ThreadingTCPServer, BaseRequestHandler
from config import ServerConfig
from database import BeaconRepository
from .command_processor import CommandProcessor
from .file_transfer import FileTransferService
from .connection_handler import ConnectionHandler
import utils

class ServerManager:
    """Manages server lifecycle and coordination"""
    def __init__(self, config: ServerConfig, beacon_repository: BeaconRepository):
        self.config = config
        self.beacon_repository = beacon_repository
        self.command_processor = CommandProcessor(beacon_repository)
        self.file_transfer_service = FileTransferService()
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
        
        # Start beacon status monitor
        monitor_thread = threading.Thread(
            target=self._monitor_beacon_status,
            daemon=True,
            name="StatusMonitorThread"
        )
        monitor_thread.start()
        
        return self.server_thread, monitor_thread

    def shutdown(self):
        """Gracefully shutdown server and threads"""
        utils.logger.log_message("Initiating server shutdown...")
        self._shutdown.set()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        utils.logger.log_message("Server shutdown complete")

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
            utils.logger.log_message(f"Server listening on port {self.config.COMBINED_PORT}")
            while not self._shutdown.is_set():
                self.server.handle_request()
        except Exception as e:
            utils.logger.log_message(f"Server error: {e}")
        finally:
            utils.logger.log_message("Server thread stopping")

    def _monitor_beacon_status(self):
        """Monitor and update beacon status"""
        while not self._shutdown.is_set():
            try:
                self.beacon_repository.mark_timed_out_beacons(
                    self.config.AGENT_TIMEOUT_MINUTES
                )
            except Exception as e:
                utils.logger.log_message(f"Error in status monitor: {e}")
            time.sleep(60)  # Check every minute

    def change_port(self, new_port: int):
        """Change the server port"""
        try:
            utils.logger.log_message(f"Changing server port from {self.config.COMBINED_PORT} to {new_port}")
            
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
            
            utils.logger.log_message(f"Server now listening on port {new_port}")
            return True
            
        except Exception as e:
            utils.logger.log_message(f"Failed to change port: {e}")
            return False