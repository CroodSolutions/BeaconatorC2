# BeaconatorC2 - C Beacon

this is a lightweight, modular C2 beacon skeleton designed for stealth and extensibility. aligning with the ethos of the project, this isn't meant to be a fully complete beacon with all capabilities of a commercial C2 framework. 

instead, this is meant as a skeleton for future capability development, with the baked in evasion infrastructure to simulate a average level of technical stealth. 

given this basis as a skeleton, this beacon on it's own's EDR evasion may vary. there are some easy fixes for this however, some of which are notated at the bottom.

## Overview
- HTTP-based C2 communication (WinHTTP)
- thread-safe heap encryption during sleep cycles
- configurable polling intervals and retry logic

### Evasion
- **Hell's Hall**: indirect syscall implementation to avoid userland hooks during injection. future modules with sensitive api calls can easily use this as well
- **Heap Encryption**: XOR-based heap encryption during beacon sleep

***and now for a quick summary by claude:***
### Built-in Modules
| Module | Description |
|--------|-------------|
| `whoami` | Get current user and computer name |
| `pwd` | Print working directory |
| `ls` | Directory listing |
| `ps` | Process enumeration |
| `inject` | AES-encrypted shellcode injection via indirect syscalls (reference sample_inj_template)|
| `execute_assembly` | Reflectively load and execute .NET assemblies (AMSI/ETW patching included, but stomping headers & unloading modules to be implemented)|

## Project Structure

```
beacons/C/
├── config.json           # Build configuration
├── compiler.bat          # Build script
├── include/
│   ├── helpers.h         # Main header with declarations
│   ├── hall.h            # Hell's Hall syscall header
│   ├── structs.h         # NT structures
├── src/
│   ├── main.c            # Entry point
│   ├── core/
│   │   ├── asynchandler.c    # Main polling loop, memory management
│   │   ├── httphandler.c     # HTTP communication
│   │   ├── base.c            # Registration, checkin, request handling
│   │   └── encryption.c      # AES decryption for payloads
│   ├── modules/
│   │   ├── whoami.c
│   │   ├── pwd.c
│   │   ├── ls.c
│   │   ├── ps.c
│   │   ├── inject.c
│   │   ├── execute_assembly.c
│   │   └── external/         # Third-party modules
│   └── utils/
│       ├── hellshall.c       # Indirect syscall implementation
│       └── hall.asm          # Assembly syscall stub
```

## Building

### Prerequisites
- Visual Studio 2019+ with C++ tools (recommended)
- Or Clang/GCC with Windows SDK

### Quick Build
1. Edit `config.json` with your C2 server details
2. Run `compiler.bat`
3. Run `build.bat` within execute_assembly's module path to compile this DLL if desired

### Configuration (config.json)
```json
{
  "beacon": {
    "id": "beacon_001",
    "server_url": "http://127.0.0.1:8080",
    "polling_interval_ms": 10000,
    "max_retries": 5
  },
  "build": {
    "output_name": "BeaconatorC2_C.exe",
    "compiler_preference": [
      "msvc",
      "clang",
      "gcc"
    ],
    "debug_mode": true,
    "optimize": false
  },
  "comms": {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
  },
  "evasion": {
    "heap_encryption": false,
    "sleep_obfuscation": false
  },
  "modules": {
    "execute_assembly": {
      "auto_compile": true,
      "dll_path": "src/modules/external/execute_assembly/x64/ExecuteAssembly.dll"
    }
  }
}
```

## Communication Protocol

The beacon uses a simple pipe-delimited protocol to align with the rest of the BeaconatorC2 framework.

## Adding New Modules

1. Create `src/modules/yourmodule.c`
2. Implement the module function:
```c
#include "helpers.h"

void yourmodule_module(const char* params) {
    // Your code here
    sendModuleOutput("Result");
}
```
3. Add declaration to `include/helpers.h`
4. Add dispatch case in `asynchandler.c` `execute_module()`
5. Add source file to `compiler.bat`

### Building External Execute Assembly Modules

- When adding new execute_assembly modules, ensure the following:
  - The module is placed in `src/modules/external/execute_assembly`.
  - The module is a valid DLL with the correct export function.
  - The compiler.bat is modified to include the new module if the DLL does not exist in `src/modules/external/execute_assembly/build/release`.

## Credits

- [Hell's Hall](https://github.com/Maldev-Academy/HellHall) by NULL (@NUL0x4C) & mr.d0x (@mrd0x)
- [ExecuteAssembly](https://github.com/med0x2e/ExecuteAssembly) by med0x2e

## Security Notes

- This is a **skeleton/framework** for teams to develop abstracted in house modules, with built-in evasion infrastructure ready to go.
- The current HTTP transport is unencrypted.
- No polling jitter.
- Implement proper error handling for production use.

**As always, for authorized security testing and research only.**