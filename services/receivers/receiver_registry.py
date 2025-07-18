"""
Receiver Registry - Dynamic receiver loading and management system
Provides extensible architecture for receiver types without hard-coded chains
"""

import importlib
from typing import Dict, Any, Type, Optional
from .base_receiver import BaseReceiver
from .receiver_config import ReceiverConfig, ReceiverType
from .encoding_strategies import EncodingStrategy
import utils


class ReceiverRegistry:
    """Registry for dynamically loading and creating receiver instances"""
    
    def __init__(self):
        self._registry: Dict[ReceiverType, Dict[str, Any]] = {}
        self._loaded_classes: Dict[ReceiverType, Type[BaseReceiver]] = {}
        
    def register_receiver(self, receiver_type: ReceiverType, config: Dict[str, Any]):
        """Register a receiver type with its configuration"""
        required_keys = ['module', 'class']
        if not all(key in config for key in required_keys):
            raise ValueError(f"Receiver config must contain {required_keys}")
            
        self._registry[receiver_type] = config
        
        if utils.logger:
            utils.logger.log_message(f"Registry: Registered receiver type {receiver_type.value}")
    
    def _load_receiver_class(self, receiver_type: ReceiverType) -> Type[BaseReceiver]:
        """Dynamically load and cache receiver class"""
        if receiver_type in self._loaded_classes:
            return self._loaded_classes[receiver_type]
            
        if receiver_type not in self._registry:
            raise ValueError(f"Receiver type {receiver_type.value} not registered")
            
        config = self._registry[receiver_type]
        
        try:
            # Import the module
            module = importlib.import_module(config['module'])
            
            # Get the class
            receiver_class = getattr(module, config['class'])
            
            # Validate it's a BaseReceiver subclass
            if not issubclass(receiver_class, BaseReceiver):
                raise TypeError(f"{config['class']} must be a subclass of BaseReceiver")
                
            # Cache the loaded class
            self._loaded_classes[receiver_type] = receiver_class
            
            if utils.logger:
                utils.logger.log_message(f"Registry: Loaded {receiver_type.value} receiver class {config['class']}")
                
            return receiver_class
            
        except ImportError as e:
            error_msg = f"Failed to import module {config['module']}: {e}"
            if utils.logger:
                utils.logger.log_message(f"Registry: {error_msg}")
            raise ImportError(error_msg)
            
        except AttributeError as e:
            error_msg = f"Class {config['class']} not found in module {config['module']}: {e}"
            if utils.logger:
                utils.logger.log_message(f"Registry: {error_msg}")
            raise AttributeError(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to load receiver class for {receiver_type.value}: {e}"
            if utils.logger:
                utils.logger.log_message(f"Registry: {error_msg}")
            raise
    
    def create_instance(self, receiver_type: ReceiverType, config: ReceiverConfig, 
                       encoding_strategy: EncodingStrategy) -> BaseReceiver:
        """Create a receiver instance of the specified type"""
        try:
            receiver_class = self._load_receiver_class(receiver_type)
            
            # Create instance
            instance = receiver_class(config, encoding_strategy)
            
            if utils.logger:
                utils.logger.log_message(f"Registry: Created {receiver_type.value} receiver instance {config.receiver_id}")
                
            return instance
            
        except Exception as e:
            error_msg = f"Failed to create {receiver_type.value} receiver instance: {e}"
            if utils.logger:
                utils.logger.log_message(f"Registry: {error_msg}")
            raise
    
    def is_supported(self, receiver_type: ReceiverType) -> bool:
        """Check if a receiver type is supported"""
        return receiver_type in self._registry
    
    def get_supported_types(self) -> list[ReceiverType]:
        """Get list of all supported receiver types"""
        return list(self._registry.keys())
    
    def get_receiver_info(self, receiver_type: ReceiverType) -> Optional[Dict[str, Any]]:
        """Get information about a receiver type"""
        return self._registry.get(receiver_type)
    
    def get_receiver_description(self, receiver_type: ReceiverType) -> str:
        """Get description for a receiver type"""
        info = self.get_receiver_info(receiver_type)
        if info:
            return info.get('description', f'{receiver_type.value} receiver')
        return f'Unknown receiver type: {receiver_type.value}'
    
    def register_from_mappings(self, mappings: Dict[ReceiverType, Dict[str, Any]]):
        """Register multiple receivers from a mappings dictionary"""
        for receiver_type, config in mappings.items():
            try:
                self.register_receiver(receiver_type, config)
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Registry: Failed to register {receiver_type.value}: {e}")
                # Continue registering other receivers even if one fails
                continue
    
    def preload_all(self):
        """Preload all registered receiver classes (optional optimization)"""
        for receiver_type in self._registry.keys():
            try:
                self._load_receiver_class(receiver_type)
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Registry: Failed to preload {receiver_type.value}: {e}")
                # Continue preloading others even if one fails
                continue
    
    def clear_cache(self):
        """Clear the loaded classes cache (useful for testing/development)"""
        self._loaded_classes.clear()
        if utils.logger:
            utils.logger.log_message("Registry: Cleared receiver class cache")
    
    def get_registry_status(self) -> Dict[str, Any]:
        """Get status information about the registry"""
        return {
            "registered_types": [rt.value for rt in self._registry.keys()],
            "loaded_classes": [rt.value for rt in self._loaded_classes.keys()],
            "total_registered": len(self._registry),
            "total_loaded": len(self._loaded_classes)
        }


# Global registry instance (singleton pattern)
_receiver_registry_instance: Optional[ReceiverRegistry] = None

def get_receiver_registry() -> ReceiverRegistry:
    """Get the global receiver registry instance"""
    global _receiver_registry_instance
    if _receiver_registry_instance is None:
        _receiver_registry_instance = ReceiverRegistry()
        # Initialize with default mappings
        from .receiver_config import RECEIVER_MAPPINGS
        _receiver_registry_instance.register_from_mappings(RECEIVER_MAPPINGS)
    return _receiver_registry_instance

def set_receiver_registry(registry: ReceiverRegistry):
    """Set the global receiver registry instance (useful for testing)"""
    global _receiver_registry_instance
    _receiver_registry_instance = registry