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


# ============================================================================
# CONTENT-BASED PARSERS (for BOF output and unknown command formats)
# ============================================================================

class ContentBasedParser:
    """
    Base class for content-based parsers that analyze output content
    regardless of what command produced it. Used as fallback when
    command-pattern matching fails (e.g., BOF outputs).
    """

    def __init__(self, description: str = ""):
        self.description = description

    def detect(self, output: str) -> bool:
        """Check if this parser can extract data from the output"""
        raise NotImplementedError

    def parse(self, output: str) -> List[Tuple[str, str]]:
        """Extract metadata from output"""
        raise NotImplementedError


class NetworkInfoContentParser(ContentBasedParser):
    """
    Content-based parser for network information.
    Detects and extracts IP addresses, MAC addresses, subnet masks, etc.
    from any output regardless of command.
    """

    def __init__(self):
        super().__init__(description="Extract network information from output content")

        # Patterns that indicate network configuration output
        self.detection_patterns = [
            r'IPv4\s*Address',
            r'IP\s*Address',
            r'inet\s+\d+\.\d+\.\d+\.\d+',
            r'Subnet\s*Mask',
            r'Default\s*Gateway',
            r'Physical\s*Address',
            r'Ethernet\s*adapter',
            r'Wireless.*adapter',
        ]

        # Extraction patterns
        self.ipv4_patterns = [
            r'IPv4[^:]*:\s*(\d+\.\d+\.\d+\.\d+)',           # Windows ipconfig
            r'IP\s*Address[^:]*:\s*(\d+\.\d+\.\d+\.\d+)',   # Generic
            r'inet\s+(\d+\.\d+\.\d+\.\d+)',                  # Linux ifconfig/ip
            r'Address:\s*(\d+\.\d+\.\d+\.\d+)',              # Various formats
        ]

        self.mac_patterns = [
            r'Physical\s*Address[^:]*:\s*([0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2})',
            r'(?:ether|HWaddr)\s+([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})',
        ]

        self.gateway_patterns = [
            r'Default\s*Gateway[^:]*:\s*(\d+\.\d+\.\d+\.\d+)',
            r'gateway[:\s]+(\d+\.\d+\.\d+\.\d+)',
        ]

        self.subnet_patterns = [
            r'Subnet\s*Mask[^:]*:\s*(\d+\.\d+\.\d+\.\d+)',
            r'netmask\s+(\d+\.\d+\.\d+\.\d+)',
        ]

        self.dns_patterns = [
            r'DNS\s*Servers?[^:]*:\s*(\d+\.\d+\.\d+\.\d+)',
        ]

    def detect(self, output: str) -> bool:
        """Check if output contains network configuration data"""
        for pattern in self.detection_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return True
        return False

    def parse(self, output: str) -> List[Tuple[str, str]]:
        metadata = []
        seen_values = set()  # Avoid duplicates

        # Extract IPv4 addresses
        for pattern in self.ipv4_patterns:
            for match in re.finditer(pattern, output, re.IGNORECASE):
                ip = match.group(1)
                # Skip localhost and link-local
                if not ip.startswith('127.') and not ip.startswith('169.254.'):
                    if ip not in seen_values:
                        seen_values.add(ip)
                        metadata.append(('ipv4_address', ip))

        # Extract MAC addresses
        for pattern in self.mac_patterns:
            for match in re.finditer(pattern, output, re.IGNORECASE):
                mac = match.group(1)
                if mac not in seen_values:
                    seen_values.add(mac)
                    metadata.append(('mac_address', mac))

        # Extract default gateway
        for pattern in self.gateway_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                gateway = match.group(1)
                if gateway not in seen_values:
                    seen_values.add(gateway)
                    metadata.append(('default_gateway', gateway))
                break

        # Extract subnet mask
        for pattern in self.subnet_patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                subnet = match.group(1)
                if subnet not in seen_values:
                    seen_values.add(subnet)
                    metadata.append(('subnet_mask', subnet))
                break

        # Extract DNS servers
        for pattern in self.dns_patterns:
            for match in re.finditer(pattern, output, re.IGNORECASE):
                dns = match.group(1)
                if dns not in seen_values:
                    seen_values.add(dns)
                    metadata.append(('dns_server', dns))

        return metadata


