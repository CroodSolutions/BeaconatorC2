#!/usr/bin/env python3
"""
Output Parser System for BeaconatorC2

Provides a modular system for parsing command outputs and extracting
structured metadata from beacons.
"""

from typing import Dict, List, Tuple, Optional
import re


class OutputParser:
    """Base class for command output parsers"""

    def __init__(self, command_pattern: str, description: str = ""):
        self.command_pattern = command_pattern
        self.description = description

    def matches_command(self, command: str) -> bool:
        """Check if this parser handles the given command"""
        return bool(re.match(self.command_pattern, command, re.IGNORECASE))

    def parse(self, command: str, output: str) -> List[Tuple[str, str]]:
        """
        Parse command output and return list of (key, value) tuples
        Override this in subclasses
        """
        raise NotImplementedError


class WhoamiParser(OutputParser):
    """Parser for whoami command output"""

    def __init__(self):
        super().__init__(
            command_pattern=r'^whoami$',
            description="Parse username from whoami output"
        )

    def parse(self, command: str, output: str) -> List[Tuple[str, str]]:
        # Clean output
        username = output.strip()

        # Remove common error prefixes
        if 'STDOUT:' in username:
            username = username.split('STDOUT:')[-1].strip()

        # Handle different formats: "DOMAIN\user" or just "user"
        if '\\' in username:
            domain, user = username.split('\\', 1)
            return [
                ('username', user),
                ('domain', domain),
                ('full_username', username)
            ]
        else:
            return [('username', username)]


class HostnameParser(OutputParser):
    """Parser for hostname command"""

    def __init__(self):
        super().__init__(
            command_pattern=r'^hostname$',
            description="Parse hostname"
        )

    def parse(self, command: str, output: str) -> List[Tuple[str, str]]:
        hostname = output.strip()

        # Remove common output prefixes
        if 'STDOUT:' in hostname:
            hostname = hostname.split('STDOUT:')[-1].strip()

        if hostname:
            return [('hostname', hostname)]
        return []


class IpconfigParser(OutputParser):
    """Parser for ipconfig/ifconfig output"""

    def __init__(self):
        super().__init__(
            command_pattern=r'^(ipconfig|ifconfig).*',
            description="Parse IP configuration"
        )

    def parse(self, command: str, output: str) -> List[Tuple[str, str]]:
        metadata = []

        # Parse IPv4 addresses
        ipv4_pattern = r'IPv4.*?:\s*(\d+\.\d+\.\d+\.\d+)'
        for match in re.finditer(ipv4_pattern, output):
            ip = match.group(1)
            if not ip.startswith('127.'):  # Skip localhost
                metadata.append(('ipv4_address', ip))

        # Parse MAC addresses (Windows format)
        mac_pattern = r'Physical Address.*?:\s*([0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2})'
        for match in re.finditer(mac_pattern, output):
            metadata.append(('mac_address', match.group(1)))

        # Parse MAC addresses (Linux format)
        if 'ifconfig' in command or 'ip addr' in command:
            mac_pattern_linux = r'(?:ether|HWaddr)\s+([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})'
            for match in re.finditer(mac_pattern_linux, output):
                metadata.append(('mac_address', match.group(1)))

            # Parse inet addresses (Linux)
            inet_pattern = r'inet\s+(\d+\.\d+\.\d+\.\d+)'
            for match in re.finditer(inet_pattern, output):
                ip = match.group(1)
                if not ip.startswith('127.'):
                    metadata.append(('ipv4_address', ip))

        return metadata


class SysteminfoParser(OutputParser):
    """Parser for systeminfo command (Windows)"""

    def __init__(self):
        super().__init__(
            command_pattern=r'^systeminfo$',
            description="Parse Windows system information"
        )

    def parse(self, command: str, output: str) -> List[Tuple[str, str]]:
        metadata = []

        # Parse OS Name
        os_match = re.search(r'OS Name:\s*(.+)', output)
        if os_match:
            metadata.append(('os_name', os_match.group(1).strip()))

        # Parse OS Version
        version_match = re.search(r'OS Version:\s*(.+)', output)
        if version_match:
            metadata.append(('os_version', version_match.group(1).strip()))

        # Parse System Type
        type_match = re.search(r'System Type:\s*(.+)', output)
        if type_match:
            metadata.append(('system_type', type_match.group(1).strip()))

        # Parse Domain
        domain_match = re.search(r'Domain:\s*(.+)', output)
        if domain_match:
            domain = domain_match.group(1).strip()
            if domain.lower() != 'workgroup':
                metadata.append(('domain', domain))

        # Parse System Manufacturer
        manufacturer_match = re.search(r'System Manufacturer:\s*(.+)', output)
        if manufacturer_match:
            metadata.append(('system_manufacturer', manufacturer_match.group(1).strip()))

        # Parse System Model
        model_match = re.search(r'System Model:\s*(.+)', output)
        if model_match:
            metadata.append(('system_model', model_match.group(1).strip()))

        return metadata


