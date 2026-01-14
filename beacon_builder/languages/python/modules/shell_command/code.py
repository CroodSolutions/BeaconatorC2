    # Shell Command module - Execute system commands

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
