# 创建 AHK 脚本的开机自启动快捷方式
$WshShell = New-Object -ComObject WScript.Shell
$StartupPath = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $StartupPath 'HermesSpotlight.lnk'
$AhkPath = 'C:\Users\26502\AppData\Local\Programs\AutoHotkey\v2\AutoHotkey64.exe'
$ScriptPath = Join-Path $PSScriptRoot 'copilot-to-hermes.ahk'

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $AhkPath
$Shortcut.Arguments = "`"$ScriptPath`""
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.WindowStyle = 7  # Minimized (hidden)
$Shortcut.Save()

Write-Host "Created startup shortcut: $ShortcutPath"
Write-Host "AHK script will run on Windows startup."
