; ============================================================================
; UPDATE CHECK-IN MODULE
; ============================================================================
; Changes the beacon's check-in interval
; ============================================================================

UpdateCheckIn(interval) {
    this.Log(interval * 1000)
    this.checkInInterval := (interval * 1000)
    this.StopCheckInLoop()
    this.StartCheckInLoop()
}
