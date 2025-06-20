from pathlib import Path
import yaml

class literal(str): 
    pass

def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

def ensure_directories(config):
    """Ensure required directories exist"""
    Path(config.LOGS_FOLDER).mkdir(exist_ok=True)
    Path(config.FILES_FOLDER).mkdir(exist_ok=True)
    Path('instance').mkdir(parents=True, exist_ok=True)