@echo off
REM Dung (tat) TalkCut Studio. Du lieu van duoc giu trong Docker volume.
cd /d "%~dp0"
echo Dang dung TalkCut Studio...
docker compose -f compose.yaml down
echo Da dung. Chay start.bat de mo lai (du lieu van con).
pause
