#include "helpers.h"
#pragma comment(lib, "winhttp.lib")

//----------------[request]-------------------------------------------------//

MyHttpResponse* makeHttpRequest(const char* url, const char* data, const char* method, const char* headers) {
    HINTERNET hSession = NULL;
    HINTERNET hConnect = NULL;
    HINTERNET hRequest = NULL;
    MyHttpResponse* response = NULL;

    printf("DEBUG: Making HTTP request to: %s\n", url ? url : "NULL");
    printf("DEBUG: Request method: %s\n", method ? method : "NULL");
    printf("DEBUG: Request data: %s\n", data ? data : "NULL");

    response = (MyHttpResponse*)safe_malloc(sizeof(MyHttpResponse));
    if (response == NULL) {
        printf("DEBUG: Failed to allocate response structure\n");
        return NULL;
    }
    response->data = NULL;
    response->size = 0;

    hSession = WinHttpOpen(
        L"Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        0
    );

    if (hSession == NULL) {
        printf("DEBUG: Failed to open WinHTTP session. Error: %lu\n", GetLastError());
        safe_free(response);
        return NULL;
    }

    URL_COMPONENTSW urlComp;
    ZeroMemory(&urlComp, sizeof(urlComp));
    urlComp.dwStructSize = sizeof(urlComp);
    urlComp.lpszHostName = (LPWSTR)safe_malloc(256 * sizeof(WCHAR));
    urlComp.dwHostNameLength = 256;
    urlComp.lpszUrlPath = (LPWSTR)safe_malloc(1024 * sizeof(WCHAR));
    urlComp.dwUrlPathLength = 1024;

    int urlLen = MultiByteToWideChar(CP_UTF8, 0, url, -1, NULL, 0);
    LPWSTR wideUrl = (LPWSTR)safe_malloc(urlLen * sizeof(WCHAR));
    MultiByteToWideChar(CP_UTF8, 0, url, -1, wideUrl, urlLen);

    if (!WinHttpCrackUrl(wideUrl, 0, 0, &urlComp)) {
        printf("DEBUG: Failed to crack URL. Error: %lu\n", GetLastError());
        goto cleanup;
    }

    printf("DEBUG: Connecting to host: %S on port: %d\n", urlComp.lpszHostName, urlComp.nPort);

    hConnect = WinHttpConnect(hSession, urlComp.lpszHostName, urlComp.nPort, 0);
    if (hConnect == NULL) {
        printf("DEBUG: Failed to connect to host. Error: %lu\n", GetLastError());
        goto cleanup;
    }

    LPCWSTR httpMethod = L"GET";
    if (method != NULL && strcmp(method, "POST") == 0) {
        httpMethod = L"POST";
    }

    hRequest = WinHttpOpenRequest(
        hConnect,
        httpMethod,
        urlComp.lpszUrlPath,
        NULL,
        WINHTTP_NO_REFERER,
        WINHTTP_DEFAULT_ACCEPT_TYPES,
        (urlComp.nScheme == INTERNET_SCHEME_HTTPS) ? WINHTTP_FLAG_SECURE : 0
    );

    if (hRequest == NULL) {
        printf("DEBUG: Failed to open request. Error: %lu\n", GetLastError());
        goto cleanup;
    }

    if (headers != NULL) {
        int headerLen = MultiByteToWideChar(CP_UTF8, 0, headers, -1, NULL, 0);
        LPWSTR wideHeaders = (LPWSTR)safe_malloc(headerLen * sizeof(WCHAR));
        MultiByteToWideChar(CP_UTF8, 0, headers, -1, wideHeaders, headerLen);

        if (!WinHttpAddRequestHeaders(hRequest, wideHeaders, -1, WINHTTP_ADDREQ_FLAG_ADD)) {
            printf("DEBUG: Failed to add headers. Error: %lu\n", GetLastError());
        }

        safe_free(wideHeaders);
    }

    BOOL bResult = FALSE;
    if (data != NULL && strcmp(method, "POST") == 0) {
        printf("DEBUG: Sending POST request with data length: %zu\n", strlen(data));
        bResult = WinHttpSendRequest(
            hRequest,
            WINHTTP_NO_ADDITIONAL_HEADERS,
            0,
            (LPVOID)data,
            (DWORD)strlen(data),
            (DWORD)strlen(data),
            0
        );
    } else {
        printf("DEBUG: Sending GET request\n");
        bResult = WinHttpSendRequest(
            hRequest,
            WINHTTP_NO_ADDITIONAL_HEADERS,
            0,
            WINHTTP_NO_REQUEST_DATA,
            0,
            0,
            0
        );
    }

    if (!bResult) {
        printf("DEBUG: Failed to send request. Error: %lu\n", GetLastError());
        goto cleanup;
    }

    if (!WinHttpReceiveResponse(hRequest, NULL)) {
        printf("DEBUG: Failed to receive response. Error: %lu\n", GetLastError());
        goto cleanup;
    }

    printf("DEBUG: Response received, reading data...\n");

    DWORD dwSize = 0;
    DWORD dwDownloaded = 0;
    char* pszOutBuffer;

    do {
        dwSize = 0;
        if (!WinHttpQueryDataAvailable(hRequest, &dwSize)) {
            printf("DEBUG: Failed to query data available. Error: %lu\n", GetLastError());
            break;
        }

        if (dwSize == 0) break;

        pszOutBuffer = (char*)safe_malloc(dwSize + 1);
        if (pszOutBuffer == NULL) {
            printf("DEBUG: Failed to allocate output buffer\n");
            break;
        }

        ZeroMemory(pszOutBuffer, dwSize + 1);

        if (!WinHttpReadData(hRequest, (LPVOID)pszOutBuffer, dwSize, &dwDownloaded)) {
            printf("DEBUG: Failed to read data. Error: %lu\n", GetLastError());
            safe_free(pszOutBuffer);
            break;
        }

        char* newData = (char*)safe_realloc(response->data, response->size + dwDownloaded + 1);
        if (newData == NULL) {
            printf("DEBUG: Failed to reallocate response buffer\n");
            safe_free(pszOutBuffer);
            break;
        }

        response->data = newData;
        memcpy(response->data + response->size, pszOutBuffer, dwDownloaded);
        response->size += dwDownloaded;
        response->data[response->size] = '\0';

        printf("DEBUG: Read %lu bytes, total size now: %zu\n", dwDownloaded, response->size);

        safe_free(pszOutBuffer);

    } while (dwSize > 0);

    if (response->data && response->size > 0) {
        printf("DEBUG: Complete response received: [%s] (length: %zu)\n", response->data, response->size);
    }

cleanup:
    if (hRequest) WinHttpCloseHandle(hRequest);
    if (hConnect) WinHttpCloseHandle(hConnect);
    if (hSession) WinHttpCloseHandle(hSession);

    if (urlComp.lpszHostName) safe_free(urlComp.lpszHostName);
    if (urlComp.lpszUrlPath) safe_free(urlComp.lpszUrlPath);
    if (wideUrl) safe_free(wideUrl);

    return response;
}

