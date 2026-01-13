#include "helpers.h"

//----------------[config]--------------------------------------------------//

#define KEY_LEN     32
#define VECTOR_LEN  16
#define AES_BLOCK_SIZE 16
#define MAX_VARS 20

//----------------[structs]-------------------------------------------------//

typedef struct {
    char name[64];
    unsigned char* data;
    size_t dataSize;
} ByteArrayVar;

//----------------[globals]-------------------------------------------------//

ByteArrayVar g_storedVars[MAX_VARS];
int g_varCount = 0;

//----------------[var extraction]------------------------------------------//

BOOL extractVarName(const char* line, char* outName, size_t maxNameLen) {
    const char* start = strstr(line, "unsigned char ");
    if (!start) return FALSE;

    start += 14;
    const char* end = strstr(start, "[]");
    if (!end || end - start >= maxNameLen) return FALSE;

    memcpy(outName, start, end - start);
    outName[end - start] = '\0';
    return TRUE;
}

BOOL parseHexByte(const char* str, unsigned char* outByte) {
    if (strncmp(str, "0x", 2) != 0) return FALSE;

    char hexStr[3] = { str[2], str[3], '\0' };
    char* endPtr = NULL;
    *outByte = (unsigned char)strtol(hexStr, &endPtr, 16);

    return (endPtr != hexStr);
}

ByteArrayVar* findVar(const char* name) {
    for (int i = 0; i < g_varCount; i++) {
        if (strcmp(g_storedVars[i].name, name) == 0) {
            return &g_storedVars[i];
        }
    }
    return NULL;
}

ByteArrayVar* parseByteArray(const char* text) {
    ByteArrayVar* result = (ByteArrayVar*)malloc(sizeof(ByteArrayVar));
    if (!result) return NULL;

    memset(result, 0, sizeof(ByteArrayVar));

    if (!extractVarName(text, result->name, sizeof(result->name))) {
        free(result);
        return NULL;
    }

    const char* ptr = text;
    size_t count = 0;

    while ((ptr = strstr(ptr, "0x"))) {
        count++;
        ptr += 2;
    }

    result->data = (unsigned char*)malloc(count);
    if (!result->data) {
        free(result);
        return NULL;
    }

    ptr = text;
    size_t index = 0;

    while ((ptr = strstr(ptr, "0x")) && index < count) {
        parseHexByte(ptr, &result->data[index++]);
        ptr += 2;
    }

    result->dataSize = index;
    return result;
}

void extractVars(const char* content) {
    const char* line = content;
    const char* nextLine = NULL;
    char* varData = NULL;

    while (line && *line) {
        nextLine = strchr(line, '\n');
        size_t lineLen = nextLine ? (nextLine - line) : strlen(line);

        if (strstr(line, "unsigned char ") && strstr(line, "[]")) {
            const char* endDecl = strstr(line, "};");
            if (!endDecl) {
                line = nextLine ? (nextLine + 1) : NULL;
                continue;
            }

            size_t declSize = (endDecl + 2) - line;
            varData = (char*)malloc(declSize + 1);
            if (!varData) {
                line = nextLine ? (nextLine + 1) : NULL;
                continue;
            }

            memcpy(varData, line, declSize);
            varData[declSize] = '\0';

            ByteArrayVar* parsedArray = parseByteArray(varData);
            if (parsedArray) {
                if (g_varCount < MAX_VARS) {
                    strcpy_s(g_storedVars[g_varCount].name, sizeof(g_storedVars[g_varCount].name), parsedArray->name);
                    g_storedVars[g_varCount].data = parsedArray->data;
                    g_storedVars[g_varCount].dataSize = parsedArray->dataSize;
                    g_varCount++;

                    free(parsedArray);
                } else {
                    free(parsedArray->data);
                    free(parsedArray);
                }
            }

            free(varData);
            line = endDecl + 2;
        } else {
            line = nextLine ? (nextLine + 1) : NULL;
        }
    }
}

void clearStoredVars() {
    for (int i = 0; i < g_varCount; i++) {
        if (g_storedVars[i].data) {
            free(g_storedVars[i].data);
            g_storedVars[i].data = NULL;
        }
        memset(g_storedVars[i].name, 0, sizeof(g_storedVars[i].name));
        g_storedVars[i].dataSize = 0;
    }
    g_varCount = 0;
}

