import socket
import threading
import time
import json
from typing import Dict, Any, Optional, List
from .base_receiver import BaseReceiver, ReceiverStatus
from .encoding_strategies import EncodingStrategy
from .receiver_config import ReceiverConfig
import utils

class MetasploitSessionHandler:
    """Handles Metasploit session connections using BaseReceiver functionality"""
    
    def __init__(self, receiver_instance):
        self.receiver_instance = receiver_instance
    
    def handle_session_event(self, session_data: Dict[str, Any]):
        """Handle a Metasploit session event"""
        
        try:
            session_id = session_data.get('session_id')
            session_type = session_data.get('type', 'unknown')
            event_type = session_data.get('event', 'unknown')
            
            if utils.logger:
                utils.logger.log_message(f"Metasploit session event: {event_type} for session {session_id} ({session_type})")
            
            # Update connection stats
            if event_type == 'session_open':
                self.receiver_instance.increment_active_connections()
            elif event_type == 'session_close':
                self.receiver_instance.decrement_active_connections()
            
            # Process the session event
            self._process_session_event(session_data)
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Metasploit session error: {str(e)}")
    
    def _process_session_event(self, session_data: Dict[str, Any]):
        """Process different types of Metasploit session events"""
        
        event_type = session_data.get('event', 'unknown')
        session_id = session_data.get('session_id')
        
        try:
            if event_type == 'session_open':
                # Register new session as a beacon
                self._register_metasploit_session(session_data)
            elif event_type == 'session_command_output':
                # Process command output from session
                self._process_session_output(session_data)
            elif event_type == 'session_close':
                # Handle session closure
                self._handle_session_closure(session_data)
            else:
                if utils.logger:
                    utils.logger.log_message(f"Unknown Metasploit event type: {event_type}")
                    
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error processing Metasploit session event {event_type}: {e}")
    
    def _register_metasploit_session(self, session_data: Dict[str, Any]):
        """Register a Metasploit session as a beacon"""
        
        session_id = session_data.get('session_id')
        session_info = session_data.get('info', {})
        
        # Create a beacon ID for the Metasploit session
        beacon_id = f"msf_session_{session_id}"
        host_info = f"{session_info.get('target_host', 'unknown')}:{session_info.get('target_port', 'unknown')}"
        
        # Register with command processor
        if self.receiver_instance.command_processor:
            response = self.receiver_instance.command_processor.process_registration(
                beacon_id, 
                host_info,
                self.receiver_instance.receiver_id, 
                self.receiver_instance.name
            )
            
            if utils.logger:
                utils.logger.log_message(f"Registered Metasploit session {session_id} as beacon {beacon_id}")
    
    def _process_session_output(self, session_data: Dict[str, Any]):
        """Process command output from Metasploit session"""
        
        session_id = session_data.get('session_id')
        output = session_data.get('output', '')
        
        beacon_id = f"msf_session_{session_id}"
        
        # Process through command processor
        if self.receiver_instance.command_processor:
            response = self.receiver_instance.command_processor.process_command_output(beacon_id, output)
    
    def _handle_session_closure(self, session_data: Dict[str, Any]):
        """Handle Metasploit session closure"""
        
        session_id = session_data.get('session_id')
        beacon_id = f"msf_session_{session_id}"
        
        if utils.logger:
            utils.logger.log_message(f"Metasploit session {session_id} closed")

