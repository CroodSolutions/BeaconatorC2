import socket
import threading
import time
from socketserver import ThreadingTCPServer, BaseRequestHandler
from typing import Dict, Any, Optional
from pathlib import Path
from werkzeug.utils import secure_filename
from .base_receiver import BaseReceiver, ReceiverStatus
from .encoding_strategies import EncodingStrategy
from .receiver_config import ReceiverConfig
import utils
from config import ServerConfig

class TCPConnectionHandler:
    """Handles TCP connections using BaseReceiver functionality"""
    
    def __init__(self, receiver_instance):
        self.receiver_instance = receiver_instance
        
    def handle_connection(self, sock: socket.socket, client_address: tuple):
        """Handle a TCP connection using BaseReceiver functionality"""
        
        try:
            # Set a reasonable timeout to prevent hanging connections
            sock.settimeout(10.0)
            
            # Receive and decode initial data
            initial_data_raw = self.receiver_instance._receive_data(sock, self.receiver_instance.config.buffer_size)
            if not initial_data_raw:
                return
                
            # Decode the data
            try:
                initial_data_decoded = self.receiver_instance.encoding_strategy.decode(initial_data_raw)
                initial_data = initial_data_decoded.decode('utf-8').strip()
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Decoding error from {client_address}: {e}")
                return
                
            parts = initial_data.split('|')
            command = parts[0] if parts else ""
            
            # Update stats using thread-safe method
            self.receiver_instance.update_bytes_received(len(initial_data_raw))
            
            if command in ("to_beacon", "from_beacon"):
                self.receiver_instance.handle_file_transfer(sock, command, parts, client_address)
            else:
                self.receiver_instance.handle_command_processing(sock, initial_data, client_address)
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Connection Error: {client_address[0]}:{client_address[1]} - {str(e)}")
        finally:
            try:
                sock.close()
            except:
                pass

class TCPReceiver(BaseReceiver):
    """TCP receiver implementation with encoding support"""
    
    def __init__(self, config: ReceiverConfig, encoding_strategy: EncodingStrategy):
        super().__init__(config.receiver_id, config.name, encoding_strategy)
        self.config = config
        self.server: Optional[ThreadingTCPServer] = None
        self.connection_handler: Optional[TCPConnectionHandler] = None
        
    def _setup_receiver(self) -> bool:
        """Setup TCP server"""
        try:
            # Create TCP connection handler
            self.connection_handler = TCPConnectionHandler(self)
            
            # Define custom TCP server class
            class ReusableTCPServer(ThreadingTCPServer):
                allow_reuse_address = True
                daemon_threads = True
                
            class CustomRequestHandler(BaseRequestHandler):
                def __init__(self, request, client_address, server, receiver_instance):
                    self.receiver_instance = receiver_instance
                    super().__init__(request, client_address, server)
                    
                def handle(self):
                    # Update connection stats using thread-safe methods
                    self.receiver_instance.increment_active_connections()
                    
                    try:
                        self.receiver_instance.connection_handler.handle_connection(
                            self.request, self.client_address
                        )
                    finally:
                        self.receiver_instance.decrement_active_connections()
                        
            # Create server with custom handler
            def handler_factory(request, client_address, server):
                return CustomRequestHandler(request, client_address, server, self)
                
            self.server = ReusableTCPServer(
                (self.config.host, self.config.port),
                handler_factory
            )
            
            # Set server timeout to allow periodic shutdown checks
            self.server.timeout = 1.0
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(self.receiver_id, f"Setup failed: {str(e)}")
            return False
            
    def _start_listening(self):
        """Start listening for connections"""
        if not self.server:
            return
            
        try:
            while not self._shutdown_event.is_set():
                if self.server:
                    try:
                        # handle_request() will timeout after server.timeout seconds
                        # This allows us to check shutdown_event periodically
                        self.server.handle_request()
                    except OSError as e:
                        # Check if this is due to shutdown or a real error
                        if self._shutdown_event.is_set():
                            break
                        # Only raise if we're not shutting down
                        raise
                    except socket.timeout:
                        # Timeout is expected, just continue to check shutdown event
                        continue
                        
        except Exception as e:
            if not self._shutdown_event.is_set():
                self.error_occurred.emit(self.receiver_id, f"Listening error: {str(e)}")
                
    def _cleanup_receiver(self):
        """Cleanup TCP server"""
        if self.server:
            try:
                # First, try graceful shutdown with timeout
                shutdown_thread = threading.Thread(target=self.server.shutdown)
                shutdown_thread.daemon = True
                shutdown_thread.start()
                
                # Wait for shutdown to complete, but don't wait forever
                shutdown_thread.join(timeout=2.0)
                
                if shutdown_thread.is_alive():
                    # If shutdown is taking too long, force close
                    try:
                        self.server.server_close()
                    except Exception:
                        pass
                else:
                    # Shutdown completed successfully, now close
                    self.server.server_close()
                    
            except Exception:
                # If anything fails, ensure we still close the server
                try:
                    self.server.server_close()
                except Exception:
                    pass
            finally:
                self.server = None
    
    def _send_data(self, sock: socket.socket, data: bytes) -> bool:
        """Send data through TCP socket"""
        try:
            self._send_all(sock, data)
            return True
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error sending TCP data: {e}")
            return False
    
    def _receive_data(self, sock: socket.socket, buffer_size: int) -> bytes:
        """Receive data through TCP socket"""
        return sock.recv(buffer_size)
                
    def get_configuration(self) -> Dict[str, Any]:
        """Get TCP receiver configuration"""
        return {
            "host": self.config.host,
            "port": self.config.port,
            "buffer_size": self.config.buffer_size,
            "timeout": self.config.timeout,
            "max_connections": self.config.max_connections,
            "encoding": self.encoding_strategy.get_name()
        }
        
    def update_configuration(self, config_updates: Dict[str, Any]) -> bool:
        """Update TCP receiver configuration"""
        try:
            if "port" in config_updates:
                new_port = int(config_updates["port"])
                if 1 <= new_port <= 65535:
                    self.config.port = new_port
                else:
                    return False
                    
            if "host" in config_updates:
                self.config.host = config_updates["host"]
                
            if "buffer_size" in config_updates:
                self.config.buffer_size = int(config_updates["buffer_size"])
                
            # Restart if running to apply changes
            if self.status == ReceiverStatus.RUNNING:
                return self.restart()
                
            return True
            
        except Exception:
            return False