// File Search module - Search for files by pattern

func (b *GoBeacon) moduleFileSearch(parameters string) string {
	parts := strings.Split(parameters, ",")
	if len(parts) < 2 {
		return "FileSearch requires 2 parameters: directory,pattern"
	}

	searchDir := strings.TrimSpace(parts[0])
	pattern := strings.TrimSpace(parts[1])

	var result strings.Builder
	result.WriteString(fmt.Sprintf("=== FILE SEARCH ===\nSearching for '%s' in '%s'\n\n", pattern, searchDir))

	count := 0
	err := filepath.Walk(searchDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}

		if strings.Contains(strings.ToLower(info.Name()), strings.ToLower(pattern)) {
			result.WriteString(fmt.Sprintf("%s (%d bytes) - %s\n", path, info.Size(), info.ModTime().Format("2006-01-02 15:04:05")))
			count++
			if count >= 100 {
				result.WriteString("... (truncated at 100 results)\n")
				return filepath.SkipDir
			}
		}
		return nil
	})

	if err != nil {
		result.WriteString(fmt.Sprintf("Search error: %v\n", err))
	}

	result.WriteString(fmt.Sprintf("\nFound %d matching files\n", count))
	return result.String()
}