class MetasploitReceiver(BaseReceiver):
    """Metasploit receiver implementation that monitors Metasploit sessions"""
    
    def __init__(self, config: ReceiverConfig, encoding_strategy: EncodingStrategy):
        super().__init__(config.receiver_id, config.name, encoding_strategy)
        self.config = config
        self.metasploit_service = None
        self.session_handler: Optional[MetasploitSessionHandler] = None
        self.polling_interval = config.protocol_config.get('polling_interval', 5)
        self.monitored_sessions: Dict[str, Dict] = {}
        
    def _setup_receiver(self) -> bool:
        """Setup Metasploit receiver"""
        try:
            # Create session handler
            self.session_handler = MetasploitSessionHandler(self)
            
            # Get Metasploit service instance
            try:
                from services.metasploit_service import get_metasploit_service
                self.metasploit_service = get_metasploit_service()
                
                if not self.metasploit_service or not self.metasploit_service.is_connected:
                    raise Exception("Metasploit service not available or not connected")
                    
            except ImportError:
                raise Exception("Metasploit service not available")
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(self.receiver_id, f"Metasploit setup failed: {str(e)}")
            return False
            
    def _start_listening(self):
        """Start monitoring Metasploit sessions"""
        if not self.metasploit_service:
            return
            
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Poll for session updates
                    self._poll_metasploit_sessions()
                    
                    # Wait for next polling interval
                    if self._shutdown_event.wait(self.polling_interval):
                        break  # Shutdown requested
                        
                except Exception as e:
                    if not self._shutdown_event.is_set():
                        if utils.logger:
                            utils.logger.log_message(f"Error polling Metasploit sessions: {e}")
                        time.sleep(self.polling_interval)
                        
        except Exception as e:
            if not self._shutdown_event.is_set():
                self.error_occurred.emit(self.receiver_id, f"Metasploit monitoring error: {str(e)}")
    
    def _poll_metasploit_sessions(self):
        """Poll Metasploit for session updates"""
        
        try:
            # Get current sessions from Metasploit
            sessions_response = self.metasploit_service.get_sessions()
            
            if not sessions_response.get('success', False):
                if utils.logger:
                    utils.logger.log_message("Failed to get Metasploit sessions")
                return
            
            current_sessions = sessions_response.get('sessions', {})
            
            # Check for new sessions
            for session_id, session_info in current_sessions.items():
                if session_id not in self.monitored_sessions:
                    # New session detected
                    session_data = {
                        'event': 'session_open',
                        'session_id': session_id,
                        'type': session_info.get('type', 'unknown'),
                        'info': session_info
                    }
                    self.session_handler.handle_session_event(session_data)
                    self.monitored_sessions[session_id] = session_info
            
            # Check for closed sessions
            closed_sessions = []
            for session_id in self.monitored_sessions:
                if session_id not in current_sessions:
                    # Session closed
                    session_data = {
                        'event': 'session_close',
                        'session_id': session_id,
                        'info': self.monitored_sessions[session_id]
                    }
                    self.session_handler.handle_session_event(session_data)
                    closed_sessions.append(session_id)
            
            # Remove closed sessions from monitoring
            for session_id in closed_sessions:
                del self.monitored_sessions[session_id]
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in Metasploit polling: {e}")
    
    def _cleanup_receiver(self):
        """Cleanup Metasploit receiver"""
        try:
            # Clear monitored sessions
            self.monitored_sessions.clear()
            
            # No specific cleanup needed for Metasploit connection
            # (it's managed by the metasploit_service)
            
        except Exception:
            pass
    
    def _send_data(self, sock: socket.socket, data: bytes) -> bool:
        """Send data through Metasploit (not applicable for session monitoring)"""
        # This method is required by the abstract base class but not used in Metasploit receiver
        # Metasploit communication is handled through the metasploit_service
        return False
    
    def _receive_data(self, sock: socket.socket, buffer_size: int) -> bytes:
        """Receive data through Metasploit (not applicable for session monitoring)"""
        # This method is required by the abstract base class but not used in Metasploit receiver
        # Metasploit data is received via session polling
        return b""
    
    def execute_session_command(self, session_id: str, command: str) -> bool:
        """Execute a command on a Metasploit session"""
        
        try:
            if not self.metasploit_service:
                return False
            
            # Execute command through Metasploit service
            result = self.metasploit_service.execute_session_command(session_id, command)
            
            if result.get('success', False):
                # Handle command output
                output = result.get('output', '')
                if output:
                    session_data = {
                        'event': 'session_command_output',
                        'session_id': session_id,
                        'output': output
                    }
                    self.session_handler.handle_session_event(session_data)
                return True
            else:
                if utils.logger:
                    utils.logger.log_message(f"Failed to execute command on session {session_id}: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error executing session command: {e}")
            return False
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific Metasploit session"""
        
        try:
            if not self.metasploit_service:
                return None
            
            sessions_response = self.metasploit_service.get_sessions()
            if sessions_response.get('success', False):
                sessions = sessions_response.get('sessions', {})
                return sessions.get(session_id)
            
            return None
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error getting session info: {e}")
            return None
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get list of active Metasploit sessions"""
        
        try:
            if not self.metasploit_service:
                return []
            
            sessions_response = self.metasploit_service.get_sessions()
            if sessions_response.get('success', False):
                sessions = sessions_response.get('sessions', {})
                return [
                    {'session_id': sid, **info} 
                    for sid, info in sessions.items()
                ]
            
            return []
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error getting active sessions: {e}")
            return []
                
    def get_configuration(self) -> Dict[str, Any]:
        """Get Metasploit receiver configuration"""
        return {
            "polling_interval": self.polling_interval,
            "monitored_sessions": len(self.monitored_sessions),
            "metasploit_connected": self.metasploit_service.is_connected if self.metasploit_service else False,
            "encoding": self.encoding_strategy.get_name()
        }
        
    def update_configuration(self, config_updates: Dict[str, Any]) -> bool:
        """Update Metasploit receiver configuration"""
        try:
            if "polling_interval" in config_updates:
                new_interval = int(config_updates["polling_interval"])
                if new_interval > 0:
                    self.polling_interval = new_interval
                else:
                    return False
                
            # Update protocol config
            if hasattr(self.config, 'protocol_config'):
                self.config.protocol_config['polling_interval'] = self.polling_interval
                
            # Restart if running to apply changes
            if self.status == ReceiverStatus.RUNNING:
                return self.restart()
                
            return True
            
        except Exception:
            return False
    
    def get_receiver_stats(self) -> Dict[str, Any]:
        """Get Metasploit receiver specific statistics"""
        base_stats = {
            "total_connections": self.stats.total_connections,
            "active_connections": self.stats.active_connections,
            "bytes_received": self.stats.bytes_received,
            "bytes_sent": self.stats.bytes_sent,
            "uptime_seconds": self.stats.uptime_seconds,
            "error_count": self.stats.error_count
        }
        
        metasploit_stats = {
            "monitored_sessions": len(self.monitored_sessions),
            "active_sessions": len(self.get_active_sessions()),
            "polling_interval": self.polling_interval,
            "metasploit_connected": self.metasploit_service.is_connected if self.metasploit_service else False
        }
        
        return {**base_stats, **metasploit_stats}