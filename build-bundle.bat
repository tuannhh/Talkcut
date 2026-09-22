@echo off
REM Danh cho nguoi build (khong gui cho nguoi dung cuoi): dong goi bo cai Windows
REM vao dist\talkcut-install\. Them tham so /build de build image truoc khi dong goi.
if /I "%~1"=="/build" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-bundle.ps1" -Build
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-bundle.ps1"
)
echo.
pause