//----------------[utils]---------------------------------------------------//

char* buildHttpUrl(const char* baseUrl, const char* endpoint) {
    if (baseUrl == NULL) {
        return NULL;
    }

    size_t totalLen = strlen(baseUrl) + (endpoint ? strlen(endpoint) : 0) + 2;
    char* url = (char*)safe_malloc(totalLen);

    if (url != NULL) {
        if (strcpy_s(url, totalLen, baseUrl) != 0) {
            safe_free(url);
            return NULL;
        }

        if (endpoint != NULL) {
            if (baseUrl[strlen(baseUrl) - 1] != '/' && endpoint[0] != '/') {
                if (strcat_s(url, totalLen, "/") != 0) {
                    safe_free(url);
                    return NULL;
                }
            }
            if (strcat_s(url, totalLen, endpoint) != 0) {
                safe_free(url);
                return NULL;
            }
        }
    }

    return url;
}

char* httpSendToServer(const char* data) {
    if (data == NULL) {
        return NULL;
    }

    printf("DEBUG: httpSendToServer called with data: %s\n", data);

    char* url = buildHttpUrl(g_serverUrl, NULL);
    MyHttpResponse* response = makeHttpRequest(url, data, "POST", "Content-Type: text/plain");

    char* responseData = NULL;
    if (response != NULL) {
        if (response->data != NULL && response->size > 0) {
            responseData = (char*)safe_malloc(response->size + 1);
            if (responseData != NULL) {
                memcpy(responseData, response->data, response->size);
                responseData[response->size] = '\0';
                printf("DEBUG: Server response: %s\n", responseData);
            }
        } else {
            printf("DEBUG: No response data received\n");
        }
        freeHttpResponse(response);
    } else {
        printf("DEBUG: No response received\n");
    }

    safe_free(url);
    return responseData;
}

char* urlEncode(const char* str) {
    if (str == NULL) {
        return NULL;
    }

    size_t len = strlen(str);
    char* encoded = (char*)safe_malloc(len * 3 + 1);
    if (encoded == NULL) {
        return NULL;
    }

    char* p = encoded;
    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)str[i];

        if (isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~') {
            *p++ = c;
        } else if (c == ' ') {
            *p++ = '%';
            *p++ = '2';
            *p++ = '0';
        } else if (c == '\n') {
            *p++ = '%';
            *p++ = '0';
            *p++ = 'A';
        } else if (c == '\t') {
            *p++ = '%';
            *p++ = '0';
            *p++ = '9';
        } else {
            *p++ = '%';
            snprintf(p, 3, "%02X", c);
            p += 2;
        }
    }
    *p = '\0';

    return encoded;
}

void freeHttpResponse(MyHttpResponse* response) {
    if (response != NULL) {
        if (response->data) {
            safe_free(response->data);
        }
        safe_free(response);
    }
}