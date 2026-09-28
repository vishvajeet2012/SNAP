"""
Virtual File Camera — browser live stream that stays up when tabs close/open.
"""
from __future__ import annotations

import cgi
import hashlib
import html
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

WATCH_DIR = Path(__file__).resolve().parent / "watch"
UPLOAD_DIR = WATCH_DIR / "uploads"
HISTORY_DIR = Path(__file__).resolve().parent / "history"
HISTORY_JSON = HISTORY_DIR / "history.json"
DOWNLOADS = Path.home() / "Downloads"
HOST = "127.0.0.1"
PORT = 8765
WIDTH, HEIGHT = 1920, 1080
FPS = 30
JPEG_QUALITY = 95
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
VIDEO_EXTS = {
    ".mp4", ".avi", ".mkv", ".mov", ".webm", ".m4v", ".wmv", ".flv", ".mpeg",
    ".mpg", ".mpe", ".3gp", ".3g2", ".ts", ".m2ts", ".mts", ".ogv", ".ogg",
    ".vob", ".f4v", ".asf", ".divx", ".xvid", ".rm", ".rmvb", ".m2v", ".m1v",
    ".hevc", ".h264", ".264", ".265", ".mp2", ".mod", ".tod", ".mxf", ".nut",
}
BROWSER_VIDEO = {".mp4", ".webm", ".ogv", ".ogg"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS
SKIP_EXTS = {".tmp", ".crdownload", ".part", ".download", ".opdownload"}

lock = threading.Lock()
current_jpeg = b""
current_rgb = None
current_path: Path | None = None
media_kind = "none"
media_token = 0
media_width = 0
media_height = 0
pan_x = 0
pan_y = 0
zoom = 1.0
PAN_STEP_X = int(WIDTH * 0.05)
PAN_STEP_Y = int(HEIGHT * 0.05)
ZOOM_STEP = 0.05
ZOOM_MIN = 0.25
ZOOM_MAX = 5.0
audio_proc = None
status_text = "Waiting for image or video..."
video_cap = None
running = True
vcam = None
MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".m4v": "video/mp4",
    ".ogv": "video/ogg",
    ".ogg": "video/ogg",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
    ".3gp": "video/3gpp",
    ".ts": "video/mp2t",
}

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Virtual File Camera</title>
<style>
  html,body{margin:0;height:100%;background:#0c0e16;color:#e8eef8;font-family:Segoe UI,Arial,sans-serif}
  .wrap{display:flex;flex-direction:column;height:100%}
  header{padding:12px 18px;display:flex;justify-content:space-between;align-items:center;
         background:#121624;border-bottom:1px solid #2a3350}
  h1{font-size:18px;margin:0;font-weight:600}
  .hint{font-size:13px;color:#9aa8c7}
  .stage{flex:1;display:flex;align-items:center;justify-content:center;padding:16px;position:relative;overflow:hidden}
  .frame{width:min(100%, calc(100vh * 16 / 9));aspect-ratio:16/9;background:#000;
         display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative}
  img#live,video#livev{max-width:100%;max-height:100%;width:auto;height:auto;
           object-fit:contain;background:#000;user-select:none;image-rendering:auto;
           transform-origin:center center}
  .drop{position:absolute;inset:16px;border:2px dashed transparent;border-radius:16px;pointer-events:none}
  body.drag .drop{border-color:#50b4ff;background:#50b4ff18}
  .nav{position:absolute;top:50%;transform:translateY(-50%);z-index:5;
       width:72px;height:72px;border:0;border-radius:50%;cursor:pointer;
       background:#50b4ff;color:#041018;font-size:28px;font-weight:700;
       box-shadow:0 8px 24px #0008}
  .nav:hover{background:#7cc8ff}
  .nav.left{left:24px}
  .nav.right{right:24px}
  .nav.up{top:24px;left:50%;transform:translateX(-50%)}
  .nav.down{top:auto;bottom:108px;left:50%;transform:translateX(-50%)}
  .zoombar{position:absolute;bottom:28px;left:50%;transform:translateX(-50%);z-index:5;
           display:flex;gap:12px;align-items:center}
  .zoombar button{width:64px;height:64px;border:0;border-radius:16px;cursor:pointer;
           background:#50b4ff;color:#041018;font-size:28px;font-weight:700;
           box-shadow:0 8px 24px #0008}
  .zoombar button:hover{background:#7cc8ff}
  .zoombar .lvl{min-width:64px;text-align:center;color:#e8eef8;font-size:16px}
  footer{padding:10px 18px;font-size:12px;color:#8b97b0;background:#121624;
         display:flex;justify-content:space-between;align-items:center;gap:12px}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Virtual File Camera</h1>
    <div class="hint"><a href="/history" style="color:#7cc8ff">History</a> · default Downloads · OBS Virtual Camera</div>
  </header>
  <div class="stage" id="stage">
    <div class="drop"></div>
    <button class="nav left" id="btnL" title="Move left">◀</button>
    <button class="nav up" id="btnU" title="Move up">▲</button>
    <div class="frame">
      <img id="live" alt="live camera"/>
      <video id="livev" autoplay loop playsinline muted style="display:none"></video>
    </div>
    <button class="nav right" id="btnR" title="Move right">▶</button>
    <button class="nav down" id="btnD" title="Move down">▼</button>
    <div class="zoombar">
      <button id="btnOut" title="Zoom out">−</button>
      <span class="lvl" id="zoomLbl">100%</span>
      <button id="btnIn" title="Zoom in">+</button>
    </div>
  </div>
  <footer>
    <span>16:9 stream · original quality</span>
    <span>◀ ▶ ▲ ▼ move · + − zoom</span>
  </footer>
</div>
<script>
const img = document.getElementById('live');
const vid = document.getElementById('livev');
let token = -1;
function applyView(x, y, z) {
  const t = 'translate(' + (x || 0) + 'px,' + (y || 0) + 'px) scale(' + (z || 1) + ')';
  img.style.transform = t;
  vid.style.transform = t;
  const lbl = document.getElementById('zoomLbl');
  if (lbl) lbl.textContent = Math.round((z || 1) * 100) + '%';
}
async function tick() {
  try {
    const s = await (await fetch('/status')).json();
    applyView(s.pan_x, s.pan_y, s.zoom);
    if (s.token === token) return;
    token = s.token;
    const src = '/original?t=' + token;
    if (s.kind === 'video') {
      img.style.display = 'none';
      vid.style.display = 'block';
      vid.muted = true;
      vid.src = src;
      vid.play().catch(()=>{});
    } else {
      vid.pause();
      vid.style.display = 'none';
      img.style.display = 'block';
      img.src = src;
    }
  } catch (e) {}
}
async function move(dir) {
  const s = await (await fetch('/move?dir=' + dir)).json();
  applyView(s.pan_x, s.pan_y, s.zoom);
}
document.getElementById('btnL').onclick = () => move('left');
document.getElementById('btnR').onclick = () => move('right');
document.getElementById('btnU').onclick = () => move('up');
document.getElementById('btnD').onclick = () => move('down');
document.getElementById('btnIn').onclick = () => move('in');
document.getElementById('btnOut').onclick = () => move('out');
window.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowLeft') move('left');
  if (e.key === 'ArrowRight') move('right');
  if (e.key === 'ArrowUp') move('up');
  if (e.key === 'ArrowDown') move('down');
  if (e.key === '+' || e.key === '=') move('in');
  if (e.key === '-' || e.key === '_') move('out');
});
document.getElementById('stage').addEventListener('wheel', (e) => {
  e.preventDefault();
  move(e.deltaY < 0 ? 'in' : 'out');
}, {passive:false});
setInterval(tick, 200);
tick();
['dragenter','dragover'].forEach(ev => {
  window.addEventListener(ev, e => { e.preventDefault(); document.body.classList.add('drag'); });
});
['dragleave','drop'].forEach(ev => {
  window.addEventListener(ev, e => { e.preventDefault(); document.body.classList.remove('drag'); });
});
window.addEventListener('drop', async e => {
  const files = [...(e.dataTransfer.files || [])];
  if (!files.length) return;
  const fd = new FormData();
  fd.append('file', files[0], files[0].name);
  await fetch('/upload', { method: 'POST', body: fd });
});
</script>
</body>
</html>
"""

CLEAN = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta http-equiv="Cache-Control" content="no-store"/>
<style>
  html,body{margin:0;padding:0;width:1920px;height:1080px;background:#000;overflow:hidden;
            display:flex;align-items:center;justify-content:center}
  img,video{max-width:1920px;max-height:1080px;width:auto;height:auto;
            object-fit:contain;display:block;image-rendering:auto;
            transform-origin:center center}
</style>
</head>
<body>
<img id="live" alt="cam"/>
<video id="livev" autoplay loop muted playsinline style="display:none"></video>
<script>
const img = document.getElementById('live');
const vid = document.getElementById('livev');
let token = -1;
function applyView(x, y, z) {
  const t = 'translate(' + (x || 0) + 'px,' + (y || 0) + 'px) scale(' + (z || 1) + ')';
  img.style.transform = t;
  vid.style.transform = t;
}
async function tick() {
  try {
    const s = await (await fetch('/status')).json();
    applyView(s.pan_x, s.pan_y, s.zoom);
    if (s.token === token) return;
    token = s.token;
    const src = '/original?t=' + token;
    if (s.kind === 'video') {
      img.style.display = 'none';
      vid.style.display = 'block';
      vid.muted = true;
      vid.src = src;
      vid.play().catch(()=>{});
    } else {
      vid.pause();
      vid.removeAttribute('src');
      vid.style.display = 'none';
      img.style.display = 'block';
      img.src = src;
    }
  } catch (e) {}
}
setInterval(tick, 120);
tick();
</script>
</body>
</html>
"""

HISTORY_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>History — Virtual File Camera</title>
<style>
  html,body{margin:0;background:#0c0e16;color:#e8eef8;font-family:Segoe UI,Arial,sans-serif}
  header{padding:14px 18px;background:#121624;border-bottom:1px solid #2a3350;
         display:flex;justify-content:space-between;align-items:center}
  a{color:#7cc8ff;text-decoration:none}
  h1{font-size:18px;margin:0}
  h2{font-size:15px;margin:18px 18px 8px;color:#9aa8c7}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;padding:0 18px 28px}
  .card{background:#121624;border:1px solid #2a3350;border-radius:12px;overflow:hidden;cursor:pointer}
  .card:hover{border-color:#50b4ff}
  .card.active{outline:2px solid #50b4ff}
  .thumb{height:140px;background:#000;display:flex;align-items:center;justify-content:center;overflow:hidden}
  .thumb img,.thumb video{max-width:100%;max-height:140px;object-fit:contain}
  .meta{padding:8px 10px;font-size:12px}
  .name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .sub{color:#8b97b0;margin-top:4px}
</style>
</head>
<body>
<header>
  <h1>History</h1>
  <div><a href="/">Live camera</a></div>
</header>
<h2>Downloads (default yahi se latest show hota hai)</h2>
<div class="grid" id="dl"></div>
<h2>Saved — kahi se bhi jo show hua</h2>
<div class="grid" id="hist"></div>
<script>
function card(item, prefix) {
  const el = document.createElement('div');
  el.className = 'card';
  const src = prefix + encodeURIComponent(item.id);
  const media = item.kind === 'video'
    ? '<video src="'+src+'" muted></video>'
    : '<img src="'+src+'" alt="">';
  el.innerHTML = '<div class="thumb">'+media+'</div><div class="meta"><div class="name"></div><div class="sub"></div></div>';
  el.querySelector('.name').textContent = item.name;
  el.querySelector('.sub').textContent = (item.width||'?')+'x'+(item.height||'?')+' · '+(item.ts||'');
  el.onclick = async () => {
    await fetch('/select?id=' + encodeURIComponent(item.id));
    location.href = '/';
  };
  return el;
}
async function load() {
  const d = await (await fetch('/api/downloads')).json();
  const h = await (await fetch('/api/history')).json();
  const dl = document.getElementById('dl');
  const hist = document.getElementById('hist');
  dl.innerHTML = ''; hist.innerHTML = '';
  (d.items||[]).forEach(it => dl.appendChild(card(it, '/dlfile?id=')));
  (h.items||[]).forEach(it => hist.appendChild(card(it, '/histfile?id=')));
}
load();
setInterval(load, 4000);
</script>
</body>
</html>
"""


def blank_frame(message: str, subtitle: str = "") -> np.ndarray:
    img = Image.new("RGB", (WIDTH, HEIGHT), (12, 14, 22))
    draw = ImageDraw.Draw(img)
    try:
        font_l = ImageFont.truetype("arial.ttf", 40)
        font_s = ImageFont.truetype("arial.ttf", 22)
        font_t = ImageFont.truetype("consola.ttf", 18)
    except OSError:
        font_l = font_s = font_t = ImageFont.load_default()
    draw.rectangle([40, 40, WIDTH - 40, HEIGHT - 40], outline=(80, 180, 255), width=3)
    draw.text((70, 70), "VIRTUAL FILE CAMERA", fill=(80, 180, 255), font=font_l)
    draw.text((70, 140), message[:95], fill=(240, 240, 240), font=font_s)
    if subtitle:
        draw.text((70, 190), subtitle[:110], fill=(160, 170, 190), font=font_t)
    draw.text((70, HEIGHT - 100), "Browser tab band/open — server chalta rahega", fill=(140, 200, 140), font=font_s)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def fit_bgr(frame: np.ndarray) -> np.ndarray:
    """Fill 16:9 camera frame (center-crop) with sharp resize — no letterbox, no overlay."""
    h, w = frame.shape[:2]
    if h == 0 or w == 0:
        return np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    scale = max(WIDTH / w, HEIGHT / h)
    nw, nh = max(WIDTH, int(round(w * scale))), max(HEIGHT, int(round(h * scale)))
    interp = cv2.INTER_LANCZOS4 if scale >= 1 else cv2.INTER_AREA
    resized = cv2.resize(frame, (nw, nh), interpolation=interp)
    x = max(0, (nw - WIDTH) // 2)
    y = max(0, (nh - HEIGHT) // 2)
    crop = resized[y : y + HEIGHT, x : x + WIDTH]
    if crop.shape[0] != HEIGHT or crop.shape[1] != WIDTH:
        crop = cv2.resize(crop, (WIDTH, HEIGHT), interpolation=cv2.INTER_LANCZOS4)
    return crop


def encode_jpeg(frame: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    return buf.tobytes() if ok else b""


def set_frame(frame: np.ndarray) -> None:
    global current_jpeg, current_rgb
    fitted = fit_bgr(frame)
    jpeg = encode_jpeg(fitted)
    rgb = cv2.cvtColor(fitted, cv2.COLOR_BGR2RGB)
    with lock:
        if jpeg:
            current_jpeg = jpeg
        current_rgb = rgb


_ffmpeg_bin: str | None = None


def obs_password() -> str:
    cfg = Path.home() / "AppData/Roaming/obs-studio/plugin_config/obs-websocket/config.json"
    try:
        return json.loads(cfg.read_text(encoding="utf-8")).get("server_password") or ""
    except Exception:
        return ""


def find_ffmpeg() -> str | None:
    global _ffmpeg_bin
    if _ffmpeg_bin:
        return _ffmpeg_bin
    found = shutil.which("ffmpeg")
    if found:
        _ffmpeg_bin = found
        return found
    guesses = [
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\Gyan\FFmpeg\bin\ffmpeg.exe"),
        Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe",
    ]
    try:
        root = Path(r"C:\Users\ritik\AppData\Local\Microsoft\WinGet\Packages")
        if root.is_dir():
            guesses.extend(root.glob("Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe"))
    except Exception:
        pass
    for p in guesses:
        if p.is_file():
            _ffmpeg_bin = str(p)
            return _ffmpeg_bin
    return None


def ensure_playable(path: Path, ext: str) -> Path:
    if ext in BROWSER_VIDEO:
        return path
    ff = find_ffmpeg()
    if not ff:
        print("ffmpeg missing — browser may not play this video type", flush=True)
        return path
    cache = HISTORY_DIR / "_play"
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / (media_id(path) + ".mp4")
    if out.is_file() and out.stat().st_size > 1000:
        return out
    cmd = [
        ff, "-y", "-i", str(path),
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "44100",
        "-movflags", "+faststart",
        str(out),
    ]
    print(f"transcoding {path.name} -> mp4+aac", flush=True)
    run = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0)
    if run.returncode != 0 or not out.is_file():
        print(f"ffmpeg failed: {run.stderr[-400:] if run.stderr else run.returncode}", flush=True)
        return path
    return out


def find_ffplay() -> str | None:
    ff = find_ffmpeg()
    if not ff:
        return None
    p = Path(ff).with_name("ffplay.exe")
    return str(p) if p.is_file() else shutil.which("ffplay")


def stop_audio() -> None:
    global audio_proc
    proc = audio_proc
    audio_proc = None
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _set_default_endpoints(play_id: str, rec_id: str) -> None:
    from comtypes import CLSCTX_ALL, GUID, CoCreateInstance
    from pycaw.api.policyconfig import IPolicyConfig

    pc = CoCreateInstance(GUID("{870af99c-171d-4f9e-af0d-e63df40c2bc9}"), IPolicyConfig, CLSCTX_ALL)
    for role in (0, 1, 2):
        pc.SetDefaultEndpoint(play_id, role)
        pc.SetDefaultEndpoint(rec_id, role)


def route_audio_for_record() -> None:
    """Video soundtrack -> Voicemeeter -> USB speakers + default MIC (so record/send gets voice)."""
    import ctypes
    from pycaw.pycaw import AudioUtilities

    exe = Path(r"C:\Program Files (x86)\VB\Voicemeeter\voicemeeter_x64.exe")
    dll_path = Path(r"C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll")
    if exe.is_file() and not running_proc("voicemeeter_x64.exe"):
        subprocess.Popen([str(exe)], close_fds=True)
        time.sleep(5)
    if not dll_path.is_file():
        print("Voicemeeter missing", flush=True)
        return
    dll = ctypes.WinDLL(str(dll_path))
    dll.VBVMR_RunVoicemeeter(1)
    time.sleep(1)
    login = -1
    for _ in range(10):
        login = dll.VBVMR_Login()
        if login == 0:
            break
        time.sleep(0.5)
    if login != 0:
        print(f"Voicemeeter login {login}", flush=True)
        return
    dll.VBVMR_SetParameterFloat.argtypes = [ctypes.c_char_p, ctypes.c_float]
    dll.VBVMR_SetParameterStringA.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    dll.VBVMR_SetParameterFloat(b"Strip[2].A1", 1.0)
    dll.VBVMR_SetParameterFloat(b"Strip[2].B1", 1.0)
    dll.VBVMR_SetParameterFloat(b"Strip[2].Mute", 0.0)
    dll.VBVMR_SetParameterFloat(b"Bus[0].Mute", 0.0)
    dll.VBVMR_SetParameterFloat(b"Bus[2].Mute", 0.0)
    dll.VBVMR_SetParameterStringA(b"Bus[0].Device.WDM", b"Speakers (3- USB Audio Device)")
    play_id = rec_id = None
    for d in AudioUtilities.GetAllDevices():
        n = d.FriendlyName or ""
        if n == "Voicemeeter Input (VB-Audio Voicemeeter VAIO)":
            play_id = d.id
        if n == "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)":
            rec_id = d.id
    if play_id and rec_id:
        _set_default_endpoints(play_id, rec_id)
        print("mic for record: Voicemeeter Out B1", flush=True)


def running_proc(name: str) -> bool:
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return name.lower() in out.lower()
    except Exception:
        return False


def play_audio(path: Path) -> None:
    """Play soundtrack into Voicemeeter so speakers AND recording mic get the voice."""
    global audio_proc
    stop_audio()
    try:
        route_audio_for_record()
    except Exception as exc:
        print(f"audio route failed: {exc}", flush=True)
    player = find_ffplay()
    if not player:
        print("ffplay missing — no soundtrack", flush=True)
        return
    flags = 0
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        flags = subprocess.CREATE_NO_WINDOW
    audio_proc = subprocess.Popen(
        [player, "-nodisp", "-autoexit", "-loop", "0", "-vn", "-volume", "100", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    print(f"audio playing: {path.name}", flush=True)


def is_ready_media(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name.startswith("~$") or path.name.startswith("."):
        return False
    ext = path.suffix.lower()
    if ext in SKIP_EXTS or ext not in MEDIA_EXTS:
        return False
    try:
        return path.stat().st_size >= 64
    except OSError:
        return False


def latest_media(*folders: Path) -> Path | None:
    newest, newest_mtime = None, -1.0
    for folder in folders:
        if not folder.is_dir():
            continue
        try:
            entries = list(folder.iterdir())
        except OSError:
            continue
        for p in entries:
            if p.is_dir():
                try:
                    nested = list(p.iterdir()) if p == UPLOAD_DIR else []
                except OSError:
                    nested = []
                for n in nested:
                    if not is_ready_media(n):
                        continue
                    try:
                        mtime = n.stat().st_mtime
                    except OSError:
                        continue
                    if mtime > newest_mtime:
                        newest, newest_mtime = n, mtime
                continue
            if not is_ready_media(p):
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if mtime > newest_mtime:
                newest, newest_mtime = p, mtime
    return newest


def wait_file_stable(path: Path, timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    last, stable = -1, 0
    while time.time() < deadline:
        try:
            size = path.stat().st_size
        except OSError:
            time.sleep(0.15)
            continue
        if size == last and size > 0:
            stable += 1
            if stable >= 3:
                return
        else:
            stable, last = 0, size
        time.sleep(0.2)


def media_size(path: Path, ext: str) -> tuple[int, int]:
    try:
        if ext in IMAGE_EXTS:
            with Image.open(path) as im:
                w, h = im.size
                return int(w), int(h)
        cap = cv2.VideoCapture(str(path))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        cap.release()
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass
    return 0, 0


def even_dim(n: int) -> int:
    n = max(2, int(n))
    return n if n % 2 == 0 else n + 1


def obs_apply_size(w: int, h: int) -> None:
    w, h = even_dim(w), even_dim(h)
    try:
        import obsws_python as obsws
    except ImportError:
        return
    last_err = None
    for _ in range(10):
        try:
            cl = obsws.ReqClient(host="127.0.0.1", port=4455, password=obs_password(), timeout=3)
            try:
                cl.stop_virtual_cam()
            except Exception:
                pass
            cl.set_video_settings(30, 1, 1920, 1080, 1920, 1080)
            cl.set_input_settings(
                name="FileCam",
                settings={
                    "width": 1920,
                    "height": 1080,
                    "url": "http://127.0.0.1:8765/clean?v=audio2",
                    "reroute_audio": False,
                },
                overlay=True,
            )
            try:
                cl.set_input_mute("FileCam", True)
            except Exception:
                pass
            try:
                cl.set_input_audio_monitor_type("FileCam", "OBS_MONITORING_TYPE_NONE")
            except Exception:
                pass
            try:
                cl.start_virtual_cam()
            except Exception:
                pass
            cl.disconnect()
            print("OBS stream size 1920x1080 (16:9)", flush=True)
            return
        except Exception as exc:
            last_err = exc
            time.sleep(1)
    print(f"OBS size sync skipped: {last_err}", flush=True)


def media_id(path: Path) -> str:
    try:
        key = str(path.resolve())
    except OSError:
        key = str(path)
    return hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:16]


def read_history() -> list:
    if not HISTORY_JSON.is_file():
        return []
    try:
        data = json.loads(HISTORY_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def write_history(items: list) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_JSON.write_text(json.dumps(items, ensure_ascii=False, indent=0), encoding="utf-8")


def remember_file(path: Path, kind: str, w: int, h: int) -> None:
    try:
        if not path.is_file():
            return
        if HISTORY_DIR in path.resolve().parents or path.parent == HISTORY_DIR:
            return
        hid = media_id(path)
        dest_name = hid + path.suffix.lower()
        dest = HISTORY_DIR / dest_name
        if not dest.exists():
            shutil.copy2(path, dest)
        items = read_history()
        items = [it for it in items if it.get("id") != hid]
        items.insert(
            0,
            {
                "id": hid,
                "name": path.name,
                "file": dest_name,
                "source": str(path),
                "kind": kind,
                "width": w,
                "height": h,
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        write_history(items[:250])
    except Exception:
        traceback.print_exc()


def list_downloads() -> list:
    items = []
    if not DOWNLOADS.is_dir():
        return items
    try:
        paths = list(DOWNLOADS.iterdir())
    except OSError:
        return items
    for p in paths:
        if not is_ready_media(p):
            continue
        ext = p.suffix.lower()
        kind = "video" if ext in VIDEO_EXTS else "image"
        w, h = media_size(p, ext)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = 0
        items.append(
            {
                "id": media_id(p),
                "name": p.name,
                "kind": kind,
                "width": w,
                "height": h,
                "mtime": mtime,
                "ts": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S") if mtime else "",
                "path": str(p),
            }
        )
    items.sort(key=lambda it: it["mtime"], reverse=True)
    return items[:80]


def find_download(fid: str) -> Path | None:
    for it in list_downloads():
        if it["id"] == fid:
            return Path(it["path"])
    return None


def find_history(fid: str) -> Path | None:
    for it in read_history():
        if it.get("id") == fid:
            p = HISTORY_DIR / it.get("file", "")
            if p.is_file():
                return p
            src = Path(it.get("source", ""))
            if src.is_file():
                return src
    return None


def load_file(path: Path) -> None:
    global status_text, video_cap, current_path, media_kind, media_token, media_width, media_height, pan_x, pan_y, zoom
    path = Path(path)
    if not is_ready_media(path):
        return
    wait_file_stable(path)
    ext = path.suffix.lower()
    kind = "video" if ext in VIDEO_EXTS else "image"
    source = path
    if kind == "video":
        path = ensure_playable(path, ext)
        ext = path.suffix.lower()
    w, h = media_size(path, ext)
    with lock:
        status_text = f"{source.name}  {w}x{h}  {datetime.now().strftime('%H:%M:%S')}"
        current_path = path
        media_kind = kind
        media_width = w
        media_height = h
        media_token += 1
        pan_x = 0
        pan_y = 0
        zoom = 1.0
        old = video_cap
        video_cap = None
    if old is not None:
        old.release()
    if kind == "video":
        play_audio(path)
    else:
        stop_audio()
    threading.Thread(target=obs_apply_size, args=(1920, 1080), daemon=True).start()
    threading.Thread(target=remember_file, args=(source, kind, w, h), daemon=True).start()


def open_vcam() -> bool:
    """OBS owns the virtual camera so Chrome can see it. Do not grab the device here."""
    return False


def pump_frames() -> None:
    global current_jpeg, vcam
    last_try = 0.0
    while running:
        try:
            with lock:
                cap = video_cap
            if cap is not None:
                ok, frame = cap.read()
                if not ok:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = cap.read()
                if ok:
                    set_frame(frame)
            else:
                with lock:
                    empty = not current_jpeg
                if empty:
                    set_frame(blank_frame(status_text, str(DOWNLOADS)))
            if vcam is None:
                now = time.time()
                if now - last_try > 5:
                    last_try = now
                    open_vcam()
            if vcam is not None:
                with lock:
                    rgb = current_rgb
                if rgb is not None:
                    vcam.send(rgb)
        except Exception as exc:
            print(f"frame/vcam error: {exc}", flush=True)
            try:
                if vcam is not None:
                    vcam.close()
            except Exception:
                pass
            vcam = None
        time.sleep(1 / FPS)


class Handler(FileSystemEventHandler):
    def _maybe(self, src: str) -> None:
        p = Path(src)
        if p.suffix.lower() in SKIP_EXTS:
            return
        time.sleep(0.25)
        if is_ready_media(p):
            load_file(p)

    def on_created(self, event):
        if not event.is_directory:
            self._maybe(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._maybe(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._maybe(event.dest_path)


class CamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))
        sys.stdout.flush()

    def _send(self, code: int, body: bytes, content_type: str, extra=None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return

    def do_OPTIONS(self):
        self._send(204, b"", "text/plain")

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/history":
                self._send(200, HISTORY_PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/history":
                items = read_history()
                self._send(200, json.dumps({"items": items}).encode("utf-8"), "application/json")
                return
            if path == "/api/downloads":
                items = list_downloads()
                for it in items:
                    it.pop("path", None)
                self._send(200, json.dumps({"items": items}).encode("utf-8"), "application/json")
                return
            if path == "/select":
                q = parse_qs(urlparse(self.path).query)
                fid = unquote((q.get("id") or [""])[0])
                chosen = find_history(fid) or find_download(fid)
                if chosen is None:
                    self._send(404, b"not found", "text/plain")
                    return
                threading.Thread(target=load_file, args=(chosen,), daemon=True).start()
                self._send(200, b"ok", "text/plain")
                return
            if path == "/histfile":
                q = parse_qs(urlparse(self.path).query)
                fid = unquote((q.get("id") or [""])[0])
                chosen = find_history(fid)
                if chosen is None:
                    self._send(404, b"not found", "text/plain")
                    return
                data = chosen.read_bytes()
                ctype = MIME.get(chosen.suffix.lower()) or "application/octet-stream"
                self._send(200, data, ctype)
                return
            if path == "/dlfile":
                q = parse_qs(urlparse(self.path).query)
                fid = unquote((q.get("id") or [""])[0])
                chosen = find_download(fid)
                if chosen is None:
                    self._send(404, b"not found", "text/plain")
                    return
                data = chosen.read_bytes()
                ctype = MIME.get(chosen.suffix.lower()) or "application/octet-stream"
                self._send(200, data, ctype)
                return
            if path == "/clean":
                self._send(200, CLEAN.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/health":
                self._send(200, b"ok", "text/plain")
                return
            if path == "/move":
                q = parse_qs(urlparse(self.path).query)
                direction = (q.get("dir") or ["right"])[0].lower()
                with lock:
                    global pan_x, pan_y, zoom
                    if direction == "left":
                        pan_x -= PAN_STEP_X
                    elif direction == "right":
                        pan_x += PAN_STEP_X
                    elif direction == "up":
                        pan_y -= PAN_STEP_Y
                    elif direction == "down":
                        pan_y += PAN_STEP_Y
                    elif direction in ("in", "zoom_in", "zoomin"):
                        zoom = min(ZOOM_MAX, round(zoom + ZOOM_STEP, 2))
                    elif direction in ("out", "zoom_out", "zoomout"):
                        zoom = max(ZOOM_MIN, round(zoom - ZOOM_STEP, 2))
                    elif direction == "reset":
                        pan_x = 0
                        pan_y = 0
                        zoom = 1.0
                    body = json.dumps({"pan_x": pan_x, "pan_y": pan_y, "zoom": zoom, "token": media_token}).encode()
                self._send(200, body, "application/json")
                return
            if path == "/status":
                with lock:
                    body = json.dumps(
                        {
                            "token": media_token,
                            "kind": media_kind,
                            "name": current_path.name if current_path else "",
                            "width": media_width,
                            "height": media_height,
                            "pan_x": pan_x,
                            "pan_y": pan_y,
                            "zoom": zoom,
                        }
                    ).encode()
                self._send(200, body, "application/json")
                return
            if path == "/original":
                with lock:
                    src = current_path
                if src is None or not src.is_file():
                    self._send(404, b"no media", "text/plain")
                    return
                data = src.read_bytes()
                ctype = MIME.get(src.suffix.lower()) or (mimetypes.guess_type(src.name)[0] or "application/octet-stream")
                self._send(200, data, ctype)
                return
            if path == "/snapshot.jpg":
                with lock:
                    jpeg = current_jpeg
                if not jpeg:
                    jpeg = encode_jpeg(fit_bgr(blank_frame(status_text)))
                self._send(200, jpeg, "image/jpeg")
                return
            if path == "/stream":
                self._mjpeg()
                return
            self._send(404, b"not found", "text/plain")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return
        except Exception:
            traceback.print_exc()
            try:
                self._send(500, b"error", "text/plain")
            except Exception:
                return

    def _mjpeg(self):
        self.send_response(200)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while running:
                with lock:
                    jpeg = current_jpeg
                if not jpeg:
                    time.sleep(0.05)
                    continue
                chunk = (
                    b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(jpeg)).encode()
                    + b"\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )
                self.wfile.write(chunk)
                self.wfile.flush()
                time.sleep(1 / FPS)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/upload":
            self._send(404, b"not found", "text/plain")
            return
        try:
            ctype, pdict = cgi.parse_header(self.headers.get("Content-Type", ""))
            if ctype != "multipart/form-data":
                self._send(400, b"need multipart", "text/plain")
                return
            pdict["boundary"] = pdict["boundary"].encode() if isinstance(pdict.get("boundary"), str) else pdict.get("boundary")
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers.get("Content-Type"),
                },
            )
            item = form["file"] if "file" in form else None
            if item is None or not getattr(item, "file", None):
                self._send(400, b"no file", "text/plain")
                return
            name = Path(item.filename or "drop.bin").name
            dest = UPLOAD_DIR / name
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            data = item.file.read()
            dest.write_bytes(data)
            threading.Thread(target=load_file, args=(dest,), daemon=True).start()
            self._send(200, b"ok", "text/plain")
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            return
        except Exception:
            traceback.print_exc()
            try:
                self._send(500, b"upload failed", "text/plain")
            except Exception:
                return


def main() -> None:
    global running
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)

    set_frame(blank_frame("Starting…", str(DOWNLOADS)))
    newest = latest_media(DOWNLOADS, WATCH_DIR, UPLOAD_DIR)
    if newest:
        print(f"Auto-catch latest: {newest}", flush=True)
        threading.Thread(target=load_file, args=(newest,), daemon=True).start()

    observer = Observer()
    fs = Handler()
    observer.schedule(fs, str(DOWNLOADS), recursive=False)
    observer.schedule(fs, str(WATCH_DIR), recursive=True)
    observer.start()
    open_vcam()
    threading.Thread(target=pump_frames, daemon=True).start()
    threading.Thread(target=obs_apply_size, args=(1920, 1080), daemon=True).start()

    httpd = ThreadingHTTPServer((HOST, PORT), CamHandler)
    httpd.daemon_threads = True
    url = f"http://{HOST}:{PORT}/"
    print(f"Browser camera: {url}", flush=True)
    print("Tab close karne se server band NAHI hoga.", flush=True)

    try:
        import webbrowser

        webbrowser.open(url)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        running = False
        observer.stop()
        observer.join(timeout=2)
        httpd.server_close()
        with lock:
            cap = video_cap
        if cap is not None:
            cap.release()
        if vcam is not None:
            try:
                vcam.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
