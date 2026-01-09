; ============================================================================
; BOF LOADER - API Resolution and Beacon API Callbacks
; ============================================================================
; Handles symbol resolution and implements Beacon API callbacks that BOFs call
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
        beaconFuncs := [
            "BeaconDataParse", "BeaconDataPtr", "BeaconDataInt", "BeaconDataShort",
            "BeaconDataLength", "BeaconDataExtract", "BeaconFormatAlloc", "BeaconFormatReset",
            "BeaconFormatFree", "BeaconFormatAppend", "BeaconFormatPrintf", "BeaconFormatToString",
            "BeaconFormatInt", "BeaconPrintf", "BeaconOutput", "BeaconUseToken",
            "BeaconRevertToken", "BeaconIsAdmin", "BeaconGetSpawnTo", "BeaconInjectProcess",
            "BeaconInjectTemporaryProcess", "BeaconCleanupProcess", "toWideChar",
            "getOSMinorVersion", "getOSMajorVersion"
        ]

        for fn in beaconFuncs {
            if (fn = funcName)
                return true
        }
        return false
    }

    ; Resolve a Win32 API function
    ResolveWin32API(moduleName, funcName) {
        hModule := this.GetModule(moduleName)

        if (!hModule) {
            return 0
        }

        ; Get function address
        address := DllCall("GetProcAddress", "Ptr", hModule, "AStr", funcName, "Ptr")

        if (!address) {
            ; Try with 'A' suffix for ANSI version
            address := DllCall("GetProcAddress", "Ptr", hModule, "AStr", funcName . "A", "Ptr")
        }

        if (!address) {
            ; Try with 'W' suffix for Wide version
            address := DllCall("GetProcAddress", "Ptr", hModule, "AStr", funcName . "W", "Ptr")
        }

        return address
    }

    ; Get a module handle, loading it if necessary
    GetModule(moduleName) {
        moduleKey := StrUpper(moduleName)

        if (this.LoadedModules.Has(moduleKey)) {
            return this.LoadedModules[moduleKey]
        }

        hModule := DllCall("GetModuleHandleA", "AStr", moduleName, "Ptr")

        if (!hModule) {
            if (!InStr(moduleName, ".")) {
                moduleName .= ".dll"
            }

            hModule := DllCall("LoadLibraryA", "AStr", moduleName, "Ptr")

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
    ParserData := Map()

    ; Format buffers
    FormatBuffers := Map()

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

        ; Process injection stubs
        this.Callbacks["BeaconGetSpawnTo"] := CallbackCreate(ObjBindMethod(this, "_BeaconGetSpawnTo"), "C", 3)
        this.Callbacks["BeaconInjectProcess"] := CallbackCreate(ObjBindMethod(this, "_BeaconInjectProcess"), "C", 7)
        this.Callbacks["BeaconInjectTemporaryProcess"] := CallbackCreate(ObjBindMethod(this, "_BeaconInjectTemporaryProcess"), "C", 6)
        this.Callbacks["BeaconCleanupProcess"] := CallbackCreate(ObjBindMethod(this, "_BeaconCleanupProcess"), "C", 1)
    }

    GetFunctionPointer(funcName) {
        if (this.Callbacks.Has(funcName)) {
            return this.Callbacks[funcName]
        }
        return 0
    }

    GetOutput() {
        return this.OutputBuffer
    }

    ClearOutput() {
        this.OutputBuffer := ""
    }

    ; === OUTPUT FUNCTIONS ===

    _BeaconPrintf(type, fmtPtr, arg1:=0, arg2:=0, arg3:=0, arg4:=0, arg5:=0, arg6:=0, arg7:=0, arg8:=0) {
        ; BeaconPrintf is variadic: void BeaconPrintf(int type, char* fmt, ...)
        ; We use wvsprintfA to format the string with the provided arguments
        BOFLog(">>> BeaconPrintf CALLED <<<", "API")
        try {
            if (fmtPtr) {
                fmtStr := StrGet(fmtPtr, "UTF-8")

                ; Build a va_list-like array of arguments on the stack
                ; wvsprintfA expects: LPSTR lpOutput, LPCSTR lpFmt, va_list arglist
                ; We'll use wsprintfA instead which takes individual args

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
                ; wsprintfA is not ideal but works for most cases
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

    ; === DATA PARSING FUNCTIONS ===

    _BeaconDataParse(parserPtr, bufferPtr, size) {
        this.ParserData[parserPtr] := {
            buffer1: bufferPtr,
            position: 0,
            length: size
        }

        if (parserPtr) {
            NumPut("Ptr", bufferPtr, parserPtr, 0)
            NumPut("Ptr", bufferPtr, parserPtr, 8)
            NumPut("Int", size, parserPtr, 16)
            NumPut("Int", size, parserPtr, 20)
        }
        return 0
    }

    _BeaconDataPtr(parserPtr, size) {
        if (!this.ParserData.Has(parserPtr)) {
            return 0
        }

        state := this.ParserData[parserPtr]

        if (state.position + size > state.length) {
            return 0
        }

        ptr := state.buffer1 + state.position
        state.position += size
        this.ParserData[parserPtr] := state

        NumPut("Ptr", state.buffer1 + state.position, parserPtr, 8)
        NumPut("Int", state.length - state.position, parserPtr, 16)

        return ptr
    }

    _BeaconDataInt(parserPtr) {
        if (!this.ParserData.Has(parserPtr)) {
            return 0
        }

        state := this.ParserData[parserPtr]

        if (state.position + 4 > state.length) {
            return 0
        }

        ; Read 4-byte big-endian integer
        value := NumGet(state.buffer1, state.position, "UInt")
        value := ((value & 0xFF) << 24) | ((value & 0xFF00) << 8) | ((value & 0xFF0000) >> 8) | ((value & 0xFF000000) >> 24)

        state.position += 4
        this.ParserData[parserPtr] := state

        NumPut("Ptr", state.buffer1 + state.position, parserPtr, 8)
        NumPut("Int", state.length - state.position, parserPtr, 16)

        return value
    }

    _BeaconDataShort(parserPtr) {
        if (!this.ParserData.Has(parserPtr)) {
            return 0
        }

        state := this.ParserData[parserPtr]

        if (state.position + 2 > state.length) {
            return 0
        }

        value := NumGet(state.buffer1, state.position, "UShort")
        value := ((value & 0xFF) << 8) | ((value & 0xFF00) >> 8)

        state.position += 2
        this.ParserData[parserPtr] := state

        NumPut("Ptr", state.buffer1 + state.position, parserPtr, 8)
        NumPut("Int", state.length - state.position, parserPtr, 16)

        return value
    }

    _BeaconDataLength(parserPtr) {
        if (!this.ParserData.Has(parserPtr)) {
            return 0
        }

        state := this.ParserData[parserPtr]
        return state.length - state.position
    }

    _BeaconDataExtract(parserPtr, outLenPtr) {
        if (!this.ParserData.Has(parserPtr)) {
            if (outLenPtr)
                NumPut("Int", 0, outLenPtr, 0)
            return 0
        }

        state := this.ParserData[parserPtr]

        if (state.position + 4 > state.length) {
            if (outLenPtr)
                NumPut("Int", 0, outLenPtr, 0)
            return 0
        }

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

    ; === FORMAT FUNCTIONS ===

    _BeaconFormatAlloc(formatPtr, maxsz) {
        buffer1 := DllCall("LocalAlloc", "UInt", 0x40, "UPtr", maxsz, "Ptr")

        this.FormatBuffers[formatPtr] := {
            buffer1: buffer1,
            position: 0,
            maxlen: maxsz
        }

        if (formatPtr) {
            NumPut("Ptr", buffer1, formatPtr, 0)
            NumPut("Ptr", buffer1, formatPtr, 8)
            NumPut("Int", maxsz, formatPtr, 16)
            NumPut("Int", maxsz, formatPtr, 20)
        }
        return 0
    }

    _BeaconFormatReset(formatPtr) {
        if (this.FormatBuffers.Has(formatPtr)) {
            state := this.FormatBuffers[formatPtr]
            state.position := 0
            this.FormatBuffers[formatPtr] := state

            if (state.buffer1) {
                DllCall("RtlZeroMemory", "Ptr", state.buffer1, "UPtr", state.maxlen)
            }

            NumPut("Ptr", state.buffer1, formatPtr, 8)
            NumPut("Int", state.maxlen, formatPtr, 16)
        }
        return 0
    }

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

    _BeaconFormatAppend(formatPtr, dataPtr, len) {
        if (!this.FormatBuffers.Has(formatPtr) || !dataPtr || len <= 0) {
            return 0
        }

        state := this.FormatBuffers[formatPtr]

        if (state.position + len > state.maxlen) {
            len := state.maxlen - state.position
        }

        if (len > 0) {
            DllCall("RtlCopyMemory", "Ptr", state.buffer1 + state.position, "Ptr", dataPtr, "UPtr", len)
            state.position += len
            this.FormatBuffers[formatPtr] := state
        }
        return 0
    }

    _BeaconFormatPrintf(formatPtr, fmtPtr, argPtr) {
        if (!this.FormatBuffers.Has(formatPtr) || !fmtPtr) {
            return 0
        }

        text := StrGet(fmtPtr, "UTF-8")
        state := this.FormatBuffers[formatPtr]

        textBytes := Buffer(StrPut(text, "UTF-8") - 1)
        StrPut(text, textBytes, "UTF-8")

        remaining := state.maxlen - state.position
        copyLen := Min(textBytes.Size, remaining)

        if (copyLen > 0) {
            DllCall("RtlCopyMemory", "Ptr", state.buffer1 + state.position, "Ptr", textBytes, "UPtr", copyLen)
            state.position += copyLen
            this.FormatBuffers[formatPtr] := state
        }
        return 0
    }

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

    ; === TOKEN FUNCTIONS ===

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

    _BeaconRevertToken() {
        DllCall("advapi32\RevertToSelf")
        this.CurrentToken := 0
        return 0
    }

    _BeaconIsAdmin() {
        try {
            hToken := 0
            DllCall("advapi32\OpenProcessToken",
                "Ptr", DllCall("GetCurrentProcess", "Ptr"),
                "UInt", 0x0008,
                "Ptr*", &hToken)

            if (!hToken) {
                return 0
            }

            elevation := 0
            returnLength := 0
            DllCall("advapi32\GetTokenInformation",
                "Ptr", hToken,
                "Int", 20,
                "Int*", &elevation,
                "UInt", 4,
                "UInt*", &returnLength)

            DllCall("CloseHandle", "Ptr", hToken)
            return elevation != 0
        } catch {
            return 0
        }
    }

    ; === UTILITY FUNCTIONS ===

    _toWideChar(srcPtr, dstPtr, max) {
        if (!srcPtr || !dstPtr || max <= 0) {
            return 0
        }

        result := DllCall("MultiByteToWideChar",
            "UInt", 65001,
            "UInt", 0,
            "Ptr", srcPtr,
            "Int", -1,
            "Ptr", dstPtr,
            "Int", max,
            "Int")

        return result > 0
    }

    _getOSMajorVersion() {
        parts := StrSplit(A_OSVersion, ".")
        if (parts.Length >= 1) {
            return Integer(parts[1])
        }
        return 10
    }

    _getOSMinorVersion() {
        parts := StrSplit(A_OSVersion, ".")
        if (parts.Length >= 2) {
            return Integer(parts[2])
        }
        return 0
    }

    ; === PROCESS INJECTION STUBS ===

    _BeaconGetSpawnTo(x86, bufferPtr, length) {
        spawnTo := x86 ? "C:\Windows\SysWOW64\rundll32.exe" : "C:\Windows\System32\rundll32.exe"

        if (bufferPtr && length > 0) {
            copyLen := Min(StrLen(spawnTo), length - 1)
            DllCall("RtlCopyMemory", "Ptr", bufferPtr, "AStr", spawnTo, "UPtr", copyLen)
            NumPut("Char", 0, bufferPtr, copyLen)
        }
        return 0
    }

    _BeaconInjectProcess(hProcess, pid, payload, payloadLen, offset, arg, argLen) {
        this.OutputBuffer .= "[!] BeaconInjectProcess not implemented`n"
        return 0
    }

    _BeaconInjectTemporaryProcess(pInfo, payload, payloadLen, offset, arg, argLen) {
        this.OutputBuffer .= "[!] BeaconInjectTemporaryProcess not implemented`n"
        return 0
    }

    _BeaconCleanupProcess(pInfo) {
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

    __Delete() {
        for name, cb in this.Callbacks {
            if (cb)
                CallbackFree(cb)
        }

        for ptr, state in this.FormatBuffers {
            if (state.buffer1)
                DllCall("LocalFree", "Ptr", state.buffer1)
        }
    }
}
