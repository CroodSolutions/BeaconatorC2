"""
Metasploit Integration Service

Provides programmatic access to Metasploit Framework via RPC for:
- Dynamic payload generation
- Listener/handler management  
- Session monitoring and interaction
- Error handling and reconnection logic
"""

import socket
import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from threading import Lock
from config import ServerConfig
from .custom_msf_rpc import (
    MetasploitRpcClient, MetasploitApiHandlers, PayloadGenerator,
    MetasploitRpcError, AuthenticationError, ConnectionError, RpcMethodError
)
import utils


@dataclass
class PayloadConfig:
    """Configuration for payload generation"""
    payload_type: str
    lhost: str
    lport: int
    format: str = 'exe'
    encoder: Optional[str] = None
    iterations: int = 1
    template: Optional[str] = None
    badchars: Optional[str] = None
    platform: Optional[str] = None
    arch: Optional[str] = None


@dataclass 
class ListenerConfig:
    """Configuration for Metasploit listeners"""
    payload_type: str
    lhost: str
    lport: int
    exit_on_session: bool = False
    persistent: bool = True


@dataclass
class MetasploitSession:
    """Represents an active Metasploit session"""
    session_id: str
    session_type: str
    info: str
    tunnel_local: str
    tunnel_peer: str
    via_exploit: str
    via_payload: str
    platform: str
    arch: str
    username: str
    computer: str
    uuid: str


