# SNAP — Virtual File Camera

Downloads (ya drag-drop / history) se latest **image ya video** ko 16:9 live camera bana deta hai. Chrome / Meet / WhatsApp mein **OBS Virtual Camera** select karo. Video ki **voice record/send** mein aane ke liye mic **Voicemeeter Out B1** hona chahiye.

Live: http://127.0.0.1:8765/  
History: http://127.0.0.1:8765/history

---

## 1) Kya download / install karna hai

Pehle yeh 4 software install karo (Windows):

| # | Software | Kahan se | Kyun |
|---|----------|----------|------|
| 1 | **Python 3.10+** | https://www.python.org/downloads/ | Camera server |
| 2 | **OBS Studio** | https://obsproject.com/download | Virtual camera driver |
| 3 | **FFmpeg** (Gyan full) | `winget install Gyan.FFmpeg` ya https://www.gyan.dev/ffmpeg/builds/ | Har video type + soundtrack |
| 4 | **Voicemeeter** | `winget install VB-Audio.Voicemeeter` ya https://vb-audio.com/Voicemeeter/ | Video ki voice mic mein |

Python installer mein **Add python.exe to PATH** tick karna.

OBS first run ke baad **Start Virtual Camera** ek baar on karo (Tools / controls).

---

## 2) Code lena

```bat
git clone https://github.com/vishvajeet2012/SNAP.git
cd SNAP
pip install -r requirements.txt
```

ZIP se bhi download kar sakte ho: repo page → **Code** → **Download ZIP** → extract.

---

## 3) Python packages

Project folder mein:

```bat
pip install -r requirements.txt
```

Isme aata hai: `opencv-python`, `watchdog`, `pillow`, `numpy`, `pyvirtualcam`, `obsws-python`, `uiautomation`. Extra (voice routing): `pycaw`, `comtypes`.

Poora ek line:

```bat
pip install opencv-python watchdog pillow numpy pyvirtualcam obsws-python uiautomation pycaw comtypes
```

---

## 4) Kaise start kare (ek click)

1. `START_ALL.bat` ko **Desktop** par copy karo (ya `SNAP Camera Start.bat`).
2. Double-click **SNAP Camera Start** / `START_ALL.bat`.
3. Watchdog wali black window **band mat karna**.
4. Browser khulega: http://127.0.0.1:8765/

Pehli baar OBS **Crash Detected** dikhe to **Run in Normal Mode** dabao.

Agar Chrome camera list empty ho to `CHROME-CAMERA.bat` chalao.

---

## 5) App mein kya select kare (WhatsApp / Meet / Chrome)

| Cheez | Select |
|--------|--------|
| Camera | **OBS Virtual Camera** |
| Microphone | **Voicemeeter Out B1** |

Pehle SNAP start karo, video play honi chahiye (awaaz speakers se). Phir dusri app mein record/send.

USB microphone select mat rehne dena — usse video ki voice nahi aati.

---

## 6) Use

- **Default:** `Downloads` ki latest image/video camera par.
- Page par **drag-drop** se koi bhi image/video.
- **History:** http://127.0.0.1:8765/history — click karke wahi file live.
- Buttons: ◀ ▶ ▲ ▼ move (5%), + − zoom (5%).
- Stream hamesha **16:9 (1920×1080)**.

---

## 7) Files

| File | Kaam |
|------|------|
| `START_ALL.bat` | Poora system start (OBS + camera + browser + watchdog) |
| `file_cam.py` | Server, history, audio, 16:9 feed |
| `keep_alive.py` | OBS/camera band ho to wapas on |
| `CHROME-CAMERA.bat` | Chrome restart taaki camera dikhe |
| `requirements.txt` | pip packages |

---

## 8) Troubleshooting

- **Camera not found:** OBS khula rakho, Virtual Camera on, Chrome `CHROME-CAMERA.bat`.
- **Voice nahi (record):** Mic = **Voicemeeter Out B1**. Voicemeeter window open. Video pehle play ho.
- **Double voice:** sirf ek audio path (Voicemeeter). Page refresh.
- **Port busy:** purani `python file_cam.py` band karke `START_ALL.bat` dubara.
