# SNAP — Virtual File Camera

Live 16:9 camera feed from the latest image/video in **Downloads** (drag-drop, history, any video type).

## Run (one click)

Desktop par **SNAP Camera Start** double-click, ya:

```bat
START_ALL.bat
```

Or:

```
pip install -r requirements.txt
python file_cam.py
```

Open http://127.0.0.1:8765/

Chrome/Meet camera: **OBS Virtual Camera** (OBS must stay open). Use `CHROME-CAMERA.bat` if Chrome does not list the camera.

## Audio when you record/send

OBS Virtual Camera is **video only**. Soundtrack plays on PC speakers via `ffplay`. In WhatsApp/Meet, set microphone to **Stereo Mix** or **Voicemeeter Output** so the video voice is recorded with the picture.

## Pages

- Live controls: http://127.0.0.1:8765/
- History: http://127.0.0.1:8765/history
