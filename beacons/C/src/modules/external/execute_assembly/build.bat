@echo off
setlocal enabledelayedexpansion

echo ===============================================
echo  ExecuteAssembly DLL Builder
echo ===============================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM ----------------[Configuration]-----------------------------------------------
set OUTPUT_DIR=x64
set OUTPUT_NAME=ExecuteAssembly.dll
set ASM_SOURCE=syscalls.asm

REM CPP source files
set CPP_SOURCES=ExecuteAssembly.cpp GZUtil.cpp Helpers.cpp HostCLR.cpp Loader.cpp PatternScan.cpp PEB.cpp PEModuleHelper.cpp Util.cpp

REM Libraries
set LIBS=Lib\libz64.lib mscoree.lib ole32.lib oleaut32.lib user32.lib kernel32.lib advapi32.lib

REM Compiler flags for DLL
REM - WIN_X64: Target x64 architecture (uses __readgsqword for PEB access)
REM - RFL_LRL: Reflective loader with lpReserved parameter
REM - RFL_MAIN: Exclude DllMain from Loader.cpp (ExecuteAssembly.cpp defines it)
set CFLAGS=/nologo /EHsc /O2 /MT /LD /DWIN32 /D_WINDOWS /DNDEBUG /DWIN_X64 /DRFL_LRL /DRFL_MAIN
set LINKFLAGS=/DLL /NOLOGO /LTCG /DEF:ExecuteAssembly.def

REM ----------------[Compiler Detection]-----------------------------------------------
echo [*] Detecting Visual Studio...

REM Try Visual Studio via vswhere
if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" (
    for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
        set VS_PATH=%%i
        if exist "!VS_PATH!\VC\Auxiliary\Build\vcvarsall.bat" (
            echo [+] Found Visual Studio at: !VS_PATH!
            call "!VS_PATH!\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul 2>&1
            goto :found_compiler
        )
    )
)

REM Fallback: check if cl.exe is in PATH
where cl.exe >nul 2>&1
if !errorlevel! == 0 (
    echo [+] Found cl.exe in PATH
    goto :found_compiler
)

echo [ERROR] Visual Studio with C++ tools not found!
echo ExecuteAssembly requires MSVC to compile.
pause
exit /b 1

:found_compiler
echo.

REM ----------------[Create Output Directory]-----------------------------------------------
if not exist "%OUTPUT_DIR%" (
    echo [*] Creating output directory: %OUTPUT_DIR%
    mkdir "%OUTPUT_DIR%"
)

REM ----------------[Assemble syscalls.asm]-----------------------------------------------
echo [*] Assembling %ASM_SOURCE%...
if exist "%ASM_SOURCE%" (
    ml64 /c /nologo /Fo"%OUTPUT_DIR%\syscalls.obj" %ASM_SOURCE%
    if !errorlevel! neq 0 (
        echo [!] Warning: Assembly compilation failed
        echo     Some features may not work correctly
        set ASM_OBJ=
    ) else (
        echo [+] Assembly compiled successfully
        set ASM_OBJ=%OUTPUT_DIR%\syscalls.obj
    )
) else (
    echo [!] Warning: %ASM_SOURCE% not found
    set ASM_OBJ=
)
echo.

REM ----------------[Compile CPP Sources]-----------------------------------------------
echo [*] Compiling C++ sources...

set OBJ_FILES=
for %%f in (%CPP_SOURCES%) do (
    echo     Compiling %%f...
    cl %CFLAGS% /c /Fo"%OUTPUT_DIR%\%%~nf.obj" "%%f"
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to compile %%f
        goto :build_failed
    )
    set OBJ_FILES=!OBJ_FILES! %OUTPUT_DIR%\%%~nf.obj
)
echo [+] All sources compiled successfully
echo.

REM ----------------[Link DLL]-----------------------------------------------
echo [*] Linking %OUTPUT_NAME%...

REM Add ASM object if it exists
if defined ASM_OBJ (
    set OBJ_FILES=!OBJ_FILES! !ASM_OBJ!
)

link %LINKFLAGS% /OUT:"%OUTPUT_DIR%\%OUTPUT_NAME%" !OBJ_FILES! %LIBS%
if !errorlevel! neq 0 (
    echo [ERROR] Linking failed
    goto :build_failed
)

echo.
echo ===============================================
echo  Build Successful
echo ===============================================
echo  Output: %OUTPUT_DIR%\%OUTPUT_NAME%
echo ===============================================

REM Cleanup object files
echo [*] Cleaning up object files...
del /q "%OUTPUT_DIR%\*.obj" 2>nul

goto :end

:build_failed
echo.
echo ===============================================
echo  Build Failed
echo ===============================================
echo  Check error messages above
echo ===============================================
exit /b 1

:end
exit /b 0
