; ============================================================================
; AHK BEACON - Header
; ============================================================================
; AutoHotkey requirements and core configuration
; ============================================================================

#Requires AutoHotkey v2.0
#SingleInstance Force

; ============================================================================
; CONFIGURATION (placeholders replaced during build)
; ============================================================================
global SERVER_IP := "{{server_ip}}"
global SERVER_PORT := {{server_port}}
global CHECK_IN_INTERVAL := {{checkin_interval}}
