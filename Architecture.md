# BeaconatorC2 Architecture Documentation

## Overview

BeaconatorC2 is a command and control (C2) framework for security testing and assessment. The application uses a layered architecture with schema-driven module execution and modular receiver management.

The system manages beacons (remote agents) through a GUI interface, with capabilities across reconnaissance, evasion, privilege escalation, persistence, lateral movement, and impact assessment.

## Project Structure

```
BeaconatorC2/
├── BeaconatorC2-Manager.py      # Main application entry point
├── config/
│   ├── __init__.py
│   ├── config_manager.py                   # Configuration persistence management
│   └── server_config.py                    # Server configuration dataclass
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
│   └── receivers/                          # Modular receiver system
│       ├── __init__.py
│       ├── receiver_manager.py             # Receiver lifecycle and coordination
│       ├── tcp_receiver.py                 # TCP receiver implementation
│       ├── receiver_config.py              # Receiver configuration management
│       └── legacy_migration.py             # Legacy system migration utilities
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
│   └── helpers.py                          # Utility functions
├── schemas/
│   ├── beacon_schema_format.yaml           # Schema format specification
│   ├── autohotkey_beacon.yaml              # Default AutoHotkey beacon schema
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
    │   ├── receivers_widget.py             # Receiver management interface
    │   ├── receiver_config_dialog.py       # Receiver configuration dialog
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
- **`services/custom_msf_rpc.py`** - Native Metasploit RPC client with session timeout handling, automatic retry logic, and comprehensive error parsing
- **`services/metasploit_manager.py`** - Metasploit Framework process lifecycle management with automatic startup, health monitoring, and installation validation
- **`services/metasploit_service.py`** - High-level Metasploit integration service with payload generation, listener management, session monitoring, and automatic session recovery
- **`services/receivers/receiver_manager.py`** - Central orchestrator managing receiver lifecycle, threading, and graceful shutdown
- **`services/receivers/tcp_receiver.py`** - TCP receiver implementation with threading and connection management
- **`services/receivers/receiver_config.py`** - Receiver configuration dataclasses and validation
- **`services/receivers/legacy_migration.py`** - Utilities for migrating from legacy server architecture

### **Background Workers**
- **`workers/beacon_update_worker.py`** - Background thread monitoring beacon heartbeats and updating status
- **`workers/receiver_update_worker.py`** - Background thread monitoring receiver status and statistics
- **`workers/command_output_monitor.py`** - Monitors and processes command output from connected beacons
- **`workers/keylogger_monitor.py`** - Specialized worker for processing keylogger output streams

### **Schema System**
- **`schemas/beacon_schema_format.yaml`** - Defines the structure and validation rules for beacon schemas
- **`schemas/autohotkey_beacon.yaml`** - Complete schema definition for AutoHotkey-based beacon
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
- **`ui/components/beacon_settings_widget.py`** - Beacon management and schema assignment
- **`ui/components/receivers_widget.py`** - Receiver management interface with status monitoring and configuration
- **`ui/components/receiver_config_dialog.py`** - Modal dialog for receiver configuration and validation
- **`ui/components/metasploit_widget.py`** - Metasploit integration interface with tabbed design for payload generation, listener management, session monitoring, and connection diagnostics

#### **Display Widgets**
- **`ui/widgets/log_widget.py`** - Console log with syntax highlighting
- **`ui/widgets/output_display.py`** - Command output display
- **`ui/widgets/keylogger_display.py`** - Keylogger output display

## Receiver Management Architecture

### **Receiver System Components**

**ReceiverManager (`services/receivers/receiver_manager.py`)**
- Central coordinator for all receiver instances
- Manages receiver lifecycle (start, stop, restart, remove)
- Provides statistics aggregation and status monitoring
- Handles configuration persistence and validation
- Implements signal-based communication with UI components

**TCP Receiver (`services/receivers/tcp_receiver.py`)**
- Standalone TCP server implementation
- Handles beacon connections and protocol processing
- Integrates with CommandProcessor and FileTransferService
- Provides connection statistics and status reporting
- Implements graceful shutdown with timeout handling

**Receiver Configuration (`services/receivers/receiver_config.py`)**
- Dataclass-based configuration management
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

**Integration Benefits:**
- **Real-Time Updates**: Schema changes immediately reflected in UI
- **Cache Consistency**: Automatic cache invalidation ensures data integrity
- **Developer Workflow**: Seamless schema development and testing

## Technical Architecture Patterns

### **Layered Architecture**
The application follows a clean layered architecture:
1. **Presentation Layer** (`ui/`) - User interface components and widgets with dynamic generation
2. **Service Layer** (`services/`) - Business logic, schema processing, and application services
3. **Data Access Layer** (`database/`) - Data models and repository pattern for beacons
4. **Infrastructure Layer** (`utils/`, `workers/`) - Cross-cutting concerns and background processing
5. **Schema Layer** (`schemas/`) - Dynamic module definitions and validation rules

### **Repository Pattern**
- `BeaconRepository` encapsulates all database operations for Beacon entities
- Provides clean separation between data access and business logic
- Enables easy testing and database technology changes
- Supports schema assignment and beacon lifecycle management

### **Schema-Driven Architecture**
- **Dynamic Module Loading**: Modules defined in YAML schemas rather than hardcoded
- **Type-Safe Parameters**: Strong typing with runtime validation
- **Extensible Design**: New modules added without code changes
- **Version Management**: Schema versioning for backward compatibility

### **Intelligent Caching Strategy**
- **Multi-Level Caching**: File-level and module-level cache optimization
- **Automatic Invalidation**: File modification tracking prevents stale data
- **Performance Optimization**: Reduced I/O and parsing overhead
- **Memory Management**: Efficient cache utilization with cleanup

### **Signal/Slot Communication**
- PyQt6 signals provide loose coupling between UI components
- Background workers communicate with UI through Qt's thread-safe signal system
- Logger emits signals for real-time log updates across the application
- Schema changes propagated through signal emissions

### **Background Processing**
- Dedicated worker threads handle time-intensive operations
- Beacon status monitoring runs independently of UI thread
- Command output processing occurs asynchronously
- Schema loading and parsing performed in background

### **Modular Component Design**
- Each UI component is self-contained with clear interfaces
- Components can be developed, tested, and maintained independently
- New functionality can be added without modifying existing components
- Schema-driven components adapt automatically to new module definitions

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

## Security Module Categories

The command interface organizes security operations into tactical categories based on the MITRE ATT&CK framework:

### **Basic Commands**
- **Command Execution**: Direct system command execution
- **WinGet PowerShell Execution**: PowerShell script execution via WinGet LOLBIN

### **Discovery** (MITRE T1057, T1018, T1083)
- **Basic Reconnaissance**: System information and network enumeration
- **PII Discovery**: Sensitive data identification in file systems
- **Domain Controller Enumeration**: Active Directory infrastructure mapping
- **Domain Trust Analysis**: Trust relationship discovery
- **Domain Administrator Identification**: Privileged account enumeration
- **Unconstrained Delegation Detection**: Kerberos delegation vulnerability assessment
- **Active Directory User Membership**: Current user privilege analysis
- **Port Scanning**: Network service discovery and enumeration

### **Evasion** (MITRE T1562, T1055, T1140)
- **Outbound Firewall Denial**: Security product communication blocking
- **Host File URL Blocking**: DNS manipulation for security bypass
- **NTDLL Unhooking**: API hook removal for EDR evasion

### **Privilege Escalation** (MITRE T1548, T1134)
- **CMSTP UAC Bypass**: User Account Control bypass technique
- **Run As User Functionality**: Credential-based privilege escalation

### **Persistence** (MITRE T1136, T1547, T1053)
- **Administrative User Creation**: Backdoor account establishment
- **Registry Startup Entries**: Boot persistence via registry modification
- **Scheduled Task Installation**: Time-based persistence mechanisms

### **Lateral Movement** (MITRE T1021, T1218)
- **MSI Package Installation**: Software deployment for lateral access
- **RDP Connection Establishment**: Remote desktop lateral movement

### **Impact** (MITRE T1486, T1565)
- **File Encryption**: Data encryption for impact demonstration
- **File Decryption**: Data recovery operations

## Communication Protocol Architecture

### **TCP Communication Protocol**

BeaconatorC2 implements a TCP-based communication system for beacon management and control. The protocol uses a pipe-delimited format for command structure and optimized chunking for file transfers.

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

#### **Connection Handling Architecture**

**TCP Receiver Infrastructure:**
- ThreadingTCPServer with configurable port
- SO_REUSEADDR enabled for rapid restart capability
- Daemon threads for automatic cleanup on shutdown
- Connection routing with protocol detection
- Session management with keep-alive support

**Connection Flow:**
```
Beacon Connection → TCP Receiver → Protocol Detection
                                 ↓
                       File Transfer ←→ Command Processing
                                 ↓
                       Response Generation → Beacon
