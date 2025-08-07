# BeaconatorC2 Architecture Documentation

## Overview

BeaconatorC2 is a command and control (C2) framework for security testing and assessment. The application uses a layered architecture with schema-driven module execution and modular receiver management.

The system manages beacons (remote agents) through a GUI interface, with capabilities across reconnaissance, evasion, privilege escalation, persistence, lateral movement, and impact assessment.

## Project Structure

```
BeaconatorC2/
├── BeaconatorC2-Manager.py      # Main application entry point
├── requirements.txt             # Python package dependencies
├── settings.json               # Application configuration file
├── config/
│   ├── __init__.py
│   ├── config_manager.py                   # Configuration persistence management
│   └── server_config.py                    # Server configuration dataclass
├── configs/
│   ├── __init__.py
│   └── receivers.json                      # Receiver configuration storage
├── database/
│   ├── __init__.py
│   ├── models.py                           # SQLAlchemy Beacon model
│   ├── repository.py                       # Beacon database operations
│   └── setup.py                            # Database initialization
├── services/
│   ├── __init__.py
│   ├── command_processor.py                # Beacon command processing and queuing
│   ├── file_transfer.py                    # File upload/download operations
│   ├── schema_service.py                   # Dynamic schema loading and caching
│   ├── custom_msf_rpc.py                   # Native Metasploit RPC client with session handling
│   ├── metasploit_manager.py               # Metasploit process lifecycle management
│   ├── metasploit_service.py               # High-level Metasploit integration service
│   └── receivers/                          # Extensible receiver system
│       ├── __init__.py
│       ├── receiver_manager.py             # Receiver lifecycle and coordination
│       ├── receiver_registry.py            # Dynamic receiver loading system
│       ├── base_receiver.py                # Abstract receiver base class
│       ├── tcp_receiver.py                 # TCP receiver implementation
│       ├── udp_receiver.py                 # UDP receiver implementation
│       ├── smb_receiver.py                 # SMB named pipe receiver implementation
│       ├── http_receiver.py                # HTTP REST receiver implementation
│       ├── metasploit_receiver.py          # Metasploit integration receiver
│       ├── encoding_strategies.py          # Data encoding/decoding strategies
│       ├── receiver_config.py              # Receiver configuration and type definitions
│       └── legacy_migration.py             # Legacy system migration utilities
├── beacons/
│   ├── python_beacon.py                   # Multi-protocol Python beacon implementation
│   └── simple_python_beacon.py            # Lightweight beacon alternative
├── workers/
│   ├── __init__.py
│   ├── beacon_update_worker.py             # Background beacon status monitoring
│   ├── receiver_update_worker.py           # Background receiver status monitoring
│   ├── command_output_monitor.py           # Command output monitoring
│   └── keylogger_monitor.py                # Keylogger output processing
├── utils/
│   ├── __init__.py
│   ├── logger.py                           # Logging system with PyQt6 signals
│   ├── documentation_manager.py            # Documentation content management
│   ├── font_manager.py                     # Application-wide font management
│   └── helpers.py                          # Utility functions and payload handling
├── schemas/
│   ├── beacon_schema_format.yaml           # Schema format specification
│   ├── autohotkey_beacon.yaml              # Default AutoHotkey beacon schema
│   ├── python_beacon.yaml                 # Multi-protocol Python beacon schema
│   ├── simple_python_beacon.yaml          # Simple beacon schema definition
│   └── SCHEMA_REFERENCE.md                 # Schema documentation
└── ui/
    ├── __init__.py
    ├── main_window.py                      # Main application window
    ├── components/
    │   ├── __init__.py
    │   ├── beacon_table.py                 # Beacon list display with QAbstractTableModel
    │   ├── command_widget.py               # Dynamic schema-driven command interface
    │   ├── navigation_menu.py              # Collapsible sidebar navigation
    │   ├── file_transfer_widget.py         # File transfer interface
    │   ├── settings_page.py                # Application settings
    │   ├── documentation_panel.py          # Help documentation with YAML editor
    │   ├── beacon_settings_widget.py       # Beacon management and schema assignment
    │   ├── receivers_widget.py             # Registry-driven receiver management interface
    │   ├── receiver_config_dialog.py       # Dynamic receiver configuration dialog
    │   └── metasploit_widget.py            # Metasploit integration interface with tabs
    └── widgets/
        ├── __init__.py
        ├── log_widget.py                   # Console log with syntax highlighting
        ├── output_display.py              # Command output display
        └── keylogger_display.py           # Keylogger output display
```

## Component Descriptions and Purposes

### **Entry Point**
- **`BeaconatorC2-Manager.py`** - Main application launcher with service initialization

### **Configuration Layer**
- **`config/server_config.py`** - Contains `ServerConfig` dataclass with application settings (ports, paths, timeouts)
- **`config/config_manager.py`** - `ConfigManager` class for persistent configuration storage and retrieval

### **Database Layer**
- **`database/models.py`** - SQLAlchemy `Beacon` model defining beacon properties (beacon_id, computer name, status, timestamps, schema assignments, receiver tracking)
- **`database/repository.py`** - `BeaconRepository` class implementing repository pattern for all beacon database operations (CRUD, status updates, command queuing, schema management, per-receiver tracking)
- **`database/setup.py`** - Database initialization and table creation

