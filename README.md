# Cam2MP4 (FireWire2MP4)

A desktop app (CustomTkinter GUI) that turns camcorder footage into MP4 (H.264/AAC) with ffmpeg:

- **Capture** live from a FireWire (IEEE 1394 / i.LINK) DV or HDV camcorder, with a live preview so you can cue the tape.
- **Convert** existing DV, AVI, MOV, M2T and similar files to MP4.
- Quality (CRF) and encoding-effort presets, deinterlacing, square-pixel aspect correction, auto-stop timer, progress bar and log.
- Light/dark mode. Tape transport buttons on Linux via `dvcont`.

The UI is in German.

## Run from source

    pip install -r requirements.txt
    python firewire2mp4.py

ffmpeg must be on PATH. On Linux, FireWire capture also needs `dvgrab` (`sudo apt install ffmpeg dvgrab`).
On Windows the camcorder has to appear as a DirectShow device; on macOS it is read via AVFoundation.

## Standalone build (no install needed)

The finished program needs **nothing installed**: Python, customtkinter, Pillow and ffmpeg are all inside it.
Only *building* it needs Python, and PyInstaller can only build for the OS it runs on.

## Option A – GitHub Actions (all three systems, nothing to install)

1. Open the **Actions** tab → **Build executables** → **Run workflow**.
2. When it finishes, download the artifacts at the bottom of the run page:
   `FireWire2MP4-Windows` (.exe), `FireWire2MP4-macOS` (.zip with the .app), `FireWire2MP4-Linux` (.tar.gz).

The macOS build is for Apple Silicon. Intel Macs need their own build (Option B on that Mac).

## Option B – build on your own machine

Install Python 3.10+ (with tkinter) on that machine once, then:

    python build.py

The result is in `release/`. Run it on Windows for the .exe, on macOS for the .app, on Linux for the Linux binary.

## First start

- **Windows**: SmartScreen shows "Windows protected your PC" because the file is unsigned → *More info* → *Run anyway*.
- **macOS**: right-click `FireWire2MP4.app` → *Open* → *Open*. If it says the app is damaged, run
  `xattr -dr com.apple.quarantine FireWire2MP4.app`. Allow camera/microphone access when asked.
- **Linux**: `tar -xzf FireWire2MP4-linux-*.tar.gz && ./FireWire2MP4`. For FireWire capture install `dvgrab`
  (`sudo apt install dvgrab`); converting files works without it.

The first start of the single-file builds takes a few seconds while the program unpacks itself.
