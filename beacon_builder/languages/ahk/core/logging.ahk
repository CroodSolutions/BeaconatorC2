; ============================================================================
; LOGGING FUNCTION
; ============================================================================

BOFLog(msg, prefix := "BOF") {
    timestamp := FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss")
    logMessage := timestamp " [" prefix "] " msg "`n"

    try {
        FileAppend(logMessage, "*")  ; stdout
    } catch Error as err {
        FileAppend(logMessage, "bof_debug.txt")
    }
}
