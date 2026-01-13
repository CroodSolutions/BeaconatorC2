#include "helpers.h"

char* whoami_module(const char* params) {
    UNREFERENCED_PARAMETER(params);

    printf("Executing whoami module function...\n");

    char userName[256] = { 0 };
    DWORD userNameSize = sizeof(userName);
    char computerName[256] = { 0 };
    DWORD computerNameSize = sizeof(computerName);

    GetUserNameA(userName, &userNameSize);
    GetComputerNameA(computerName, &computerNameSize);

    char* whoamiResult = (char*)malloc(1024);
    if (whoamiResult != NULL) {
        snprintf(whoamiResult, 1024, "User: %s\\%s", computerName, userName);
        printf("Whoami result: %s\n", whoamiResult);
    }

    return whoamiResult;
}