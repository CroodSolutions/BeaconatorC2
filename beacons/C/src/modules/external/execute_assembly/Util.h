#ifndef _UTIL_H
#define _UTIL_H

#include <windows.h>
#include <winternl.h>
#include <stdio.h>
#include <evntprov.h>

typedef ULONG(NTAPI *_PFNEtwEventWriteFull)(
	__in REGHANDLE RegHandle,
	__in PCEVENT_DESCRIPTOR EventDescriptor,
	__in USHORT EventProperty,
	__in_opt LPCGUID ActivityId,
	__in_opt LPCGUID RelatedActivityId,
	__in ULONG UserDataCount,
	__in_ecount_opt(UserDataCount) PEVENT_DATA_DESCRIPTOR UserData
	);

// Check if patches are already applied (memory inspection)
extern BOOL isEtwPatched();
extern BOOL isAmsiPatched();

// Return values for patch functions:
// 0 = Success (newly patched)
// 1 = Already patched (skipped)
// -1 = Error
extern int patchAmci();
extern int patchEtw();

#define _separator() printf("[*]:-----------------------------------------\n")

#endif