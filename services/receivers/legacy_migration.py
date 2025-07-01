"""
Legacy Migration Utilities
Provides functions to migrate from legacy ServerManager to ReceiverManager
"""

from typing import Optional
from datetime import datetime
from config import ServerConfig, ConfigManager
from .receiver_config import ReceiverConfig, ReceiverConfigManager, ReceiverType


def create_legacy_compatible_receiver(config: ServerConfig) -> ReceiverConfig:
    """
    Create a receiver configuration that mirrors the legacy server settings
    
    Args:
        config: Legacy ServerConfig to mirror
        
    Returns:
        ReceiverConfig: Configuration matching legacy server parameters
    """
    return ReceiverConfig(
        name="Legacy Compatible Receiver",
        description="Auto-generated receiver to replace legacy server functionality",
        receiver_type=ReceiverType.TCP,
        enabled=True,
        auto_start=True,
        host="0.0.0.0",
        port=config.COMBINED_PORT,
        buffer_size=config.BUFFER_SIZE,  # 4096 from legacy
        timeout=config.AGENT_TIMEOUT_MINUTES * 60,  # Convert minutes to seconds
        encoding_type="plain",
        encoding_config={},
        max_connections=100,  # Reasonable default
        connection_timeout=300,  # 5 minutes
        keep_alive=True,
        created_at=datetime.now().isoformat(),
        modified_at=datetime.now().isoformat()
    )


def ensure_legacy_receiver_exists(server_config: ServerConfig) -> Optional[str]:
    """
    Ensure a legacy-compatible receiver exists, create one if it doesn't
    
    Args:
        server_config: Legacy server configuration to mirror
        
    Returns:
        Optional[str]: Receiver ID of the legacy-compatible receiver, or None if creation failed
    """
    config_manager = ReceiverConfigManager()
    configs = config_manager.get_all_configs()
    
    # Check if a receiver already exists on the legacy port
    legacy_port = server_config.COMBINED_PORT
    existing_receiver = None
    
    for receiver_id, receiver_config in configs.items():
        if (receiver_config.port == legacy_port and 
            receiver_config.receiver_type == ReceiverType.TCP):
            existing_receiver = receiver_config
            break
    
    if existing_receiver:
        # Update existing receiver to ensure it's enabled and auto-start
        existing_receiver.enabled = True
        existing_receiver.auto_start = True
        existing_receiver.name = "Legacy Compatible Receiver"
        existing_receiver.description = "Auto-generated receiver to replace legacy server functionality"
        existing_receiver.modified_at = datetime.now().isoformat()
        
        config_manager.update_config(existing_receiver)
        return existing_receiver.receiver_id
    else:
        # Create new legacy-compatible receiver
        legacy_receiver_config = create_legacy_compatible_receiver(server_config)
        
        try:
            config_manager.add_config(legacy_receiver_config)
            return legacy_receiver_config.receiver_id
        except Exception as e:
            print(f"Failed to create legacy-compatible receiver: {e}")
            return None


def migrate_port_setting(old_port: int, new_port: int) -> bool:
    """
    Migrate port setting from legacy server to receiver configuration
    
    Args:
        old_port: Current port from legacy configuration
        new_port: New port to set
        
    Returns:
        bool: True if migration was successful
    """
    config_manager = ReceiverConfigManager()
    configs = config_manager.get_all_configs()
    
    # Find the legacy-compatible receiver
    for receiver_id, receiver_config in configs.items():
        if (receiver_config.port == old_port and 
            receiver_config.name == "Legacy Compatible Receiver"):
            
            # Update the port
            receiver_config.port = new_port
            receiver_config.modified_at = datetime.now().isoformat()
            
            try:
                config_manager.update_config(receiver_config)
                
                # Also update the settings.json file
                config_mgr = ConfigManager()
                config_mgr.update_setting('port', new_port)
                
                return True
            except Exception as e:
                print(f"Failed to migrate port setting: {e}")
                return False
    
    return False