// System Info module - Gather system information

func (b *GoBeacon) moduleSystemInfo(parameters string) string {
	var info strings.Builder

	info.WriteString("=== SYSTEM INFORMATION ===\n")
	info.WriteString(fmt.Sprintf("Hostname: %s\n", b.ComputerName))
	info.WriteString(fmt.Sprintf("OS: %s\n", runtime.GOOS))
	info.WriteString(fmt.Sprintf("Architecture: %s\n", runtime.GOARCH))
	info.WriteString(fmt.Sprintf("Go Version: %s\n", runtime.Version()))
	info.WriteString(fmt.Sprintf("CPUs: %d\n", runtime.NumCPU()))

	if u, err := user.Current(); err == nil {
		info.WriteString(fmt.Sprintf("Current User: %s\n", u.Username))
		info.WriteString(fmt.Sprintf("User UID: %s\n", u.Uid))
		info.WriteString(fmt.Sprintf("User GID: %s\n", u.Gid))
		info.WriteString(fmt.Sprintf("Home Directory: %s\n", u.HomeDir))
	}

	if wd, err := os.Getwd(); err == nil {
		info.WriteString(fmt.Sprintf("Working Directory: %s\n", wd))
	}

	if exe, err := os.Executable(); err == nil {
		info.WriteString(fmt.Sprintf("Executable Path: %s\n", exe))
	}

	info.WriteString(fmt.Sprintf("Process PID: %d\n", os.Getpid()))
	info.WriteString(fmt.Sprintf("Parent PID: %d\n", os.Getppid()))

	return info.String()
}