class UnameParser(OutputParser):
    """Parser for uname command (Linux/Unix)"""

    def __init__(self):
        super().__init__(
            command_pattern=r'^uname\s*-a$',
            description="Parse Unix system information"
        )

    def parse(self, command: str, output: str) -> List[Tuple[str, str]]:
        metadata = []

        # Clean output
        output = output.strip()
        if 'STDOUT:' in output:
            output = output.split('STDOUT:')[-1].strip()

        # uname -a format: Linux hostname 5.4.0-42-generic #46-Ubuntu SMP x86_64 GNU/Linux
        parts = output.split()

        if len(parts) >= 3:
            metadata.append(('os_name', parts[0]))
            metadata.append(('hostname', parts[1]))
            metadata.append(('kernel_version', parts[2]))

        if len(parts) >= 12:
            # Try to extract architecture
            for part in parts:
                if 'x86_64' in part or 'i686' in part or 'aarch64' in part or 'arm' in part:
                    metadata.append(('architecture', part))
                    break

        return metadata


class IdParser(OutputParser):
    """Parser for id command (Linux/Unix)"""

    def __init__(self):
        super().__init__(
            command_pattern=r'^id$',
            description="Parse user ID information"
        )

    def parse(self, command: str, output: str) -> List[Tuple[str, str]]:
        metadata = []

        # Clean output
        output = output.strip()
        if 'STDOUT:' in output:
            output = output.split('STDOUT:')[-1].strip()

        # Parse uid
        uid_match = re.search(r'uid=(\d+)\(([^)]+)\)', output)
        if uid_match:
            metadata.append(('uid', uid_match.group(1)))
            metadata.append(('username', uid_match.group(2)))

        # Parse gid
        gid_match = re.search(r'gid=(\d+)\(([^)]+)\)', output)
        if gid_match:
            metadata.append(('gid', gid_match.group(1)))
            metadata.append(('primary_group', gid_match.group(2)))

        # Check for root/admin privileges
        if uid_match and uid_match.group(1) == '0':
            metadata.append(('is_root', 'true'))
        else:
            metadata.append(('is_root', 'false'))

        return metadata


class PwdParser(OutputParser):
    """Parser for pwd command (current directory)"""

    def __init__(self):
        super().__init__(
            command_pattern=r'^pwd$',
            description="Parse current working directory"
        )

    def parse(self, command: str, output: str) -> List[Tuple[str, str]]:
        # Clean output
        path = output.strip()
        if 'STDOUT:' in path:
            path = path.split('STDOUT:')[-1].strip()

        if path:
            return [('current_directory', path)]
        return []


class NetUserParser(OutputParser):
    """Parser for 'net user' command (Windows)"""

    def __init__(self):
        super().__init__(
            command_pattern=r'^net\s+user\s+\S+',
            description="Parse Windows user account details"
        )

    def parse(self, command: str, output: str) -> List[Tuple[str, str]]:
        metadata = []

        # Parse username
        user_match = re.search(r'User name\s+(.+)', output)
        if user_match:
            metadata.append(('username', user_match.group(1).strip()))

        # Parse full name
        fullname_match = re.search(r'Full Name\s+(.+)', output)
        if fullname_match:
            fullname = fullname_match.group(1).strip()
            if fullname:
                metadata.append(('full_name', fullname))

        # Parse account active status
        active_match = re.search(r'Account active\s+(.+)', output)
        if active_match:
            metadata.append(('account_active', active_match.group(1).strip()))

        # Parse local group memberships
        groups_match = re.search(r'Local Group Memberships\s+(.+)', output)
        if groups_match:
            groups = groups_match.group(1).strip()
            if 'Administrators' in groups or '*Administrators' in groups:
                metadata.append(('is_admin', 'true'))
            else:
                metadata.append(('is_admin', 'false'))

        return metadata


class OutputParserRegistry:
    """Registry for managing output parsers"""

    def __init__(self):
        self.parsers: List[OutputParser] = []
        self._register_default_parsers()

    def _register_default_parsers(self):
        """Register built-in parsers"""
        self.register(WhoamiParser())
        self.register(HostnameParser())
        self.register(IpconfigParser())
        self.register(SysteminfoParser())
        self.register(UnameParser())
        self.register(IdParser())
        self.register(PwdParser())
        self.register(NetUserParser())

    def register(self, parser: OutputParser):
        """Register a new parser"""
        self.parsers.append(parser)

    def get_parser(self, command: str) -> Optional[OutputParser]:
        """Find a parser that matches the given command"""
        for parser in self.parsers:
            if parser.matches_command(command):
                return parser
        return None

    def parse_output(self, command: str, output: str) -> List[Tuple[str, str]]:
        """Parse command output and return extracted metadata"""
        parser = self.get_parser(command)
        if parser:
            try:
                return parser.parse(command, output)
            except Exception as e:
                print(f"Parser error for command '{command}': {e}")
                return []
        return []

    def get_all_parsers(self) -> List[OutputParser]:
        """Get list of all registered parsers"""
        return self.parsers.copy()
