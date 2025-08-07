"""
Custom Metasploit RPC Client

A native Python implementation for interacting with Metasploit Framework's RPC API
without relying on outdated third-party libraries.

Supports both MessagePack and JSON RPC protocols.
"""

import json
import time
import base64
import requests
import msgpack
from typing import Dict, Any, List, Optional, Tuple, Union
from urllib.parse import urljoin
from threading import Lock
import ssl
import utils


def normalize_response(data):
    """
    Recursively normalize MessagePack response data, converting bytes to strings
    """
    if isinstance(data, bytes):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return data
    elif isinstance(data, dict):
        return {
            normalize_response(k): normalize_response(v) 
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [normalize_response(item) for item in data]
    else:
        return data


class MetasploitRpcError(Exception):
    """Base exception for Metasploit RPC errors"""
    pass


class AuthenticationError(MetasploitRpcError):
    """Authentication failed"""
    pass


class ConnectionError(MetasploitRpcError):
    """Connection to RPC server failed"""
    pass


class RpcMethodError(MetasploitRpcError):
    """RPC method execution failed"""
    pass


class MetasploitRpcClient:
    """
    Custom Metasploit RPC client using native Python libraries
    
    Supports both MessagePack RPC (msfrpcd) and JSON RPC protocols
    """
    
    def __init__(self, host: str = '127.0.0.1', port: int = 55553, 
                 username: str = 'msf', password: str = 'msf123',
                 ssl: bool = True, uri: str = '/api/', timeout: int = 30,
                 use_json_rpc: bool = False):
        """
        Initialize RPC client
        
        Args:
            host: RPC server hostname
            port: RPC server port  
            username: Authentication username
            password: Authentication password
            ssl: Use SSL/TLS connection
            uri: RPC endpoint URI
            timeout: Request timeout in seconds
            use_json_rpc: Use JSON RPC instead of MessagePack RPC
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = ssl
        self.uri = uri
        self.timeout = timeout
        self.use_json_rpc = use_json_rpc
        
        # Connection state
        self._token = None
        self._authenticated = False
        self._session = None
        self._lock = Lock()
        
        # Build base URL
        protocol = 'https' if ssl else 'http'
        self.base_url = f"{protocol}://{host}:{port}"
        self.rpc_url = urljoin(self.base_url, uri)
        
        # Initialize requests session
        self._init_session()
        
    def _init_session(self):
        """Initialize HTTP session with proper SSL handling"""
        self._session = requests.Session()
        self._session.timeout = self.timeout
        
        # Configure SSL verification
        if self.use_ssl:
            # Disable SSL warnings for self-signed certificates
            requests.packages.urllib3.disable_warnings()
            self._session.verify = False
            
        # Set common headers
        if self.use_json_rpc:
            self._session.headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
        else:
            self._session.headers.update({
                'Content-Type': 'binary/message-pack',
                'Accept': 'binary/message-pack'
            })
    
    def connect(self) -> bool:
        """
        Establish connection and authenticate with RPC server
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            return self.authenticate()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Metasploit RPC: {str(e)}")
    
    def authenticate(self) -> bool:
        """
        Authenticate with the RPC server
        
        Returns:
            True if authentication successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        with self._lock:
            try:
                if self.use_json_rpc:
                    result = self._call_json_rpc('auth.login', [self.username, self.password])
                else:
                    result = self._call_msgpack_rpc('auth.login', [self.username, self.password])
                
                if result and 'result' in result:
                    if result['result'] == 'success':
                        self._token = result.get('token')
                        self._authenticated = True
                        return True
                    else:
                        raise AuthenticationError(f"Authentication failed: {result.get('error', 'Unknown error')}")
                else:
                    raise AuthenticationError("Invalid authentication response")
                    
            except requests.exceptions.RequestException as e:
                raise ConnectionError(f"Network error during authentication: {str(e)}")
            except Exception as e:
                raise AuthenticationError(f"Authentication error: {str(e)}")
    
    def _call_json_rpc(self, method: str, params: List[Any] = None) -> Dict[str, Any]:
        """
        Make a JSON RPC call
        
        Args:
            method: RPC method name
            params: Method parameters
            
        Returns:
            RPC response as dictionary
        """
        if params is None:
            params = []
            
        payload = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': int(time.time() * 1000)  # Use timestamp as ID
        }
        
        # Add token to params if authenticated (except for auth.login)
        if self._authenticated and method != 'auth.login':
            payload['params'] = [self._token] + params
        
        response = self._session.post(self.rpc_url, json=payload)
        response.raise_for_status()
        
        return response.json()
    
    def _call_msgpack_rpc(self, method: str, params: List[Any] = None) -> Dict[str, Any]:
        """
        Make a MessagePack RPC call
        
        Args:
            method: RPC method name  
            params: Method parameters
            
        Returns:
            RPC response as dictionary
        """
        if params is None:
            params = []
            
        # Build MessagePack RPC request array
        if self._authenticated and method != 'auth.login':
            request_data = [method, self._token] + params
        else:
            request_data = [method] + params
        
        # Encode request with MessagePack
        packed_data = msgpack.packb(request_data)
        
        response = self._session.post(self.rpc_url, data=packed_data)
        response.raise_for_status()
        
        # Decode MessagePack response and normalize byte strings
        raw_response = msgpack.unpackb(response.content, raw=False, strict_map_key=False)
        return normalize_response(raw_response)
    
    def call(self, method: str, params: List[Any] = None) -> Dict[str, Any]:
        """
        Make an RPC call using the configured protocol
        
        Args:
            method: RPC method name
            params: Method parameters
            
        Returns:
            RPC response
            
        Raises:
            RpcMethodError: If RPC call fails
            AuthenticationError: If not authenticated
        """
        if not self._authenticated and method != 'auth.login':
            raise AuthenticationError("Not authenticated - call authenticate() first")
        
        try:
            # Log RPC request for debugging
            import utils
            if utils.logger:
                utils.logger.log_message(f"RPC Call: {method} with params: {params}")
            
            # Original logging comment
            if utils.logger:
                params_str = str(params) if params else "[]"
                utils.logger.log_message(f"Metasploit RPC Request: {method}({params_str})")
            
            if self.use_json_rpc:
                result = self._call_json_rpc(method, params)
            else:
                result = self._call_msgpack_rpc(method, params)
            
            # Log RPC response for debugging (truncated if too long)
            if utils.logger:
                result_str = str(result)
                if len(result_str) > 200:
                    result_str = result_str[:200] + "..."
                utils.logger.log_message(f"Metasploit RPC Response: {result_str}")
            
            # Check for RPC errors
            if isinstance(result, dict) and 'error' in result:
                error_value = result['error']
                
                # Extract additional error information if available
                error_class = result.get('error_class', '')
                error_string = result.get('error_string', '')
                error_backtrace = result.get('error_backtrace', [])
                
                # Handle the case where Metasploit returns True as error
                if error_value is True:
                    # Use Metasploit's error class for more specific error messages
                    if error_class == 'Msf::RPC::Exception':
                        # This could be session timeout, module not found, or other RPC issues
                        if params and len(params) >= 2 and method.startswith('module.'):
                            module_type = params[0] if isinstance(params[0], str) else str(params[0])
                            module_name = params[1] if isinstance(params[1], str) else str(params[1])
                            
                            # Check if it's a module.payloads error (different format)
                            if method == 'module.payloads':
                                raise RpcMethodError("Failed to retrieve payload list from Metasploit. This may indicate a session timeout or database connection issue.")
                            else:
                                # For module.execute, this often indicates session timeout
                                if method == 'module.execute':
                                    raise RpcMethodError(f"Module execution failed for {module_type}/{module_name}. This may indicate a session timeout - try reconnecting to Metasploit.")
                                else:
                                    raise RpcMethodError(f"Module not found: {module_type}/{module_name}")
                        else:
                            # Generic RPC exception - likely session timeout
                            if error_string and error_string != 'Msf::RPC::Exception':
                                raise RpcMethodError(f"Metasploit RPC error: {error_string}")
                            else:
                                raise RpcMethodError(f"Metasploit RPC session may have expired. Try reconnecting.")
                    else:
                        # Other error types
                        error_msg = error_class if error_class else "Unknown Metasploit error"
                        if error_string and error_string != error_class:
                            error_msg += f": {error_string}"
                        raise RpcMethodError(error_msg)
                else:
                    # Handle specific database errors more gracefully
                    if error_class == 'NameError' and ('DBManager' in error_string or 'Acunetix' in error_string):
                        # Database module errors - these can affect various operations
                        if method in ['db.status', 'console.create', 'console.read', 'console.write']:
                            if utils.logger:
                                utils.logger.log_message(f"Database module error (attempting workaround): {error_string}")
                            # Return a result indicating database issues but don't fail completely
                            return {'error': 'database_module_error', 'error_message': error_string, 'critical': False}
                        else:
                            raise RpcMethodError(f"Database error in '{method}': {error_string}")
                    else:
                        # Standard error message handling
                        raise RpcMethodError(f"RPC method '{method}' failed: {error_value}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Network error calling '{method}': {str(e)}")
        except Exception as e:
            if isinstance(e, (AuthenticationError, RpcMethodError, ConnectionError)):
                raise
            raise RpcMethodError(f"Error calling '{method}': {str(e)}")
    
    def is_connected(self) -> bool:
        """Check if client is connected and authenticated"""
        return self._authenticated and self._token is not None
    
    def disconnect(self):
        """Disconnect from RPC server"""
        if self._authenticated:
            try:
                self.call('auth.logout')
            except:
                pass  # Ignore logout errors
                
        self._authenticated = False
        self._token = None
        
        if self._session:
            self._session.close()


class MetasploitApiHandlers:
    """
    High-level API handlers for different Metasploit RPC functionality
    """
    
    def __init__(self, client: MetasploitRpcClient):
        self.client = client
        self.core = CoreHandler(client)
        self.auth = AuthHandler(client)
        self.module = ModuleHandler(client)
        self.session = SessionHandler(client)
        self.console = ConsoleHandler(client)
        self.job = JobHandler(client)
        self.db = DatabaseHandler(client)
    
    def diagnose_connection(self) -> Dict[str, Any]:
        """
        Perform comprehensive connection diagnostics
        
        Returns:
            Dictionary with diagnostic information
        """
        diagnostics = {
            'core_version': None,
            'core_stats': None,
            'db_status': None,
            'module_stats': None,
            'errors': []
        }
        
        try:
            # Test core.version (basic connectivity)
            diagnostics['core_version'] = self.core.version()
        except Exception as e:
            diagnostics['errors'].append(f"Core version check failed: {str(e)}")
        
        try:
            # Test module.stats (module system)
            diagnostics['core_stats'] = self.core.module_stats()
        except Exception as e:
            diagnostics['errors'].append(f"Module stats check failed: {str(e)}")
        
        try:
            # Test database connectivity
            db_status = self.db.status()
            diagnostics['db_status'] = db_status
            
            # Check if it's a non-critical database error
            if isinstance(db_status, dict) and not db_status.get('critical', True):
                # Non-critical database error - log as warning instead of error
                diagnostics['warnings'] = diagnostics.get('warnings', [])
                diagnostics['warnings'].append(f"Database warning: {db_status.get('error', 'Unknown database issue')}")
        except Exception as e:
            diagnostics['errors'].append(f"Database status check failed: {str(e)}")
        
        return diagnostics


class BaseHandler:
    """Base class for RPC API handlers"""
    
    def __init__(self, client: MetasploitRpcClient):
        self.client = client
    
    def call(self, method: str, params: List[Any] = None) -> Dict[str, Any]:
        """Convenience method for making RPC calls"""
        return self.client.call(method, params)


class CoreHandler(BaseHandler):
    """Handler for core framework operations"""
    
    def version(self) -> Dict[str, Any]:
        """Get Metasploit Framework version information"""
        return self.call('core.version')
    
    def module_stats(self) -> Dict[str, Any]:
        """Get module statistics (count by type)"""
        return self.call('core.module_stats')
    
    def reload_modules(self) -> Dict[str, Any]:
        """Reload all modules"""
        return self.call('core.reload_modules')
    
    def thread_list(self) -> Dict[str, Any]:
        """List background threads"""
        return self.call('core.thread_list')
    
    def stop(self) -> Dict[str, Any]:
        """Stop the Metasploit Framework"""
        return self.call('core.stop')


class AuthHandler(BaseHandler):
    """Handler for authentication operations"""
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate with username and password"""
        return self.call('auth.login', [username, password])
    
    def logout(self) -> Dict[str, Any]:
        """Logout and invalidate token"""
        return self.call('auth.logout')
    
    def token_add(self, token: str) -> Dict[str, Any]:
        """Add a permanent authentication token"""
        return self.call('auth.token_add', [token])
    
    def token_generate(self) -> Dict[str, Any]:
        """Generate a random authentication token"""
        return self.call('auth.token_generate')
    
    def token_list(self) -> Dict[str, Any]:
        """List all authentication tokens"""
        return self.call('auth.token_list')
    
    def token_remove(self, token: str) -> Dict[str, Any]:
        """Remove a specific authentication token"""
        return self.call('auth.token_remove', [token])


class ModuleHandler(BaseHandler):
    """Handler for module operations"""
    
    def exploits(self) -> List[str]:
        """List all exploit modules"""
        result = self.call('module.exploits')
        return result.get('modules', []) if isinstance(result, dict) else result
    
    def auxiliary(self) -> List[str]:
        """List all auxiliary modules"""
        result = self.call('module.auxiliary')
        return result.get('modules', []) if isinstance(result, dict) else result
    
    def post(self) -> List[str]:
        """List all post-exploitation modules"""
        result = self.call('module.post')
        return result.get('modules', []) if isinstance(result, dict) else result
    
    def payloads(self) -> List[str]:
        """List all payload modules"""
        result = self.call('module.payloads')
        return result.get('modules', []) if isinstance(result, dict) else result
    
    def encoders(self) -> List[str]:
        """List all encoder modules"""
        result = self.call('module.encoders')
        return result.get('modules', []) if isinstance(result, dict) else result
    
    def nops(self) -> List[str]:
        """List all NOP modules"""
        result = self.call('module.nops')
        return result.get('modules', []) if isinstance(result, dict) else result
    
    def info(self, module_type: str, module_name: str) -> Dict[str, Any]:
        """Get detailed information about a module"""
        return self.call('module.info', [module_type, module_name])
    
    def options(self, module_type: str, module_name: str) -> Dict[str, Any]:
        """Get module options/parameters"""
        return self.call('module.options', [module_type, module_name])
    
    def compatible_payloads(self, module_name: str) -> List[str]:
        """Get compatible payloads for an exploit module"""
        result = self.call('module.compatible_payloads', [module_name])
        return result.get('payloads', []) if isinstance(result, dict) else result
    
    def execute(self, module_type: str, module_name: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a module with specified options"""
        import utils
        if utils.logger:
            utils.logger.log_message(f"ModuleHandler.execute: module_type={module_type}, module_name={module_name}, options={options}")
        
        result = self.call('module.execute', [module_type, module_name, options])
        
        if utils.logger:
            utils.logger.log_message(f"ModuleHandler.execute: RPC result={result}")
        
        return result
    
    def encode(self, data: str, encoder: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Encode data using specified encoder"""
        params = [data, encoder]
        if options:
            params.append(options)
        return self.call('module.encode', params)


class SessionHandler(BaseHandler):
    """Handler for session operations"""
    
    def list(self) -> Dict[str, Any]:
        """List all active sessions"""
        return self.call('session.list')
    
    def stop(self, session_id: str) -> Dict[str, Any]:
        """Stop/terminate a session"""
        return self.call('session.stop', [session_id])
    
    def shell_read(self, session_id: str) -> Dict[str, Any]:
        """Read output from a shell session"""
        return self.call('session.shell_read', [session_id])
    
    def shell_write(self, session_id: str, data: str) -> Dict[str, Any]:
        """Write input to a shell session"""
        return self.call('session.shell_write', [session_id, data])
    
    def meterpreter_read(self, session_id: str) -> Dict[str, Any]:
        """Read output from a Meterpreter session"""
        return self.call('session.meterpreter_read', [session_id])
    
    def meterpreter_write(self, session_id: str, data: str) -> Dict[str, Any]:
        """Write input to a Meterpreter session"""
        return self.call('session.meterpreter_write', [session_id, data])
    
    def meterpreter_run_single(self, session_id: str, command: str) -> Dict[str, Any]:
        """Run a single command in a Meterpreter session"""
        return self.call('session.meterpreter_run_single', [session_id, command])
    
    def compatible_modules(self, session_id: str) -> List[str]:
        """List post-exploitation modules compatible with session"""
        result = self.call('session.compatible_modules', [session_id])
        return result.get('modules', []) if isinstance(result, dict) else result


class ConsoleHandler(BaseHandler):
    """Handler for console operations"""
    
    def create(self) -> Dict[str, Any]:
        """Create a new console instance"""
        return self.call('console.create')
    
    def destroy(self, console_id: str) -> Dict[str, Any]:
        """Destroy a console instance"""
        return self.call('console.destroy', [console_id])
    
    def list(self) -> Dict[str, Any]:
        """List all console instances"""
        return self.call('console.list')
    
    def write(self, console_id: str, data: str) -> Dict[str, Any]:
        """Write data to console"""
        return self.call('console.write', [console_id, data])
    
    def read(self, console_id: str) -> Dict[str, Any]:
        """Read console output"""
        return self.call('console.read', [console_id])
    
    def session_detach(self, console_id: str) -> Dict[str, Any]:
        """Detach from interactive session"""
        return self.call('console.session_detach', [console_id])
    
    def session_kill(self, console_id: str) -> Dict[str, Any]:
        """Kill interactive session"""
        return self.call('console.session_kill', [console_id])
    
    def tabs(self, console_id: str, input_line: str) -> Dict[str, Any]:
        """Get tab completion suggestions"""
        return self.call('console.tabs', [console_id, input_line])


class JobHandler(BaseHandler):
    """Handler for job operations"""
    
    def list(self) -> Dict[str, Any]:
        """List all background jobs"""
        return self.call('job.list')
    
    def stop(self, job_id: str) -> Dict[str, Any]:
        """Stop a background job"""
        return self.call('job.stop', [job_id])
    
    def info(self, job_id: str) -> Dict[str, Any]:
        """Get information about a job"""
        return self.call('job.info', [job_id])


class DatabaseHandler(BaseHandler):
    """Handler for database operations"""
    
    def status(self) -> Dict[str, Any]:
        """Get database connection status"""
        try:
            result = self.call('db.status')
            # Check for graceful database error
            if isinstance(result, dict) and result.get('error') == 'database_module_error':
                return {
                    'connected': False,
                    'error': result.get('error_message', 'Database module error'),
                    'critical': False
                }
            return result
        except RpcMethodError as e:
            # Handle database errors gracefully
            if 'database' in str(e).lower() or 'dbmanager' in str(e).lower():
                return {
                    'connected': False,
                    'error': str(e),
                    'critical': False
                }
            raise
    
    def connect(self, opts: Dict[str, Any]) -> Dict[str, Any]:
        """Connect to database"""
        return self.call('db.connect', [opts])
    
    def disconnect(self) -> Dict[str, Any]:
        """Disconnect from database"""
        return self.call('db.disconnect')
    
    def hosts(self, opts: Dict[str, Any] = None) -> Dict[str, Any]:
        """List hosts in database"""
        params = [opts] if opts else []
        return self.call('db.hosts', params)
    
    def services(self, opts: Dict[str, Any] = None) -> Dict[str, Any]:
        """List services in database"""
        params = [opts] if opts else []
        return self.call('db.services', params)
    
    def vulns(self, opts: Dict[str, Any] = None) -> Dict[str, Any]:
        """List vulnerabilities in database"""
        params = [opts] if opts else []
        return self.call('db.vulns', params)
    
    def workspaces(self) -> Dict[str, Any]:
        """List database workspaces"""
        return self.call('db.workspaces')
    
    def current_workspace(self) -> Dict[str, Any]:
        """Get current workspace"""
        return self.call('db.current_workspace')
    
    def set_workspace(self, name: str) -> Dict[str, Any]:
        """Set current workspace"""
        return self.call('db.set_workspace', [name])
    
    def add_workspace(self, name: str) -> Dict[str, Any]:
        """Add new workspace"""
        return self.call('db.add_workspace', [name])
    
    def del_workspace(self, name: str) -> Dict[str, Any]:
        """Delete workspace"""
        return self.call('db.del_workspace', [name])


class PayloadGenerator:
    """
    High-level payload generation helper using Metasploit RPC
    """
    
    def __init__(self, client: MetasploitRpcClient):
        self.client = client
        self.handlers = MetasploitApiHandlers(client)
    
    def list_payloads(self, platform_filter: str = None) -> List[str]:
        """
        List available payloads, optionally filtered by platform
        
        Args:
            platform_filter: Filter by platform (e.g., 'windows', 'linux', 'python')
            
        Returns:
            List of payload module names
        """
        try:
            payloads = self.handlers.module.payloads()
            
            if platform_filter:
                # Filter payloads by platform
                filtered = []
                platform_lower = platform_filter.lower()
                for payload in payloads:
                    if platform_lower in payload.lower():
                        filtered.append(payload)
                return filtered
            
            return payloads
            
        except Exception as e:
            raise RpcMethodError(f"Failed to list payloads: {str(e)}")
    
    def validate_payload_name(self, payload_name: str) -> Tuple[bool, Optional[str], List[str]]:
        """
        Validate a payload name and suggest corrections if invalid
        
        Args:
            payload_name: Payload name to validate
            
        Returns:
            Tuple of (is_valid, corrected_name, suggestions)
        """
        try:
            # Get list of all payloads
            available_payloads = self.list_payloads()
            
            # Check if exact match exists
            if payload_name in available_payloads:
                return True, payload_name, []
            
            # Look for similar payload names
            suggestions = []
            payload_lower = payload_name.lower()
            
            # Check for common naming pattern fixes
            corrected_name = None
            
            # Common fix: replace underscore with slash (e.g., meterpreter_reverse_tcp -> meterpreter/reverse_tcp)
            if '_' in payload_name:
                parts = payload_name.split('/')
                if len(parts) >= 2:
                    # Try replacing underscores in the last part with slashes
                    last_part = parts[-1]
                    if '_' in last_part:
                        sub_parts = last_part.split('_', 1)  # Split only on first underscore
                        potential_fix = '/'.join(parts[:-1]) + '/' + '/'.join(sub_parts)
                        if potential_fix in available_payloads:
                            corrected_name = potential_fix
            
            # Find similar names using fuzzy matching
            for payload in available_payloads:
                payload_parts = payload.lower().split('/')
                input_parts = payload_lower.split('/')
                
                # Check if significant parts match
                if len(payload_parts) >= 2 and len(input_parts) >= 2:
                    # Check platform match
                    if payload_parts[0] == input_parts[0]:
                        # Check if payload type is similar
                        if any(part in payload.lower() for part in input_parts[1:]):
                            suggestions.append(payload)
                
                # Limit suggestions to avoid overwhelming the user
                if len(suggestions) >= 5:
                    break
            
            # Sort suggestions by similarity (platform matches first)
            suggestions.sort(key=lambda x: (
                not x.lower().startswith(payload_lower.split('/')[0]) if '/' in payload_lower else True,
                len(x)
            ))
            
            return False, corrected_name, suggestions[:5]
            
        except Exception:
            # If validation fails, assume payload might be valid and let RPC handle it
            return True, payload_name, []

    def get_payload_info(self, payload_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a payload including options
        
        Args:
            payload_name: Full payload module name (e.g., 'windows/meterpreter/reverse_tcp')
            
        Returns:
            Dictionary containing payload info and options
        """
        try:
            # Validate payload name first
            is_valid, corrected_name, suggestions = self.validate_payload_name(payload_name)
            
            # Use corrected name if available
            if corrected_name:
                payload_name = corrected_name
            elif not is_valid and suggestions:
                # Include suggestions in error message
                suggestion_text = f". Did you mean: {', '.join(suggestions[:3])}"
                raise RpcMethodError(f"Payload '{payload_name}' not found{suggestion_text}")
            
            # Get basic module info
            info = self.handlers.module.info('payload', payload_name)
            
            # Get module options
            options = self.handlers.module.options('payload', payload_name)
            
            # Combine into single response
            result = {
                'name': payload_name,
                'description': info.get('description', ''),
                'authors': info.get('author', []),
                'platform': info.get('platform', ''),
                'arch': info.get('arch', ''),
                'options': options
            }
            
            return result
            
        except RpcMethodError:
            # Re-raise RPC method errors as-is
            raise
        except Exception as e:
            raise RpcMethodError(f"Failed to get payload info for '{payload_name}': {str(e)}")
    
    def generate_payload(self, payload_name: str, options: Dict[str, Any], 
                        format: str = 'raw') -> Tuple[bool, Any, str]:
        """
        Generate a payload with specified options
        
        Args:
            payload_name: Full payload module name
            options: Dictionary of payload options (LHOST, LPORT, etc.)
            format: Output format ('raw', 'exe', 'elf', 'hex', etc.)
            
        Returns:
            Tuple of (success, payload_data, error_message)
        """
        try:
            # Import helper functions to determine format type
            from utils.helpers import is_text_format
            
            # Prepare payload options
            payload_options = dict(options)
            if format != 'raw':
                payload_options['Format'] = format
            
            # Execute payload generation
            result = self.handlers.module.execute('payload', payload_name, payload_options)
            
            if result and 'payload' in result:
                payload_data = result['payload']
                
                # Handle different payload formats appropriately
                if is_text_format(format):
                    # Text-based formats (PowerShell, Python, etc.) should be returned as strings
                    if isinstance(payload_data, str):
                        return True, payload_data, ""
                    elif isinstance(payload_data, bytes):
                        try:
                            # Try to decode as UTF-8
                            text_data = payload_data.decode('utf-8')
                            return True, text_data, ""
                        except UnicodeDecodeError:
                            # If decoding fails, return as bytes
                            return True, payload_data, ""
                    else:
                        return False, "", f"Unexpected payload data type for text format: {type(payload_data)}"
                else:
                    # Binary formats should be returned as bytes
                    if isinstance(payload_data, str):
                        try:
                            # Try to decode base64 for binary payloads
                            decoded_data = base64.b64decode(payload_data)
                            return True, decoded_data, ""
                        except:
                            # If not base64, encode as bytes
                            return True, payload_data.encode('utf-8'), ""
                    elif isinstance(payload_data, bytes):
                        return True, payload_data, ""
                    else:
                        return False, b'', f"Unexpected payload data type for binary format: {type(payload_data)}"
            else:
                error_msg = result.get('error', 'Unknown error during payload generation')
                return False, b'', error_msg
                
        except Exception as e:
            return False, b'', f"Payload generation failed: {str(e)}"
    
    def create_handler(self, payload_name: str, lhost: str, lport: int, 
                      exit_on_session: bool = False) -> Tuple[bool, str, str]:
        """
        Create a handler/listener for a payload
        
        Args:
            payload_name: Payload type for the handler
            lhost: Listen host
            lport: Listen port
            exit_on_session: Exit handler when session is created
            
        Returns:
            Tuple of (success, job_id, error_message)
        """
        try:
            # Prepare handler options
            handler_options = {
                'PAYLOAD': payload_name,
                'LHOST': lhost,
                'LPORT': lport,
                'ExitOnSession': exit_on_session
            }
            
            # Execute multi/handler
            result = self.handlers.module.execute('exploit', 'multi/handler', handler_options)
            
            if result and 'job_id' in result:
                job_id = str(result['job_id'])
                return True, job_id, ""
            else:
                error_msg = result.get('error', 'Failed to start handler')
                return False, "", error_msg
                
        except Exception as e:
            return False, "", f"Handler creation failed: {str(e)}"
    
    def list_sessions(self) -> Dict[str, Any]:
        """
        List all active sessions
        
        Returns:
            Dictionary of active sessions
        """
        try:
            return self.handlers.session.list()
        except Exception as e:
            raise RpcMethodError(f"Failed to list sessions: {str(e)}")
    
    def get_server_ip(self) -> str:
        """
        Get the server's IP address for use as LHOST
        
        Returns:
            IP address string
        """
        import socket
        try:
            # Connect to a remote address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"  # Fallback to localhost