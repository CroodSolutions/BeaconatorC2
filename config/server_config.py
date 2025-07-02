from dataclasses import dataclass

@dataclass
class ServerConfig:
    """Server configuration with default values"""
    APP_ID: str = u'Beaconator.AgentManager'
    LOGS_FOLDER: str = 'logs'
    RESOURCES_FOLDER: str = 'resources'
    FILES_FOLDER: str = 'files'
    DB_PATH: str = 'instance/beaconator.db'
    COMBINED_PORT: int = 5074
    BEACON_TIMEOUT_MINUTES: int = 1
    BUFFER_SIZE: int = 4096
    MAX_RETRIES: int = 5