; Hermes Spotlight 快捷键
#Requires AutoHotkey v2.0
#SingleInstance Force

; F11 键切换搜索框显示/隐藏
F11:: {
    ; 检查 pythonw.exe 是否在运行
    if ProcessExist("pythonw.exe") {
        ; 创建信号文件
        FileAppend "toggle", A_ScriptDir "\toggle_signal.txt"
    } else {
        ; 启动搜索框
        Run '"' A_ScriptDir '\hermes_spotlight.bat"', , 'Hide'
    }
}

; F23 键 (Copilot 键) 切换搜索框显示/隐藏 - 使用扫描码
SC06E:: {
    ; 检查 pythonw.exe 是否在运行
    if ProcessExist("pythonw.exe") {
        ; 创建信号文件
        FileAppend "toggle", A_ScriptDir "\toggle_signal.txt"
    } else {
        ; 启动搜索框
        Run '"' A_ScriptDir '\hermes_spotlight.bat"', , 'Hide'
    }
}
