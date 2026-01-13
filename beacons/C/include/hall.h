//--------------------------------------------------------------------------------
// Hell's Hall - Indirect Syscall Header
// Original concept by various security researchers
//--------------------------------------------------------------------------------

#ifndef HALL_H
#define HALL_H

#include <Windows.h>

//----------------[types]---------------------------------------------------//

typedef unsigned char      uint8_t;
typedef unsigned short     uint16_t;
typedef unsigned int       uint32_t;
typedef unsigned long long uint64_t;
typedef uint32_t UINT32_T;

//----------------[hashing]-------------------------------------------------//

uint32_t crc32b(const uint8_t* str);
#define HASH(API) (crc32b((uint8_t*)API))

//----------------[structs]-------------------------------------------------//

typedef struct _SysFunc {
    PVOID       pInst;
    PBYTE       pAddress;
    WORD        wSSN;
    UINT32_T    uHash;
} SysFunc, *PSysFunc;

//----------------[functions]-----------------------------------------------//

BOOL Initialize();
BOOL InitilizeSysFunc(IN UINT32_T uSysFuncHash);
VOID getSysFuncStruct(OUT PSysFunc psF);

extern VOID SetConfig(WORD wSystemCall, PVOID pSyscallInst);
extern NTSTATUS HellHall();

#define SYSCALL(sF) (SetConfig(sF.wSSN, sF.pInst))

#endif