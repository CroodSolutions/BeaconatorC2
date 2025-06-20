import json
from pathlib import Path

class ConfigManager:
    def __init__(self, config_file="settings.json"):
        self.config_file = Path(config_file)
        self.settings = self.load_settings()

    def load_settings(self) -> dict:
        default_settings = {
            'port': 5074,  
            'font_size': 14  
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_settings = json.load(f)
                    # Update defaults with saved values
                    default_settings.update(saved_settings)
            except json.JSONDecodeError:
                pass  # Use defaults if file is corrupted
                
        return default_settings

    def get_font_size(self) -> int:
        return self.settings.get('font_size', 14)

    def save_settings(self, port, font_size):
        self.settings = {
            'port': port,
            'font_size': font_size
        }
        with open(self.config_file, 'w') as f:
            json.dump(self.settings, f)