### **Service Layer**
- **`services/command_processor.py`** - Handles beacon command validation, queuing, and execution coordination
- **`services/file_transfer.py`** - Manages file upload/download operations with progress tracking  
- **`services/schema_service.py`** - Schema loading, parsing, validation, and caching

#### **Receiver System Architecture**
- **`services/receivers/receiver_manager.py`** - Central orchestrator managing receiver lifecycle, threading, and graceful shutdown with registry integration
- **`services/receivers/receiver_registry.py`** - Dynamic receiver loading system implementing registry pattern for extensible receiver management
- **`services/receivers/base_receiver.py`** - Abstract base class providing unified data processing, encoding integration, and common receiver functionality
- **`services/receivers/tcp_receiver.py`** - TCP receiver implementation with threading, connection management, and unified data processing
- **`services/receivers/udp_receiver.py`** - UDP receiver implementation with stateless datagram processing and connection handling
- **`services/receivers/smb_receiver.py`** - SMB named pipe receiver supporting Windows (win32pipe) and Unix (FIFO) implementations
- **`services/receivers/http_receiver.py`** - HTTP REST receiver implementation supporting GET/POST requests with root path communication
- **`services/receivers/metasploit_receiver.py`** - Specialized receiver for Metasploit Framework integration and session management
- **`services/receivers/encoding_strategies.py`** - Pluggable encoding/decoding strategies (Plain, Base64, XOR) implementing strategy pattern
- **`services/receivers/receiver_config.py`** - Receiver configuration dataclasses, validation, and type definitions with registry mappings
- **`services/receivers/legacy_migration.py`** - Utilities for migrating from legacy server architecture

#### **Metasploit Integration**
- **`services/custom_msf_rpc.py`** - Native Metasploit RPC client with session timeout handling, automatic retry logic, and comprehensive error parsing
- **`services/metasploit_manager.py`** - Metasploit Framework process lifecycle management with automatic startup, health monitoring, and installation validation
- **`services/metasploit_service.py`** - High-level Metasploit integration service with payload generation, listener management, session monitoring, and automatic session recovery

### **Beacon Implementations**
- **`beacons/python_beacon.py`** - Multi-protocol Python beacon supporting TCP, UDP, SMB, and HTTP communication with file transfer capabilities
- **`beacons/simple_python_beacon.py`** - Lightweight beacon implementation with minimal dependencies and basic command execution

### **Background Workers**
- **`workers/beacon_update_worker.py`** - Background thread monitoring beacon heartbeats and updating status
- **`workers/receiver_update_worker.py`** - Background thread monitoring receiver status and statistics
- **`workers/command_output_monitor.py`** - Monitors and processes command output from connected beacons
- **`workers/keylogger_monitor.py`** - Specialized worker for processing keylogger output streams

### **Configuration Management**
- **`config/server_config.py`** - Contains `ServerConfig` dataclass with application settings (ports, paths, timeouts)
- **`config/config_manager.py`** - `ConfigManager` class for persistent configuration storage and retrieval
- **`configs/receivers.json`** - JSON-based receiver configuration storage and persistence
- **`settings.json`** - Application-wide configuration file for UI preferences
- **`requirements.txt`** - Python package dependencies specification

### **Schema System**
- **`schemas/beacon_schema_format.yaml`** - Defines the structure and validation rules for beacon schemas
- **`schemas/autohotkey_beacon.yaml`** - Complete schema definition for AutoHotkey-based beacon
- **`schemas/python_beacon.yaml`** - Multi-protocol Python beacon schema supporting TCP, UDP, SMB, and HTTP protocols
- **`schemas/simple_python_beacon.yaml`** - Lightweight beacon schema with minimal command set
- **`schemas/SCHEMA_REFERENCE.md`** - Comprehensive documentation for schema creation and modification

### **Utilities**
- **`utils/logger.py`** - PyQt6-based logging system with file rotation and GUI signal emission
- **`utils/documentation_manager.py`** - Manages help documentation content and navigation
- **`utils/font_manager.py`** - Singleton font manager providing consistent typography across the application
- **`utils/helpers.py`** - Common utility functions for file operations and data processing

### **User Interface**

#### **Main Window**
- **`ui/main_window.py`** - Primary application window with 2x2 grid layout, direct service injection

#### **Core Components**
- **`ui/components/beacon_table.py`** - Beacon list using QAbstractTableModel with status indicators
- **`ui/components/command_widget.py`** - Schema-driven command interface with lazy loading and tree navigation
- **`ui/components/navigation_menu.py`** - Collapsible sidebar navigation
- **`ui/components/file_transfer_widget.py`** - File upload/download interface with progress tracking
- **`ui/components/settings_page.py`** - Application configuration interface
- **`ui/components/documentation_panel.py`** - Help panel with module documentation and YAML editor
- **`ui/components/beacon_settings_widget.py`** - Beacon management and schema assignment with dynamic tab visibility
- **`ui/components/receivers_widget.py`** - Registry-driven receiver management interface with dynamic type support, status monitoring, and enhanced metadata display
- **`ui/components/receiver_config_dialog.py`** - Dynamic receiver configuration dialog with registry-based type population and enhanced descriptions
- **`ui/components/metasploit_widget.py`** - Metasploit integration interface with tabbed design for payload generation, listener management, session monitoring, and connection diagnostics

#### **Display Widgets**
- **`ui/widgets/log_widget.py`** - Console log with syntax highlighting
- **`ui/widgets/output_display.py`** - Command output display
- **`ui/widgets/keylogger_display.py`** - Keylogger output display

