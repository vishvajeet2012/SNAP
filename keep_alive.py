"""Keep OBS Virtual Camera + file camera server running."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OBS_DIR = Path(r"C:\Program Files\obs-studio\bin\64bit")
OBS_EXE = OBS_DIR / "obs64.exe"
CAM_PY = ROOT / "file_cam.py"
LOG = ROOT / "keep_alive.log"
URL = "http://127.0.0.1:8765/health"
PY = sys.executable


def log(msg: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def running(name: str) -> bool:
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return name.lower() in out.lower()
    except Exception:
        return False


def cam_ok() -> bool:
    try:
        with urllib.request.urlopen(URL, timeout=2) as r:
            return r.read().strip() == b"ok"
    except Exception:
        return False


def start_obs() -> None:
    if running("obs64.exe"):
        return
    log("Starting OBS")
    subprocess.Popen(
        [
            str(OBS_EXE),
            "--startvirtualcam",
            "--disable-shutdown-check",
            "--disable-updater",
        ],
        cwd=str(OBS_DIR),
        close_fds=True,
    )


def start_cam() -> None:
    if cam_ok():
        return
    log("Starting file camera")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    subprocess.Popen(
        [PY, "-u", str(CAM_PY)],
        cwd=str(ROOT),
        env=env,
        close_fds=True,
    )


def main() -> None:
    log("Watchdog running — leave this window open")
    while True:
        try:
            start_obs()
            time.sleep(4)
            start_cam()
        except Exception as exc:
            log(f"error: {exc}")
        time.sleep(5)


if __name__ == "__main__":
    main()
