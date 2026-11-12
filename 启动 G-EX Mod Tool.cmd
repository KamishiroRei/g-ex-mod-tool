@echo off
cd /d "%~dp0"
if exist "%~dp0G-EX Mod Tool.exe" (
    start "" "%~dp0G-EX Mod Tool.exe" %*
    exit /b
)
if exist "%~dp0dist\G-EX Mod Tool.exe" (
    start "" "%~dp0dist\G-EX Mod Tool.exe" %*
    exit /b
)
powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Please download the Windows release and run G-EX Mod Tool.exe.','G-EX Mod Tool')" >nul
exit /b 1