## Multi-Protocol Communication Architecture

BeaconatorC2 implements multiple communication protocols for diverse operational environments and beacon deployment scenarios. The system supports TCP, UDP, SMB, and HTTP protocols with unified command processing.

### **Universal Protocol Features**

**Common Message Format:**
```
command|parameter1|parameter2|parameter3|...
```

**Core Commands (All Protocols):**
- `register|beacon_id|computer_name` - Initial beacon registration with system identification
- `request_action|beacon_id` - Beacon requests pending commands from server
- `command_output|beacon_id|output_data` - Beacon submits command execution results
- `keylogger_output|beacon_id|keylog_data` - Beacon submits keylogger capture data
- `checkin|beacon_id` - Periodic beacon heartbeat for status monitoring
- `to_beacon|filename` - Server initiates file download to beacon
- `from_beacon|filename` - Beacon initiates file upload to server

### **HTTP Communication Protocol**

**RESTful Architecture:**
- **Endpoint**: Root path `/` for clean URL structure
- **Methods**: GET (query parameters) and POST (request body) support
- **Content Types**: `application/octet-stream` for binary data, query parameters for simple commands
- **Status Codes**: Standard HTTP response codes for error handling

**HTTP Request Patterns:**
```http
POST / HTTP/1.1
Content-Type: application/octet-stream
User-Agent: BeaconatorC2-Beacon/agent_id

register|beacon_id|computer_name
```

**Response Handling:**
- **Success Responses**: HTTP 200 with response data in body
- **Error Responses**: Appropriate HTTP status codes (400, 404, 500) with error details
- **File Transfers**: Content-Disposition headers for file downloads

### **TCP Communication Protocol**

BeaconatorC2's TCP implementation provides reliable, connection-oriented communication with optimized performance for sustained operations.

#### **Protocol Structure**

**Message Format:**
```
command|parameter1|parameter2|parameter3|...
```

**Core Commands:**
- `register|beacon_id|computer_name` - Initial beacon registration with system identification
- `request_action|beacon_id` - Beacon requests pending commands from server
- `command_output|beacon_id|output_data` - Beacon submits command execution results
- `keylogger_output|beacon_id|keylog_data` - Beacon submits keylogger capture data
- `checkin|beacon_id` - Periodic beacon heartbeat for status monitoring
- `to_beacon|filename` - Server initiates file download to beacon
- `from_beacon|filename` - Beacon initiates file upload to server

**Response Formatting:**
```python
# File operations: action|parameter
"download_file|document.pdf" → "download_file|document.pdf"

# Module execution: execute_module|module_data
"execute_module|reconnaissance_data" → "execute_module|reconnaissance_data"

# Standard commands: execute_command|command_string
"whoami" → "execute_command|whoami"
```

#### **File Transfer System Architecture**

**Optimized Chunking System:**

**Transfer Configuration:**
- **Chunk Size**: 1,048,576 bytes (1MB chunks)
- **Socket Buffers**: 1MB send/receive buffers for optimal throughput
- **Progress Tracking**: Logging every MB transferred for monitoring
- **Error Recovery**: Comprehensive error handling with status reporting

**File Upload Process (from beacon):**
```
1. Beacon sends: "from_beacon|filename"
2. Server responds: "READY"
3. Beacon transmits file in 1MB chunks
4. Server writes chunks to secure filename
5. Server confirms: "SUCCESS" or "ERROR|details"
```

**File Download Process (to beacon):**
```
1. Beacon sends: "to_beacon|filename"
2. Server validates file existence
3. Server transmits file in 1MB chunks
4. Progress logged every 1MB transferred
5. Transfer completion logged with total size
```

### **UDP Communication Protocol**

**Stateless Architecture:**
- **Datagram-Based**: Each command sent as independent UDP datagram
- **No Connection State**: Server processes each datagram independently
- **Timeout Handling**: Client-side timeout and retry logic for reliability
- **File Transfer Restrictions**: File operations rejected with appropriate error messages

**UDP Packet Structure:**
```
UDP Datagram: command|parameter1|parameter2|...
Response: response_data (separate UDP datagram)
```

### **SMB Communication Protocol**

**Named Pipe Architecture:**
- **Windows Implementation**: Win32 named pipes with proper authentication
- **Unix Implementation**: FIFO-based simulation for cross-platform support
- **Persistent Sessions**: Maintained pipe connections for multiple commands

**Platform-Specific Details:**
```python
# Windows Named Pipe
pipe_path = f"\\\\.\\pipe\\{pipe_name}"

# Unix FIFO
pipe_path = f"/tmp/beaconator_c2_pipes/{pipe_name}"
```

**Connection Flow:**
1. **Pipe Creation**: Server creates named pipe or FIFO
2. **Client Connection**: Beacon connects to named pipe
3. **Command Exchange**: Bidirectional communication through pipe
4. **Session Management**: Persistent connection for multiple commands

## Receiver Architecture

### **Receiver Registry System**

The BeaconatorC2 framework implements an extensible receiver architecture using the registry pattern, enabling zero-code addition of new receiver types through configuration-driven loading.

#### **Core Registry Components**

**ReceiverRegistry (`services/receivers/receiver_registry.py`)**
- **Dynamic Receiver Loading**: Implements factory pattern with on-demand module importing
- **Configuration-Driven Mapping**: Uses `RECEIVER_MAPPINGS` dictionary for receiver type definitions
- **Type Safety**: Validates receiver classes inherit from `BaseReceiver` before instantiation
- **Error Isolation**: Import failures for one receiver type don't affect others
- **Metadata Support**: Stores receiver descriptions and capabilities for UI integration
- **Singleton Pattern**: Global registry instance with thread-safe operations

