import socket
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, Optional
from pathlib import Path
from werkzeug.utils import secure_filename
from .base_receiver import BaseReceiver, ReceiverStatus
from .encoding_strategies import EncodingStrategy
from .receiver_config import ReceiverConfig
import utils
from config import ServerConfig

class HTTPConnectionHandler:
    """Handles HTTP connections using BaseReceiver functionality"""
    
    def __init__(self, receiver_instance):
        self.receiver_instance = receiver_instance
        
    def handle_request(self, request_handler):
        """Handle an HTTP request using BaseReceiver functionality"""
        
        try:
            # Extract request data based on method
            if request_handler.command == 'POST':
                # Get content length
                content_length = int(request_handler.headers.get('Content-Length', 0))
                if content_length > 0:
                    # Read POST data
                    request_data = request_handler.rfile.read(content_length)
                else:
                    request_data = b""
            elif request_handler.command == 'GET':
                # Parse query parameters for GET requests
                parsed_path = urlparse(request_handler.path)
                query_params = parse_qs(parsed_path.query)
                
                # Look for 'data' parameter in query string
                if 'data' in query_params:
                    request_data = query_params['data'][0].encode('utf-8')
                else:
                    request_data = b""
            else:
                # Unsupported method
                request_handler.send_response(405)
                request_handler.send_header('Content-type', 'text/plain')
                request_handler.end_headers()
                request_handler.wfile.write(b'Method Not Allowed')
                return
            
            if not request_data:
                # No data provided
                request_handler.send_response(400)
                request_handler.send_header('Content-type', 'text/plain')
                request_handler.end_headers()
                request_handler.wfile.write(b'Bad Request: No data provided')
                return
            
            # Use unified data processing
            client_info = {
                "address": request_handler.client_address, 
                "transport": "http",
                "method": request_handler.command,
                "path": request_handler.path,
                "user_agent": request_handler.headers.get('User-Agent', 'Unknown')
            }
            
            response_bytes, keep_alive = self.receiver_instance.process_received_data(request_data, client_info)
            
            # Handle file transfer case
            if response_bytes == b"FILE_TRANSFER_REQUIRED":
                initial_data_decoded = self.receiver_instance.encoding_strategy.decode(request_data)
                initial_data = initial_data_decoded.decode('utf-8').strip()
                parts = initial_data.split('|')
                command = parts[0] if parts else ""
                self.receiver_instance.handle_file_transfer_http(request_handler, command, parts, client_info)
                return
            
            # Send successful HTTP response
            request_handler.send_response(200)
            request_handler.send_header('Content-type', 'application/octet-stream')
            request_handler.send_header('Content-Length', str(len(response_bytes)))
            if keep_alive:
                request_handler.send_header('Connection', 'keep-alive')
            else:
                request_handler.send_header('Connection', 'close')
            request_handler.end_headers()
            
            # Send response body
            request_handler.wfile.write(response_bytes)
            self.receiver_instance.update_bytes_sent(len(response_bytes))
            
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"HTTP Connection Error: {request_handler.client_address} - {str(e)}")
            
            # Send error response
            try:
                request_handler.send_response(500)
                request_handler.send_header('Content-type', 'text/plain')
                request_handler.end_headers()
                request_handler.wfile.write(b'Internal Server Error')
            except:
                pass

