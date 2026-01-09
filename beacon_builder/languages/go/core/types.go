// GoBeacon struct definition

type GoBeacon struct {
	ServerIP      string
	ServerPort    int
	AgentID       string
	ComputerName  string
	Schema        string
	CheckInterval time.Duration
	IsRunning     bool
	Logger        *log.Logger
}

func NewGoBeacon(serverIP string, serverPort int) *GoBeacon {
	beacon := &GoBeacon{
		ServerIP:      serverIP,
		ServerPort:    serverPort,
		Schema:        SchemaFile,
		CheckInterval: time.Duration(DefaultCheckInterval) * time.Second,
		IsRunning:     false,
		Logger:        log.New(os.Stdout, "[GoBeacon] ", log.LstdFlags),
	}

	beacon.ComputerName = beacon.getComputerName()
	beacon.AgentID = beacon.generateAgentID()

	beacon.Logger.Printf("Go Beacon initialized")
	beacon.Logger.Printf("Agent ID: %s", beacon.AgentID)
	beacon.Logger.Printf("Computer: %s", beacon.ComputerName)
	beacon.Logger.Printf("Schema: %s", beacon.Schema)
	beacon.Logger.Printf("Server: %s:%d", beacon.ServerIP, beacon.ServerPort)

	return beacon
}

func (b *GoBeacon) getComputerName() string {
	hostname, err := os.Hostname()
	if err != nil {
		return "unknown"
	}
	return hostname
}