```python
class ReceiverRegistry:
    def create_instance(self, receiver_type: ReceiverType, config: ReceiverConfig, 
                       encoding_strategy: EncodingStrategy) -> BaseReceiver:
        receiver_class = self._load_receiver_class(receiver_type)
        return receiver_class(config, encoding_strategy)
```

**Registry Configuration (`services/receivers/receiver_config.py`)**
```python
RECEIVER_MAPPINGS = {
    ReceiverType.TCP: {
        "module": "services.receivers.tcp_receiver",
        "class": "TCPReceiver",
        "description": "TCP socket receiver for direct network communication"
    },
    ReceiverType.HTTP: {
        "module": "services.receivers.http_receiver", 
        "class": "HTTPReceiver",
        "description": "HTTP REST receiver for web-based communication"
    }
    # Additional receiver types...
}
```

#### **BaseReceiver Abstraction**

**Unified Data Processing (`services/receivers/base_receiver.py`)**
- **Abstract Base Class**: Defines common interface for all receiver implementations
- **Unified Command Processing**: `process_received_data()` method provides transport-agnostic command handling
- **Encoding Integration**: Automatic encoding/decoding using strategy pattern
- **Statistics Collection**: Thread-safe statistics tracking with real-time updates
- **Signal-Based Communication**: PyQt6 signals for UI integration and status updates
- **Lifecycle Management**: Standardized start/stop/restart operations

```python
def process_received_data(self, raw_data: bytes, client_info: Dict[str, Any]) -> tuple[bytes, bool]:
    """Transport-agnostic data processing returning response and connection persistence flag"""
    decoded_data = self.encoding_strategy.decode(raw_data)
    # Process commands, generate responses, handle file transfers
    return response_bytes, keep_connection_alive
```

### **Multi-Protocol Receiver Implementations**

#### **HTTP Receiver (`services/receivers/http_receiver.py`)**
- **RESTful Communication**: Supports GET and POST methods with query parameter handling
- **Root Path Endpoint**: Uses `/` as default endpoint for clean URL structure
- **HTTP Standards Compliance**: Proper status codes, headers, and content types
- **File Transfer Support**: HTTP-based file upload/download with multipart handling
- **Request Routing**: Validates endpoint paths and method compatibility

#### **UDP Receiver (`services/receivers/udp_receiver.py`)**
- **Stateless Communication**: Each datagram processed independently
- **Connection Simulation**: Treats each datagram as a temporary "connection" for statistics
- **File Transfer Restrictions**: Properly rejects file transfer requests over UDP
- **Error Handling**: Robust error handling for malformed datagrams

#### **SMB Receiver (`services/receivers/smb_receiver.py`)**
- **Cross-Platform Support**: Windows named pipes (win32pipe) and Unix FIFOs
- **Persistent Connections**: Maintains pipe connections for multiple command exchanges
- **Platform Detection**: Automatic selection of Windows vs Unix implementation
- **Enhanced Security**: Proper file permissions and access control for FIFOs

#### **TCP Receiver (`services/receivers/tcp_receiver.py`)**
- **Enhanced with Unified Processing**: Migrated to use `BaseReceiver.process_received_data()`
- **Connection Management**: Threading with configurable timeouts and keep-alive
- **File Transfer Optimization**: Large file support with chunked transfer
- **Socket Optimization**: Buffer size tuning for performance

### **Encoding Strategies System**

**Strategy Pattern Implementation (`services/receivers/encoding_strategies.py`)**
- **Pluggable Encoding**: Abstract `EncodingStrategy` base class for extensible encoding support
- **Multiple Algorithms**: Plain text, Base64, and XOR encoding implementations
- **Configuration Support**: Strategy-specific configuration (XOR keys, rotation values)
- **Transparent Integration**: Automatic encoding/decoding in BaseReceiver

```python
class XOREncoding(EncodingStrategy):
    def __init__(self, key: str):
        self.key = key.encode('utf-8')
    
    def encode(self, data: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(data, itertools.cycle(self.key)))
```

### **Receiver Manager Integration**

**Registry-Driven Management (`services/receivers/receiver_manager.py`)**
- **Zero-Code Extensibility**: New receiver types require only registry mapping entry
- **Dynamic Type Discovery**: UI components query registry for supported types
- **Enhanced Error Handling**: Registry validates receiver availability before creation
- **Metadata Integration**: Registry descriptions displayed in UI tooltips and help

```python
def _create_receiver_instance(self, config: ReceiverConfig, encoding_strategy) -> Optional[BaseReceiver]:
    return self.receiver_registry.create_instance(config.receiver_type, config, encoding_strategy)
```

## Traditional Receiver Management (Legacy)

### **Receiver System Components**

**ReceiverManager (`services/receivers/receiver_manager.py`)**
- Central coordinator for all receiver instances with registry integration
- Manages receiver lifecycle (start, stop, restart, remove)
- Provides statistics aggregation and status monitoring
- Handles configuration persistence and validation
- Implements signal-based communication with UI components

**Receiver Configuration (`services/receivers/receiver_config.py`)**
- Dataclass-based configuration management with registry mappings
- Supports multiple receiver types and encoding strategies
- Provides validation and serialization methods
- Handles defensive programming for type consistency

