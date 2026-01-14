; ============================================================================
; BOF LOADER - Memory Management
; ============================================================================
; Handles virtual memory allocation for BOF code and data sections
; ============================================================================

class MemoryManager {
    Allocations := []

    __New() {
        this.Allocations := []
    }

    ; Allocate RWX memory for code sections
    AllocateRWX(size) {
        ; MEM_COMMIT | MEM_RESERVE = 0x3000
        ; PAGE_EXECUTE_READWRITE = 0x40
        addr := DllCall("VirtualAlloc",
            "Ptr", 0,
            "Ptr", size,
            "UInt", 0x3000,
            "UInt", 0x40,
            "Ptr")

        if (!addr)
            throw Error("VirtualAlloc RWX failed: " . A_LastError)

        this.Allocations.Push(addr)
        BOFLog(Format("Allocated RWX: 0x{:016X} ({} bytes)", addr, size), "MEMORY")
        return addr
    }

    ; Allocate RW memory for data sections
    AllocateRW(size) {
        ; MEM_COMMIT | MEM_RESERVE = 0x3000
        ; PAGE_READWRITE = 0x04
        addr := DllCall("VirtualAlloc",
            "Ptr", 0,
            "Ptr", size,
            "UInt", 0x3000,
            "UInt", 0x04,
            "Ptr")

        if (!addr)
            throw Error("VirtualAlloc RW failed: " . A_LastError)

        this.Allocations.Push(addr)
        BOFLog(Format("Allocated RW: 0x{:016X} ({} bytes)", addr, size), "MEMORY")
        return addr
    }

    ; Free a specific allocation
    Free(address) {
        ; MEM_RELEASE = 0x8000
        result := DllCall("VirtualFree", "Ptr", address, "Ptr", 0, "UInt", 0x8000)

        ; Remove from tracking
        newAllocs := []
        for addr in this.Allocations {
            if (addr != address)
                newAllocs.Push(addr)
        }
        this.Allocations := newAllocs

        return result
    }

    ; Free all tracked allocations
    FreeAll() {
        if (this.Allocations.Length > 0) {
            BOFLog(Format("Freeing {} memory allocations", this.Allocations.Length), "MEMORY")
            for addr in this.Allocations {
                DllCall("VirtualFree", "Ptr", addr, "Ptr", 0, "UInt", 0x8000)
            }
            this.Allocations := []
        }
    }

    ; Copy bytes to destination
    WriteBytes(dest, src, size) {
        DllCall("RtlCopyMemory", "Ptr", dest, "Ptr", src, "UPtr", size)
    }

    ; Change memory protection
    SetProtection(address, size, protection) {
        oldProtect := 0
        result := DllCall("VirtualProtect",
            "Ptr", address,
            "Ptr", size,
            "UInt", protection,
            "UInt*", &oldProtect)
        return result
    }

    __Delete() {
        this.FreeAll()
    }
}
