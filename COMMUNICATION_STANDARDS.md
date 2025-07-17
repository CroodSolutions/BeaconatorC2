# BeaconatorC2 Communication Standards

**Version**: 1.1  
**Date**: 2025-07-15  
**Purpose**: Standardized communication protocol between beacons and the C2 manager

## Overview

BeaconatorC2 uses a pipe-delimited (`|`) protocol for all beacon-to-manager communication. This document defines the standard communication patterns to ensure consistency across all receiver implementations and beacon types.

## Core Protocol Format

All commands follow the basic format:
```
{command}|{parameter1}|{parameter2}|...
```

- **Delimiter**: Pipe character (`|`)
- **Encoding**: UTF-8 text (with optional encoding strategies)
- **Transport**: TCP, UDP, SMB, or Metasploit sessions

## 1. Core Commands Quick Reference
\* Required commands

| **Command**         | **Direction**   | **Format**                                  | **Purpose**                       | **Parameters**                | **Response**                     |
| ------------------- | --------------- | ------------------------------------------- | --------------------------------- | ----------------------------- | -------------------------------- |
| `register`*         | Beacon → Server | register\|{beacon_id}\|{computer_name}      | Initial beacon registration       | beacon_id, computer_name      | "Registration successful"        |
| `request_action`*   | Beacon → Server | request_action\|{beacon_id}                 | Request pending commands          | beacon_id                     | Command or "no_pending_commands" |
| `execute_module`*   | Server → Beacon | execute_module\|{module}\|{params}          | Execute beacon module             | module_name, parameters       | Executes module                  |
| `command_output`*   | Beacon → Server | command_output\|{beacon_id}\|{output}       | Submit command results            | beacon_id, output             | None (logged)                    |
| `shutdown`*         | Server → Beacon | shutdown                                    | Terminate beacon                  | None                          | Beacon exits                     |
| `execute_command`   | Server → Beacon | execute_command\|{command}                  | Execute raw OS command            | command_string                | Executes command                 |
| `checkin`           | Beacon → Server | checkin\|{beacon_id}                        | Heartbeat without command request | beacon_id                     | "Check-in acknowledged"          |
| `keylogger_output`  | Beacon → Server | keylogger_output\|{beacon_id}\|{keystrokes} | Submit keylogger data             | beacon_id, encoded_keystrokes | None (logged)                    |
| `to_beacon`         | Server → Beacon | to_beacon\|{filename}                       | Download file to beacon           | filename                      | File transfer                    |
| `from_beacon`       | Beacon → Server | from_beacon\|{filename}                     | Upload file from beacon           | filename                      | File transfer                    |
| `download_complete` | Beacon → Server | download_complete\|{beacon_id}\|{filename}  | Report successful download        | beacon_id, filename           | None (logged)                    |
| `download_failed`   | Beacon → Server | download_failed\|{beacon_id}\|{filename}    | Report failed download            | beacon_id, filename           | None (logged)                    |


## 2. Registration and Heartbeat Commands

### Beacon Registration
```
register|{beacon_id}|{computer_name}
```

**Purpose**: Initial beacon registration with the C2 server  
**Parameters**:
- `beacon_id`: Unique identifier for the beacon (8-16 chars, alphanumeric)
- `computer_name`: System hostname/computer name

**Server Response**: `"Registration successful"` or error message  
**Implementation**: Required by all receivers

**Example**:
```
register|a1b2c3d4|DESKTOP-ABC123
```

### Action Request (Primary Heartbeat)
```
request_action|{beacon_id}
```

**Purpose**: Beacon requests pending commands from server  
**Parameters**:
- `beacon_id`: Beacon identifier

**Server Response**: Queued command or `"no_pending_commands"`  
**Frequency**: Every 15-60 seconds (configurable)

**Example**:
```
request_action|a1b2c3d4
```

### Simple Check-in
```
checkin|{beacon_id}
```

**Purpose**: Status heartbeat without requesting commands  
**Parameters**:
- `beacon_id`: Beacon identifier

