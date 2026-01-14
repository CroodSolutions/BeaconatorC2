    # System Information module - Gather basic system info

    def system_info(self):
        """Gather basic system information"""
        try:
            info_lines = []
            info_lines.append("=== System Information ===")
            info_lines.append(f"Hostname: {platform.node()}")
            info_lines.append(f"OS: {platform.system()} {platform.release()}")
            info_lines.append(f"OS Version: {platform.version()}")
            info_lines.append(f"Architecture: {platform.machine()}")
            info_lines.append(f"Processor: {platform.processor()}")
            info_lines.append(f"Python Version: {platform.python_version()}")

            # Get username
            try:
                username = os.getlogin()
            except:
                username = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
            info_lines.append(f"Username: {username}")

            # Get current working directory
            info_lines.append(f"Working Directory: {os.getcwd()}")

            # Get home directory
            info_lines.append(f"Home Directory: {Path.home()}")

            # Platform-specific info
            if platform.system() == "Windows":
                try:
                    result = subprocess.run(
                        "systeminfo",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.stdout:
                        info_lines.append("\n=== Windows SystemInfo ===")
                        info_lines.append(result.stdout)
                except:
                    pass
            else:
                try:
                    result = subprocess.run(
                        "uname -a",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.stdout:
                        info_lines.append(f"\nUname: {result.stdout.strip()}")
                except:
                    pass

            return "\n".join(info_lines)

        except Exception as e:
            return f"ERROR gathering system info: {e}"