### **Configuration Management**

**Receiver Configuration Storage:**
```json
{
  "receivers": [
    {
      "receiver_id": "unique-identifier",
      "name": "Display Name",
      "receiver_type": "tcp",
      "enabled": true,
      "auto_start": true,
      "host": "0.0.0.0",
      "port": 5074,
      "buffer_size": 4096,
      "timeout": 60,
      "encoding_type": "plain",
      "encoding_config": {},
      "protocol_config": {},
      "max_connections": 100,
      "connection_timeout": 300,
      "keep_alive": true,
      "description": "Receiver description",
      "tags": [],
      "created_at": "timestamp",
      "modified_at": "timestamp"
    }
  ]
}
```

### **Receiver Operations**

**Background Operations:**
- Non-blocking receiver start/stop/restart operations
- Progress indication with loading spinners
- Error handling with user feedback
- Thread-safe statistics collection

**Status Monitoring:**
- Real-time receiver health checks
- Connection count tracking
- Data transfer statistics
- Per-receiver beacon counting

## Multi-Protocol Beacon Architecture

### **Beacon Implementations**

BeaconatorC2 provides multiple beacon implementations supporting diverse communication protocols and deployment scenarios.

#### **Python Beacon (`beacons/python_beacon.py`)**

**Multi-Protocol Support:**
- **TCP Communication**: Direct socket-based communication with persistent connections
- **UDP Communication**: Stateless datagram communication with timeout handling
- **SMB Communication**: Named pipe communication supporting Windows (win32pipe) and Unix (FIFO)
- **HTTP Communication**: RESTful communication using root path `/` endpoint with GET/POST support

**Protocol Selection:**
```python
python beacon.py --protocol http --server 192.168.1.100 --port 8080 --endpoint /
python beacon.py --protocol tcp --server 192.168.1.100 --port 5074
python beacon.py --protocol udp --server 192.168.1.100 --port 5075
python beacon.py --protocol smb --server 192.168.1.100 --pipe BeaconatorC2_5074
```

**Core Capabilities:**
- **Command Execution**: System command execution with output capture and timeout handling
- **File Transfer**: Upload/download operations with protocol-specific implementations
- **Registration System**: Automatic beacon registration with unique agent ID generation
- **Heartbeat Monitoring**: Configurable check-in intervals with server communication
- **Error Handling**: Comprehensive error handling with protocol-specific recovery

**Agent ID Generation:**
```python
def generate_agent_id(self):
    system_info = f"{platform.node()}{platform.system()}{username}{mac_address}{script_path}"
    return hashlib.md5(system_info.encode()).hexdigest()[:8]
```

#### **Simple Python Beacon (`beacons/simple_python_beacon.py`)**

**Lightweight Design:**
- **Minimal Dependencies**: Reduced external library requirements for broad compatibility
- **Basic Command Set**: Essential command execution and communication capabilities
- **Simplified Protocol Support**: Focus on TCP communication with optional protocol extensions
- **Reduced Footprint**: Smaller file size and memory consumption for constrained environments

### **Protocol-Specific Implementations**

#### **HTTP Protocol Implementation**
- **Endpoint Configuration**: Configurable endpoint path (default: `/`)
- **Method Support**: GET requests with query parameters, POST requests with body data
- **Content Handling**: Proper Content-Type headers and response formatting
- **File Transfer**: HTTP-based file upload via POST and download via GET
- **Error Responses**: Standard HTTP status codes for error conditions

#### **TCP Protocol Implementation** 
- **Persistent Connections**: Long-lived socket connections with keep-alive
- **Binary Protocol**: Efficient binary communication with minimal overhead
- **Connection Management**: Automatic reconnection and timeout handling
- **Streaming Support**: Large file transfer with streaming capabilities

#### **UDP Protocol Implementation**
- **Stateless Design**: Each request/response independent of previous communications
- **Reliability Handling**: Application-level acknowledgment and retry mechanisms
- **Broadcast Support**: Potential for broadcast and multicast communication patterns
- **Firewall Traversal**: Enhanced NAT and firewall traversal capabilities

#### **SMB Protocol Implementation**
- **Named Pipes**: Windows named pipe communication with proper authentication
- **FIFO Support**: Unix FIFO-based communication for cross-platform compatibility
- **Persistence**: Maintains pipe connections across multiple command exchanges
- **Security**: Proper access control and permission management

### **Beacon Configuration and Management**

**Schema Integration:**
- **Dynamic Capabilities**: Beacon capabilities defined in YAML schema files
- **Protocol-Aware Schemas**: Schema definitions include supported protocols and features
- **Tab Visibility Control**: UI components dynamically show/hide features based on beacon capabilities
- **Version Management**: Schema versioning for backward compatibility

**Runtime Configuration:**
```yaml
beacon_info:
  beacon_type: python_beacon
  supported_protocols: [tcp, udp, smb, http]
  file_transfer_supported: true
  keylogger_supported: true
```

## Dynamic Schema System Architecture

### **Schema-Driven Module Execution**

The BeaconatorC2 framework implements schema-driven architecture that enables dynamic module loading, parameter validation, and UI generation.

#### **Core Schema Components**

**1. Schema Service (`services/schema_service.py`)**
- **SchemaService**: Main orchestrator for schema loading and management
- **AgentSchema**: Complete schema representation with categories and modules  
- **Module**: Individual command definition with parameters, documentation, and execution settings
- **ModuleParameter**: Type-safe parameter definitions with validation rules
- **ParameterType**: Enumerated parameter types (text, textarea, integer, float, boolean, choice, file, directory)

