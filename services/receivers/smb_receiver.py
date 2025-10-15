import os
import platform
import socket
import threading
import time
from typing import Dict, Any, Optional
from pathlib import Path

from .base_receiver import BaseReceiver, ReceiverStatus
from .encoding_strategies import EncodingStrategy
from .receiver_config import ReceiverConfig
from config import ServerConfig
from werkzeug.utils import secure_filename
import utils

# Platform-specific imports for Windows
_platform_imports_available = False
if platform.system().lower() == 'windows':
    try:
        import win32file
        import win32pipe
        import win32api
        import pywintypes
        _platform_imports_available = True
    except ImportError:
        pass

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
            
            # Use unified data processing
            client_info_extended = {**client_info, "transport": "smb"}
            response_bytes, keep_alive = self.receiver_instance.process_received_data(initial_data_raw, client_info_extended)
            
            # Handle file transfer case
            if response_bytes == b"FILE_TRANSFER_REQUIRED":
                initial_data_decoded = self.receiver_instance.encoding_strategy.decode(initial_data_raw)
                initial_data = initial_data_decoded.decode('utf-8').strip()
                parts = initial_data.split('|')
                command = parts[0] if parts else ""
                self.receiver_instance.handle_file_transfer_smb(pipe_handle, command, parts, client_info)
                return
            
            # Send response through pipe
            self._write_to_pipe(pipe_handle, response_bytes)
            self.receiver_instance.update_bytes_sent(len(response_bytes))
            
            # Handle persistent connections if needed
            if keep_alive:
                self._handle_persistent_pipe_connection(pipe_handle, client_info_extended)
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"SMB Connection Error: {client_info} - {str(e)}")
        finally:
            try:
                self._close_pipe(pipe_handle)
            except:
                pass
    
    def _handle_persistent_pipe_connection(self, pipe_handle, client_info: Dict[str, Any]):
        """Handle persistent SMB pipe connection for multiple messages"""
        timeout_count = 0
        max_timeouts = 10
        
        while timeout_count < max_timeouts and not self.receiver_instance._shutdown_event.is_set():
            try:
                data_raw = self._read_from_pipe(pipe_handle, self.receiver_instance.config.buffer_size)
                if not data_raw:
                    timeout_count += 1
                    time.sleep(0.1)
                    continue
                
                response_bytes, keep_alive = self.receiver_instance.process_received_data(data_raw, client_info)
                
                # Handle file transfer requests
                if response_bytes == b"FILE_TRANSFER_REQUIRED":
                    initial_data_decoded = self.receiver_instance.encoding_strategy.decode(data_raw)
                    initial_data = initial_data_decoded.decode('utf-8').strip()
                    parts = initial_data.split('|')
                    command = parts[0] if parts else ""
                    self.receiver_instance.handle_file_transfer_smb(pipe_handle, command, parts, client_info)
                    continue
                
                # Send response
                self._write_to_pipe(pipe_handle, response_bytes)
                self.receiver_instance.update_bytes_sent(len(response_bytes))
                
                if not keep_alive:
                    break
                    
                timeout_count = 0  # Reset timeout counter
                
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Error in persistent SMB connection from {client_info}: {e}")
                break
    
    def _read_from_pipe(self, pipe_handle, buffer_size: int) -> bytes:
        """Read data from named pipe (platform-specific implementation)"""
        try:
            if os.name == 'nt' and _platform_imports_available:  # Windows
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
            if os.name == 'nt' and _platform_imports_available:  # Windows
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
            if os.name == 'nt' and _platform_imports_available:  # Windows
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
            
            if utils.logger:
                utils.logger.log_message(f"SMB: Setting up receiver on {os.name} platform")
            
            if os.name == 'nt':  # Windows
                if utils.logger:
                    utils.logger.log_message(f"SMB: Using Windows named pipes")
                self._setup_windows_pipe()
            else:  # Unix-like systems
                if utils.logger:
                    utils.logger.log_message(f"SMB: Using Unix FIFOs")
                self._setup_unix_fifo()
            
            if utils.logger:
                utils.logger.log_message(f"SMB: Receiver setup completed successfully")
            return True
            
        except Exception as e:
            error_msg = f"SMB setup failed: {str(e)}"
            if utils.logger:
                utils.logger.log_message(f"SMB: {error_msg}")
            self.error_occurred.emit(self.receiver_id, error_msg)
            return False
    
    def _setup_windows_pipe(self):
        """Setup Windows named pipe"""
        try:
            import win32pipe
            import win32file
            import win32api
            
            self.pipe_path = f"\\\\.\\pipe\\{self.pipe_name}"
            
            if utils.logger:
                utils.logger.log_message(f"SMB: Creating Windows named pipe: {self.pipe_path}")
            
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
                error_code = win32api.GetLastError()
                error_msg = f"Failed to create named pipe. Error code: {error_code}"
                if utils.logger:
                    utils.logger.log_message(f"SMB: {error_msg}")
                raise Exception(error_msg)
            else:
                if utils.logger:
                    utils.logger.log_message(f"SMB: Successfully created Windows named pipe: {self.pipe_path}")
                    utils.logger.log_message(f"SMB: Pipe handle value: {self.pipe_handle}")
                    # Check if pipe handle is valid by trying to get info about it
                    try:
                        import win32pipe
                        pipe_state = win32pipe.GetNamedPipeHandleState(self.pipe_handle)
                        utils.logger.log_message(f"SMB: Pipe state info retrieved successfully")
                    except Exception as state_error:
                        utils.logger.log_message(f"SMB: Could not get pipe state: {state_error}")
                
                # Verify pipe is accessible (WaitNamedPipe returns False for server pipes, which is normal)
                try:
                    if utils.logger:
                        utils.logger.log_message(f"SMB: Verifying pipe accessibility...")
                    result = win32pipe.WaitNamedPipe(self.pipe_path, 100)  # Short timeout
                    error_code = win32api.GetLastError()
                    
                    if not result and error_code == 0:
                        # This is normal - server pipe in listening mode
                        if utils.logger:
                            utils.logger.log_message(f"SMB: Named pipe server is ready to accept client connections")
                    elif not result and error_code != 0:
                        # Actual error
                        if utils.logger:
                            utils.logger.log_message(f"SMB: Warning - pipe verification failed with error code: {error_code}")
                    else:
                        # Unexpected success
                        if utils.logger:
                            utils.logger.log_message(f"SMB: Pipe verification returned unexpected success")
                except Exception as verify_error:
                    if utils.logger:
                        utils.logger.log_message(f"SMB: Pipe verification error: {verify_error}")
                
        except ImportError as e:
            error_msg = f"pywin32 package required for Windows SMB support: {e}"
            if utils.logger:
                utils.logger.log_message(f"SMB: {error_msg}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Windows named pipe setup failed: {e}"
            if utils.logger:
                utils.logger.log_message(f"SMB: {error_msg}")
            raise
    
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
        
        current_pipe = self.pipe_handle
        
        while not self._shutdown_event.is_set():
            try:
                # Wait for client connection
                if utils.logger:
                    utils.logger.log_message(f"SMB: Waiting for client connection on pipe...")
                win32pipe.ConnectNamedPipe(current_pipe, None)
                
                if utils.logger:
                    utils.logger.log_message(f"SMB: Client connected to named pipe")
                
                # Update connection stats
                self.increment_active_connections()
                
                try:
                    # Handle the connection
                    client_info = {"type": "named_pipe", "path": self.pipe_path}
                    self.connection_handler.handle_pipe_connection(current_pipe, client_info)
                finally:
                    self.decrement_active_connections()
                    
                    # Disconnect current client
                    try:
                        win32pipe.DisconnectNamedPipe(current_pipe)
                        if utils.logger:
                            utils.logger.log_message(f"SMB: Disconnected client from pipe")
                    except pywintypes.error as disconnect_error:
                        if utils.logger:
                            utils.logger.log_message(f"SMB: Disconnect error: {disconnect_error}")
                    
                    # For named pipes, we need to create a new instance for the next connection
                    try:
                        if utils.logger:
                            utils.logger.log_message(f"SMB: Creating new pipe instance for next connection")
                        
                        new_pipe = win32pipe.CreateNamedPipe(
                            self.pipe_path,
                            win32pipe.PIPE_ACCESS_DUPLEX,
                            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                            win32pipe.PIPE_UNLIMITED_INSTANCES,
                            self.config.buffer_size,
                            self.config.buffer_size,
                            300,  # Default timeout
                            None
                        )
                        
                        if new_pipe == win32file.INVALID_HANDLE_VALUE:
                            if utils.logger:
                                utils.logger.log_message(f"SMB: Failed to create new pipe instance")
                            break
                        else:
                            # Close the old pipe and use the new one
                            try:
                                win32file.CloseHandle(current_pipe)
                            except:
                                pass
                            current_pipe = new_pipe
                            if utils.logger:
                                utils.logger.log_message(f"SMB: New pipe instance ready")
                    
                    except Exception as create_error:
                        if utils.logger:
                            utils.logger.log_message(f"SMB: Error creating new pipe instance: {create_error}")
                        break
                    
            except pywintypes.error as e:
                if self._shutdown_event.is_set():
                    break
                if utils.logger:
                    utils.logger.log_message(f"SMB: Windows pipe error: {e}")
                time.sleep(0.1)
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"SMB: Unexpected error: {e}")
                time.sleep(1)
        
        # Cleanup final pipe handle
        if current_pipe and current_pipe != self.pipe_handle:
            try:
                win32file.CloseHandle(current_pipe)
            except:
                pass
    
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
        
        if command == "to_beacon":
            # Send file through pipe
            self._send_file_smb(pipe_handle, filename)
        else:  # from_beacon
            # Receive file through pipe
            ready_response = self.encoding_strategy.encode(b"READY")
            self.connection_handler._write_to_pipe(pipe_handle, ready_response)
            self._receive_file_smb(pipe_handle, filename)
    
    # Note: SMB command processing now uses the unified process_received_data() method from BaseReceiver
    
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