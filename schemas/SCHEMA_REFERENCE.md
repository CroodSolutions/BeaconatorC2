# BeaconatorC2 Schema Reference Card

## Quick Start Guide for Creating Beacon Schemas

### Basic Schema Structure
```yaml
schema_version: "1.1"
beacon_info:
  beacon_type: "your_beacon_type"
  version: "1.0.0"
  description: "Beacon description"
  supported_platforms: ["windows", "linux", "macos"]
  encoding_strategy: "plaintext"

categories:
  category_name:
    display_name: "Category Name"
    description: "What this category does"
    modules:
      module_name:
        display_name: "Module Name"
        description: "What this module does"
        command_template: "execute_module|ModuleName|{param1},{param2}"
        parameters: # See parameter types below
        documentation:
          content: "Detailed explanation"
          examples: ["example1", "example2"]
        execution:
          timeout: 300
          requires_admin: false
        ui:
          icon: "icon_name"
          layout: "simple"
```

## Encoding Strategy Options

The `encoding_strategy` field in `beacon_info` specifies the preferred encoding method for beacon communication:

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `plaintext` | No encoding (default) | Standard communication, debugging |
| `base64` | Base64 encoding | Text-safe transmission, basic obfuscation |
| `xor` | XOR encryption | Simple encryption with configurable key |

### Encoding Strategy Examples

```yaml
# Plaintext encoding (default)
beacon_info:
  beacon_type: "my_beacon"
  encoding_strategy: "plaintext"

# Base64 encoding
beacon_info:
  beacon_type: "my_beacon"
  encoding_strategy: "base64"

# XOR encoding
beacon_info:
  beacon_type: "my_beacon"
  encoding_strategy: "xor"
```

**Note**: The encoding strategy in the schema represents the beacon's preferred encoding method. The actual encoding used depends on the receiver configuration and beacon implementation.

## Parameter Types Reference

| Type | Widget | Example Use Case |
|------|--------|------------------|
| `text` | Single-line input | Hostnames, usernames, short strings |
| `textarea` | Multi-line input | Scripts, commands, lists |
| `integer` | Number spinner | Timeouts, ports, counts |
| `float` | Decimal spinner | Ratios, percentages |
| `boolean` | Checkbox | Enable/disable options |
| `choice` | Dropdown | Predefined options |
| `file` | File browser | Script files, certificates |
| `directory` | Folder browser | Target directories, output paths |

## Parameter Definition Examples

### Simple Text Parameter
```yaml
username:
  type: "text"
  display_name: "Username"
  description: "Target username"
  required: true
  default: "Administrator"
  validation:
    min_length: 1
    max_length: 64
```

### Textarea with Default Script
```yaml
script:
  type: "textarea"
  display_name: "PowerShell Script"
  description: "Script to execute"
  required: true
  default: |
    Get-Process | Select-Object Name, CPU
  validation:
    max_length: 8192
```

### Integer with Range
```yaml
timeout:
  type: "integer"
  display_name: "Timeout (seconds)"
  description: "Connection timeout"
  required: true
  default: 30
  validation:
    min_value: 1
    max_value: 300
```

### Choice Parameter
```yaml
log_level:
  type: "choice"
  display_name: "Log Level"
  description: "Logging verbosity"
  required: true
  default: "INFO"
  choices: ["DEBUG", "INFO", "WARNING", "ERROR"]
```

### Directory with Validation
```yaml
target_dir:
  type: "directory"
  display_name: "Target Directory"
  description: "Directory to scan"
  required: true
  default: "C:\\temp"
  validation:
    pattern: "^[A-Za-z]:\\\\.*"  # Windows path validation
```

## Command Template Patterns

| Pattern | Example | Use Case |
|---------|---------|----------|
| No parameters | `execute_module\|BasicRecon` | Simple modules |
| Single parameter | `execute_module\|ModuleName\|{param}` | Basic modules |
| Multiple parameters | `execute_module\|ModuleName\|{p1},{p2},{p3}` | Complex modules |
| Direct command | `{command}` | Raw command execution |

## UI Layout Options

### Simple Layout (default)
```yaml
ui:
  layout: "simple"  # Single grid, good for 1-4 parameters
```

### Advanced Layout with Grouping
```yaml
ui:
  layout: "advanced"
  grouping:
    - ["username", "password"]    # First group
    - ["hostname", "port"]        # Second group
```

### Tabbed Layout
```yaml
ui:
  layout: "tabbed"
  grouping:
    - ["connection_params"]       # Tab 1: Connection
    - ["execution_params"]        # Tab 2: Execution
```

## Validation Regex Patterns

```yaml
# Windows file paths
pattern: "^[A-Za-z]:\\\\.*"

# IP addresses and ranges
pattern: "^[0-9.,\\-/\\s]+$"

# Alphanumeric usernames
pattern: "^[a-zA-Z0-9_]+$"

# Email addresses
pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
```

## Timeout Recommendations

| Operation Type | Timeout (seconds) | Examples |
|----------------|-------------------|----------|
| Quick operations | 30-60 | Registry, user management |
| Standard operations | 120-300 | Basic recon, simple commands |
| Network operations | 600-1800 | Port scanning, RDP connections |
| File operations | 1800+ | Encryption, large transfers |

## Category Organization

| Category | Purpose | Example Modules |
|----------|---------|-----------------|
| `basic_commands` | Command execution | Terminal, PowerShell |
| `discovery` | Information gathering | Recon, enumeration |
| `evasion` | Defense evasion | Firewall bypass, unhooking |
| `privilege_escalation` | Privilege escalation | UAC bypass, exploit |
| `persistence` | Maintain access | Registry, scheduled tasks |
| `lateral_movement` | Network movement | RDP, MSI installation |
| `impact` | Data impact | Encryption, destruction |

## Best Practices

### Do
- Use snake_case for internal identifiers
- Provide meaningful descriptions
- Set appropriate timeouts
- Use validation for user inputs
- Group related parameters

### Don't
- Use spaces in internal names
- Skip parameter validation
- Mix unrelated parameters in groups
- Forget to set admin requirements


## Example: Complete Module
```yaml
port_scanner:
  display_name: "Port Scanner"
  description: "TCP port scanning with threading"
  command_template: "execute_module|PortScanner|{targets},{ports},{timeout},{threads}"
  parameters:
    targets:
      type: "text"
      display_name: "Target IPs"
      description: "Comma-separated IPs or ranges"
      required: true
      default: "192.168.1.1-254"
      validation:
        pattern: "^[0-9.,\\-/\\s]+$"
    ports:
      type: "text"
      display_name: "Ports"
      description: "Ports to scan (e.g., 80,443 or 1-1000)"
      required: true
      default: "22,80,443,3389"
    timeout:
      type: "integer"
      display_name: "Timeout (seconds)"
      description: "Connection timeout per port"
      required: true
      default: 3
      validation:
        min_value: 1
        max_value: 30
    threads:
      type: "integer"
      display_name: "Threads"
      description: "Concurrent scanning threads"
      required: true
      default: 50
      validation:
        min_value: 1
        max_value: 200
  documentation:
    content: "Performs TCP port scanning using socket connections"
    examples:
      - "192.168.1.1-254 / 1-1000 / 5 / 100"
  execution:
    timeout: 1800
    requires_admin: false
  ui:
    icon: "network"
    layout: "advanced"
    grouping:
      - ["targets", "ports"]
      - ["timeout", "threads"]
```
