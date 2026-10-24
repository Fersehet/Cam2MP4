#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Builds FireWire2MP4 as a standalone program (ffmpeg is bundled).

    python build.py

Only BUILDING needs Python 3.10+ with tkinter. The finished program needs nothing.
PyInstaller cannot cross-compile: build the Windows program on Windows,
the macOS program on macOS, the Linux program on Linux (or all of them via GitHub Actions).

Output in the folder  release/ :
    Windows  FireWire2MP4.exe
    macOS    FireWire2MP4-macos-<arch>.zip   (contains FireWire2MP4.app)
    Linux    FireWire2MP4-linux-<arch>.tar.gz
"""
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "FireWire2MP4"
SYSTEM = platform.system()  # Windows, Darwin, Linux
ARCH = platform.machine().lower().replace("amd64", "x64").replace("x86_64", "x64")
ENV = HERE / ".buildenv"
PY = ENV / ("Scripts/python.exe" if SYSTEM == "Windows" else "bin/python")
PACKAGES = ["customtkinter", "pillow", "pyinstaller", "imageio-ffmpeg"]


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, cwd=HERE, **kw)


def selftest(exe):
    """Runs the finished program in test mode: does it find its bundled ffmpeg with libx264/AAC?"""
    with tempfile.TemporaryDirectory() as tmp:
        result = Path(tmp) / "selftest.txt"
        print(f"+ {exe} --selftest", flush=True)
        subprocess.run([str(exe), "--selftest", str(result)], check=False, timeout=300)
        text = result.read_text(encoding="utf-8") if result.exists() else "(no output)"
    print(text)
    if "SELFTEST OK" not in text:
        sys.exit("ERROR: self-test of the built program failed.")


def main():
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.exit("tkinter is missing in this Python. Windows/macOS: install Python from python.org. "
                 "Linux: sudo apt install python3-tk")

    if not PY.exists():
        print("Creating build environment ...", flush=True)
        venv.EnvBuilder(with_pip=True).create(ENV)
    run([PY, "-m", "pip", "install", "--upgrade", "pip"])
    run([PY, "-m", "pip", "install", *PACKAGES])

    for d in ("build", "dist", "release"):
        shutil.rmtree(HERE / d, ignore_errors=True)
    (HERE / "release").mkdir()

    cmd = [PY, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", NAME,
           "--collect-all", "customtkinter", "--collect-all", "imageio_ffmpeg"]
    # Window icon inside the program, plus the file icon of the .exe/.app
    cmd += ["--add-data", f"assets/cam2mp4-icon-256.png{os.pathsep}assets"]
    if SYSTEM == "Windows":
        cmd += ["--icon", "assets/cam2mp4.ico"]
    elif SYSTEM == "Darwin":
        cmd += ["--icon", "assets/cam2mp4-icon-1024.png"]  # PyInstaller converts it to .icns via Pillow
    if SYSTEM != "Darwin":  # on macOS an .app folder is the usual way
        cmd.append("--onefile")
    run(cmd + ["firewire2mp4.py"])

    dist = HERE / "dist"
    if SYSTEM == "Windows":
        exe = dist / f"{NAME}.exe"
        selftest(exe)
        shutil.copy2(exe, HERE / "release" / exe.name)

    elif SYSTEM == "Darwin":
        app = dist / f"{NAME}.app"
        plist = app / "Contents" / "Info.plist"
        # Without these texts macOS cannot grant the program camera/microphone access
        for key, text in (("NSCameraUsageDescription", "FireWire2MP4 reads the video signal from the camcorder."),
                          ("NSMicrophoneUsageDescription", "FireWire2MP4 reads the audio from the camcorder.")):
            run(["plutil", "-replace", key, "-string", text, plist])
        run(["codesign", "--force", "--deep", "--sign", "-", app])  # ad-hoc signature after the change
        selftest(app / "Contents" / "MacOS" / NAME)
        run(["ditto", "-c", "-k", "--keepParent", app, HERE / "release" / f"{NAME}-macos-{ARCH}.zip"])

    else:
        exe = dist / NAME
        selftest(exe)
        run(["tar", "-czf", HERE / "release" / f"{NAME}-linux-{ARCH}.tar.gz", "-C", dist, NAME])

    print("\nDone. Output:")
    for p in sorted((HERE / "release").iterdir()):
        print(f"  {p}  ({p.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