class HTTPReceiver(BaseReceiver):
    """HTTP receiver implementation with encoding support"""
    
    def __init__(self, config: ReceiverConfig, encoding_strategy: EncodingStrategy):
        super().__init__(config.receiver_id, config.name, encoding_strategy)
        self.config = config
        self.server: Optional[HTTPServer] = None
        self.connection_handler: Optional[HTTPConnectionHandler] = None
        
        # HTTP-specific configuration
        self.endpoint_path = config.protocol_config.get('endpoint_path', '/')
        
    def _setup_receiver(self) -> bool:
        """Setup HTTP server"""
        try:
            # Create HTTP connection handler
            self.connection_handler = HTTPConnectionHandler(self)
            
            # Define custom HTTP request handler
            class CustomHTTPRequestHandler(BaseHTTPRequestHandler):
                def __init__(self, request, client_address, server, receiver_instance):
                    self.receiver_instance = receiver_instance
                    # Suppress default logging by overriding log_message
                    super().__init__(request, client_address, server)
                    
                def log_message(self, format, *args):
                    # Suppress default HTTP server logging
                    pass
                    
                def do_GET(self):
                    """Handle GET requests"""
                    self._handle_request()
                    
                def do_POST(self):
                    """Handle POST requests"""
                    self._handle_request()
                    
                def _handle_request(self):
                    """Handle both GET and POST requests"""
                    # Check if path matches endpoint
                    parsed_path = urlparse(self.path)
                    if parsed_path.path != self.receiver_instance.endpoint_path:
                        self.send_response(404)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b'Not Found')
                        return
                    
                    # Update connection stats
                    self.receiver_instance.increment_active_connections()
                    
                    try:
                        # Handle the request
                        self.receiver_instance.connection_handler.handle_request(self)
                    finally:
                        self.receiver_instance.decrement_active_connections()
            
            # Create server with custom handler
            def handler_factory(request, client_address, server):
                return CustomHTTPRequestHandler(request, client_address, server, self)
                
            self.server = HTTPServer(
                (self.config.host, self.config.port),
                handler_factory
            )
            
            # Set server timeout to allow periodic shutdown checks
            self.server.timeout = 1.0
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(self.receiver_id, f"HTTP setup failed: {str(e)}")
            return False
            
    def _start_listening(self):
        """Start listening for HTTP connections"""
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
                self.error_occurred.emit(self.receiver_id, f"HTTP listening error: {str(e)}")
                
    def _cleanup_receiver(self):
        """Cleanup HTTP server"""
        if self.server:
            try:
                # Graceful shutdown
                shutdown_thread = threading.Thread(target=self.server.shutdown)
                shutdown_thread.daemon = True
                shutdown_thread.start()
                
                # Wait for shutdown to complete
                shutdown_thread.join(timeout=2.0)
                
                if shutdown_thread.is_alive():
                    # Force close if shutdown takes too long
                    try:
                        self.server.server_close()
                    except Exception:
                        pass
                else:
                    # Normal cleanup
                    self.server.server_close()
                    
            except Exception:
                # Ensure server is closed even if shutdown fails
                try:
                    self.server.server_close()
                except Exception:
                    pass
            finally:
                self.server = None
    
    def _send_data(self, sock: socket.socket, data: bytes) -> bool:
        """Send data through HTTP (not applicable for HTTP receiver pattern)"""
        # This method is required by the abstract base class but not used in HTTP receiver
        # HTTP responses are sent via the request handler's wfile
        return False
    
    def _receive_data(self, sock: socket.socket, buffer_size: int) -> bytes:
        """Receive data through HTTP (not applicable for HTTP receiver pattern)"""
        # This method is required by the abstract base class but not used in HTTP receiver
        # HTTP data is received via the request handler's rfile
        return b""
    
    def handle_file_transfer_http(self, request_handler, command: str, parts: list, client_info: Dict[str, Any]):
        """Handle HTTP file transfer"""
        if len(parts) < 2:
            request_handler.send_response(400)
            request_handler.send_header('Content-type', 'text/plain')
            request_handler.end_headers()
            request_handler.wfile.write(b'ERROR: Invalid file transfer command')
            return
            
        filename = parts[1]
        
        if command == "to_beacon":
            # Send file via HTTP
            self._send_file_http(request_handler, filename)
        else:  # from_beacon
            # Receive file via HTTP
            if request_handler.command == 'POST':
                self._receive_file_http(request_handler, filename)
            else:
                request_handler.send_response(405)
                request_handler.send_header('Content-type', 'text/plain')
                request_handler.end_headers()
                request_handler.wfile.write(b'ERROR: File upload requires POST method')
    
    def _send_file_http(self, request_handler, filename: str):
        """Send file via HTTP response"""
        try:
            config = ServerConfig()
            filepath = Path(config.FILES_FOLDER) / secure_filename(filename)
            if not filepath.exists():
                request_handler.send_response(404)
                request_handler.send_header('Content-type', 'text/plain')
                request_handler.end_headers()
                request_handler.wfile.write(b'ERROR: File not found')
                return
            
            # Send file as HTTP response
            file_size = filepath.stat().st_size
            request_handler.send_response(200)
            request_handler.send_header('Content-type', 'application/octet-stream')
            request_handler.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            request_handler.send_header('Content-Length', str(file_size))
            request_handler.end_headers()
            
            # Send file data in chunks
            CHUNK_SIZE = 8192
            bytes_sent = 0
            
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                        
                    # Encode the chunk
                    encoded_chunk = self.encoding_strategy.encode(chunk)
                    request_handler.wfile.write(encoded_chunk)
                    bytes_sent += len(encoded_chunk)
                    self.update_bytes_sent(len(encoded_chunk))
                    
            if utils.logger:
                utils.logger.log_message(f"HTTP file transfer complete: {filename} ({bytes_sent} bytes)")
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in HTTP file send: {e}")
            try:
                request_handler.send_response(500)
                request_handler.send_header('Content-type', 'text/plain')
                request_handler.end_headers()
                request_handler.wfile.write(b'Internal Server Error')
            except:
                pass
    
    def _receive_file_http(self, request_handler, filename: str):
        """Receive file via HTTP POST"""
        try:
            config = ServerConfig()
            filepath = Path(config.FILES_FOLDER) / secure_filename(filename)
            
            # Get content length
            content_length = int(request_handler.headers.get('Content-Length', 0))
            if content_length == 0:
                request_handler.send_response(400)
                request_handler.send_header('Content-type', 'text/plain')
                request_handler.end_headers()
                request_handler.wfile.write(b'ERROR: No file data provided')
                return
            
            # Receive file data
            with open(filepath, 'wb') as f:
                total_received = 0
                remaining = content_length
                
                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    encoded_chunk = request_handler.rfile.read(chunk_size)
                    if not encoded_chunk:
                        break
                        
                    # Decode the chunk
                    chunk = self.encoding_strategy.decode(encoded_chunk)
                    f.write(chunk)
                    
                    total_received += len(encoded_chunk)
                    remaining -= len(encoded_chunk)
                    self.update_bytes_received(len(encoded_chunk))
                        
            # Send success response
            request_handler.send_response(200)
            request_handler.send_header('Content-type', 'text/plain')
            request_handler.end_headers()
            request_handler.wfile.write(b'SUCCESS')
            
            if utils.logger:
                utils.logger.log_message(f"HTTP file received: {filename} ({total_received} bytes)")
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in HTTP file receive: {e}")
            try:
                request_handler.send_response(500)
                request_handler.send_header('Content-type', 'text/plain')
                request_handler.end_headers()
                request_handler.wfile.write(b'ERROR: File upload failed')
            except:
                pass
                
    def get_configuration(self) -> Dict[str, Any]:
        """Get HTTP receiver configuration"""
        return {
            "host": self.config.host,
            "port": self.config.port,
            "endpoint_path": self.endpoint_path,
            "buffer_size": self.config.buffer_size,
            "timeout": self.config.timeout,
            "encoding": self.encoding_strategy.get_name()
        }
        
    def update_configuration(self, config_updates: Dict[str, Any]) -> bool:
        """Update HTTP receiver configuration"""
        try:
            if "port" in config_updates:
                new_port = int(config_updates["port"])
                if 1 <= new_port <= 65535:
                    self.config.port = new_port
                else:
                    return False
                    
            if "host" in config_updates:
                self.config.host = config_updates["host"]
                
            if "endpoint_path" in config_updates:
                self.endpoint_path = config_updates["endpoint_path"]
                
            if "buffer_size" in config_updates:
                self.config.buffer_size = int(config_updates["buffer_size"])
                
            # Restart if running to apply changes
            if self.status == ReceiverStatus.RUNNING:
                return self.restart()
                
            return True
            
        except Exception:
            return False