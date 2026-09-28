@echo off
title SNAP Camera — starting full system
cd /d C:\Users\ritik\virtual-file-cam

echo Starting Frame Server...
sc.exe start FrameServer >nul 2>&1
sc.exe start FrameServerMonitor >nul 2>&1

if exist "C:\Program Files (x86)\VB\Voicemeeter\voicemeeter_x64.exe" (
  echo Starting Voicemeeter...
  start "" "C:\Program Files (x86)\VB\Voicemeeter\voicemeeter_x64.exe"
)

echo Starting OBS Virtual Camera...
start "" /D "C:\Program Files\obs-studio\bin\64bit" "C:\Program Files\obs-studio\bin\64bit\obs64.exe" --startvirtualcam --disable-shutdown-check --disable-updater

timeout /t 6 /nobreak >nul
python -c "import time
try:
 import uiautomation as auto
 w=auto.WindowControl(searchDepth=1, Name='OBS Studio Crash Detected')
 if w.Exists(4):
  w.ButtonControl(Name='Run in Normal Mode').Click()
except Exception:
 pass
" 2>nul

echo Starting file camera server...
start "SNAP File Camera" python -u C:\Users\ritik\virtual-file-cam\file_cam.py

timeout /t 4 /nobreak >nul
start "" http://127.0.0.1:8765/
start "" http://127.0.0.1:8765/history

echo Keep this window open. Watchdog OBS + camera ko zinda rakhega.
python -u C:\Users\ritik\virtual-file-cam\keep_alive.py
pause
