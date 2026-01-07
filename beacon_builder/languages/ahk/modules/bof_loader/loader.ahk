; ============================================================================
; BOF LOADER - Main Loader Class
; ============================================================================
; Main BOFLoader class that orchestrates BOF execution
; ============================================================================

class BOFLoader {
    Parser := ""
    Memory := ""
    API := ""
    Resolver := ""
    Relocator := ""
    IATBuffer := ""        ; Import Address Table buffer
    IATBaseAddress := 0    ; Base address of IAT

    __New() {
        this.Memory := MemoryManager()
        this.API := BeaconAPI()
        this.Resolver := APIResolver(this.API)
        this.Relocator := RelocationProcessor()
    }

    ; Main entry point - execute a BOF
    Execute(bofBytes, arguments := []) {
        BOFLog("========================================", "LOADER")
        BOFLog("       BOF EXECUTION STARTING", "LOADER")
        BOFLog("========================================", "LOADER")

        ; Clear any previous output
        this.API.ClearOutput()

        try {
            ; 1. Parse COFF structure
            this.Parser := COFFParser()
            this.Parser.Parse(bofBytes)

            ; 2. Allocate memory for sections and load them
            BOFLog("=== LOADING SECTIONS ===", "LOADER")
            this.LoadSections()

            ; 3. Build Import Address Table for external symbols
            BOFLog("=== BUILDING IAT ===", "LOADER")
            this.BuildImportAddressTable()

            ; 4. Process relocations (resolves symbols and patches addresses)
            BOFLog("=== RESOLVING SYMBOLS ===", "LOADER")
            this.Relocator.ProcessRelocations(
                this.Parser.Sections,
                this.Parser.Symbols,
                this.Resolver,
                this.Parser.Is64Bit()
            )

            ; 4. Find entry point (go or _go symbol)
            BOFLog("=== FINDING ENTRY POINT ===", "LOADER")
            entrySymbol := this.Parser.FindEntryPoint()
            if (!entrySymbol) {
                throw Error("No entry point found (expected 'go' or '_go' symbol)")
            }

            entryAddress := this.GetSymbolAddress(entrySymbol)
            if (!entryAddress) {
                throw Error("Failed to resolve entry point address")
            }

            BOFLog(Format("Entry point '{}' at 0x{:016X}", entrySymbol.ResolvedName, entryAddress), "LOADER")

            ; 5. Pack arguments for BOF
            argBuffer := this.PackArguments(arguments)
            BOFLog(Format("Packed {} arguments ({} bytes)", arguments.Length, argBuffer.Size), "LOADER")

            ; 6. Call the entry point
            BOFLog("=== EXECUTING BOF ===", "LOADER")
            BOFLog("Calling entry point...", "LOADER")
            this.CallEntryPoint(entryAddress, argBuffer)
            BOFLog("Entry point returned successfully", "LOADER")

            ; 7. Return collected output
            BOFLog("=== BOF EXECUTION COMPLETE ===", "LOADER")
            return this.API.GetOutput()

        } catch as err {
            BOFLog(Format("BOF EXECUTION FAILED: {}", err.Message), "LOADER")
            return "BOF Error: " . err.Message . "`n" . this.API.GetOutput()
        }
    }

    ; Load sections into memory
    LoadSections() {
        loadedCount := 0
        for section in this.Parser.Sections {
            if (section.SizeOfRawData = 0) {
                BOFLog(Format("  Skipping empty section '{}'", section.Name), "LOADER")
                continue
            }

            ; Determine memory type based on section characteristics
            memType := ""
            if (section.IsExecutable() || section.IsCode()) {
                ; Code section - needs RWX
                section.LoadedAddress := this.Memory.AllocateRWX(section.SizeOfRawData)
                memType := "RWX"
            } else {
                ; Data section - just RW
                section.LoadedAddress := this.Memory.AllocateRW(section.SizeOfRawData)
                memType := "RW"
            }

            if (!section.LoadedAddress) {
                throw Error("Failed to allocate memory for section: " . section.Name)
            }

            ; Copy section data
            if (section.RawData && section.SizeOfRawData > 0) {
                this.Memory.WriteBytes(
                    section.LoadedAddress,
                    section.RawData,
                    section.SizeOfRawData
                )
            }

            loadedCount++
            BOFLog(Format("  Loaded section '{}' ({}) at 0x{:016X} ({} bytes)",
                section.Name, memType, section.LoadedAddress, section.SizeOfRawData), "LOADER")
        }

        BOFLog(Format("Loaded {} sections into memory", loadedCount), "LOADER")
    }

