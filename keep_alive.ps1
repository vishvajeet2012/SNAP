$ErrorActionPreference = "SilentlyContinue"
$obsDir = "C:\Program Files\obs-studio\bin\64bit"
$obsExe = Join-Path $obsDir "obs64.exe"
$py = "C:\Users\ritik\AppData\Local\Programs\Python\Python310\python.exe"
$script = "C:\Users\ritik\virtual-file-cam\file_cam.py"
$log = "C:\Users\ritik\virtual-file-cam\keep_alive.log"

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Add-Content -Path $log -Value $line
}

function Ensure-Obs {
    $p = Get-Process obs64 -ErrorAction SilentlyContinue
    if ($p) { return }
    Write-Log "Starting OBS virtual camera"
    Start-Process -FilePath $obsExe -WorkingDirectory $obsDir -ArgumentList "--startvirtualcam","--minimize-to-tray","--disable-shutdown-check","--disable-updater"
    Start-Sleep -Seconds 6
}

function Ensure-Cam {
    $ok = $false
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8765/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ok = $true }
    } catch { $ok = $false }
    if ($ok) { return }
    Write-Log "Starting file camera server"
    Start-Process -FilePath $py -WorkingDirectory "C:\Users\ritik\virtual-file-cam" -ArgumentList "-u",$script -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

Write-Log "Watchdog started"
while ($true) {
    try {
        Ensure-Obs
        Ensure-Cam
    } catch {
        Write-Log "loop error: $_"
    }
    Start-Sleep -Seconds 4
}