**2. Schema Caching System**
- **SchemaCache**: Intelligent file-based caching with automatic invalidation
- **SchemaCacheEntry**: Cache entry with file modification time tracking
- **Selective Invalidation**: Module-level cache updates for optimal performance

#### **Schema File Structure**

```yaml
schema_version: "1.1"
beacon_info:
  beacon_type: "autohotkey_beacon"
  version: "1.0.0"
  description: "Default AutoHotkey C2 beacon"
  supported_platforms: ["windows"]

categories:
  basic_commands:
    display_name: "Basic Commands"
    description: "Fundamental command execution capabilities"
    modules:
      command_execution:
        display_name: "Command Execution"
        description: "Execute arbitrary system commands"
        command_template: "{command}"
        parameters:
          command:
            type: "textarea"
            display_name: "Command"
            description: "Enter command to execute on the target system"
            required: true
            validation:
              min_length: 1
              max_length: 8192
        documentation:
          content: "Execute system commands directly on the target machine..."
          examples: ["whoami", "systeminfo", "dir C:\\"]
        execution:
          timeout: 300
          requires_admin: false
        ui:
          layout: "simple"
```

#### **Parameter Type System**

**Supported Parameter Types:**
- **TEXT**: Single-line text input with length and pattern validation
- **TEXTAREA**: Multi-line text input for scripts and longer content
- **INTEGER**: Numeric input with min/max value constraints
- **FLOAT**: Decimal number input with precision validation
- **BOOLEAN**: Checkbox input for true/false values
- **CHOICE**: Dropdown selection from predefined options
- **FILE**: File browser with extension filtering
- **DIRECTORY**: Directory browser with path validation

**Validation Framework:**
- **Length Constraints**: min_length, max_length for text inputs
- **Value Constraints**: min_value, max_value for numeric inputs  
- **Pattern Matching**: Regular expression validation for text formats
- **Required Fields**: Mandatory parameter enforcement
- **Default Values**: Pre-populated parameter values

#### **UI Layout System**

**Layout Types:**
- **Simple**: Single-column parameter layout
- **Advanced**: Grouped parameters with logical organization
- **Tabbed**: Multi-tab interface for complex modules

**Grouping Support:**
```yaml
ui:
  layout: "advanced"
  grouping:
    - ["target_ips", "ports"]      # Network configuration group
    - ["timeout", "threads"]       # Execution parameters group
```

### **Dynamic UI Generation**

#### **Command Widget Architecture**

The `CommandWidget` (`ui/components/command_widget.py`) implements dynamic UI generation:

**1. Schema Loading and Caching**
```python
def load_schema(self, schema_file: str):
    """Load and apply a schema with intelligent caching"""
    self.current_schema = self.schema_service.load_schema(schema_file)
    self.build_navigation_tree()

def get_module_yaml_data(self, category_name: str, module_name: str) -> dict:
    """Extract YAML data using efficient caching"""
    schema_file = self.current_schema.schema_file if self.current_schema else self._loaded_schema_file
    return self.schema_service.get_module_yaml_data(schema_file, category_name, module_name)
```

**2. Lazy Loading and Performance Optimization**
- **On-Demand Interface Creation**: Module interfaces created only when accessed
- **Smart UI Caching**: Built interfaces cached with schema version tracking
- **Efficient Navigation Tree**: Lightweight tree construction with deferred interface loading
- **Memory Management**: Automatic cleanup of unused interface objects

**3. Parameter Widget Generation**
```python
class ParameterWidget:
    """Dynamic parameter input widget based on schema definition"""
    def setup_widget(self):
        if self.parameter.type == ParameterType.TEXT:
            self.widget = QLineEdit()
            self.widget.setPlaceholderText(self.parameter.description)
        elif self.parameter.type == ParameterType.CHOICE:
            self.widget = QComboBox()
            self.widget.addItems(self.parameter.choices)
        # ... additional parameter types
```

### **Schema Caching System**

#### **Intelligent File Caching**

**Cache Architecture:**
```python
@dataclass
class SchemaCacheEntry:
    raw_data: Dict[str, Any]           # Parsed YAML content
    file_mtime: float                  # File modification timestamp
    parsed_schema: Optional['AgentSchema'] = None  # Compiled schema object

class SchemaCache:
    def get_raw_data(self, schema_file: str, schema_path: Path) -> Dict[str, Any]:
        # Check file modification time for automatic invalidation
        current_mtime = os.path.getmtime(schema_path)
        if schema_file in self._cache:
            cached_entry = self._cache[schema_file]
            if cached_entry.file_mtime == current_mtime:
                return cached_entry.raw_data  # Cache hit
        # Cache miss - reload file
```

**Cache Invalidation Strategies:**
- **File Modification Tracking**: Automatic invalidation when schema files change
- **Selective Updates**: Module-level cache updates without full reload
- **Manual Invalidation**: Explicit cache clearing for development workflows

**Performance Benefits:**
- **Reduced File I/O**: Schema files loaded only when modified
- **Faster UI Updates**: Cached schema data eliminates parsing overhead
- **Memory Efficiency**: Shared cache across all UI components

#### **Module-Level Caching**

