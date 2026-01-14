    # Network Information module - Gather network configuration

    def network_info(self):
        """Gather network configuration information"""
        try:
            info_lines = []
            info_lines.append("=== Network Information ===")

            # Get hostname and basic network info
            info_lines.append(f"Hostname: {socket.gethostname()}")

            # Try to get local IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                info_lines.append(f"Local IP: {local_ip}")
            except:
                info_lines.append("Local IP: Unable to determine")

            # Get all IPs associated with hostname
            try:
                hostname = socket.gethostname()
                ips = socket.gethostbyname_ex(hostname)
                info_lines.append(f"All IPs: {', '.join(ips[2])}")
            except:
                pass

            # Platform-specific network commands
            if platform.system() == "Windows":
                commands = [
                    ("ipconfig /all", "Windows IP Configuration"),
                    ("arp -a", "ARP Table"),
                    ("netstat -an", "Network Connections"),
                    ("route print", "Routing Table")
                ]
            else:
                commands = [
                    ("ip addr show 2>/dev/null || ifconfig", "IP Configuration"),
                    ("arp -a 2>/dev/null || ip neigh show", "ARP Table"),
                    ("netstat -an 2>/dev/null || ss -an", "Network Connections"),
                    ("route -n 2>/dev/null || ip route show", "Routing Table")
                ]

            for cmd, description in commands:
                try:
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.stdout:
                        info_lines.append(f"\n=== {description} ===")
                        info_lines.append(result.stdout.strip())
                except Exception as e:
                    info_lines.append(f"\n=== {description} ===")
                    info_lines.append(f"ERROR: {e}")

            return "\n".join(info_lines)

        except Exception as e:
            return f"ERROR gathering network info: {e}"
