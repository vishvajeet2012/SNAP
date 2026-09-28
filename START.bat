@echo off
title Virtual File Camera Watchdog
cd /d C:\Users\ritik\virtual-file-cam
start "" "C:\Program Files\obs-studio\bin\64bit\obs64.exe" --startvirtualcam --disable-shutdown-check --disable-updater
timeout /t 6 /nobreak >nul
start "File Camera Server" python -u C:\Users\ritik\virtual-file-cam\file_cam.py
timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8765/
echo Keep this window open. OBS + camera auto-restart yahin se hoga.
python -u C:\Users\ritik\virtual-file-cam\keep_alive.py
pause
