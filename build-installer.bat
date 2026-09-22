@echo off
REM Danh cho nguoi build: tao bo cai mot file dist\TalkCutStudio-Setup.exe.
REM Them /build de build lai image tu ma nguon truoc khi dong goi.
if /I "%~1"=="/build" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\build-installer.ps1" -Build
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\build-installer.ps1"
)
echo.
pause
