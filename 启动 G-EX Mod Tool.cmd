@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 "%~dp0gex_mod_tool.pyw" %*
    exit /b
)
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%~dp0gex_mod_tool.pyw" %*
    exit /b
)
echo Python 3 with Tkinter is required.
pause
exit /b 1
