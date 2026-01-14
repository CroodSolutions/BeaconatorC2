#include "helpers.h"

char* ls_module(const char* params) {
    printf("Executing ls module function...\n");

    const char* path = (params && strlen(params) > 0) ? params : ".";

    WIN32_FIND_DATAA findFileData;
    char searchPath[MAX_PATH];
    snprintf(searchPath, sizeof(searchPath), "%s\\*", path);

    HANDLE hFind = FindFirstFileA(searchPath, &findFileData);

    if (hFind == INVALID_HANDLE_VALUE) {
        return _strdup("ERROR: Directory not found or access denied");
    }

    char* lsResult = (char*)malloc(8192);
    if (lsResult == NULL) {
        FindClose(hFind);
        return _strdup("ERROR: Memory allocation failed");
    }

    snprintf(lsResult, 8192, "Directory listing for %s:\n", path);

    do {
        char fileInfo[256];
        if (findFileData.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            snprintf(fileInfo, sizeof(fileInfo), "[DIR]  %s\n", findFileData.cFileName);
        } else {
            snprintf(fileInfo, sizeof(fileInfo), "[FILE] %s (%lu bytes)\n",
                findFileData.cFileName, findFileData.nFileSizeLow);
        }

        if (strlen(lsResult) + strlen(fileInfo) < 8192 - 1) {
            strcat_s(lsResult, 8192, fileInfo);
        }
    } while (FindNextFileA(hFind, &findFileData) != 0);

    FindClose(hFind);

    printf("LS result: %s\n", lsResult);
    return lsResult;
}