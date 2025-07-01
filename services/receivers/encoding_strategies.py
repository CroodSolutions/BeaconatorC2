from abc import ABC, abstractmethod
import base64
from typing import Dict, Any

class EncodingStrategy(ABC):
    """Abstract base class for encoding/decoding strategies"""
    
    @abstractmethod
    def encode(self, data: bytes) -> bytes:
        """Encode the data"""
        pass
        
    @abstractmethod
    def decode(self, data: bytes) -> bytes:
        """Decode the data"""
        pass
        
    @abstractmethod
    def get_name(self) -> str:
        """Get the strategy name"""
        pass
        
    @abstractmethod
    def get_description(self) -> str:
        """Get strategy description"""
        pass
        
    @abstractmethod
    def get_configuration(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        pass
        
    @abstractmethod
    def set_configuration(self, config: Dict[str, Any]) -> bool:
        """Set strategy configuration"""
        pass

class PlainTextEncoding(EncodingStrategy):
    """No encoding - pass data through unchanged"""
    
    def encode(self, data: bytes) -> bytes:
        return data
        
    def decode(self, data: bytes) -> bytes:
        return data
        
    def get_name(self) -> str:
        return "Plain Text"
        
    def get_description(self) -> str:
        return "No encoding - data passes through unchanged"
        
    def get_configuration(self) -> Dict[str, Any]:
        return {}
        
    def set_configuration(self, config: Dict[str, Any]) -> bool:
        return True  # No configuration needed

class Base64Encoding(EncodingStrategy):
    """Base64 encoding strategy"""
    
    def encode(self, data: bytes) -> bytes:
        try:
            return base64.b64encode(data)
        except Exception:
            return data  # Fallback to original data on error
            
    def decode(self, data: bytes) -> bytes:
        try:
            return base64.b64decode(data)
        except Exception:
            return data  # Fallback to original data on error
            
    def get_name(self) -> str:
        return "Base64"
        
    def get_description(self) -> str:
        return "Base64 encoding for text-safe transmission"
        
    def get_configuration(self) -> Dict[str, Any]:
        return {}
        
    def set_configuration(self, config: Dict[str, Any]) -> bool:
        return True  # No configuration needed

class XOREncoding(EncodingStrategy):
    """XOR encoding with configurable key"""
    
    def __init__(self, key: bytes = b"default_key"):
        self.key = key
        
    def encode(self, data: bytes) -> bytes:
        try:
            return bytes(a ^ b for a, b in zip(data, self._cycle_key(len(data))))
        except Exception:
            return data
            
    def decode(self, data: bytes) -> bytes:
        # XOR is symmetric - same operation for encode/decode
        return self.encode(data)
        
    def _cycle_key(self, length: int) -> bytes:
        """Cycle the key to match data length"""
        if not self.key:
            return b'\x00' * length
            
        return (self.key * ((length // len(self.key)) + 1))[:length]
        
    def get_name(self) -> str:
        return "XOR"
        
    def get_description(self) -> str:
        return f"XOR encoding with key: {self.key.decode('utf-8', errors='replace')}"
        
    def get_configuration(self) -> Dict[str, Any]:
        return {"key": self.key.decode('utf-8', errors='replace')}
        
    def set_configuration(self, config: Dict[str, Any]) -> bool:
        try:
            if "key" in config:
                self.key = config["key"].encode('utf-8')
            return True
        except Exception:
            return False

class RotEncoding(EncodingStrategy):
    """ROT encoding (Caesar cipher) with configurable shift"""
    
    def __init__(self, shift: int = 13):
        self.shift = shift % 256  # Keep within byte range
        
    def encode(self, data: bytes) -> bytes:
        try:
            return bytes((b + self.shift) % 256 for b in data)
        except Exception:
            return data
            
    def decode(self, data: bytes) -> bytes:
        try:
            return bytes((b - self.shift) % 256 for b in data)
        except Exception:
            return data
            
    def get_name(self) -> str:
        return f"ROT{self.shift}"
        
    def get_description(self) -> str:
        return f"ROT encoding with shift of {self.shift}"
        
    def get_configuration(self) -> Dict[str, Any]:
        return {"shift": self.shift}
        
    def set_configuration(self, config: Dict[str, Any]) -> bool:
        try:
            if "shift" in config:
                self.shift = int(config["shift"]) % 256
            return True
        except Exception:
            return False

# Factory function for creating encoding strategies
def create_encoding_strategy(strategy_type: str, config: Dict[str, Any] = None) -> EncodingStrategy:
    """Factory function to create encoding strategies"""
    config = config or {}
    
    strategy_map = {
        "plain": PlainTextEncoding,
        "base64": Base64Encoding,
        "xor": lambda: XOREncoding(config.get("key", "default_key").encode('utf-8')),
        "rot": lambda: RotEncoding(config.get("shift", 13))
    }
    
    if strategy_type.lower() not in strategy_map:
        raise ValueError(f"Unknown encoding strategy: {strategy_type}")
        
    strategy_class = strategy_map[strategy_type.lower()]
    strategy = strategy_class() if not callable(strategy_class) else strategy_class()
    
    if config:
        strategy.set_configuration(config)
        
    return strategy

def get_available_encodings() -> Dict[str, str]:
    """Get list of available encoding strategies"""
    return {
        "plain": "Plain Text",
        "base64": "Base64",
        "xor": "XOR",
        "rot": "ROT/Caesar"
    }