**Granular Cache Updates:**
```python
def update_module_cache(self, schema_file: str, schema_path: Path, 
                       category_name: str, module_name: str, new_module_data: dict):
    """Update cached data for specific module without full file reload"""
    cached_data = self.get_raw_data(schema_file, schema_path)
    cached_data['categories'][category_name]['modules'][module_name] = new_module_data
    self._cache[schema_file].raw_data = cached_data
```

**Benefits:**
- **Efficient Save Operations**: Module edits update cache without full schema reload
- **Consistent State**: Cache remains synchronized with file system changes
- **Reduced Latency**: Immediate UI updates after module modifications

### **Documentation Panel Integration**

#### **YAML Editor with Schema Integration**

The Documentation Panel (`ui/components/documentation_panel.py`) provides schema editing capabilities:

**Features:**
- **Live YAML Editing**: Real-time syntax highlighting and validation
- **Save & Apply Functionality**: Immediate schema updates with cache integration
- **Module Documentation**: Contextual help with parameter descriptions
- **Schema Validation**: YAML syntax checking before save operations

**Save/Apply Workflow:**
```python
def apply_yaml_changes(self):
    """Apply YAML changes with cache integration"""
    # Save changes to file
    self.save_yaml_changes()
    
    # Invalidate cache and force UI reload
    schema_service.cache.invalidate(schema_file)
    self.command_widget.set_beacon(current_beacon_id, force_reload=True)
```
## Data Model Architecture

### **Beacon Model**

```python
class Beacon(Base):
    __tablename__ = 'beacon'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    beacon_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    computer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False, default='online')
    last_checkin: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    pending_command: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    output_file: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_response: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    schema_file: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    receiver_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
```

### **Repository Operations**

**Core Methods:**
```python
def get_beacon(self, beacon_id: str) -> Optional[Beacon]
def update_beacon_status(self, beacon_id: str, status: str, computer_name: Optional[str] = None, receiver_id: Optional[str] = None)
def update_beacon_command(self, beacon_id: str, command: Optional[str])
def get_online_beacons_count() -> int
def get_online_beacons_count_by_receiver(self, receiver_id: str) -> int
def mark_timed_out_beacons(self, timeout_minutes: int)
```

## System Dependencies and Requirements

### **Python Package Dependencies**

**Core Dependencies (`requirements.txt`):**
```
PyQt6>=6.8.0           # GUI framework for cross-platform desktop application
PyQt6-Qt6>=6.8.1       # Qt6 libraries and bindings for PyQt6
PyQt6_sip>=13.9.1      # SIP module for PyQt6 Python/C++ bindings
PyYAML>=6.0.2          # YAML parsing for schema files and configuration
SQLAlchemy>=2.0.37     # Database ORM for beacon persistence and management
Werkzeug>=3.1.3        # Utility library for secure filename handling and HTTP utilities
requests>=2.32.4       # HTTP library for external API communication and payload generation
msgpack>=1.0.8         # Binary serialization for Metasploit RPC communication
```

### **Platform Requirements**

**Operating System Support:**
- **Windows**: Windows 10/11 with optional pywin32 for SMB named pipe support
- **Linux**: Modern distributions with Python 3.8+ and Qt6 libraries

**Python Version:**
- **Minimum**: Python 3.8 for dataclass support and type annotations
- **Recommended**: Python 3.10+ for improved type hints and pattern matching
- **Compatibility**: Tested with Python 3.8, 3.9, 3.10, and 3.11

### **Optional Dependencies**

**Enhanced SMB Support (Windows):**
```python
# Optional for enhanced Windows SMB named pipe functionality
pywin32>=227  # Windows-specific APIs for named pipe management
```
### **External Tool Integration**

**Metasploit Framework (Optional):**
- **Installation**: Metasploit Framework 6.0+ for payload generation and session management
- **RPC Daemon**: msfrpcd for remote procedure call interface
- **Database**: PostgreSQL backend for Metasploit data persistence

## Data Flow Architecture

### **Beacon Registration Flow**
1. Beacon connects to TCP Receiver
2. ReceiverManager coordinates the connection
3. BeaconRepository stores beacon information
4. BeaconUpdateWorker begins monitoring
5. UI components receive updates via signals
6. Schema assignment enables module access

### **Schema Loading Flow**
1. BeaconSettingsWidget triggers schema assignment
2. SchemaService loads and caches schema definition
3. CommandWidget receives schema change notification
4. Navigation tree rebuilt with new module definitions
5. Module interfaces created on-demand via lazy loading
6. Documentation panel updates with module information

### **Command Execution Flow**
1. User selects command in CommandWidget with schema-generated interface
2. Parameter validation performed using schema rules
3. CommandProcessor validates and queues command
4. BeaconRepository stores command for beacon
5. Beacon retrieves command on next check-in
6. CommandOutputMonitor processes results
7. UI displays output in real-time

### **Receiver Management Flow**
1. User configures receiver in ReceiversWidget
2. ReceiverManager validates configuration
3. Background worker starts/stops receiver instance
4. ReceiverUpdateWorker monitors status and statistics
5. UI updates with real-time receiver information
6. Beacon connections routed to active receivers

### **File Transfer Flow**
1. User initiates transfer in FileTransferWidget
2. FileTransferService handles upload/download logic
3. Progress updates sent via Qt signals
4. Transfer status logged and displayed

## Configuration Management

