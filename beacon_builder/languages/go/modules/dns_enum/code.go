// DNS Enumeration module - Query DNS records

func (b *GoBeacon) moduleDNSEnum(parameters string) string {
	if parameters == "" {
		return "DNSEnum requires a domain parameter"
	}

	domain := strings.TrimSpace(parameters)
	var result strings.Builder
	result.WriteString(fmt.Sprintf("=== DNS ENUMERATION for %s ===\n", domain))

	recordTypes := []string{"A", "AAAA", "MX", "NS", "TXT", "CNAME"}

	for _, recordType := range recordTypes {
		result.WriteString(fmt.Sprintf("\n%s Records:\n", recordType))

		var cmd *exec.Cmd
		if runtime.GOOS == "windows" {
			cmd = exec.Command("nslookup", "-type="+recordType, domain)
		} else {
			cmd = exec.Command("dig", "+short", recordType, domain)
		}

		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error querying %s records: %v\n", recordType, err))
		} else {
			if len(output) > 0 {
				result.Write(output)
			} else {
				result.WriteString("No records found\n")
			}
		}
	}

	result.WriteString("\nReverse DNS Lookup:\n")
	addrs, err := net.LookupHost(domain)
	if err == nil {
		for _, addr := range addrs {
			names, err := net.LookupAddr(addr)
			if err == nil {
				result.WriteString(fmt.Sprintf("%s -> %v\n", addr, names))
			}
		}
	}

	return result.String()
}
