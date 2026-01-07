; ============================================================================
; BOF LOADER - Relocation Processing
; ============================================================================
; Handles COFF relocation processing for x86 and x64 architectures
; ============================================================================

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
