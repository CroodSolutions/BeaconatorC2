// Update Check-In module - Change the beacon's check-in interval

func (b *GoBeacon) moduleUpdateCheckIn(parameters string) string {
	if parameters == "" {
		return fmt.Sprintf("Current check-in interval: %v", b.CheckInterval)
	}

	newInterval, err := strconv.Atoi(strings.TrimSpace(parameters))
	if err != nil {
		return fmt.Sprintf("Invalid interval value: %s", parameters)
	}

	if newInterval < 1 {
		return "Interval must be at least 1 second"
	}

	if newInterval > 86400 {
		return "Interval cannot exceed 86400 seconds (24 hours)"
	}

	oldInterval := b.CheckInterval
	b.CheckInterval = time.Duration(newInterval) * time.Second

	b.Logger.Printf("Check-in interval updated from %v to %v", oldInterval, b.CheckInterval)

	return fmt.Sprintf("Check-in interval updated from %v to %v", oldInterval, b.CheckInterval)
}