**Server Response**: `"Check-in acknowledged"`  
**Usage**: Lightweight status updates

## 3. Command Execution Standards

### Direct Command Execution
```
execute_command|{command}
```

**Purpose**: Execute arbitrary system commands  
**Direction**: Server → Beacon  
**Parameters**:
- `command`: Raw OS command string

**Usage**: Direct shell/cmd execution (e.g., `whoami`, `systeminfo`, `ls -la`)

**Example**:
```
execute_command|whoami
```

### Module Execution
```
execute_module|{module_name}|{parameters}
```

**Purpose**: Execute predefined beacon modules with structured parameters  
**Direction**: Server → Beacon  
**Parameters**:
- `module_name`: Name of the module to execute
- `parameters`: Comma-separated parameter list (optional)

**Examples**:
```
execute_module|BasicRecon
execute_module|PortScanner|192.168.1.1-254,80,443,3389
execute_module|EncryptDirectory|C:\temp,txt,MySecretKey123
```

## 4. Command Output Reporting

### Standard Command Output
```
command_output|{beacon_id}|{output}
```

**Purpose**: Beacon reports command execution results  
**Direction**: Beacon → Server  
**Parameters**:
- `beacon_id`: Beacon identifier
- `output`: Command output (stdout/stderr combined)

**Server Processing**: 
- Logged to `output_{beacon_id}.txt` in logs directory
- Clears pending command for the beacon
- Updates last response timestamp

**Example**:
```
command_output|a1b2c3d4|DESKTOP-ABC123\user1
```

### Keylogger Output
```
keylogger_output|{beacon_id}|{encoded_keystrokes}
```

**Purpose**: Specialized output for keylogger data  
**Direction**: Beacon → Server  
**Parameters**:
- `beacon_id`: Beacon identifier
- `encoded_keystrokes`: URL-encoded keystroke data

**Encoding**:
- `%20` = Space
- `%0A` = Newline
- `%09` = Tab
- Special characters URL-encoded for safe transmission

**Server Processing**: Logged to `keylogger_output_{beacon_id}.txt`

## 5. File Transfer Protocol

### Download Request (Server to Beacon)
```
to_beacon|{filename}
```

**Purpose**: Beacon downloads file from server  
**Direction**: Server → Beacon  
**Parameters**:
- `filename`: Name of file in server's files directory

**Process Flow**:
1. Server sends `to_beacon|filename`
2. Server immediately begins sending file data in chunks
3. Beacon receives and reassembles file
4. Optional: Beacon reports completion status

**Supported Transports**: TCP, SMB  
**Not Supported**: UDP (returns ERROR)

### Upload Request (Beacon to Server)
```
from_beacon|{filename}
```

**Purpose**: Beacon uploads file to server  
**Direction**: Beacon → Server  
**Parameters**:
- `filename`: Name of file being uploaded

**Process Flow**:
1. Beacon sends `from_beacon|filename`
2. Server responds `"READY"`
3. Beacon sends file data in chunks
4. Server responds `"SUCCESS"` or `"ERROR|details"`

**Supported Transports**: TCP, SMB  
**Not Supported**: UDP (returns ERROR)

### File Transfer Status
```
download_complete|{beacon_id}|{filename}
download_failed|{beacon_id}|{filename}
```

**Purpose**: Beacon reports file transfer status  
**Direction**: Beacon → Server  
**Usage**: Optional status reporting for file operations

## 6. Schema-Driven Command Templates

Commands are defined in YAML schemas with standardized templates:

### Basic Command Template
```yaml
command_template: '{command}'
```
**Result**: Direct parameter substitution

### Module Template
```yaml
command_template: 'execute_module|ModuleName|{param1},{param2}'
```
**Result**: Structured module execution with parameters

### Examples from AutoHotkey Schema
```yaml
# Simple module
command_template: 'execute_module|BasicRecon'

# Parameterized module
command_template: 'execute_module|PortScanner|{target_ips},{ports},{timeout},{threads}'

# Complex module
command_template: 'execute_module|EncryptDirectory|{directory_path},{file_extensions},{encryption_key}'
```

