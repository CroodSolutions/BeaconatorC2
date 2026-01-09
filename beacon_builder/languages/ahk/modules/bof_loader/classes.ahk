; ============================================================================
; BOF LOADER - COFF Structure Classes
; ============================================================================
; Classes for parsing COFF (Common Object File Format) structures
; Required for BOF (Beacon Object File) execution
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
