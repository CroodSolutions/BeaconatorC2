// Port Scanner module - Scan target ports

func (b *GoBeacon) modulePortScan(parameters string) string {
	parts := strings.Split(parameters, ",")
	if len(parts) < 2 {
		return "PortScan requires 2 parameters: target,ports (e.g., 192.168.1.1,80,443,3389)"
	}

	target := strings.TrimSpace(parts[0])
	var ports []int

	for i := 1; i < len(parts); i++ {
		if port, err := strconv.Atoi(strings.TrimSpace(parts[i])); err == nil {
			ports = append(ports, port)
		}
	}

	if len(ports) == 0 {
		return "No valid ports specified"
	}

	var result strings.Builder
	result.WriteString(fmt.Sprintf("=== PORT SCAN ===\nScanning %s for %d ports\n\n", target, len(ports)))

	openPorts := []int{}
	closedPorts := []int{}

	for _, port := range ports {
		conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", target, port), 3*time.Second)
		if err == nil {
			conn.Close()
			openPorts = append(openPorts, port)
			result.WriteString(fmt.Sprintf("Port %d: OPEN\n", port))
		} else {
			closedPorts = append(closedPorts, port)
		}
	}

	result.WriteString(fmt.Sprintf("\nScan Complete:\n"))
	result.WriteString(fmt.Sprintf("Open ports: %v\n", openPorts))
	result.WriteString(fmt.Sprintf("Closed/filtered ports: %d\n", len(closedPorts)))

	return result.String()
}
