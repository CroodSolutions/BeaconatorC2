from pathlib import Path
import yaml
import os
from datetime import datetime
from typing import Tuple

class literal(str): 
    pass

def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

def ensure_directories(config):
    """Ensure required directories exist"""
    Path(config.LOGS_FOLDER).mkdir(exist_ok=True)
    Path(config.FILES_FOLDER).mkdir(exist_ok=True)
    Path('instance').mkdir(parents=True, exist_ok=True)
    
    # Ensure payload storage directory exists if enabled
    if hasattr(config, 'PAYLOAD_STORAGE_ENABLED') and config.PAYLOAD_STORAGE_ENABLED:
        Path(config.PAYLOADS_FOLDER).mkdir(parents=True, exist_ok=True)


def get_payload_storage_path(config, payload_type: str, format: str, include_timestamp: bool = True) -> Tuple[Path, str]:
    """
    Generate the storage path and filename for a payload
    
    Args:
        config: Server configuration object
        payload_type: Metasploit payload type (e.g., 'windows/meterpreter/reverse_tcp')
        format: Payload format (e.g., 'exe', 'elf', 'raw')
        include_timestamp: Whether to include timestamp in filename
        
    Returns:
        Tuple of (full_path, filename)
    """
    base_dir = Path(config.PAYLOADS_FOLDER)
    
    # Organize by payload platform if enabled
    if config.PAYLOAD_ORGANIZE_BY_TYPE:
        # Extract platform from payload type (e.g., 'windows' from 'windows/meterpreter/reverse_tcp')
        platform = payload_type.split('/')[0] if '/' in payload_type else 'generic'
        storage_dir = base_dir / platform
    else:
        storage_dir = base_dir
    
    # Ensure storage directory exists
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    # Clean payload type for filename (replace slashes with underscores)
    clean_payload_type = payload_type.replace('/', '_').replace('\\', '_')
    
    if include_timestamp and config.PAYLOAD_INCLUDE_TIMESTAMP:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{clean_payload_type}.{format}"
    else:
        filename = f"{clean_payload_type}.{format}"
    
    full_path = storage_dir / filename
    
    # Handle filename conflicts by adding a counter
    counter = 1
    original_path = full_path
    while full_path.exists():
        stem = original_path.stem
        suffix = original_path.suffix
        full_path = original_path.parent / f"{stem}_{counter}{suffix}"
        counter += 1
    
    return full_path, full_path.name


def save_payload_to_disk(config, payload_type: str, format: str, payload_data: bytes, 
                        metadata: dict = None) -> Tuple[bool, str, str]:
    """
    Save payload binary data to disk with metadata
    
    Args:
        config: Server configuration object
        payload_type: Metasploit payload type
        format: Payload format
        payload_data: Binary payload data
        metadata: Optional metadata dictionary
        
    Returns:
        Tuple of (success, file_path, error_message)
    """
    try:
        if not config.PAYLOAD_STORAGE_ENABLED:
            return False, "", "Payload storage is disabled"
        
        # Get storage path and filename
        full_path, filename = get_payload_storage_path(config, payload_type, format)
        
        # Write payload binary data
        with open(full_path, 'wb') as f:
            f.write(payload_data)
        
        # Write metadata file if provided
        if metadata:
            metadata_path = full_path.with_suffix(full_path.suffix + '.meta')
            metadata['generated_at'] = datetime.now().isoformat()
            metadata['payload_type'] = payload_type
            metadata['format'] = format
            metadata['file_size'] = len(payload_data)
            
            with open(metadata_path, 'w') as f:
                yaml.dump(metadata, f, default_flow_style=False)
        
        return True, str(full_path), ""
        
    except Exception as e:
        return False, "", f"Failed to save payload: {str(e)}"


def list_saved_payloads(config) -> list:
    """
    List all saved payloads with their metadata
    
    Args:
        config: Server configuration object
        
    Returns:
        List of dictionaries containing payload information
    """
    payloads = []
    
    if not config.PAYLOAD_STORAGE_ENABLED:
        return payloads
    
    try:
        base_dir = Path(config.PAYLOADS_FOLDER)
        if not base_dir.exists():
            return payloads
        
        # Find all payload files (excluding .meta files)
        for payload_file in base_dir.rglob('*'):
            if payload_file.is_file() and not payload_file.suffix == '.meta':
                # Check if it's a recognized payload format
                if payload_file.suffix.lower() in ['.exe', '.elf', '.raw', '.bin', '.dll', '.so']:
                    payload_info = {
                        'filename': payload_file.name,
                        'path': str(payload_file),
                        'size': payload_file.stat().st_size,
                        'created': datetime.fromtimestamp(payload_file.stat().st_ctime),
                        'modified': datetime.fromtimestamp(payload_file.stat().st_mtime),
                        'platform': payload_file.parent.name if payload_file.parent != base_dir else 'generic'
                    }
                    
                    # Load metadata if available
                    metadata_file = payload_file.with_suffix(payload_file.suffix + '.meta')
                    if metadata_file.exists():
                        try:
                            with open(metadata_file, 'r') as f:
                                metadata = yaml.safe_load(f)
                                payload_info.update(metadata)
                        except:
                            pass  # Ignore metadata errors
                    
                    payloads.append(payload_info)
        
        # Sort by creation time (newest first)
        payloads.sort(key=lambda x: x['created'], reverse=True)
        
    except Exception:
        pass  # Return empty list on errors
    
    return payloads


def delete_saved_payload(config, file_path: str) -> Tuple[bool, str]:
    """
    Delete a saved payload and its metadata
    
    Args:
        config: Server configuration object
        file_path: Path to the payload file
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        payload_path = Path(file_path)
        
        # Ensure the file is within the payloads directory for security
        base_dir = Path(config.PAYLOADS_FOLDER).resolve()
        if not payload_path.resolve().is_relative_to(base_dir):
            return False, "Invalid file path"
        
        # Delete payload file
        if payload_path.exists():
            payload_path.unlink()
        
        # Delete metadata file if it exists
        metadata_path = payload_path.with_suffix(payload_path.suffix + '.meta')
        if metadata_path.exists():
            metadata_path.unlink()
        
        return True, ""
        
    except Exception as e:
        return False, f"Failed to delete payload: {str(e)}"