## 7. Receiver-Specific Implementation Notes

### TCP Receiver
- **Full Protocol Support**: All commands supported
- **Connection Type**: Persistent socket connections
- **File Transfers**: Full chunked transfer with progress tracking
- **Threading**: Multi-threaded connection handling
- **Encoding**: All encoding strategies supported

### UDP Receiver
- **Limited Protocol Support**: No file transfers
- **Connection Type**: Stateless datagram processing
- **File Transfers**: Returns `"ERROR|File transfer not supported over UDP"`
- **Threading**: Single-threaded datagram handling
- **Encoding**: All encoding strategies supported
- **Use Case**: Lightweight command execution and status updates

### SMB Receiver
- **Full Protocol Support**: All commands supported
- **Connection Type**: Named pipes (Windows) / FIFOs (Unix)
- **File Transfers**: Custom pipe-based chunked transfer
- **Platform Differences**: 
  - Windows: Native named pipes (`\\.\pipe\{name}`)
  - Unix: FIFO simulation (`/tmp/beaconator_c2_pipes/{name}`)
- **Encoding**: All encoding strategies supported

### Metasploit Receiver
- **Special Integration**: Monitors Metasploit sessions as beacons
- **Auto-Registration**: Sessions register automatically as `msf_session_{id}`
- **Limited Interaction**: Primarily read-only monitoring
- **Command Injection**: Supports shellcode injection via `inject_shellcode|{base64_data}`

## 8. Encoding Strategies

All receivers support pluggable encoding for data obfuscation:

### Available Strategies
- **PlainText**: No encoding (UTF-8)
- **Base64**: Standard base64 encoding
- **XOR**: XOR encryption with configurable key

### Application
- Command transmission (both directions)
- File transfer data
- Response messages

### Configuration
```python
# Example encoding strategy instantiation
encoding_strategy = Base64Encoding()
encoded_data = encoding_strategy.encode(b"command_data")
```

## 9. Error Handling Standards

### Standard Error Response Format
```
ERROR|{error_description}
```

### Common Error Patterns
- `ERROR|File transfer not supported over UDP`
- `ERROR|File not found`
- `ERROR|Invalid command format`
- `ERROR|Connection timeout`

## 10. Best Practices for Implementation

### For Receiver Developers
1. **Implement Core Commands**: Register, request_action, checkin, command_output
2. **Handle File Transfers**: Implement to_beacon/from_beacon or return appropriate errors
3. **Support Encoding**: Use provided encoding strategy interfaces
4. **Error Handling**: Return standardized error messages
6. **Logging**: Log all communications for debugging

### For Beacon Developers
1. **Generate Unique IDs**: Use system info + script path if desired, but the manager will accept most things.
2. **Implement Heartbeat**: Regular request_action calls (15-60 seconds)
3. **Handle All Response Types**: Commands, file transfers, errors
4. **Support Protocol Switching**: Allow runtime protocol configuration
5. **Graceful Degradation**: Handle unsupported features (e.g., UDP file transfers)

### For Schema Developers
1. **Use Standard Templates**: Follow execute_command vs execute_module patterns
2. **Parameter Validation**: Define proper validation rules
3. **Clear Documentation**: Provide examples and usage notes
4. **Platform Awareness**: Note platform-specific limitations

## 11. Testing and Validation

### Required Test Cases
1. **Basic Registration**: Beacon successfully registers and appears in UI
2. **Command Execution**: Both execute_command and execute_module work
3. **File Transfers**: Upload/download work for supported protocols
4. **Error Handling**: Unsupported operations return proper errors
5. **Protocol Switching**: Same beacon works across different receivers
6. **Encoding**: All encoding strategies function correctly

### Validation Checklist
- [ ] Beacon registers successfully
- [ ] Commands execute and return output
- [ ] File transfers work (TCP/SMB only)
- [ ] Encoding/decoding functions properly
- [ ] Logs are generated correctly


