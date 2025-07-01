from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional
import json
import uuid
from pathlib import Path

class ReceiverType(Enum):
    """Types of receivers available"""
    TCP = "tcp"
    UDP = "udp"
    DNS = "dns"
    CLOUD = "cloud"

@dataclass
class ReceiverConfig:
    """Configuration for a receiver instance"""
    receiver_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    receiver_type: ReceiverType = ReceiverType.TCP
    enabled: bool = False
    auto_start: bool = False
    
    # Connection settings
    host: str = "0.0.0.0"
    port: int = 5074
    buffer_size: int = 1048576  # 1MB
    timeout: int = 30
    
    # Encoding settings
    encoding_type: str = "plain"
    encoding_config: Dict[str, Any] = field(default_factory=dict)
    
    # Protocol settings
    protocol_config: Dict[str, Any] = field(default_factory=dict)
    
    # Advanced settings
    max_connections: int = 100
    connection_timeout: int = 300
    keep_alive: bool = True
    
    # Metadata
    description: str = ""
    tags: list = field(default_factory=list)
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        # Handle receiver_type safely - could be string or enum
        if isinstance(self.receiver_type, str):
            receiver_type_value = self.receiver_type
        else:
            receiver_type_value = self.receiver_type.value
            
        return {
            "receiver_id": self.receiver_id,
            "name": self.name,
            "receiver_type": receiver_type_value,
            "enabled": self.enabled,
            "auto_start": self.auto_start,
            "host": self.host,
            "port": self.port,
            "buffer_size": self.buffer_size,
            "timeout": self.timeout,
            "encoding_type": self.encoding_type,
            "encoding_config": self.encoding_config,
            "protocol_config": self.protocol_config,
            "max_connections": self.max_connections,
            "connection_timeout": self.connection_timeout,
            "keep_alive": self.keep_alive,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at,
            "modified_at": self.modified_at
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReceiverConfig':
        """Create config from dictionary"""
        # Handle enum conversion
        receiver_type = ReceiverType(data.get("receiver_type", "tcp"))
        
        return cls(
            receiver_id=data.get("receiver_id", str(uuid.uuid4())),
            name=data.get("name", ""),
            receiver_type=receiver_type,
            enabled=data.get("enabled", False),
            auto_start=data.get("auto_start", False),
            host=data.get("host", "0.0.0.0"),
            port=data.get("port", 5074),
            buffer_size=data.get("buffer_size", 1048576),
            timeout=data.get("timeout", 30),
            encoding_type=data.get("encoding_type", "plain"),
            encoding_config=data.get("encoding_config", {}),
            protocol_config=data.get("protocol_config", {}),
            max_connections=data.get("max_connections", 100),
            connection_timeout=data.get("connection_timeout", 300),
            keep_alive=data.get("keep_alive", True),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            created_at=data.get("created_at"),
            modified_at=data.get("modified_at")
        )
        
    def validate(self) -> tuple[bool, str]:
        """Validate configuration"""
        if not self.name.strip():
            return False, "Receiver name is required"
        
        # Validate receiver_type
        valid_types = [t.value for t in ReceiverType]
        if isinstance(self.receiver_type, str):
            if self.receiver_type not in valid_types:
                return False, f"Invalid receiver type: {self.receiver_type}"
        elif not isinstance(self.receiver_type, ReceiverType):
            return False, "Receiver type must be a valid ReceiverType"
            
        if not (1 <= self.port <= 65535):
            return False, "Port must be between 1 and 65535"
            
        if self.buffer_size <= 0:
            return False, "Buffer size must be positive"
            
        if self.timeout < 0:
            return False, "Timeout must be non-negative"
            
        if self.max_connections <= 0:
            return False, "Max connections must be positive"
            
        return True, ""
        
    def get_display_name(self) -> str:
        """Get display name for UI"""
        # Handle receiver_type safely - could be string or enum
        if isinstance(self.receiver_type, str):
            type_display = self.receiver_type.upper()
        else:
            type_display = self.receiver_type.value.upper()
            
        if self.name:
            return f"{self.name} ({type_display}:{self.port})"
        return f"{type_display} Receiver - Port {self.port}"

class ReceiverConfigManager:
    """Manages receiver configurations"""
    
    def __init__(self, config_dir: str = "configs"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "receivers.json"
        self._configs: Dict[str, ReceiverConfig] = {}
        self.load_configs()
        
    def load_configs(self) -> bool:
        """Load receiver configurations from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    
                self._configs = {}
                for config_data in data.get("receivers", []):
                    config = ReceiverConfig.from_dict(config_data)
                    self._configs[config.receiver_id] = config
                    
            return True
        except Exception as e:
            print(f"Error loading receiver configs: {e}")
            return False
            
    def save_configs(self) -> bool:
        """Save receiver configurations to file"""
        try:
            data = {
                "receivers": [config.to_dict() for config in self._configs.values()]
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            return True
        except Exception as e:
            print(f"Error saving receiver configs: {e}")
            return False
            
    def add_config(self, config: ReceiverConfig) -> bool:
        """Add a new receiver configuration"""
        is_valid, error = config.validate()
        if not is_valid:
            raise ValueError(error)
            
        # Check for port conflicts
        for existing_config in self._configs.values():
            if (existing_config.receiver_id != config.receiver_id and 
                existing_config.port == config.port and 
                existing_config.receiver_type == config.receiver_type):
                raise ValueError(f"Port {config.port} already in use by {existing_config.name}")
                
        self._configs[config.receiver_id] = config
        return self.save_configs()
        
    def update_config(self, config: ReceiverConfig) -> bool:
        """Update an existing receiver configuration"""
        if config.receiver_id not in self._configs:
            return False
            
        is_valid, error = config.validate()
        if not is_valid:
            raise ValueError(error)
            
        self._configs[config.receiver_id] = config
        return self.save_configs()
        
    def remove_config(self, receiver_id: str) -> bool:
        """Remove a receiver configuration"""
        if receiver_id in self._configs:
            del self._configs[receiver_id]
            return self.save_configs()
        return False
        
    def get_config(self, receiver_id: str) -> Optional[ReceiverConfig]:
        """Get a specific receiver configuration"""
        return self._configs.get(receiver_id)
        
    def get_all_configs(self) -> Dict[str, ReceiverConfig]:
        """Get all receiver configurations"""
        return self._configs.copy()
        
    def get_configs_by_type(self, receiver_type: ReceiverType) -> Dict[str, ReceiverConfig]:
        """Get configurations by receiver type"""
        return {
            rid: config for rid, config in self._configs.items() 
            if config.receiver_type == receiver_type
        }
        
    def get_auto_start_configs(self) -> Dict[str, ReceiverConfig]:
        """Get configurations marked for auto-start"""
        return {
            rid: config for rid, config in self._configs.items() 
            if config.auto_start
        }