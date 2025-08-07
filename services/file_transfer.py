import socket
from pathlib import Path
from werkzeug.utils import secure_filename

class FileTransferService:
    """Handles file transfer operations"""

    @staticmethod
    def send_file(conn: socket.socket, filename: str, config, logger) -> bool:
        """Send file to agent"""
        from utils import strip_filename_quotes
        
        try:
            # Strip quotes from filename and log the processing
            original_filename = filename
            filename = strip_filename_quotes(filename)
            logger.log_message(f"File Transfer: Processing filename - Original: '{original_filename}' -> Clean: '{filename}'")
            
            # Use safe_filename_path instead of secure_filename to preserve spaces
            try:
                from utils import safe_filename_path
                filepath = safe_filename_path(Path(config.FILES_FOLDER), filename)
            except ValueError as e:
                conn.send(f'ERROR|Invalid filename: {str(e)}'.encode('utf-8'))
                logger.log_message(f"File Transfer Failed: Invalid filename '{filename}' - {e}")
                return False
                
            logger.log_message(f"File Transfer: Looking for file at {filepath}")
            
            if not filepath.exists():
                conn.send(b'ERROR|File not found')
                logger.log_message(f"File Transfer Failed: {filename} - File not found at {filepath}")
                return False
                
            try:
                filesize = filepath.stat().st_size
                logger.log_message(f"File Transfer Started: {filename} ({filesize/1024:.1f} KB)")
                
                # Set socket options for larger transfers
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)  # 1MB buffer
                
                # Send file in chunks
                CHUNK_SIZE = 1048576  # 1MB chunks
                bytes_sent = 0
                
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                            
                        bytes_sent += conn.send(chunk)
                        if bytes_sent >= 1048576:  # Log every MB
                            logger.log_message(f"File Transfer Progress: {filename} - {bytes_sent//1048576}MB sent")
                    
                logger.log_message(f"File Transfer Complete: {filename} ({bytes_sent/1024:.1f} KB)")
                return True
                
            except Exception as e:
                conn.send(f"ERROR|Could not read file: {str(e)}".encode('utf-8'))
                logger.log_message(f"Error reading file {filename}: {e}")
                return False
            
        except Exception as e:
            logger.log_message(f"Error sending file: {e}")
            return False

    @staticmethod
    def receive_file(conn: socket.socket, filename: str, config, logger) -> bool:
        """Receive file from agent"""
        from utils import strip_filename_quotes
        
        try:
            # Strip quotes from filename and log the processing
            original_filename = filename
            filename = strip_filename_quotes(filename)
            logger.log_message(f"File Receive: Processing filename - Original: '{original_filename}' -> Clean: '{filename}'")
            
            # Use safe_filename_path instead of secure_filename to preserve spaces
            try:
                from utils import safe_filename_path
                filepath = safe_filename_path(Path(config.FILES_FOLDER), filename)
            except ValueError as e:
                logger.log_message(f"File Receive Failed: Invalid filename '{filename}' - {e}")
                try:
                    conn.send(f'ERROR|Invalid filename: {str(e)}'.encode('utf-8'))
                except:
                    pass
                return False
            
            # Set socket options for larger transfers
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  # 1MB buffer
            
            with open(filepath, 'wb') as f:
                total_received = 0
                while True:
                    try:
                        chunk = conn.recv(1048576)  # 1MB chunks
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        total_received += len(chunk)
                        
                        if total_received >= 1048576:  # Log every MB
                            logger.log_message(f"Received {total_received//1048576}MB")
                            
                    except socket.timeout:
                        if total_received > 0:
                            break
                        raise
            
            if total_received > 0:
                logger.log_message(f"File {filename} received and saved ({total_received} bytes)")
                conn.send(b'SUCCESS')
                return True
            else:
                logger.log_message("No data received")
                conn.send(b'ERROR|No data received')
                return False
                
        except Exception as e:
            logger.log_message(f"Error receiving file: {e}")
            try:
                conn.send(f"ERROR|{str(e)}".encode('utf-8'))
            except:
                pass
            return False