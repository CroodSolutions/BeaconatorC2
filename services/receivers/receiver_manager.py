from typing import Dict, Optional, List, Any
from PyQt6.QtCore import QObject, pyqtSignal
import threading
import time

from .base_receiver import BaseReceiver, ReceiverStatus
from .receiver_config import ReceiverConfig, ReceiverConfigManager, ReceiverType
from .encoding_strategies import create_encoding_strategy
from .receiver_registry import get_receiver_registry

class ReceiverManager(QObject):
    """Manages all receiver instances"""
    
    # Signals for UI updates
    receiver_added = pyqtSignal(str)  # receiver_id
    receiver_removed = pyqtSignal(str)  # receiver_id
    receiver_status_changed = pyqtSignal(str, str)  # receiver_id, status
    receiver_stats_updated = pyqtSignal(str)  # receiver_id
    error_occurred = pyqtSignal(str, str)  # receiver_id, error_message
    
    def __init__(self, command_processor=None, file_transfer_service=None):
        super().__init__()
        self.command_processor = command_processor
        self.file_transfer_service = file_transfer_service
        self.config_manager = ReceiverConfigManager()
        
        # Initialize receiver registry
        self.receiver_registry = get_receiver_registry()
        
        # Active receiver instances
        self._receivers: Dict[str, BaseReceiver] = {}
        
        # Load and auto-start receivers
        self._load_existing_receivers()
        
    def _load_existing_receivers(self):
        """Load existing receiver configurations and create instances for all receivers"""
        configs = self.config_manager.get_all_configs()
        
        for config in configs.values():
            # Create receiver instance for all configurations (regardless of enabled status)
            receiver_id = self.create_receiver(config)
            # Only auto-start if specifically configured to do so
            if receiver_id and config.auto_start:
                self.start_receiver(receiver_id)
                
    def create_receiver(self, config: ReceiverConfig) -> Optional[str]:
        """Create a new receiver instance"""
        try:
            # Validate configuration
            is_valid, error = config.validate()
            if not is_valid:
                self.error_occurred.emit("", f"Invalid config: {error}")
                return None
                
            # Check for port conflicts
            for receiver in self._receivers.values():
                if (hasattr(receiver, 'config') and 
                    receiver.config.port == config.port and 
                    receiver.config.receiver_type == config.receiver_type):
                    self.error_occurred.emit("", f"Port {config.port} already in use")
                    return None
                    
            # Create encoding strategy
            encoding_strategy = create_encoding_strategy(
                config.encoding_type, 
                config.encoding_config
            )
            
            # Create receiver based on type
            receiver = self._create_receiver_instance(config, encoding_strategy)
            if not receiver:
                return None
                
            # Set up services
            receiver.set_command_processor(self.command_processor)
            receiver.set_file_transfer_service(self.file_transfer_service)
            
            # Connect signals
            receiver.status_changed.connect(
                lambda rid=config.receiver_id: self.receiver_status_changed.emit(rid, receiver.get_status_display())
            )
            receiver.stats_updated.connect(
                lambda rid=config.receiver_id: self.receiver_stats_updated.emit(rid)
            )
            receiver.error_occurred.connect(self.error_occurred.emit)
            
            # Store receiver
            self._receivers[config.receiver_id] = receiver
            
            # Save configuration if not already saved
            if config.receiver_id not in self.config_manager.get_all_configs():
                self.config_manager.add_config(config)
                
            # Auto-start if configured
            if config.auto_start:
                receiver.start()
                
            self.receiver_added.emit(config.receiver_id)
            return config.receiver_id
            
        except Exception as e:
            self.error_occurred.emit("", f"Failed to create receiver: {str(e)}")
            return None
            
    def _create_receiver_instance(self, config: ReceiverConfig, encoding_strategy) -> Optional[BaseReceiver]:
        """Factory method to create receiver instances using registry"""
        try:
            # Check if receiver type is supported
            if not self.receiver_registry.is_supported(config.receiver_type):
                error_msg = f"Receiver type {config.receiver_type.value} not supported. Available types: {[rt.value for rt in self.receiver_registry.get_supported_types()]}"
                self.error_occurred.emit("", error_msg)
                return None
            
            # Create instance using registry
            return self.receiver_registry.create_instance(config.receiver_type, config, encoding_strategy)
            
        except Exception as e:
            self.error_occurred.emit("", f"Error creating {config.receiver_type.value} receiver: {str(e)}")
            return None
            
    def start_receiver(self, receiver_id: str) -> bool:
        """Start a specific receiver"""
        if receiver_id not in self._receivers:
            return False
            
        receiver = self._receivers[receiver_id]
        return receiver.start()
        
    def stop_receiver(self, receiver_id: str) -> bool:
        """Stop a specific receiver"""
        if receiver_id not in self._receivers:
            return False
            
        receiver = self._receivers[receiver_id]
        return receiver.stop()
        
    def restart_receiver(self, receiver_id: str) -> bool:
        """Restart a specific receiver"""
        if receiver_id not in self._receivers:
            return False
            
        receiver = self._receivers[receiver_id]
        return receiver.restart()
        
    def remove_receiver(self, receiver_id: str) -> bool:
        """Remove a receiver instance"""
        if receiver_id not in self._receivers:
            return False
            
        try:
            receiver = self._receivers[receiver_id]
            
            # Stop receiver if running
            if receiver.status == ReceiverStatus.RUNNING:
                receiver.stop()
                
            # Remove from active receivers
            del self._receivers[receiver_id]
            
            # Remove from configuration
            self.config_manager.remove_config(receiver_id)
            
            self.receiver_removed.emit(receiver_id)
            return True
            
        except Exception as e:
            self.error_occurred.emit(receiver_id, f"Error removing receiver: {str(e)}")
            return False
            
    def update_receiver_config(self, receiver_id: str, updates: Dict[str, Any]) -> bool:
        """Update receiver configuration"""
        try:
            # Update stored configuration
            config = self.config_manager.get_config(receiver_id)
            if not config:
                return False
                
            # Apply updates
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                    
            # Validate updated config
            is_valid, error = config.validate()
            if not is_valid:
                self.error_occurred.emit(receiver_id, f"Invalid config: {error}")
                return False
                
            # Save configuration
            self.config_manager.update_config(config)
            
            # Update receiver if it exists
            if receiver_id in self._receivers:
                receiver = self._receivers[receiver_id]
                receiver.update_configuration(updates)
                
            return True
            
        except Exception as e:
            self.error_occurred.emit(receiver_id, f"Error updating config: {str(e)}")
            return False
            
    def get_receiver(self, receiver_id: str) -> Optional[BaseReceiver]:
        """Get a specific receiver instance"""
        return self._receivers.get(receiver_id)
        
    def get_all_receivers(self) -> Dict[str, BaseReceiver]:
        """Get all receiver instances"""
        return self._receivers.copy()
        
    def get_receiver_configs(self) -> Dict[str, ReceiverConfig]:
        """Get all receiver configurations"""
        return self.config_manager.get_all_configs()
        
    def get_receiver_config(self, receiver_id: str) -> Optional[ReceiverConfig]:
        """Get specific receiver configuration"""
        return self.config_manager.get_config(receiver_id)
        
    def get_receivers_by_type(self, receiver_type: ReceiverType) -> Dict[str, BaseReceiver]:
        """Get receivers of a specific type"""
        return {
            rid: receiver for rid, receiver in self._receivers.items()
            if hasattr(receiver, 'config') and receiver.config.receiver_type == receiver_type
        }
        
    def get_running_receivers(self) -> Dict[str, BaseReceiver]:
        """Get all currently running receivers"""
        return {
            rid: receiver for rid, receiver in self._receivers.items()
            if receiver.status == ReceiverStatus.RUNNING
        }
        
    def get_receiver_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all receivers"""
        total_receivers = len(self._receivers)
        running_receivers = len(self.get_running_receivers())
        total_connections = sum(r.stats.active_connections for r in self._receivers.values())
        total_bytes_received = sum(r.stats.bytes_received for r in self._receivers.values())
        total_bytes_sent = sum(r.stats.bytes_sent for r in self._receivers.values())
        
        return {
            "total_receivers": total_receivers,
            "running_receivers": running_receivers,
            "stopped_receivers": total_receivers - running_receivers,
            "total_connections": total_connections,
            "total_bytes_received": total_bytes_received,
            "total_bytes_sent": total_bytes_sent
        }
        
    def start_all_auto_start_receivers(self):
        """Start all receivers configured for auto-start"""
        auto_start_configs = self.config_manager.get_auto_start_configs()
        
        for config in auto_start_configs.values():
            if config.receiver_id not in self._receivers:
                self.create_receiver(config)
            else:
                self.start_receiver(config.receiver_id)
                
    def stop_all_receivers(self):
        """Stop all running receivers"""
        for receiver_id in list(self._receivers.keys()):
            self.stop_receiver(receiver_id)
            
    def _update_all_stats(self):
        """Update statistics for all receivers"""
        for receiver_id, receiver in self._receivers.items():
            # Trigger stats update which will emit signal
            receiver._update_stats()
            
    def shutdown(self):
        """Shutdown all receivers and cleanup"""
        self.stop_all_receivers()
        
        # Wait a moment for clean shutdown
        time.sleep(1)
        
        self._receivers.clear()
    
    def get_supported_receiver_types(self) -> list[ReceiverType]:
        """Get list of all supported receiver types from registry"""
        return self.receiver_registry.get_supported_types()
    
    def get_receiver_type_info(self, receiver_type: ReceiverType) -> Optional[Dict[str, Any]]:
        """Get information about a specific receiver type"""
        return self.receiver_registry.get_receiver_info(receiver_type)
    
    def get_registry_status(self) -> Dict[str, Any]:
        """Get status information about the receiver registry"""
        return self.receiver_registry.get_registry_status()

# Global receiver manager instance (singleton pattern)
_receiver_manager_instance: Optional[ReceiverManager] = None

def get_receiver_manager() -> ReceiverManager:
    """Get the global receiver manager instance"""
    global _receiver_manager_instance
    if _receiver_manager_instance is None:
        _receiver_manager_instance = ReceiverManager()
    return _receiver_manager_instance

def set_receiver_manager(manager: ReceiverManager):
    """Set the global receiver manager instance"""
    global _receiver_manager_instance
    _receiver_manager_instance = manager