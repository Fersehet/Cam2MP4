# FireWire2MP4 – standalone build

The finished program needs **nothing installed**: Python, customtkinter, Pillow and ffmpeg are all inside it.
Only *building* it needs Python, and PyInstaller can only build for the OS it runs on.

## Option A – GitHub Actions (all three systems, nothing to install)

1. Create a GitHub repository and upload everything in this folder (keep `.github/workflows/build.yml`).
2. Open the **Actions** tab → **Build executables** → **Run workflow**.
3. When it finishes, download the artifacts at the bottom of the run page:
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