class UserInfoContentParser(ContentBasedParser):
    """
    Content-based parser for user/identity information.
    Extracts usernames, domains, SIDs, privileges, etc.
    """

    def __init__(self):
        super().__init__(description="Extract user identity information from output content")

        self.detection_patterns = [
            r'UserName\s+SID',           # whoami BOF output header
            r'DOMAIN\\',                  # Domain\User format
            r'S-1-5-\d+-',               # Windows SID
            r'uid=\d+',                   # Linux uid
            r'User\s*Name\s*:',          # net user output
            r'Privilege\s*Name',         # Windows privileges
        ]

    def detect(self, output: str) -> bool:
        for pattern in self.detection_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return True
        return False

    def parse(self, output: str) -> List[Tuple[str, str]]:
        metadata = []

        # Windows DOMAIN\username format (common in whoami BOF output)
        domain_user_match = re.search(r'([A-Za-z0-9_-]+)\\([A-Za-z0-9_.-]+)', output)
        if domain_user_match:
            domain = domain_user_match.group(1)
            username = domain_user_match.group(2)
            # Avoid matching things like file paths
            if domain.upper() not in ['C', 'D', 'E', 'SYSTEM32', 'WINDOWS']:
                metadata.append(('domain', domain))
                metadata.append(('username', username))
                metadata.append(('full_username', f"{domain}\\{username}"))

        # Windows SID
        sid_match = re.search(r'(S-1-5-\d+(?:-\d+)+)', output)
        if sid_match:
            metadata.append(('user_sid', sid_match.group(1)))

        # Linux uid/gid
        uid_match = re.search(r'uid=(\d+)\(([^)]+)\)', output)
        if uid_match:
            metadata.append(('uid', uid_match.group(1)))
            if not any(k == 'username' for k, v in metadata):
                metadata.append(('username', uid_match.group(2)))

        gid_match = re.search(r'gid=(\d+)\(([^)]+)\)', output)
        if gid_match:
            metadata.append(('gid', gid_match.group(1)))
            metadata.append(('primary_group', gid_match.group(2)))

        # Check for admin/root indicators
        if re.search(r'\bAdministrators?\b', output, re.IGNORECASE):
            metadata.append(('is_admin', 'true'))
        if uid_match and uid_match.group(1) == '0':
            metadata.append(('is_root', 'true'))

        # Extract privileges (Windows)
        priv_matches = re.findall(r'(Se\w+Privilege)', output)
        if priv_matches:
            # Store notable privileges
            notable_privs = ['SeDebugPrivilege', 'SeImpersonatePrivilege',
                           'SeBackupPrivilege', 'SeRestorePrivilege',
                           'SeTakeOwnershipPrivilege', 'SeLoadDriverPrivilege']
            for priv in priv_matches:
                if priv in notable_privs:
                    metadata.append(('privilege', priv))

        return metadata


class SystemInfoContentParser(ContentBasedParser):
    """
    Content-based parser for system information.
    Extracts OS details, architecture, hostname, etc.
    """

    def __init__(self):
        super().__init__(description="Extract system information from output content")

        self.detection_patterns = [
            r'OS\s*Name\s*:',
            r'OS\s*Version\s*:',
            r'System\s*Type\s*:',
            r'Computer\s*Name\s*:',
            r'Host\s*Name\s*:',
            r'Windows\s+\d+',
            r'Microsoft\s+Windows',
        ]

    def detect(self, output: str) -> bool:
        for pattern in self.detection_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                return True
        return False

    def parse(self, output: str) -> List[Tuple[str, str]]:
        metadata = []

        # OS Name
        os_match = re.search(r'OS\s*Name\s*:\s*(.+?)(?:\r?\n|$)', output, re.IGNORECASE)
        if os_match:
            metadata.append(('os_name', os_match.group(1).strip()))

        # OS Version
        ver_match = re.search(r'OS\s*Version\s*:\s*(.+?)(?:\r?\n|$)', output, re.IGNORECASE)
        if ver_match:
            metadata.append(('os_version', ver_match.group(1).strip()))

        # System Type (architecture)
        type_match = re.search(r'System\s*Type\s*:\s*(.+?)(?:\r?\n|$)', output, re.IGNORECASE)
        if type_match:
            metadata.append(('system_type', type_match.group(1).strip()))

        # Computer/Host Name
        host_match = re.search(r'(?:Computer|Host)\s*Name\s*:\s*(.+?)(?:\r?\n|$)', output, re.IGNORECASE)
        if host_match:
            metadata.append(('hostname', host_match.group(1).strip()))

        # Domain
        domain_match = re.search(r'Domain\s*:\s*(.+?)(?:\r?\n|$)', output, re.IGNORECASE)
        if domain_match:
            domain = domain_match.group(1).strip()
            if domain.lower() != 'workgroup':
                metadata.append(('domain', domain))

        return metadata


