from pathlib import Path
import yaml
import os
import base64
from datetime import datetime
from typing import Tuple

class literal(str): 
    pass

def literal_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

def get_file_extension_for_format(format: str) -> str:
    """
    Get the correct file extension for a given payload format
    
    Args:
        format: Metasploit payload format
        
    Returns:
        Appropriate file extension (with dot)
    """
    format_extension_map = {
        # Binary formats
        'exe': '.exe',
        'dll': '.dll',
        'msi': '.msi',
        'elf': '.elf',
        'macho': '.macho',
        'apk': '.apk',
        'jar': '.jar',
        'war': '.war',
        'raw': '.bin',
        
        # Text-based formats
        'powershell': '.ps1',
        'python': '.py',
        'py': '.py',
        'php': '.php',
        'perl': '.pl',
        'ruby': '.rb',
        
        # Data formats
        'hex': '.hex',
        'base64': '.b64',
        'c': '.c',
        'csharp': '.cs',
        'java': '.java',
        
        # Web formats
        'asp': '.asp',
        'aspx': '.aspx',
        'jsp': '.jsp',
    }
    
    return format_extension_map.get(format.lower(), f'.{format}')

def is_text_format(format: str) -> bool:
    """
    Determine if a payload format produces text output rather than binary
    
    Args:
        format: Metasploit payload format
        
    Returns:
        True if format produces text output, False for binary
    """
    text_formats = {
        'powershell', 'python', 'py', 'php', 'perl', 'ruby',
        'hex', 'base64', 'c', 'csharp', 'java', 'asp', 'aspx', 'jsp'
    }
    
    return format.lower() in text_formats

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
    
    # Get proper file extension for the format
    extension = get_file_extension_for_format(format)
    
    if include_timestamp and config.PAYLOAD_INCLUDE_TIMESTAMP:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{clean_payload_type}{extension}"
    else:
        filename = f"{clean_payload_type}{extension}"
    
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


def save_payload_to_disk(config, payload_type: str, format: str, payload_data, 
                        metadata: dict = None) -> Tuple[bool, str, str]:
    """
    Save payload data to disk with metadata, handling both binary and text formats
    
    Args:
        config: Server configuration object
        payload_type: Metasploit payload type
        format: Payload format
        payload_data: Payload data (bytes for binary, str for text)
        metadata: Optional metadata dictionary
        
    Returns:
        Tuple of (success, file_path, error_message)
    """
    try:
        if not config.PAYLOAD_STORAGE_ENABLED:
            return False, "", "Payload storage is disabled"
        
        # Get storage path and filename
        full_path, filename = get_payload_storage_path(config, payload_type, format)
        
        # Determine if this is a text or binary format
        if is_text_format(format):
            # Handle text-based formats
            if isinstance(payload_data, bytes):
                try:
                    # Try to decode as UTF-8 text
                    text_data = payload_data.decode('utf-8')
                except UnicodeDecodeError:
                    # If decoding fails, fall back to binary mode
                    with open(full_path, 'wb') as f:
                        f.write(payload_data)
                else:
                    # Write as text
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(text_data)
            elif isinstance(payload_data, str):
                # Write string directly as text
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(payload_data)
            else:
                return False, "", f"Unexpected data type for text format: {type(payload_data)}"
        else:
            # Handle binary formats
            if isinstance(payload_data, str):
                # Convert string to bytes for binary formats
                payload_data = payload_data.encode('utf-8')
            
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
                recognized_extensions = {
                    # Binary formats
                    '.exe', '.dll', '.msi', '.elf', '.macho', '.apk', '.jar', '.war', '.bin', '.so',
                    # Text formats  
                    '.ps1', '.py', '.php', '.pl', '.rb', '.hex', '.b64', '.c', '.cs', '.java',
                    # Web formats
                    '.asp', '.aspx', '.jsp'
                }
                if payload_file.suffix.lower() in recognized_extensions:
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


def strip_filename_quotes(filename: str) -> str:
    """
    Safely strip surrounding quotes from filenames while preserving internal quotes
    
    Args:
        filename: The filename that may be surrounded by quotes
        
    Returns:
        Filename with surrounding quotes removed
        
    Examples:
        '"file with spaces.txt"' -> 'file with spaces.txt'
        "'file with spaces.txt'" -> 'file with spaces.txt'
        'file_without_spaces.txt' -> 'file_without_spaces.txt'
        '"file with "inner" quotes.txt"' -> 'file with "inner" quotes.txt'
    """
    if not filename:
        return filename
    
    # Strip whitespace first
    filename = filename.strip()
    
    # Handle double quotes
    if len(filename) >= 2 and filename.startswith('"') and filename.endswith('"'):
        return filename[1:-1]
    
    # Handle single quotes
    if len(filename) >= 2 and filename.startswith("'") and filename.endswith("'"):
        return filename[1:-1]
    
    # Return unchanged if no surrounding quotes
    return filename


def safe_filename_path(base_dir: Path, filename: str) -> Path:
    """
    Create a safe file path that preserves the original filename while preventing directory traversal
    
    Args:
        base_dir: Base directory path
        filename: Original filename (potentially unsafe)
        
    Returns:
        Safe Path object within the base directory
        
    Raises:
        ValueError: If the filename contains dangerous path elements
    """
    # Strip quotes if present
    filename = strip_filename_quotes(filename)
    
    # Check for dangerous path elements
    if not filename or filename in ('.', '..'):
        raise ValueError(f"Invalid filename: {filename}")
    
    # Check for path separators and other dangerous characters
    dangerous_chars = ['/', '\\', '..', '\x00']
    for char in dangerous_chars:
        if char in filename:
            raise ValueError(f"Filename contains dangerous character: {char}")
    
    # Create path and ensure it's within the base directory
    filepath = base_dir / filename
    
    # Resolve both paths to catch any potential traversal attempts
    try:
        base_resolved = base_dir.resolve()
        file_resolved = filepath.resolve()
        
        # Check if the resolved file path is within the base directory
        if not str(file_resolved).startswith(str(base_resolved)):
            raise ValueError("Path traversal attempt detected")
            
    except (OSError, RuntimeError):
        raise ValueError("Invalid file path")
    
    return filepath