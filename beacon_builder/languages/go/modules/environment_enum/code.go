// Environment Enumeration module - List environment variables

func (b *GoBeacon) moduleEnvironmentEnum(parameters string) string {
	var result strings.Builder
	result.WriteString("=== ENVIRONMENT ENUMERATION ===\n")

	result.WriteString("\nEnvironment Variables:\n")
	for _, env := range os.Environ() {
		result.WriteString(fmt.Sprintf("%s\n", env))
	}

	result.WriteString("\nPath Directories:\n")
	pathVar := os.Getenv("PATH")
	if pathVar != "" {
		paths := strings.Split(pathVar, string(os.PathListSeparator))
		for _, path := range paths {
			if info, err := os.Stat(path); err == nil && info.IsDir() {
				result.WriteString(fmt.Sprintf("%s (exists)\n", path))
			} else {
				result.WriteString(fmt.Sprintf("%s (missing)\n", path))
			}
		}
	}

	return result.String()
}
