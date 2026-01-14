// Network Enumeration module - Enumerate network interfaces and connections

func (b *GoBeacon) moduleNetworkEnum(parameters string) string {
	var result strings.Builder
	result.WriteString("=== NETWORK ENUMERATION ===\n")

	interfaces, err := net.Interfaces()
	if err != nil {
		return fmt.Sprintf("Error getting network interfaces: %v", err)
	}

	for _, iface := range interfaces {
		result.WriteString(fmt.Sprintf("\nInterface: %s (MTU: %d)\n", iface.Name, iface.MTU))
		result.WriteString(fmt.Sprintf("Hardware Address: %s\n", iface.HardwareAddr))
		result.WriteString(fmt.Sprintf("Flags: %s\n", iface.Flags))

		addrs, err := iface.Addrs()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error getting addresses: %v\n", err))
			continue
		}

		for _, addr := range addrs {
			result.WriteString(fmt.Sprintf("  Address: %s\n", addr))
		}
	}

	result.WriteString("\n=== LISTENING PORTS ===\n")
	if runtime.GOOS == "windows" {
		cmd := exec.Command("netstat", "-an")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error getting listening ports: %v\n", err))
		} else {
			result.Write(output)
		}
	} else {
		cmd := exec.Command("netstat", "-tulpn")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error getting listening ports: %v\n", err))
		} else {
			result.Write(output)
		}
	}

	return result.String()
}