```

#### **Command Processing Pipeline**

**Command Validation:**
- **Registration Processing**: Beacon registration with status tracking
- **Action Requests**: Pending command retrieval and queuing
- **Output Processing**: Command result storage with timestamp logging
- **Status Updates**: Beacon heartbeat and timeout monitoring

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

**Security Features:**
- **Secure Filename Handling**: `werkzeug.secure_filename()` prevents path traversal
- **File Validation**: Existence checking before transfer initiation
- **Error Boundaries**: Isolated error handling prevents connection corruption
- **Resource Management**: Automatic file handle cleanup

#### **Socket Optimization**

**Performance Enhancements:**
```python
# Optimized buffer sizes for large file transfers
conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)  # 1MB send buffer
conn.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  # 1MB receive buffer

# Chunked transfer for memory efficiency
CHUNK_SIZE = 1048576  # 1MB chunks reduce memory pressure
```

**Connection Management:**
- **Timeout Handling**: Configurable timeouts for different operation types
- **Keep-Alive Sessions**: Multi-command sessions for efficiency
- **Graceful Shutdown**: Clean connection termination with proper resource cleanup
- **Thread Safety**: ThreadingTCPServer handles concurrent connections

## Performance Optimizations

### **UI Performance Enhancements**

**Beacon Table Optimization:**
- **QAbstractTableModel**: High-performance table implementation
- **Efficient Updates**: Model-based updates reduce UI overhead
- **Selection Optimization**: Async beacon selection prevents UI blocking

**Command Widget Performance:**
- **Lazy Loading**: Module interfaces created on-demand
- **Smart Caching**: UI state preservation across selections
- **Async Operations**: Heavy operations deferred to prevent blocking

**Memory Management:**
- **Interface Cleanup**: Automatic disposal of unused components
- **Cache Boundaries**: Intelligent cache size management
- **Resource Pooling**: Shared resources across components

### **Schema Processing Optimization**

**File I/O Reduction:**
- **Modification Time Tracking**: Files loaded only when changed
- **Bulk Operations**: Multiple module updates in single file operation
- **Streaming Parser**: Memory-efficient YAML processing

**Caching Strategy:**
- **Hierarchical Caching**: Schema, category, and module level caching
- **Selective Invalidation**: Granular cache updates
- **Memory Efficiency**: Optimal cache utilization patterns

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

### **Error Handling Strategy**

#### **Error Classification**
- **Session Timeout**: Detected via `Msf::RPC::Exception` with specific method context
- **Module Not Found**: Enhanced with payload name suggestions and correction
- **Connection Issues**: Network and authentication problems with specific guidance
- **Database Problems**: Metasploit database connectivity issues

#### **User Experience**
- **Progressive Disclosure**: Basic error messages with option to view detailed information
- **Actionable Guidance**: Specific steps for resolving different error types
- **Automatic Recovery**: Silent recovery for transient issues with user notification
- **Context-Aware Messages**: Different messaging based on operation being performed

### **Performance Optimizations**

#### **Connection Management**
- **Session Persistence**: Long-lived connections with keep-alive management
- **Connection Pooling**: Efficient reuse of authenticated sessions
- **Background Operations**: Non-blocking payload discovery and status monitoring
- **Cache Integration**: Payload list caching to reduce RPC overhead

#### **Error Recovery Efficiency**
- **Fast Failure Detection**: Quick identification of session timeout conditions
- **Minimal Reconnection Time**: Streamlined reconnection process
- **Operation Queuing**: Maintain operation context during reconnection
- **Resource Cleanup**: Proper cleanup of failed connections and resources

### **Security Considerations**

#### **Defensive Focus**
- **Payload Generation**: For authorized security testing and red team exercises
- **Session Monitoring**: Tracking of authorized penetration testing activities
- **Access Control**: Integration respects Metasploit's authentication mechanisms
- **Audit Logging**: Comprehensive logging of all RPC operations and errors

#### **Error Information Disclosure**
- **Safe Error Messages**: Technical details logged but user messages are generalized
- **Debugging Information**: Detailed RPC logs available for authorized troubleshooting
- **Connection Security**: Proper SSL/TLS handling for encrypted RPC communications