### **ServerConfig Dataclass**
```python
@dataclass
class ServerConfig:
    APP_ID: str = 'Beaconator.BeaconManager'
    LOGS_FOLDER: str = 'logs'
    RESOURCES_FOLDER: str = 'resources'
    FILES_FOLDER: str = 'files'
    SCHEMAS_FOLDER: str = 'schemas'
    DB_PATH: str = 'instance/beaconator.db'
    COMBINED_PORT: int = 5074
    BEACON_TIMEOUT_MINUTES: int = 5
```

### **Persistent Settings**
- Font sizes and family preferences
- Window layout and positions  
- Server configuration parameters
- Module execution preferences
- Schema file associations
- Cache configuration settings

### **Schema Configuration**
- Schema file location and discovery
- Validation rules and error handling
- Cache size and invalidation policies
- Module loading preferences

## Metasploit Integration Architecture

### **Overview**

BeaconatorC2 includes comprehensive Metasploit Framework integration for defensive security operations, enabling payload generation, listener management, session monitoring, and connection diagnostics. The integration is designed with robust error handling, automatic session recovery, and preventive timeout management.

### **Integration Components**

#### **Custom RPC Client (`services/custom_msf_rpc.py`)**
- **Native Python Implementation**: Self-contained RPC client supporting both MessagePack and JSON protocols without third-party dependencies
- **Session Timeout Handling**: Automatic detection of `Msf::RPC::Exception` errors and intelligent error classification
- **Comprehensive Error Parsing**: Enhanced error messages with context-specific guidance:
  - Module not found errors with payload name suggestions
  - Session timeout detection with automatic recovery hints
  - Database connection issue identification
- **Payload Name Validation**: Built-in validation with automatic correction for common naming patterns (e.g., `meterpreter_reverse_tcp` → `meterpreter/reverse_tcp`)
- **Debug Logging**: Complete request/response logging for troubleshooting
- **Connection Diagnostics**: Multi-level diagnostic system testing core connectivity, module system, and database status

#### **Process Manager (`services/metasploit_manager.py`)**
- **Lifecycle Management**: Automatic startup, monitoring, and shutdown of Metasploit RPC daemon
- **Installation Validation**: Comprehensive checks for Metasploit Framework installation and dependencies
- **Health Monitoring**: Background thread monitoring RPC availability and process status
- **Graceful Shutdown**: Clean termination with proper resource cleanup
- **Enhanced Error Reporting**: Detailed installation and connectivity diagnostics with actionable guidance

#### **Service Layer (`services/metasploit_service.py`)**
- **High-Level API**: Simplified interface for payload generation, listener management, and session monitoring
- **Automatic Session Recovery**: Intelligent retry logic that detects session timeouts and automatically reconnects:
  1. Session timeout detection via error pattern matching
  2. Automatic disconnection and reconnection
  3. Transparent retry of failed operations
  4. User notification of recovery actions
- **Session Keep-Alive System**: Preventive timeout management with configurable intervals:
  - Default 5-minute keep-alive intervals
  - Smart activity tracking to avoid unnecessary requests
  - Automatic timer management on connect/disconnect
- **Activity Tracking**: Monitoring of RPC usage to optimize keep-alive timing
- **Connection Pooling**: Efficient RPC connection management with automatic cleanup

### **Session Management**

#### **Timeout Prevention**
- **Configurable Keep-Alive**: `MSF_SESSION_KEEP_ALIVE` enables periodic connectivity checks
- **Smart Timing**: Keep-alive only triggered during periods of inactivity
- **Default Interval**: 300 seconds (5 minutes) between keep-alive checks
- **Activity Awareness**: Recent RPC activity suppresses unnecessary keep-alive requests

#### **Automatic Recovery**
- **Error Detection**: Pattern matching identifies session timeout vs. other RPC errors
- **Transparent Reconnection**: Failed operations automatically trigger reconnection attempts
- **User Feedback**: Clear messaging about recovery actions without technical jargon
- **Retry Logic**: Single retry attempt after successful reconnection

#### **Configuration Options**
```python
MSF_SESSION_KEEP_ALIVE: bool = True   # Enable periodic keep-alive
MSF_KEEP_ALIVE_INTERVAL: int = 300    # Seconds between keep-alive checks
MSF_HEALTH_CHECK_INTERVAL: int = 60   # Process health monitoring interval
MSF_STARTUP_TIMEOUT: int = 30         # RPC startup timeout
```

### **User Interface Integration**

#### **Metasploit Widget (`ui/components/metasploit_widget.py`)**
- **Tabbed Interface**: Organized tabs for different functionality areas:
  - **Payload Generator**: Dynamic payload discovery, parameter configuration, and generation
  - **Listeners**: Handler/listener management (placeholder for future implementation)
  - **Sessions**: Active session monitoring (placeholder for future implementation)
  - **Status**: Connection diagnostics and health monitoring
- **Real-Time Payload Discovery**: Background loading of available payloads with platform filtering
- **Dynamic Parameter Generation**: Automatic UI generation based on payload module options
- **Enhanced Error Handling**: User-friendly error messages with specific recovery guidance
- **Connection Status Monitoring**: Live status updates with automatic refresh capabilities

#### **Status and Diagnostics Tab**
- **Connection Status**: Real-time display of RPC connectivity with visual indicators
- **Installation Information**: Framework version, daemon path, and database status
- **Diagnostic Tools**: One-click comprehensive connection and functionality testing
- **Manual Controls**: Refresh connection and run diagnostics buttons
- **Automatic Updates**: 5-second status refresh intervals