class MetasploitService:
    """Service for interacting with Metasploit Framework via RPC"""
    
    def __init__(self, config: ServerConfig = None):
        self.config = config or ServerConfig()
        self._client = None
        self._handlers = None
        self._payload_generator = None
        self._connected = False
        self._connection_lock = Lock()
        self._last_connection_attempt = 0
        self._connection_retry_delay = 5  # seconds
        
        # Keep-alive mechanism
        self._keep_alive_timer = None
        self._last_activity = time.time()
        
    @property
    def is_enabled(self) -> bool:
        """Check if Metasploit integration is enabled"""
        return self.config.MSF_ENABLED
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Metasploit RPC"""
        return self._connected and self._client is not None
    
    def connect(self) -> bool:
        """Establish connection to Metasploit RPC server"""
        if not self.is_enabled:
            if utils.logger:
                utils.logger.log_message("Metasploit integration is disabled")
            return False
            
        with self._connection_lock:
            # Rate limit connection attempts
            current_time = time.time()
            if current_time - self._last_connection_attempt < self._connection_retry_delay:
                return False
                
            self._last_connection_attempt = current_time
            
            try:
                if utils.logger:
                    utils.logger.log_message(f"Connecting to Metasploit RPC at {self.config.MSF_RPC_HOST}:{self.config.MSF_RPC_PORT}")
                
                # Create custom RPC client
                self._client = MetasploitRpcClient(
                    host=self.config.MSF_RPC_HOST,
                    port=self.config.MSF_RPC_PORT,
                    username=self.config.MSF_RPC_USER,
                    password=self.config.MSF_RPC_PASS,
                    ssl=self.config.MSF_RPC_SSL,
                    uri=self.config.MSF_RPC_URI,
                    timeout=30
                )
                
                # Establish connection and authenticate
                if self._client.connect():
                    self._connected = True
                    
                    # Initialize handlers and payload generator
                    self._handlers = MetasploitApiHandlers(self._client)
                    self._payload_generator = PayloadGenerator(self._client)
                    
                    # Test connection with version info
                    version_info = self._handlers.core.version()
                    if utils.logger:
                        framework_version = version_info.get('version', 'Unknown')
                        utils.logger.log_message(f"Connected to Metasploit Framework {framework_version}")
                    
                    # Start keep-alive timer if enabled
                    self._start_keep_alive()
                    
                    return True
                else:
                    self._connected = False
                    self._client = None
                    return False
                
            except AuthenticationError as e:
                if utils.logger:
                    utils.logger.log_message(f"Metasploit authentication failed: {str(e)}")
                self._connected = False
                self._client = None
                return False
                
            except ConnectionError as e:
                if utils.logger:
                    utils.logger.log_message(f"Failed to connect to Metasploit RPC: {str(e)}")
                self._connected = False
                self._client = None
                return False
                
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Unexpected error connecting to Metasploit RPC: {str(e)}")
                self._connected = False
                self._client = None
                return False
    
    def disconnect(self):
        """Disconnect from Metasploit RPC"""
        with self._connection_lock:
            # Stop keep-alive timer
            self._stop_keep_alive()
            
            if self._client:
                try:
                    self._client.disconnect()
                except:
                    pass
                    
            self._client = None
            self._handlers = None
            self._payload_generator = None
            self._connected = False
            if utils.logger:
                utils.logger.log_message("Disconnected from Metasploit RPC")
    
    def _ensure_connected(self) -> bool:
        """Ensure we have a valid connection, attempt reconnect if needed"""
        if self.is_connected:
            return True
            
        return self.connect()
    
    def _handle_rpc_error_with_retry(self, func, *args, **kwargs):
        """
        Execute an RPC function with automatic retry on session timeout
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If retry fails or non-recoverable error
        """
        try:
            return func(*args, **kwargs)
        except RpcMethodError as e:
            error_msg = str(e).lower()
            
            # Check if this looks like a session timeout error
            if any(keyword in error_msg for keyword in ['session timeout', 'session may have expired', 'try reconnecting']):
                if utils.logger:
                    utils.logger.log_message(f"Detected possible session timeout: {str(e)}")
                    utils.logger.log_message("Attempting to reconnect to Metasploit RPC...")
                
                # Force disconnect and reconnect
                self.disconnect()
                
                if self.connect():
                    if utils.logger:
                        utils.logger.log_message("Reconnection successful, retrying operation...")
                    
                    # Retry the operation once
                    try:
                        return func(*args, **kwargs)
                    except Exception as retry_error:
                        if utils.logger:
                            utils.logger.log_message(f"Retry failed: {str(retry_error)}")
                        raise retry_error
                else:
                    if utils.logger:
                        utils.logger.log_message("Reconnection failed")
                    raise ConnectionError("Failed to reconnect to Metasploit RPC after session timeout")
            else:
                # Not a session timeout error, re-raise original exception
                raise
    
    def _start_keep_alive(self):
        """Start keep-alive timer to prevent session timeout"""
        if not self.config.MSF_SESSION_KEEP_ALIVE:
            return
            
        self._stop_keep_alive()  # Stop any existing timer
        
        self._keep_alive_timer = threading.Timer(
            self.config.MSF_KEEP_ALIVE_INTERVAL,
            self._keep_alive_tick
        )
        self._keep_alive_timer.daemon = True
        self._keep_alive_timer.start()
        
        if utils.logger:
            utils.logger.log_message(f"Started Metasploit keep-alive timer ({self.config.MSF_KEEP_ALIVE_INTERVAL}s interval)")
    
    def _stop_keep_alive(self):
        """Stop keep-alive timer"""
        if self._keep_alive_timer:
            self._keep_alive_timer.cancel()
            self._keep_alive_timer = None
    
    def _keep_alive_tick(self):
        """Perform keep-alive check"""
        try:
            # Check if we've had recent activity
            time_since_activity = time.time() - self._last_activity
            
            # Only send keep-alive if we haven't had activity recently
            if time_since_activity >= (self.config.MSF_KEEP_ALIVE_INTERVAL * 0.8):
                if self.is_connected and self._handlers:
                    # Simple keep-alive: get version info
                    version_info = self._handlers.core.version()
                    if utils.logger:
                        utils.logger.log_message("Metasploit keep-alive check successful")
                    self._last_activity = time.time()
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Keep-alive check failed: {str(e)}")
        finally:
            # Restart timer if still connected
            if self.is_connected:
                self._start_keep_alive()
    
    def _update_activity(self):
        """Update last activity timestamp"""
        self._last_activity = time.time()
    
    def generate_payload(self, config: PayloadConfig) -> Tuple[bool, bytes, str]:
        """
        Generate a payload using Metasploit with automatic retry on session timeout
        
        Returns:
            Tuple of (success, payload_bytes, error_message)
        """
        if not self._ensure_connected():
            return False, b'', "Not connected to Metasploit RPC"
            
        def _generate_payload_internal():
            if utils.logger:
                utils.logger.log_message(f"Generating payload: {config.payload_type} ({config.format})")
            
            # Prepare payload options
            options = {
                'LHOST': config.lhost,
                'LPORT': config.lport
            }
            
            # Add optional parameters
            if config.encoder and config.encoder != 'none':
                options['Encoder'] = config.encoder
                options['Iterations'] = config.iterations
                
            if config.template:
                options['Template'] = config.template
                
            if config.badchars:
                options['BadChars'] = config.badchars
                
            if config.platform:
                options['Platform'] = config.platform
                
            if config.arch:
                options['Arch'] = config.arch
            
            # Use payload generator if available
            if self._payload_generator:
                success, payload_data, error = self._payload_generator.generate_payload(
                    config.payload_type, options, config.format
                )
                
                if success and utils.logger:
                    utils.logger.log_message(f"Generated payload: {len(payload_data)} bytes")
                
                return success, payload_data, error
            else:
                # Fallback to direct module execution
                result = self._handlers.module.execute('payload', config.payload_type, options)
                
                if result and 'payload' in result:
                    payload_data = result['payload']
                    if isinstance(payload_data, bytes):
                        if utils.logger:
                            utils.logger.log_message(f"Generated payload: {len(payload_data)} bytes")
                        return True, payload_data, ""
                    else:
                        return False, b'', f"Unexpected payload data type: {type(payload_data)}"
                else:
                    error = result.get('error', 'Unknown error during payload generation')
                    return False, b'', error
        
        try:
            # Use retry logic for payload generation
            result = self._handle_rpc_error_with_retry(_generate_payload_internal)
            self._update_activity()  # Update activity timestamp on success
            return result
        except (AuthenticationError, ConnectionError) as e:
            error_msg = f"Connection error generating payload: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return False, b'', error_msg
        except RpcMethodError as e:
            # RPC method errors now contain meaningful messages
            error_msg = f"Payload generation failed: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return False, b'', error_msg
        except Exception as e:
            error_msg = f"Unexpected error generating payload: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return False, b'', error_msg
    
    def start_listener(self, config: ListenerConfig) -> Tuple[bool, str, str]:
        """
        Start a Metasploit listener/handler
        
        Returns:
            Tuple of (success, job_id, error_message)
        """
        if not self._ensure_connected():
            return False, "", "Not connected to Metasploit RPC"
            
        try:
            # Use the multi/handler exploit
            handler = self._client.modules.use('exploit', 'multi/handler')
            if not handler:
                return False, "", "Failed to load multi/handler module"
            
            # Configure handler options
            handler['PAYLOAD'] = config.payload_type
            handler['LHOST'] = config.lhost
            handler['LPORT'] = config.lport
            handler['ExitOnSession'] = config.exit_on_session
            
            if utils.logger:
                utils.logger.log_message(f"Starting listener: {config.payload_type} on {config.lhost}:{config.lport}")
            
            # Execute the handler
            job_id = handler.execute()
            
            if job_id:
                if utils.logger:
                    utils.logger.log_message(f"Listener started with job ID: {job_id}")
                return True, str(job_id), ""
            else:
                return False, "", "Failed to start listener - no job ID returned"
                
        except Exception as e:
            error_msg = f"Error starting listener: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return False, "", error_msg
    
    def stop_listener(self, job_id: str) -> Tuple[bool, str]:
        """
        Stop a Metasploit listener by job ID
        
        Returns:
            Tuple of (success, error_message)
        """
        if not self._ensure_connected():
            return False, "Not connected to Metasploit RPC"
            
        try:
            result = self._client.jobs.stop(job_id)
            
            if utils.logger:
                utils.logger.log_message(f"Stopped listener job: {job_id}")
                
            return True, ""
            
        except Exception as e:
            error_msg = f"Error stopping listener {job_id}: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return False, error_msg
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List active Metasploit jobs"""
        if not self._ensure_connected():
            return []
            
        try:
            jobs = self._client.jobs.list
            return [{"id": job_id, "name": job_info} for job_id, job_info in jobs.items()]
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error listing jobs: {str(e)}")
            return []
    
    def list_sessions(self) -> List[MetasploitSession]:
        """List active Metasploit sessions"""
        if not self._ensure_connected():
            return []
            
        try:
            sessions = self._client.sessions.list
            session_list = []
            
            for session_id, session_info in sessions.items():
                session = MetasploitSession(
                    session_id=str(session_id),
                    session_type=session_info.get('type', ''),
                    info=session_info.get('info', ''),
                    tunnel_local=session_info.get('tunnel_local', ''),
                    tunnel_peer=session_info.get('tunnel_peer', ''),
                    via_exploit=session_info.get('via_exploit', ''),
                    via_payload=session_info.get('via_payload', ''),
                    platform=session_info.get('platform', ''),
                    arch=session_info.get('arch', ''),
                    username=session_info.get('username', ''),
                    computer=session_info.get('computer', ''),
                    uuid=session_info.get('uuid', '')
                )
                session_list.append(session)
                
            return session_list
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error listing sessions: {str(e)}")
            return []
    
    def get_payload_info(self, payload_type: str) -> Dict[str, Any]:
        """Get information about a specific payload module with automatic retry on session timeout"""
        if not self._ensure_connected():
            return {}
        
        def _get_payload_info_internal():
            if self._payload_generator:
                return self._payload_generator.get_payload_info(payload_type)
            else:
                # Fallback to direct handlers access
                return self._handlers.module.info('payload', payload_type)
        
        try:
            # Use retry logic for payload info retrieval
            result = self._handle_rpc_error_with_retry(_get_payload_info_internal)
            self._update_activity()  # Update activity timestamp on success
            return result
        except (AuthenticationError, ConnectionError) as e:
            if utils.logger:
                utils.logger.log_message(f"Connection error getting payload info for {payload_type}: {str(e)}")
            return {}
        except RpcMethodError as e:
            # RPC method errors contain meaningful messages now, so log them directly
            if utils.logger:
                utils.logger.log_message(f"Payload info error for {payload_type}: {str(e)}")
            return {}
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Unexpected error getting payload info for {payload_type}: {str(e)}")
            return {}
    
    def list_payloads(self, platform_filter: Optional[str] = None) -> List[str]:
        """List available payload modules, optionally filtered by platform with automatic retry"""
        if not self._ensure_connected():
            return []
        
        def _list_payloads_internal():
            if self._payload_generator:
                return self._payload_generator.list_payloads(platform_filter)
            else:
                # Fallback to direct handlers access
                payloads = self._handlers.module.payloads()
                
                if platform_filter:
                    # Filter by platform (e.g., 'windows', 'linux', 'python')
                    filtered = [p for p in payloads if platform_filter.lower() in p.lower()]
                    return sorted(filtered)
                else:
                    return sorted(payloads)
        
        try:
            # Use retry logic for payload listing
            result = self._handle_rpc_error_with_retry(_list_payloads_internal)
            self._update_activity()  # Update activity timestamp on success
            return result
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error listing payloads: {str(e)}")
            return []
    
    def get_server_ip(self) -> str:
        """Get the server IP for LHOST defaults"""
        if self.config.MSF_DEFAULT_LHOST:
            return self.config.MSF_DEFAULT_LHOST
            
        # Try to detect external IP
        try:
            # Try to get IP by connecting to a remote host
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(1)
                s.connect(('8.8.8.8', 80))
                local_ip = s.getsockname()[0]
                return local_ip
        except:
            pass
            
        # Fallback to localhost
        return '127.0.0.1'
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to Metasploit RPC and return status"""
        if not self.is_enabled:
            return False, "Metasploit integration is disabled"
            
        if self.connect():
            try:
                if self._handlers:
                    version_info = self._handlers.core.version()
                    version = version_info.get('version', 'Unknown')
                    return True, f"Connected to Metasploit Framework {version}"
                else:
                    return True, "Connected to Metasploit RPC"
            except Exception as e:
                return False, f"Connection test failed: {str(e)}"
        else:
            return False, "Failed to connect to Metasploit RPC"
    
    def diagnose_connection(self) -> Dict[str, Any]:
        """
        Perform comprehensive diagnostics on Metasploit connection
        
        Returns:
            Dictionary with diagnostic information
        """
        if not self.is_enabled:
            return {'error': 'Metasploit integration is disabled'}
        
        if not self._ensure_connected():
            return {'error': 'Failed to establish connection to Metasploit RPC'}
        
        if utils.logger:
            utils.logger.log_message("Running Metasploit connection diagnostics...")
        
        try:
            # Run comprehensive diagnostics
            diagnostics = self._handlers.diagnose_connection()
            
            # Log diagnostic results
            if utils.logger:
                if diagnostics['errors']:
                    utils.logger.log_message(f"Metasploit diagnostics found {len(diagnostics['errors'])} issues:")
                    for error in diagnostics['errors']:
                        utils.logger.log_message(f"  - {error}")
                else:
                    utils.logger.log_message("Metasploit diagnostics completed successfully")
            
            return diagnostics
            
        except Exception as e:
            error_msg = f"Diagnostic check failed: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return {'error': error_msg}