class OutputParserRegistry:
    """Registry for managing output parsers"""

    def __init__(self):
        self.parsers: List[OutputParser] = []
        self.content_parsers: List[ContentBasedParser] = []
        self._register_default_parsers()
        self._register_content_parsers()

    def _register_default_parsers(self):
        """Register built-in command-based parsers"""
        self.register(WhoamiParser())
        self.register(HostnameParser())
        self.register(IpconfigParser())
        self.register(SysteminfoParser())
        self.register(UnameParser())
        self.register(IdParser())
        self.register(PwdParser())
        self.register(NetUserParser())

    def _register_content_parsers(self):
        """Register content-based parsers for fallback detection"""
        self.content_parsers.append(NetworkInfoContentParser())
        self.content_parsers.append(UserInfoContentParser())
        self.content_parsers.append(SystemInfoContentParser())

    def register(self, parser: OutputParser):
        """Register a new command-based parser"""
        self.parsers.append(parser)

    def register_content_parser(self, parser: ContentBasedParser):
        """Register a new content-based parser"""
        self.content_parsers.append(parser)

    def get_parser(self, command: str) -> Optional[OutputParser]:
        """Find a parser that matches the given command"""
        for parser in self.parsers:
            if parser.matches_command(command):
                return parser
        return None

    def parse_output(self, command: str, output: str) -> List[Tuple[str, str]]:
        """
        Parse command output and return extracted metadata.

        Strategy:
        1. Try command-based parsing first (if command matches a known pattern)
        2. If no command parser matches OR if it returns empty results,
           fall back to content-based parsing (analyzes output content)
        3. Combine results from both approaches, avoiding duplicates
        """
        metadata = []
        seen_keys = set()

        # Step 1: Try command-based parsing
        parser = self.get_parser(command)
        if parser:
            try:
                command_metadata = parser.parse(command, output)
                for key, value in command_metadata:
                    if key not in seen_keys:
                        metadata.append((key, value))
                        seen_keys.add(key)
            except Exception as e:
                print(f"Parser error for command '{command}': {e}")

        # Step 2: Always run content-based parsing to catch additional data
        # This is especially useful for BOF outputs where we don't know the command
        content_metadata = self._parse_with_content_parsers(output)
        for key, value in content_metadata:
            # Only add if we don't already have this key (command parser takes precedence)
            if key not in seen_keys:
                metadata.append((key, value))
                seen_keys.add(key)

        return metadata

    def _parse_with_content_parsers(self, output: str) -> List[Tuple[str, str]]:
        """Run all content-based parsers on the output"""
        metadata = []
        seen_values = set()

        for parser in self.content_parsers:
            try:
                if parser.detect(output):
                    results = parser.parse(output)
                    for key, value in results:
                        # Avoid duplicate key-value pairs
                        pair = (key, value)
                        if pair not in seen_values:
                            seen_values.add(pair)
                            metadata.append(pair)
            except Exception as e:
                print(f"Content parser error ({parser.description}): {e}")

        return metadata

    def get_all_parsers(self) -> List[OutputParser]:
        """Get list of all registered command-based parsers"""
        return self.parsers.copy()

    def get_all_content_parsers(self) -> List[ContentBasedParser]:
        """Get list of all registered content-based parsers"""
        return self.content_parsers.copy()
