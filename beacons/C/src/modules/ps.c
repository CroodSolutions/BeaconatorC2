#include "helpers.h"

char* ps_module(const char* params) {
    UNREFERENCED_PARAMETER(params);

    printf("Executing ps module function...\n");

    char* psResult = (char*)malloc(65536);
    if (psResult == NULL) {
        return _strdup("ERROR: Memory allocation failed");
    }

    snprintf(psResult, 65536, "Process list:\n");

    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) {
        free(psResult);
        return _strdup("ERROR: Failed to create process snapshot");
    }

    PROCESSENTRY32W pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32W);

    if (Process32FirstW(hSnapshot, &pe32)) {
        do {
            char processInfo[256];
            char exeFileName[MAX_PATH];
            WideCharToMultiByte(CP_UTF8, 0, pe32.szExeFile, -1, exeFileName, sizeof(exeFileName), NULL, NULL);

            snprintf(processInfo, sizeof(processInfo), "PID: %lu | %s\n",
                pe32.th32ProcessID, exeFileName);

            if (strlen(psResult) + strlen(processInfo) < 65536 - 1) {
                strcat_s(psResult, 65536, processInfo);
            }
        } while (Process32NextW(hSnapshot, &pe32));
    }

    CloseHandle(hSnapshot);

    printf("PS result: %s\n", psResult);
    return psResult;
}