//----------------[aes decryption]------------------------------------------//

BOOL AesDecryption(IN PVOID pInputBuffer, IN DWORD sInputSize,
    IN PBYTE pKey, IN PBYTE pVector,
    OUT PVOID* pOutputBuffer, OUT DWORD* sOutputSize) {

    if (!pInputBuffer || !sInputSize || !pKey || !pVector)
        return FALSE;

    BOOL bResult = FALSE;
    HCRYPTPROV hProv = 0;
    HCRYPTKEY hKey = 0;
    PBYTE pbOutputBuf = NULL;
    DWORD dwOutputLen = 0;
    DWORD dwBufferLen = 0;

    struct _AES_KEY_BLOB {
        BLOBHEADER hdr;
        DWORD dwKeySize;
        BYTE rgbKeyData[KEY_LEN];
    } keyBlobData;

    if (!CryptAcquireContextA(&hProv, NULL, MS_ENH_RSA_AES_PROV_A, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) {
        goto Cleanup;
    }

    ZeroMemory(&keyBlobData, sizeof(keyBlobData));
    keyBlobData.hdr.bType = PLAINTEXTKEYBLOB;
    keyBlobData.hdr.bVersion = CUR_BLOB_VERSION;
    keyBlobData.hdr.reserved = 0;
    keyBlobData.hdr.aiKeyAlg = CALG_AES_256;
    keyBlobData.dwKeySize = KEY_LEN;
    memcpy(keyBlobData.rgbKeyData, pKey, KEY_LEN);

    if (!CryptImportKey(hProv, (BYTE*)&keyBlobData, sizeof(keyBlobData), 0, 0, &hKey)) {
        goto Cleanup;
    }

    if (!CryptSetKeyParam(hKey, KP_IV, pVector, 0)) {
        goto Cleanup;
    }

    DWORD dwMode = CRYPT_MODE_CBC;
    if (!CryptSetKeyParam(hKey, KP_MODE, (BYTE*)&dwMode, 0)) {
        goto Cleanup;
    }

    DWORD dwPadding = PKCS5_PADDING;
    if (!CryptSetKeyParam(hKey, KP_PADDING, (BYTE*)&dwPadding, 0)) {
        goto Cleanup;
    }

    dwOutputLen = sInputSize;
    if (!CryptDecrypt(hKey, 0, TRUE, 0, NULL, &dwOutputLen)) {
        goto Cleanup;
    }

    pbOutputBuf = (PBYTE)HeapAlloc(GetProcessHeap(), 0, dwOutputLen);
    if (pbOutputBuf == NULL) {
        goto Cleanup;
    }

    memcpy(pbOutputBuf, pInputBuffer, sInputSize);
    dwBufferLen = sInputSize;

    if (!CryptDecrypt(hKey, 0, TRUE, 0, pbOutputBuf, &dwBufferLen)) {
        goto Cleanup;
    }

    *pOutputBuffer = pbOutputBuf;
    *sOutputSize = dwBufferLen;
    bResult = TRUE;
    pbOutputBuf = NULL;

Cleanup:
    if (hKey) CryptDestroyKey(hKey);
    if (hProv) CryptReleaseContext(hProv, 0);
    if (pbOutputBuf) HeapFree(GetProcessHeap(), 0, pbOutputBuf);

    return bResult;
}

//----------------[helpers]-------------------------------------------------//

char* formatRawBytesToCCode(PBYTE ciphertext, SIZE_T cipherSize,
    PBYTE key, SIZE_T keySize,
    PBYTE iv, SIZE_T ivSize) {
    if (!ciphertext || !key || !iv || cipherSize == 0 || keySize == 0 || ivSize == 0) {
        return NULL;
    }

    size_t bufferSize = 1024 + (cipherSize * 6) + (keySize * 6) + (ivSize * 6);
    char* formatted = (char*)malloc(bufferSize);

    if (!formatted) {
        return NULL;
    }

    char* pos = formatted;
    size_t remainingSize = bufferSize;
    int written;

    written = sprintf_s(pos, remainingSize, "unsigned char AesCipherText[] = { ");
    if (written < 0) { free(formatted); return NULL; }
    pos += written;
    remainingSize -= written;

    for (SIZE_T i = 0; i < cipherSize; i++) {
        written = sprintf_s(pos, remainingSize, "0x%02X", ciphertext[i]);
        if (written < 0) { free(formatted); return NULL; }
        pos += written;
        remainingSize -= written;

        if (i < cipherSize - 1) {
            written = sprintf_s(pos, remainingSize, ", ");
            if (written < 0) { free(formatted); return NULL; }
            pos += written;
            remainingSize -= written;
        }
    }
    written = sprintf_s(pos, remainingSize, " };\n");
    if (written < 0) { free(formatted); return NULL; }
    pos += written;
    remainingSize -= written;

    written = sprintf_s(pos, remainingSize, "unsigned char AesKey[] = { ");
    if (written < 0) { free(formatted); return NULL; }
    pos += written;
    remainingSize -= written;

    for (SIZE_T i = 0; i < keySize; i++) {
        written = sprintf_s(pos, remainingSize, "0x%02X", key[i]);
        if (written < 0) { free(formatted); return NULL; }
        pos += written;
        remainingSize -= written;

        if (i < keySize - 1) {
            written = sprintf_s(pos, remainingSize, ", ");
            if (written < 0) { free(formatted); return NULL; }
            pos += written;
            remainingSize -= written;
        }
    }
    written = sprintf_s(pos, remainingSize, " };\n");
    if (written < 0) { free(formatted); return NULL; }
    pos += written;
    remainingSize -= written;

    written = sprintf_s(pos, remainingSize, "unsigned char AesIv[] = { ");
    if (written < 0) { free(formatted); return NULL; }
    pos += written;
    remainingSize -= written;

    for (SIZE_T i = 0; i < ivSize; i++) {
        written = sprintf_s(pos, remainingSize, "0x%02X", iv[i]);
        if (written < 0) { free(formatted); return NULL; }
        pos += written;
        remainingSize -= written;

        if (i < ivSize - 1) {
            written = sprintf_s(pos, remainingSize, ", ");
            if (written < 0) { free(formatted); return NULL; }
            pos += written;
            remainingSize -= written;
        }
    }
    written = sprintf_s(pos, remainingSize, " };\n");
    if (written < 0) { free(formatted); return NULL; }

    return formatted;
}

BOOL aesDecryptionHelper(IN const char* encryptedContent, OUT PBYTE* pDecryptedData, OUT SIZE_T* sDecryptedData) {
    printf("[*] raw content\n");
    
    clearStoredVars();
    extractVars(encryptedContent);

    printf("[*] Extracted %d variables from encrypted content\n", g_varCount);

    ByteArrayVar* AesCipherText = findVar("AesCipherText");
    ByteArrayVar* AesKey = findVar("AesKey");
    ByteArrayVar* AesIv = findVar("AesIv");

    if (!AesCipherText || !AesKey || !AesIv) {
        printf("[!] Failed to find required variables: AesCipherText=%p, AesKey=%p, AesIv=%p\n", 
                 AesCipherText, AesKey, AesIv);
        clearStoredVars();
        return FALSE;
    }

    printf("[*] Found variables: CipherText size=%zu, Key size=%zu, IV size=%zu\n",
             AesCipherText->dataSize, AesKey->dataSize, AesIv->dataSize);

    PVOID tempDecryptedData = NULL;
    DWORD tempDecryptedSize = 0;

    if (!AesDecryption(AesCipherText->data, (DWORD)AesCipherText->dataSize, 
                       AesKey->data, AesIv->data, 
                       &tempDecryptedData, &tempDecryptedSize)) {
        printf("[!] AesDecryption function failed\n");
        clearStoredVars();
        return FALSE;
    }

    *pDecryptedData = (PBYTE)tempDecryptedData;
    *sDecryptedData = (SIZE_T)tempDecryptedSize;

    printf("[*] Decryption successful, output size: %zu bytes\n", *sDecryptedData);
    
    clearStoredVars();
    
    return TRUE;
}