    ; Build Import Address Table for external symbols
    ; This creates a local table of 64-bit function pointers that nearby REL32
    ; relocations can reach, solving the +-2GB relative addressing limitation
    BuildImportAddressTable() {
        ; Count external symbols that need IAT entries
        externalSymbols := []
        for index, sym in this.Parser.Symbols {
            if (sym.IsExternal && InStr(sym.ResolvedName, "__imp_")) {
                externalSymbols.Push(sym)
            }
        }

        if (externalSymbols.Length = 0) {
            BOFLog("No external imports requiring IAT", "LOADER")
            return
        }

        ; Allocate IAT: 8 bytes per entry (64-bit pointers)
        iatSize := externalSymbols.Length * 8
        this.IATBaseAddress := this.Memory.AllocateRW(iatSize)

        if (!this.IATBaseAddress) {
            throw Error("Failed to allocate Import Address Table")
        }

        BOFLog(Format("Allocated IAT at 0x{:016X} ({} entries, {} bytes)",
            this.IATBaseAddress, externalSymbols.Length, iatSize), "LOADER")

        ; Populate IAT and update symbol ResolvedAddress fields
        iatOffset := 0
        for sym in externalSymbols {
            ; Resolve the actual API address
            BOFLog(Format("  Resolving: {}", sym.ResolvedName), "LOADER")
            apiAddress := this.Resolver.ResolveImport(sym.ResolvedName)

            if (apiAddress = 0) {
                BOFLog(Format("  *** FAILED TO RESOLVE: {} ***", sym.ResolvedName), "LOADER")
            }

            ; Calculate the IAT entry address for this symbol
            iatEntryAddress := this.IATBaseAddress + iatOffset

            ; Write the 64-bit API address to the IAT
            NumPut("Int64", apiAddress, iatEntryAddress, 0)

            ; Store the IAT entry address in the symbol (not the API address!)
            ; This is what REL32 relocations will reference
            sym.ResolvedAddress := iatEntryAddress

            BOFLog(Format("  IAT[{}]: {} -> 0x{:016X} @ IAT 0x{:016X}",
                iatOffset // 8, sym.ResolvedName, apiAddress, iatEntryAddress), "LOADER")

            iatOffset += 8
        }

        BOFLog(Format("IAT populated with {} entries", externalSymbols.Length), "LOADER")
    }

    ; Get the runtime address of a symbol
    GetSymbolAddress(sym) {
        if (sym.SectionNumber > 0 && sym.SectionNumber <= this.Parser.Sections.Length) {
            section := this.Parser.Sections[sym.SectionNumber]
            if (section.LoadedAddress) {
                return section.LoadedAddress + sym.Value
            }
        }
        return 0
    }

    ; Pack arguments into BOF argument format
    ; Cobalt Strike BOF argument format: 4-byte length prefix followed by data
    PackArguments(arguments) {
        if (arguments.Length = 0) {
            ; Return empty buffer
            return Buffer(0)
        }

        ; Calculate total size needed
        totalSize := 0
        for arg in arguments {
            if (Type(arg) = "Buffer") {
                totalSize += 4 + arg.Size  ; 4 bytes length + data
            } else if (Type(arg) = "Integer") {
                totalSize += 4  ; Just the integer
            } else {
                ; String - include null terminator
                strLen := StrPut(arg, "UTF-8")
                totalSize += 4 + strLen
            }
        }

        ; Create buffer
        argBuffer := Buffer(totalSize, 0)
        offset := 0

        for arg in arguments {
            if (Type(arg) = "Buffer") {
                ; Length prefix (big-endian)
                this.WriteInt32BE(argBuffer, offset, arg.Size)
                offset += 4
                ; Data
                DllCall("RtlCopyMemory",
                    "Ptr", argBuffer.Ptr + offset,
                    "Ptr", arg,
                    "UPtr", arg.Size)
                offset += arg.Size
            } else if (Type(arg) = "Integer") {
                ; Integer (big-endian)
                this.WriteInt32BE(argBuffer, offset, arg)
                offset += 4
            } else {
                ; String with length prefix
                strBytes := Buffer(StrPut(arg, "UTF-8"))
                StrPut(arg, strBytes, "UTF-8")
                strLen := strBytes.Size

                ; Length prefix (big-endian)
                this.WriteInt32BE(argBuffer, offset, strLen)
                offset += 4

                ; String data
                DllCall("RtlCopyMemory",
                    "Ptr", argBuffer.Ptr + offset,
                    "Ptr", strBytes,
                    "UPtr", strLen)
                offset += strLen
            }
        }

        return argBuffer
    }

    ; Write 32-bit integer in big-endian format
    WriteInt32BE(buf, offset, value) {
        NumPut("UChar", (value >> 24) & 0xFF, buf, offset)
        NumPut("UChar", (value >> 16) & 0xFF, buf, offset + 1)
        NumPut("UChar", (value >> 8) & 0xFF, buf, offset + 2)
        NumPut("UChar", value & 0xFF, buf, offset + 3)
    }

    ; Call the BOF entry point
    ; Signature: void go(char* args, int argLen)
    CallEntryPoint(entryAddr, argBuffer) {
        argPtr := argBuffer.Size > 0 ? argBuffer.Ptr : 0
        argLen := argBuffer.Size

        BOFLog(Format("About to call entry point at 0x{:016X} with args(ptr=0x{:X}, len={})",
            entryAddr, argPtr, argLen), "LOADER")

        ; Debug: Read first 16 bytes at entry point to verify code is there
        bytes := ""
        Loop 16 {
            b := NumGet(entryAddr, A_Index - 1, "UChar")
            bytes .= Format("{:02X} ", b)
        }
        BOFLog(Format("Entry point bytes: {}", bytes), "LOADER")

        ; Debug: The first call (E8 xx xx xx xx at offset 4) - where does it go?
        if (NumGet(entryAddr, 4, "UChar") = 0xE8) {
            ; Read the relative displacement (little-endian signed 32-bit)
            callDisp := NumGet(entryAddr, 5, "Int")
            callTarget := entryAddr + 9 + callDisp  ; 9 = offset after the call instruction
            BOFLog(Format("First internal call: disp=0x{:08X} -> target 0x{:016X}", callDisp & 0xFFFFFFFF, callTarget), "LOADER")

            ; Show bytes at the call target
            targetBytes := ""
            Loop 16 {
                b := NumGet(callTarget, A_Index - 1, "UChar")
                targetBytes .= Format("{:02X} ", b)
            }
            BOFLog(Format("Call target bytes: {}", targetBytes), "LOADER")
        }

        ; Debug: Find and verify BeaconOutput IAT entry
        if (this.IATBaseAddress) {
            ; Find BeaconOutput symbol dynamically (it's at different IAT positions for different BOFs)
            beaconOutputIAT := 0
            for index, sym in this.Parser.Symbols {
                if (sym.ResolvedName = "__imp_BeaconOutput" && sym.ResolvedAddress != 0) {
                    ; sym.ResolvedAddress points to the IAT entry, read the pointer from it
                    beaconOutputIAT := NumGet(sym.ResolvedAddress, 0, "Int64")
                    iatOffset := sym.ResolvedAddress - this.IATBaseAddress
                    BOFLog(Format("BeaconOutput IAT entry at offset {} -> pointer 0x{:016X}", iatOffset, beaconOutputIAT), "LOADER")
                    break
                }
            }

            if (beaconOutputIAT != 0) {
                ; Test: Try calling our BeaconOutput callback directly to verify it works
                BOFLog("Testing direct callback invocation...", "LOADER")
                testStr := "CALLBACK_TEST"
                testBuf := Buffer(StrPut(testStr, "UTF-8"))
                StrPut(testStr, testBuf, "UTF-8")
                try {
                    DllCall(beaconOutputIAT, "Int", 0, "Ptr", testBuf.Ptr, "Int", StrLen(testStr))
                    BOFLog("Direct callback test SUCCEEDED", "LOADER")
                } catch as err {
                    BOFLog(Format("Direct callback test FAILED: {}", err.Message), "LOADER")
                }
            } else {
                BOFLog("BeaconOutput not found in BOF imports - skipping callback test", "LOADER")
            }
        }

        ; Call the entry point
        ; void go(char* args, int len)
        ; Note: x64 Windows uses only one calling convention (Microsoft x64)
        try {
            BOFLog("Invoking DllCall now...", "LOADER")
            result := DllCall(entryAddr,
                "Ptr", argPtr,
                "Int", argLen)
            BOFLog(Format("DllCall returned successfully (result={})", result), "LOADER")
        } catch as err {
            BOFLog(Format("DllCall threw exception: {}", err.Message), "LOADER")
            throw Error("Entry point call failed: " . err.Message)
        }
    }

    ; Cleanup all resources
    Cleanup() {
        BOFLog("Cleaning up BOF resources...", "LOADER")
        this.Memory.FreeAll()
        BOFLog("Cleanup complete", "LOADER")
    }

    ; Get debug info about loaded BOF
    DumpInfo() {
        if (!this.Parser) {
            return "No BOF loaded"
        }

        info := this.Parser.DumpInfo()

        info .= "`n=== Loaded Sections ===`n"
        for section in this.Parser.Sections {
            if (section.LoadedAddress) {
                info .= Format("{}: 0x{:016X}`n", section.Name, section.LoadedAddress)
            }
        }

        info .= "`n" . this.Resolver.DumpResolved()

        return info
    }
}
