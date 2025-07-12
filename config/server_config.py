from dataclasses import dataclass

@dataclass
class ServerConfig:
    """Server configuration with default values"""
    APP_ID: str = u'Beaconator.AgentManager'
    LOGS_FOLDER: str = 'logs'
    RESOURCES_FOLDER: str = 'resources'
    FILES_FOLDER: str = 'files'
    SCHEMAS_FOLDER: str = 'schemas'
    DB_PATH: str = 'instance/beaconator.db'
    COMBINED_PORT: int = 5074
    BEACON_TIMEOUT_MINUTES: int = 1
    BUFFER_SIZE: int = 4096
    MAX_RETRIES: int = 5
    
    # Metasploit RPC Configuration
    MSF_RPC_HOST: str = '127.0.0.1'
    MSF_RPC_PORT: int = 55553
    MSF_RPC_USER: str = 'msf'
    MSF_RPC_PASS: str = 'msf123'
    MSF_RPC_SSL: bool = True
    MSF_RPC_URI: str = '/api/'
    MSF_ENABLED: bool = True
    MSF_AUTO_CLEANUP: bool = True
    MSF_DEFAULT_LHOST: str = ''  # Will be auto-detected if empty
    
    # Metasploit Process Management
    MSF_AUTO_START: bool = True          # Auto-start RPC on BeaconatorC2 launch
    MSF_AUTO_STOP: bool = True           # Auto-stop RPC on BeaconatorC2 exit
    MSF_DAEMON_PATH: str = 'msfrpcd'     # Path to msfrpcd executable
    MSF_CONSOLE_PATH: str = 'msfconsole' # Path to msfconsole executable
    MSF_STARTUP_TIMEOUT: int = 30        # Seconds to wait for RPC startup
    MSF_HEALTH_CHECK_INTERVAL: int = 60  # Seconds between health checks
    MSF_SESSION_KEEP_ALIVE: bool = True   # Enable periodic keep-alive to prevent session timeout
    MSF_KEEP_ALIVE_INTERVAL: int = 300    # Seconds between keep-alive checks (5 minutes)
    
    # Payload Storage Configuration
    PAYLOAD_STORAGE_ENABLED: bool = True   # Enable automatic payload storage
    PAYLOADS_FOLDER: str = 'files/payloads'  # Directory for storing generated payloads
    PAYLOAD_AUTO_SAVE: bool = True         # Automatically save all generated payloads
    PAYLOAD_ORGANIZE_BY_TYPE: bool = True  # Organize payloads in subdirectories by type
    PAYLOAD_INCLUDE_TIMESTAMP: bool = True # Include timestamp in payload filenames