#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baut FireWire2MP4 als eigenständiges Programm (ffmpeg ist eingebaut).

    python build.py

Nur zum BAUEN wird Python 3.10+ mit tkinter gebraucht. Das fertige Programm braucht nichts.
PyInstaller kann nicht für andere Systeme bauen: Windows-Programm unter Windows bauen,
macOS-Programm unter macOS, Linux-Programm unter Linux (oder alles per GitHub Actions).

Ergebnis im Ordner  release/ :
    Windows  FireWire2MP4.exe
    macOS    FireWire2MP4-macos-<arch>.zip   (enthält FireWire2MP4.app)
    Linux    FireWire2MP4-linux-<arch>.tar.gz
"""
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
    """Startet das fertige Programm im Testmodus: findet es sein eingebautes ffmpeg samt libx264/AAC?"""
    with tempfile.TemporaryDirectory() as tmp:
        result = Path(tmp) / "selftest.txt"
        print(f"+ {exe} --selftest", flush=True)
        subprocess.run([str(exe), "--selftest", str(result)], check=False, timeout=300)
        text = result.read_text(encoding="utf-8") if result.exists() else "(keine Ausgabe)"
    print(text)
    if "SELFTEST OK" not in text:
        sys.exit("FEHLER: Selbsttest des gebauten Programms fehlgeschlagen.")


def main():
    try:
        import tkinter  # noqa: F401
    except ImportError:
        sys.exit("tkinter fehlt in diesem Python. Windows/macOS: Python von python.org installieren. "
                 "Linux: sudo apt install python3-tk")

    if not PY.exists():
        print("Erzeuge Build-Umgebung ...", flush=True)
        venv.EnvBuilder(with_pip=True).create(ENV)
    run([PY, "-m", "pip", "install", "--upgrade", "pip"])
    run([PY, "-m", "pip", "install", *PACKAGES])

    for d in ("build", "dist", "release"):
        shutil.rmtree(HERE / d, ignore_errors=True)
    (HERE / "release").mkdir()

    cmd = [PY, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", NAME,
           "--collect-all", "customtkinter", "--collect-all", "imageio_ffmpeg"]
    if SYSTEM != "Darwin":  # unter macOS ist ein .app-Ordner der übliche Weg
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
        # Ohne diese Texte darf macOS dem Programm den Zugriff auf Kamera/Mikrofon nicht erlauben
        for key, text in (("NSCameraUsageDescription", "FireWire2MP4 liest das Videosignal des Camcorders."),
                          ("NSMicrophoneUsageDescription", "FireWire2MP4 liest den Ton des Camcorders.")):
            run(["plutil", "-replace", key, "-string", text, plist])
        run(["codesign", "--force", "--deep", "--sign", "-", app])  # Ad-hoc-Signatur nach der Änderung
        selftest(app / "Contents" / "MacOS" / NAME)
        run(["ditto", "-c", "-k", "--keepParent", app, HERE / "release" / f"{NAME}-macos-{ARCH}.zip"])

    else:
        exe = dist / NAME
        selftest(exe)
        run(["tar", "-czf", HERE / "release" / f"{NAME}-linux-{ARCH}.tar.gz", "-C", dist, NAME])

    print("\nFertig. Ergebnis:")
    for p in sorted((HERE / "release").iterdir()):
        print(f"  {p}  ({p.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
