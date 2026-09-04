; Honor Agent - Universal Desktop Launcher
; Binds global shortcuts (Ctrl + Shift + Space / F11) to trigger the Spotlight assistant
#Requires AutoHotkey v2.0
#SingleInstance Force

; Primary global hotkey: Ctrl + Shift + Space
^+Space::ToggleSpotlight()

; Secondary hotkey fallback: F11
F11::ToggleSpotlight()

ToggleSpotlight() {
    signalFile := A_ScriptDir "\toggle_signal.txt"
    batchLauncher := A_ScriptDir "\hermes_spotlight.bat"

    ; Check if pythonw or python process is active
    if ProcessExist("pythonw.exe") || ProcessExist("python.exe") {
        try {
            FileAppend "toggle`n", signalFile
        } catch as e {
            ; Fallback to launching batch if file write fails
            Run '"' batchLauncher '"', , 'Hide'
        }
    } else {
        ; Start Spotlight process
        Run '"' batchLauncher '"', , 'Hide'
    }
}
