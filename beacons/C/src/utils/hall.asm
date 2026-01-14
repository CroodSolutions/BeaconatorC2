;--------------------------------------------------------------------------------
; Hell's Hall - Assembly Syscall Stub
; Provides indirect syscall execution via dynamic SSN and syscall instruction address
;--------------------------------------------------------------------------------

.data
    dwSSN   DWORD   0h
    qAddr   QWORD   0h

.code

;--------------------------------------------------------------------------------
; SetConfig - Configure SSN and syscall instruction address before call
;--------------------------------------------------------------------------------
public SetConfig
SetConfig proc
    mov dwSSN, ecx
    mov qAddr, rdx
    ret
SetConfig endp

;--------------------------------------------------------------------------------
; HellHall - Execute syscall with configured SSN, jumping to legit syscall instruction
;--------------------------------------------------------------------------------
public HellHall
HellHall proc
    mov r10, rcx
    mov eax, dwSSN
    jmp qword ptr [qAddr]
    ret
HellHall endp

end