@echo off
title Chrome with OBS Virtual Camera
echo Chrome restart ho raha hai taaki OBS Virtual Camera dikhe...
taskkill /IM chrome.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --disable-features=MediaFoundationVideoCapture,MediaFoundationD3D11VideoCapture --use-fake-ui-for-media-stream=false "http://127.0.0.1:8765/"
echo Chrome khul gaya. Camera list mein: OBS Virtual Camera
exit
