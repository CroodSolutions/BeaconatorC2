#include "helpers.h"

char* pwd_module(const char* params) {
    UNREFERENCED_PARAMETER(params);

    printf("Executing pwd module function...\n");

    char currentDir[MAX_PATH];
    DWORD length = GetCurrentDirectoryA(sizeof(currentDir), currentDir);

    char* pwdResult = NULL;
    if (length > 0) {
        pwdResult = (char*)malloc(1024);
        if (pwdResult != NULL) {
            snprintf(pwdResult, 1024, "Current Directory: %s", currentDir);
            printf("PWD result: %s\n", pwdResult);
        }
    } else {
        pwdResult = _strdup("ERROR: Failed to get current directory");
    }

    return pwdResult;
}