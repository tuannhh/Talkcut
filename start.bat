@echo off
REM TalkCut Studio - nhan doi (double-click) file nay de chay tren Windows.
REM Goi scripts\start.ps1 (bo qua ExecutionPolicy vi day la script noi bo).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
echo.
pause
