; ============================================================================
; BASE64 HELPER
; ============================================================================
; Base64 encoding/decoding utilities
; ============================================================================

Base64Decode(base64String) {
    ; Use CryptStringToBinary for decoding
    ; CRYPT_STRING_BASE64 = 1

    ; First call to get required size
    decodedSize := 0
    DllCall("Crypt32\CryptStringToBinaryW",
        "Str", base64String,
        "UInt", 0,
        "UInt", 1,  ; CRYPT_STRING_BASE64
        "Ptr", 0,
        "UInt*", &decodedSize,
        "Ptr", 0,
        "Ptr", 0)

    if (decodedSize = 0) {
        throw Error("Base64 decode size check failed")
    }

    ; Allocate buffer and decode
    decoded := Buffer(decodedSize, 0)
    result := DllCall("Crypt32\CryptStringToBinaryW",
        "Str", base64String,
        "UInt", 0,
        "UInt", 1,  ; CRYPT_STRING_BASE64
        "Ptr", decoded,
        "UInt*", &decodedSize,
        "Ptr", 0,
        "Ptr", 0)

    if (!result) {
        throw Error("Base64 decode failed: " A_LastError)
    }

    return decoded
}

Base64Encode(data, dataSize := 0) {
    ; Use CryptBinaryToString for encoding
    ; CRYPT_STRING_BASE64 = 1

    if (Type(data) = "Buffer") {
        dataPtr := data.Ptr
        dataSize := data.Size
    } else {
        dataPtr := data
    }

    ; First call to get required size
    encodedSize := 0
    DllCall("Crypt32\CryptBinaryToStringW",
        "Ptr", dataPtr,
        "UInt", dataSize,
        "UInt", 1,  ; CRYPT_STRING_BASE64
        "Ptr", 0,
        "UInt*", &encodedSize)

    if (encodedSize = 0) {
        throw Error("Base64 encode size check failed")
    }

    ; Allocate buffer and encode
    encoded := Buffer(encodedSize * 2, 0)  ; Wide chars
    result := DllCall("Crypt32\CryptBinaryToStringW",
        "Ptr", dataPtr,
        "UInt", dataSize,
        "UInt", 1,  ; CRYPT_STRING_BASE64
        "Ptr", encoded,
        "UInt*", &encodedSize)

    if (!result) {
        throw Error("Base64 encode failed: " A_LastError)
    }

    return StrGet(encoded, "UTF-16")
}
