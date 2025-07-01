from abc import abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject, Qt, pyqtSlot
import threading
import time
from .encoding_strategies import EncodingStrategy

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