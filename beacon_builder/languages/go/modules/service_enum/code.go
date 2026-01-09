// Service Enumeration module - List system services

func (b *GoBeacon) moduleServiceEnum(parameters string) string {
	var result strings.Builder
	result.WriteString("=== SERVICE ENUMERATION ===\n")

	if runtime.GOOS == "windows" {
		cmd := exec.Command("sc", "query", "state=", "all")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error enumerating services: %v\n", err))
		} else {
			result.Write(output)
		}
	} else {
		cmd := exec.Command("systemctl", "list-units", "--type=service", "--no-pager")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString("Systemctl not available, trying alternative methods...\n")

			cmd = exec.Command("service", "--status-all")
			output, err = cmd.Output()
			if err != nil {
				result.WriteString(fmt.Sprintf("Error enumerating services: %v\n", err))
			} else {
				result.Write(output)
			}
		} else {
			result.Write(output)
		}
	}

	return result.String()
}
