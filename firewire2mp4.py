#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cam2MP4 - camcorder (FireWire / IEEE 1394, DV or HDV) -> MP4
Modern CustomTkinter interface (light/dark mode).

Installation:
    pip install customtkinter pillow
    + ffmpeg (on the PATH)
    + Linux: dvgrab (recommended), optionally dvcont for tape control

Start:
    python3 firewire2mp4.py

Without extra packages, the plain variant firewire2mp4_classic.py runs.
"""

import io
import json
import locale
import os
import platform
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

_missing = []
try:
    import customtkinter as ctk
except ImportError:
    _missing.append("customtkinter")
try:
    from PIL import Image, ImageTk
except ImportError:
    _missing.append("pillow")
if _missing:
    _r = tk.Tk()
    _r.withdraw()
    _hint = ("\n\nOn Linux also:  sudo apt install python3-pil.imagetk"
             if platform.system() == "Linux" and "pillow" in _missing else "")
    messagebox.showerror("Python package missing",
                         "Please install first:\n\n    pip install " + " ".join(_missing) + _hint + "\n\n"
                         "Alternatively: firewire2mp4_classic.py (no extra packages).")
    raise SystemExit(1)

SYSTEM = platform.system()  # "Windows", "Darwin" or "Linux"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ------------------------------------------------------------------ Language
# English is the source language; DE holds the German translations.
DE = {
    "Record camcorder": "Camcorder aufnehmen",
    "Convert file": "Datei konvertieren",
    "High (CRF 18)": "Hoch (CRF 18)",
    "Good (CRF 21)": "Gut (CRF 21)",
    "Compact (CRF 24)": "Kompakt (CRF 24)",
    "Fast (larger file)": "Schnell (größere Datei)",
    "Medium (recommended)": "Mittel (empfohlen)",
    "Slow (smaller file)": "Langsam (kleinere Datei)",
    "(in video stream / none)": "(im Videostream / keiner)",
    "(no device found)": "(kein Gerät gefunden)",
    "Light": "Hell",
    "Dark": "Dunkel",
    "Keep your memories alive": "Bewahre deine Erinnerungen",
    "Source": "Quelle",
    "FireWire card": "FireWire-Karte",
    "HDV (experimental)": "HDV (experimentell)",
    "Leave card empty = automatic. Switch the camcorder on in VCR/Play mode.":
        "Karte leer lassen = automatisch. Camcorder im VCR-/Play-Modus einschalten.",
    "Switch the camcorder on in VCR/Play mode, then click ↻.":
        "Camcorder im VCR-/Play-Modus einschalten, dann ↻ klicken.",
    "Browse …": "Durchsuchen …",
    "Output file (MP4)": "Ausgabedatei (MP4)",
    "Change …": "Ändern …",
    "Quality & options": "Qualität & Optionen",
    "Quality": "Qualität",
    "Encoding speed": "Kodiertempo",
    "Remove interlacing (deinterlace)": "Zeilensprung entfernen (Deinterlacing)",
    "Square pixels (correct 4:3 / 16:9)": "Quadratische Pixel (korrektes 4:3 / 16:9)",
    "Auto stop (min)": "Auto-Stopp (Min.)",
    "Advanced": "Erweitert",
    "Auto stop 0 = off · \"Advanced\" = extra ffmpeg input options":
        "Auto-Stopp 0 = aus · „Erweitert“ = zusätzliche ffmpeg-Eingabe-Optionen",
    "Live preview": "Live-Vorschau",
    "No preview": "Keine Vorschau",
    "Ready.": "Bereit.",
    "■  Stop": "■  Stopp",
    "Open folder": "Ordner öffnen",
    "Tape:": "Band:",
    "Log": "Protokoll",
    "Preview appears during conversion": "Vorschau erscheint während der Konvertierung",
    "Preview is turned off": "Vorschau ist ausgeschaltet",
    "Preview running – ready to record.": "Vorschau läuft – bereit zur Aufnahme.",
    "●  Start recording": "●  Aufnahme starten",
    "▶  Start conversion": "▶  Konvertierung starten",
    "Choose input file": "Eingabedatei wählen",
    "Video files": "Videodateien",
    "All files": "Alle Dateien",
    "Save MP4 as": "MP4 speichern unter",
    "MP4 video": "MP4-Video",
    "Could not open folder: {e}": "Ordner konnte nicht geöffnet werden: {e}",
    "ffmpeg not found – see log.": "ffmpeg nicht gefunden – siehe Protokoll.",
    "ERROR: ffmpeg was not found. Installation:": "FEHLER: ffmpeg wurde nicht gefunden. Installation:",
    "Note: dvgrab is missing (sudo apt install dvgrab). Falling back to ffmpeg's iec61883 input.":
        "Hinweis: dvgrab fehlt (sudo apt install dvgrab). Ersatzweise wird ffmpegs iec61883-Eingang versucht.",
    "Device list failed: {e}": "Geräteliste fehlgeschlagen: {e}",
    "Found {v} video and {a} audio devices.": "{v} Video- und {a} Audio-Geräte gefunden.",
    "No camcorder detected. Switch the camera on in VCR/Play mode, check the cable and click ↻.":
        "Kein Camcorder erkannt. Kamera im VCR-/Play-Modus einschalten, Kabel prüfen und ↻ klicken.",
    "Please choose an existing input file.": "Bitte eine vorhandene Eingabedatei auswählen.",
    "No camcorder found. Switch it on (VCR mode) and click ↻.":
        "Kein Camcorder gefunden. Einschalten (VCR-Modus) und ↻ klicken.",
    "No camcorder found": "Kein Camcorder gefunden",
    "ffmpeg missing": "ffmpeg fehlt",
    "ffmpeg was not found. Please install it (see log).":
        "ffmpeg wurde nicht gefunden. Bitte installieren (siehe Protokoll).",
    "Output file": "Ausgabedatei",
    "Please specify an output file.": "Bitte eine Ausgabedatei angeben.",
    "File exists": "Datei existiert",
    "Overwrite\n{out}?": "{out}\nüberschreiben?",
    "Error": "Fehler",
    "Handing camera over to recording …": "Übergebe Kamera an die Aufnahme …",
    "Waiting for picture …\n\nSwitch the camcorder on (VCR mode) and press Play":
        "Warte auf Bild …\n\nCamcorder einschalten (VCR-Modus) und „Play“ drücken",
    "Starting preview …": "Vorschau startet …",
    "Starting …": "Starte …",
    "Recording started – play the tape on the camcorder (Play) if it doesn't start automatically.":
        "Aufnahme gestartet – Band am Camcorder abspielen (Play), falls es nicht automatisch startet.",
    "Program not found: {e}": "Programm nicht gefunden: {e}",
    "Error: {e}": "Fehler: {e}",
    "Stopping and finalizing MP4 file …": "Beende und schließe MP4-Datei ab …",
    "dvcont {command} failed: {e}": "dvcont {command} fehlgeschlagen: {e}",
    "File size: {size}": "Dateigröße: {size}",
    "Converting … {pct:.0f} %": "Konvertiere … {pct:.0f} %",
    "Recording …": "Nimmt auf …",
    "Converting …": "Konvertiere …",
    "No picture from camcorder": "Kein Bild vom Camcorder",
    "No preview – switch the camcorder on (VCR mode) and click ↻.":
        "Keine Vorschau – Camcorder einschalten (VCR-Modus) und ↻ klicken.",
    "Preview ended: no signal from camcorder. Tips: VCR mode? Cable/driver OK?":
        "Vorschau beendet: kein Signal vom Camcorder. Tipps: VCR-Modus? Kabel/Treiber ok?",
    "Done: {name} ({mb:.1f} MB)": "Fertig: {name} ({mb:.1f} MB)",
    "Failed (code {rc}) – details in the log.": "Fehlgeschlagen (Code {rc}) – Details im Protokoll.",
    "No valid MP4 file was created. Tips: camcorder in VCR mode? Cable/driver OK? "
    "Extra input options may be needed.":
        "Es wurde keine gültige MP4-Datei erzeugt. Tipps: Camcorder im VCR-Modus? "
        "Kabel/Treiber ok? Eventuell zusätzliche Eingabe-Optionen nötig.",
    "Quit": "Beenden",
    "A recording/conversion is still running. Really quit?":
        "Es läuft noch eine Aufnahme/Konvertierung. Wirklich beenden?",
    "Language can be changed once the recording/conversion has finished.":
        "Die Sprache lässt sich ändern, sobald die Aufnahme/Konvertierung fertig ist.",
}
LANGS = {"EN": "en", "DE": "de"}
CONFIG = os.path.join(os.path.expanduser("~"), ".cam2mp4.json")


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def save_config(**values):
    cfg = load_config()
    cfg.update(values)
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except OSError:
        pass


def system_language():
    try:
        code = locale.getlocale()[0] or os.environ.get("LANG", "")
    except Exception:  # noqa: BLE001
        code = ""
    return "de" if code.lower().startswith(("de", "german")) else "en"


LANG = load_config().get("lang") or system_language()


def tr(text, **kw):
    """Translates an English UI text into the current language; fills in {placeholders}."""
    text = DE.get(text, text) if LANG == "de" else text
    return text.format(**kw) if kw else text


MODE_CAP = "Record camcorder"
MODE_FILE = "Convert file"
QUALITY = {"High (CRF 18)": 18, "Good (CRF 21)": 21, "Compact (CRF 24)": 24}
PRESET = {"Fast (larger file)": "veryfast", "Medium (recommended)": "medium", "Slow (smaller file)": "slow"}
NO_AUDIO_DEV = "(in video stream / none)"
NO_DEVICE = "(no device found)"
PW, PH = 448, 252  # preview size (16:9)
PREVIEW_BG = "#121212"

# Apple-style palette (light, dark): soft tinted backdrop, frosted cards with a bright glass edge
BG = ("#E8EDF4", "#0E1117")
CARD = ("#F7F9FC", "#1A1F27")
CARD_EDGE = ("#FFFFFF", "#2B323D")
FIELD = ("#EBEFF5", "#252B35")
FIELD_EDGE = ("#DCE2EA", "#323A46")
FIELD_HOVER = ("#DFE5EE", "#2E3541")
TEXT = ("#1C1C1E", "#F2F2F7")
ACCENT = ("#007AFF", "#0A84FF")
ACCENT_HOVER = ("#0062CC", "#3395FF")
TINT = ("#DCEBFF", "#16263B")
TINT_HOVER = ("#C9DFFF", "#1D3350")
GREEN = ("#34C759", "#30D158")
GREEN_HOVER = ("#2DB14F", "#28B84C")
RED = ("#FF3B30", "#FF453A")
RED_HOVER = ("#E0342A", "#E03C32")
COL_INFO = ("#3A3A3C", "#D1D1D6")
COL_OK = ("#248A3D", "#30D158")
COL_ERR = ("#D70015", "#FF6961")
COL_HINT = ("#8E8E93", "#8E8E93")

UI_FONTS = (".AppleSystemUIFont", "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", "Inter", "Cantarell", "Ubuntu")
MONO_FONTS = ("SF Mono", "Menlo", "Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono")


def resource(rel):
    """Path to a bundled file (PyInstaller unpacks data files to sys._MEIPASS)."""
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), rel)


def apply_theme():
    """Restyles the CustomTkinter widgets in an Apple-like look. Call before creating the window."""
    t = ctk.ThemeManager.theme
    t["CTk"]["fg_color"] = BG
    t["CTkToplevel"]["fg_color"] = BG
    t["CTkFrame"].update(fg_color=CARD, top_fg_color=CARD, border_color=CARD_EDGE, border_width=1, corner_radius=18)
    t["CTkButton"].update(fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=10,
                          text_color=("#FFFFFF", "#FFFFFF"), text_color_disabled=("#AEAEB2", "#636366"))
    t["CTkLabel"]["text_color"] = TEXT
    t["CTkEntry"].update(fg_color=FIELD, border_color=FIELD_EDGE, border_width=1, corner_radius=10, text_color=TEXT)
    t["CTkOptionMenu"].update(fg_color=FIELD, button_color=FIELD, button_hover_color=FIELD_HOVER,
                              corner_radius=10, text_color=TEXT)
    t["CTkSegmentedButton"].update(fg_color=FIELD, unselected_color=FIELD, unselected_hover_color=FIELD_HOVER,
                                   selected_color=("#FFFFFF", "#48505E"), selected_hover_color=("#FFFFFF", "#525B6A"),
                                   border_width=3, corner_radius=10, text_color=TEXT)
    t["CTkSwitch"].update(fg_color=("#D9DDE3", "#39393D"), progress_color=GREEN, border_width=2,
                          button_color=("#FFFFFF", "#FFFFFF"), button_hover_color=("#FFFFFF", "#FFFFFF"),
                          text_color=TEXT)
    t["CTkProgressBar"].update(fg_color=FIELD, progress_color=ACCENT)
    t["CTkTextbox"].update(fg_color=FIELD, corner_radius=12, text_color=TEXT,
                           scrollbar_button_color=FIELD_EDGE, scrollbar_button_hover_color=COL_HINT)
    t["CTkScrollbar"].update(button_color=FIELD_EDGE, button_hover_color=COL_HINT)
    t["DropdownMenu"].update(fg_color=CARD, hover_color=TINT, text_color=TEXT)


def fmt_cmd(cmd):
    return subprocess.list2cmdline(cmd) if SYSTEM == "Windows" else shlex.join(cmd)


def find_ffmpeg():
    """Find ffmpeg. In the built program (PyInstaller) prefer the bundled ffmpeg,
    otherwise the ffmpeg on the PATH; finally the imageio-ffmpeg package, if present."""
    def bundled():
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if not (exe and os.path.isfile(exe)):
                return None
            if not os.access(exe, os.X_OK):  # make the unpacked file executable
                try:
                    os.chmod(exe, 0o755)
                except OSError:
                    pass
            return exe
        except Exception:  # noqa: BLE001
            return None

    if getattr(sys, "frozen", False):
        return bundled() or shutil.which("ffmpeg")
    return shutil.which("ffmpeg") or bundled()


# --------------------------------------------------------------------------
# Device detection
# --------------------------------------------------------------------------
def parse_dshow(text):
    """Parses: ffmpeg -list_devices true -f dshow -i dummy"""
    video, audio, section = [], [], None
    for line in text.splitlines():
        if "Alternative name" in line:
            continue
        m = re.search(r'"(.+?)"\s+\(([a-z, ]+)\)\s*$', line)  # new format
        if m:
            if "video" in m.group(2):
                video.append(m.group(1))
            if "audio" in m.group(2):
                audio.append(m.group(1))
            continue
        low = line.lower()
        if "directshow video devices" in low:
            section = "video"
        elif "directshow audio devices" in low:
            section = "audio"
        else:  # old format
            m = re.search(r'\]\s+"(.+?)"\s*$', line)
            if m and section:
                (video if section == "video" else audio).append(m.group(1))
    return video, audio


def parse_avfoundation(text):
    """Parses: ffmpeg -f avfoundation -list_devices true -i ''"""
    video, audio, section = [], [], None
    for line in text.splitlines():
        if "video devices" in line:
            section = "video"
        elif "audio devices" in line:
            section = "audio"
        else:
            m = re.search(r"\[(\d+)\]\s+(.+?)\s*$", line)
            if m and section:
                (video if section == "video" else audio).append((m.group(1), m.group(2)))
    return video, audio


class App(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        apply_theme()
        super().__init__()
        families = set(tkfont.families(self))
        ctk.ThemeManager.theme["CTkFont"]["family"] = next((f for f in UI_FONTS if f in families), "TkDefaultFont")
        self.mono = next((f for f in MONO_FONTS if f in families), "TkFixedFont")
        self.title("Cam2MP4")
        self._icon = None
        try:
            self._icon = Image.open(resource(os.path.join("assets", "cam2mp4-icon-256.png")))
            self._icon_ph = ImageTk.PhotoImage(self._icon)
            self.iconphoto(True, self._icon_ph)
        except Exception:  # noqa: BLE001
            pass
        self.geometry("1080x840")
        self.minsize(980, 720)

        self.ffmpeg = find_ffmpeg()
        self.dvgrab = shutil.which("dvgrab") if SYSTEM == "Linux" else None
        self.dvcont = shutil.which("dvcont") if SYSTEM == "Linux" else None

        self.q = queue.Queue()
        self.dv = None
        self.ff = None
        self.running = False
        self.stopping = False
        self.current_out = ""
        self.total_secs = None
        self.video_map, self.audio_map = {}, {}
        self.preview_only = False      # is only the live preview running (no file)?
        self.use_preview = False
        self.preview_failed = False    # after an error, don't restart endlessly
        self._after_idle = None        # action to run once the current process has ended
        self._ready = False
        self._hold_status = False      # don't overwrite the "Done …" message right away
        self._gen = 0                  # run number, to ignore stale messages
        self._last_dv = None
        self._frame = None
        self._shown = None
        self._video_on = False

        self.src_file = tk.StringVar()
        self.dev_video = tk.StringVar(value=tr(NO_DEVICE))
        self.dev_audio = tk.StringVar(value=tr(NO_AUDIO_DEV))
        self.cam_format = tk.StringVar(value="DV")
        self.card = tk.StringVar()
        self.outfile = tk.StringVar(value=self._default_output())
        self.quality = tk.StringVar(value=tr("Good (CRF 21)"))
        self.preset = tk.StringVar(value=tr("Medium (recommended)"))
        self.deint = tk.BooleanVar(value=True)
        self.square = tk.BooleanVar(value=True)
        self.stop_min = tk.StringVar(value="0")
        self.extra = tk.StringVar()
        self.show_preview = tk.BooleanVar(value=True)

        self._build()
        self._mode_changed()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)
        self.after(100, self._preview_tick)
        self.after(250, self._startup_checks)

    # --------------------------------------------------------------- Helpers
    def _default_output(self):
        base = os.path.join(os.path.expanduser("~"), "Videos")
        if not os.path.isdir(base):
            base = os.path.expanduser("~")
        return os.path.join(base, datetime.now().strftime("Camcorder_%Y%m%d_%H%M%S.mp4"))

    def _is_capture(self):
        return self.mode_btn.get() == tr(MODE_CAP)

    @staticmethod
    def _key(table, shown):
        """English key of a translated menu entry (menus show tr(key))."""
        return next((k for k in table if tr(k) == shown), shown)

    def _set_theme(self, value):
        ctk.set_appearance_mode({tr("Light"): "light", tr("Dark"): "dark", "Auto": "system"}[value])

    def _set_language(self, value):
        global LANG
        if LANGS[value] == LANG:
            return
        if self.running and not self.preview_only:
            self.lang_btn.set(next(k for k, v in LANGS.items() if v == LANG))
            messagebox.showinfo("Cam2MP4", tr("Language can be changed once the recording/conversion has finished."))
            return
        # Remember the choices as language-neutral keys, switch, then rebuild the window
        capture = self._is_capture()
        theme = {tr("Light"): "Light", tr("Dark"): "Dark"}.get(self.theme_btn.get(), "Auto")
        quality = self._key(QUALITY, self.quality.get())
        preset = self._key(PRESET, self.preset.get())
        fmt = self._key(["DV", "HDV (experimental)"], self.cam_format.get())
        no_video = self.dev_video.get() == tr(NO_DEVICE)
        no_audio = self.dev_audio.get() == tr(NO_AUDIO_DEV)
        log = self.txt.get("1.0", "end-1c")
        status = self.lbl_status.cget("text") if self._hold_status else None
        status_color = self.lbl_status.cget("text_color")
        folder_state = self.btn_folder.cget("state")

        LANG = LANGS[value]
        save_config(lang=LANG)
        for w in self.winfo_children():
            w.destroy()
        self.quality.set(tr(quality))
        self.preset.set(tr(preset))
        self.cam_format.set(tr(fmt))
        if no_video:
            self.dev_video.set(tr(NO_DEVICE))
        if no_audio:
            self.dev_audio.set(tr(NO_AUDIO_DEV))
        self._video_on = False
        self._build()
        self.theme_btn.set(tr(theme) if theme != "Auto" else "Auto")
        self.mode_btn.set(tr(MODE_CAP if capture else MODE_FILE))
        self.btn_folder.configure(state=folder_state)
        if SYSTEM != "Linux":
            self.om_video.configure(values=list(self.video_map) or [tr(NO_DEVICE)])
            self.om_audio.configure(values=[tr(NO_AUDIO_DEV)] + list(self.audio_map))
        if log:
            self._log(log)
        if status:
            self.lbl_status.configure(text=status, text_color=status_color)
        else:
            self._set_status(tr(tr("Ready.")))
        self._mode_changed()

    def _card(self, parent, title):
        """Grouped section like in iOS/macOS settings: small caps heading above a frosted card."""
        ctk.CTkLabel(parent, text=title.upper(), font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=COL_HINT, anchor="w").pack(fill="x", padx=14, pady=(12, 4))
        card = ctk.CTkFrame(parent)
        card.pack(fill="x", pady=(0, 4))
        body = ctk.CTkFrame(card, fg_color="transparent", border_width=0)
        body.pack(fill="x", padx=16, pady=14)
        return body

    @staticmethod
    def _tinted(parent, text, width, command, **kw):
        """Secondary button: tinted accent background, accent text (Apple's 'tinted' style)."""
        return ctk.CTkButton(parent, text=text, width=width, command=command, fg_color=TINT,
                             hover_color=TINT_HOVER, text_color=ACCENT, **kw)

    @staticmethod
    def _lbl(parent, text, **kw):
        return ctk.CTkLabel(parent, text=text, anchor="w", **kw)

    # -------------------------------------------------------------------- UI
    def _build(self):
        self.columnconfigure(0, weight=0, minsize=480)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Header
        head = ctk.CTkFrame(self, fg_color="transparent", border_width=0)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=22, pady=(18, 6))
        head.columnconfigure(1, weight=1)
        if self._icon is not None:
            ctk.CTkLabel(head, text="", image=ctk.CTkImage(self._icon, size=(52, 52))).grid(
                row=0, column=0, rowspan=2, sticky="w", padx=(0, 14))
        ctk.CTkLabel(head, text="Cam2MP4", anchor="w",
                     font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(head, text=tr("Keep your memories alive"), anchor="w",
                     text_color=COL_HINT).grid(row=1, column=1, sticky="nw")
        self.lang_btn = ctk.CTkSegmentedButton(head, values=list(LANGS), command=self._set_language,
                                               width=96, height=32)
        self.lang_btn.set(next(k for k, v in LANGS.items() if v == LANG))
        self.lang_btn.grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 10))
        self.theme_btn = ctk.CTkSegmentedButton(head, values=[tr("Light"), tr("Dark"), "Auto"],
                                                command=self._set_theme, width=200, height=32)
        self.theme_btn.set("Auto")
        self.theme_btn.grid(row=0, column=3, rowspan=2, sticky="e")

        # Left column: settings
        left = ctk.CTkScrollableFrame(self, width=450, fg_color="transparent", border_width=0)
        left.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=(0, 16))

        self.mode_btn = ctk.CTkSegmentedButton(left, values=[tr(MODE_CAP), tr(MODE_FILE)],
                                               command=self._mode_changed, height=38)
        self.mode_btn.set(tr(MODE_CAP))
        self.mode_btn.pack(fill="x", pady=(0, 6))

        # Source
        body = self._card(left, tr("Source"))
        body.columnconfigure(0, weight=1)

        self.cap_frame = ctk.CTkFrame(body, fg_color="transparent", border_width=0)
        self.cap_frame.columnconfigure(1, weight=1)
        if SYSTEM == "Linux":
            self._lbl(self.cap_frame, "Format").grid(row=0, column=0, sticky="w", pady=4)
            ctk.CTkOptionMenu(self.cap_frame, variable=self.cam_format, dynamic_resizing=False,
                              command=lambda _v: self._restart_preview(),
                              values=["DV", tr("HDV (experimental)")]).grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=4)
            self._lbl(self.cap_frame, tr("FireWire card")).grid(row=1, column=0, sticky="w", pady=4)
            ctk.CTkEntry(self.cap_frame, textvariable=self.card, width=70).grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)
            hint = tr("Leave card empty = automatic. Switch the camcorder on in VCR/Play mode.")
            hint_row = 2
        else:
            self._lbl(self.cap_frame, "Camcorder").grid(row=0, column=0, sticky="w", pady=4)
            self.om_video = ctk.CTkOptionMenu(self.cap_frame, variable=self.dev_video,
                                              command=lambda _v: self._restart_preview(),
                                              dynamic_resizing=False, values=[tr(NO_DEVICE)])
            self.om_video.grid(row=0, column=1, sticky="ew", padx=(10, 6), pady=4)
            self._tinted(self.cap_frame, "↻", 36, self.refresh_devices).grid(row=0, column=2, pady=4)
            self._lbl(self.cap_frame, "Audio").grid(row=1, column=0, sticky="w", pady=4)
            self.om_audio = ctk.CTkOptionMenu(self.cap_frame, variable=self.dev_audio,
                                              dynamic_resizing=False, values=[tr(NO_AUDIO_DEV)])
            self.om_audio.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=4)
            hint = tr("Switch the camcorder on in VCR/Play mode, then click ↻.")
            hint_row = 2
        self._lbl(self.cap_frame, hint, text_color=COL_HINT, wraplength=390,
                  justify="left").grid(row=hint_row, column=0, columnspan=3, sticky="w", pady=(4, 0))

        self.file_frame = ctk.CTkFrame(body, fg_color="transparent", border_width=0)
        self.file_frame.columnconfigure(0, weight=1)
        ctk.CTkEntry(self.file_frame, textvariable=self.src_file).grid(row=0, column=0, sticky="ew", pady=4)
        self._tinted(self.file_frame, tr("Browse …"), 110, self._pick_src).grid(row=0, column=1, padx=(8, 0), pady=4)
        self._lbl(self.file_frame, "DV, AVI, MOV, M2T, MTS, MPG …", text_color=COL_HINT).grid(
            row=1, column=0, columnspan=2, sticky="w")

        # Output
        body = self._card(left, tr("Output file (MP4)"))
        body.columnconfigure(0, weight=1)
        ctk.CTkEntry(body, textvariable=self.outfile).grid(row=0, column=0, sticky="ew", pady=4)
        self._tinted(body, tr("Change …"), 90, self._pick_out).grid(row=0, column=1, padx=(8, 0), pady=4)

        # Quality
        body = self._card(left, tr("Quality & options"))
        body.columnconfigure(1, weight=1)
        self._lbl(body, tr("Quality")).grid(row=0, column=0, sticky="w", pady=4)
        ctk.CTkOptionMenu(body, variable=self.quality, values=[tr(k) for k in QUALITY],
                          dynamic_resizing=False).grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=4)
        self._lbl(body, tr("Encoding speed")).grid(row=1, column=0, sticky="w", pady=4)
        ctk.CTkOptionMenu(body, variable=self.preset, values=[tr(k) for k in PRESET],
                          dynamic_resizing=False).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=4)
        ctk.CTkSwitch(body, text=tr("Remove interlacing (deinterlace)"),
                      variable=self.deint).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 4))
        ctk.CTkSwitch(body, text=tr("Square pixels (correct 4:3 / 16:9)"),
                      variable=self.square).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)
        self._lbl(body, tr("Auto stop (min)")).grid(row=4, column=0, sticky="w", pady=(10, 4))
        ctk.CTkEntry(body, textvariable=self.stop_min, width=70).grid(row=4, column=1, sticky="w", padx=(10, 0), pady=(10, 4))
        self._lbl(body, tr("Advanced")).grid(row=5, column=0, sticky="w", pady=4)
        ctk.CTkEntry(body, textvariable=self.extra).grid(row=5, column=1, sticky="ew", padx=(10, 0), pady=4)
        self._lbl(body, tr("Auto stop 0 = off · \"Advanced\" = extra ffmpeg input options"),
                  text_color=COL_HINT, wraplength=390, justify="left").grid(row=6, column=0, columnspan=2, sticky="w")

        # Right column: preview, status, controls, log
        right = ctk.CTkFrame(self, fg_color="transparent", border_width=0)
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 22), pady=(0, 16))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)
        bold14 = ctk.CTkFont(size=14, weight="bold")

        # Preview
        pv = ctk.CTkFrame(right)
        pv.grid(row=0, column=0, sticky="ew", pady=6)
        ph = ctk.CTkFrame(pv, fg_color="transparent", border_width=0)
        ph.pack(fill="x", padx=16, pady=(10, 6))
        ph.columnconfigure(0, weight=1)
        ctk.CTkLabel(ph, text=tr("Live preview"), anchor="w", font=bold14).grid(row=0, column=0, sticky="w")
        self._tinted(ph, "↻", 30, self._refresh_preview, height=26).grid(
            row=0, column=1, sticky="e", padx=(0, 8))
        ctk.CTkSwitch(ph, text="", variable=self.show_preview, width=46,
                      command=self._restart_preview).grid(row=0, column=2, sticky="e")
        # Plain tk.Label + reused PhotoImage: much smoother than one CTkImage per frame
        self._blank_ph = ImageTk.PhotoImage(Image.new("RGB", (PW, PH), (18, 18, 18)))
        self._video_ph = ImageTk.PhotoImage(Image.new("RGB", (PW, PH), (18, 18, 18)))
        self.lbl_prev = tk.Label(pv, image=self._blank_ph, text=tr("No preview"), compound="center",
                                 bg=PREVIEW_BG, fg="#9a9a9a", bd=0, highlightthickness=0)
        self.lbl_prev.pack(pady=(0, 14))

        # Status
        sc = ctk.CTkFrame(right)
        sc.grid(row=1, column=0, sticky="ew", pady=6)
        self.lbl_timer = ctk.CTkLabel(sc, text="00:00:00", font=ctk.CTkFont(size=44, weight="bold"))
        self.lbl_timer.pack(pady=(12, 0))
        self.lbl_size = ctk.CTkLabel(sc, text=" ", text_color=COL_HINT)
        self.lbl_size.pack()
        self.pb = ctk.CTkProgressBar(sc, height=8)
        self.pb.set(0)
        self.pb.pack(fill="x", padx=24, pady=(8, 6))
        self.lbl_status = ctk.CTkLabel(sc, text=tr("Ready."), text_color=COL_INFO, wraplength=440)
        self.lbl_status.pack(pady=(0, 12), padx=16)

        # Start / stop
        bar = ctk.CTkFrame(right, fg_color="transparent", border_width=0)
        bar.grid(row=2, column=0, sticky="ew", pady=6)
        bar.columnconfigure((0, 1), weight=1, uniform="b")
        self.btn_start = ctk.CTkButton(bar, text="", height=48, corner_radius=24, fg_color=GREEN,
                                       hover_color=GREEN_HOVER, font=ctk.CTkFont(size=15, weight="bold"),
                                       command=self.start)
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_stop = ctk.CTkButton(bar, text=tr("■  Stop"), height=48, corner_radius=24, fg_color=RED,
                                      hover_color=RED_HOVER, font=ctk.CTkFont(size=15, weight="bold"),
                                      state="disabled", command=self.stop)
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Extra buttons
        extras = ctk.CTkFrame(right, fg_color="transparent", border_width=0)
        extras.grid(row=3, column=0, sticky="ew")
        self.btn_folder = self._tinted(extras, tr("Open folder"), 120, self.open_folder, state="disabled",
                                       text_color_disabled=COL_HINT)
        self.btn_folder.pack(side="left")
        if self.dvcont:
            for label, cmd in (("■", "stop"), ("▶", "play"), ("◀◀", "rewind")):
                self._tinted(extras, label, 44, lambda c=cmd: self.tape(c)).pack(side="right", padx=2)
            ctk.CTkLabel(extras, text=tr("Tape:"), text_color=COL_HINT).pack(side="right", padx=(0, 6))

        # Log
        lg = ctk.CTkFrame(right)
        lg.grid(row=4, column=0, sticky="nsew", pady=(6, 0))
        lg.columnconfigure(0, weight=1)
        lg.rowconfigure(1, weight=1)
        ctk.CTkLabel(lg, text=tr("Log"), anchor="w", font=bold14).grid(
            row=0, column=0, sticky="w", padx=16, pady=(10, 2))
        self.txt = ctk.CTkTextbox(lg, wrap="word", height=80, font=ctk.CTkFont(family=self.mono, size=12))
        self.txt.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.txt.configure(state="disabled")

    # ------------------------------------------------------- Status & dialogs
    def _log(self, msg):
        self.txt.configure(state="normal")
        self.txt.insert("end", msg.rstrip() + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _set_status(self, text, kind="info"):
        color = {"info": COL_INFO, "ok": COL_OK, "err": COL_ERR}[kind]
        self.lbl_status.configure(text=text, text_color=color)

    def _pb_indeterminate(self):
        self.pb.stop()
        self.pb.configure(mode="indeterminate")
        self.pb.start()

    def _pb_determinate(self, value):
        self.pb.stop()
        self.pb.configure(mode="determinate")
        self.pb.set(value)

    def _update_buttons(self):
        busy = self.running and not self.preview_only   # recording/conversion running
        pending = self._after_idle is not None          # camera is being handed over
        can_start = not (busy or pending)
        # Disabled buttons fade to a neutral fill instead of keeping their full color
        self.btn_start.configure(state="normal" if can_start else "disabled",
                                 fg_color=GREEN if can_start else FIELD)
        self.btn_stop.configure(state="normal" if busy else "disabled", fg_color=RED if busy else FIELD)

    def _show_placeholder(self, text=None):
        self._video_on = False
        self.lbl_prev.configure(image=self._blank_ph, text=text or tr("No preview"))

    def _idle_text(self):
        if not self._is_capture():
            return tr("Preview appears during conversion")
        if not self.show_preview.get():
            return tr("Preview is turned off")
        return tr("No preview")

    def _preview_tick(self):
        """Draws the newest preview frame (checked up to ~60 times per second)."""
        data = self._frame
        if data is not None and data is not self._shown and self.running:
            self._shown = data
            try:
                img = Image.open(io.BytesIO(data))
                img.load()
                if img.size != (PW, PH):
                    img = img.resize((PW, PH))
                self._video_ph.paste(img)  # reuse the same image object → no flicker
                if not self._video_on:
                    self._video_on = True
                    self.lbl_prev.configure(image=self._video_ph, text="")
                    if self.preview_only and not self._hold_status:
                        self._set_status(tr("Preview running – ready to record."))
            except Exception:  # noqa: BLE001
                pass
        self.after(15, self._preview_tick)

    def _pump_preview(self, stream, gen):
        """Reads MJPEG frames from ffmpeg's stdout; keeps only the newest frame."""
        buf = b""
        try:
            while True:
                chunk = stream.read1(65536)
                if not chunk:
                    break
                buf += chunk
                while True:
                    a = buf.find(b"\xff\xd8")
                    if a < 0:
                        buf = buf[-1:]
                        break
                    b = buf.find(b"\xff\xd9", a + 2)
                    if b < 0:
                        buf = buf[a:]
                        break
                    if gen == self._gen:
                        self._frame = buf[a:b + 2]
                    buf = buf[b + 2:]
                if len(buf) > 8_000_000:
                    buf = b""
        except Exception:  # noqa: BLE001
            pass
        try:  # drain the pipe so ffmpeg never blocks
            while stream.read(65536):
                pass
        except Exception:  # noqa: BLE001
            pass

    def _mode_changed(self, *_):
        if self._is_capture():
            self.file_frame.grid_remove()
            self.cap_frame.grid(row=0, column=0, sticky="ew")
            self.btn_start.configure(text=tr("●  Start recording"))
        else:
            self.cap_frame.grid_remove()
            self.file_frame.grid(row=0, column=0, sticky="ew")
            self.btn_start.configure(text=tr("▶  Start conversion"))
        self._update_buttons()
        self._restart_preview()

    def _pick_src(self):
        p = filedialog.askopenfilename(title=tr("Choose input file"), filetypes=[
            (tr("Video files"), "*.dv *.avi *.mov *.m2t *.mts *.m2ts *.ts *.mpg *.mkv *.mp4"), (tr("All files"), "*.*")])
        if p:
            self.src_file.set(p)
            if os.path.basename(self.outfile.get()).startswith("Camcorder_"):
                self.outfile.set(os.path.splitext(p)[0] + ".mp4")

    def _pick_out(self):
        p = filedialog.asksaveasfilename(title=tr("Save MP4 as"), defaultextension=".mp4",
                                         initialfile=os.path.basename(self.outfile.get()),
                                         filetypes=[(tr("MP4 video"), "*.mp4")])
        if p:
            self.outfile.set(p)

    def open_folder(self):
        folder = os.path.dirname(os.path.abspath(self.current_out or self.outfile.get()))
        try:
            if SYSTEM == "Windows":
                os.startfile(folder)  # noqa: S606
            elif SYSTEM == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:  # noqa: BLE001
            self._log(tr("Could not open folder: {e}", e=e))

    # --------------------------------------------------------------- Devices
    def _startup_checks(self):
        if not self.ffmpeg:
            self._set_status(tr("ffmpeg not found – see log."), "err")
            self._log(tr("ERROR: ffmpeg was not found. Installation:") + "\n"
                      "  Windows: winget install ffmpeg\n"
                      "  macOS:   brew install ffmpeg\n"
                      "  Linux:   sudo apt install ffmpeg dvgrab")
            return
        self._log(f"ffmpeg: {self.ffmpeg}")
        self._ready = True
        if SYSTEM == "Linux":
            if self.dvgrab:
                self._log(f"dvgrab: {self.dvgrab}")
            else:
                self._log(tr("Note: dvgrab is missing (sudo apt install dvgrab). "
                             "Falling back to ffmpeg's iec61883 input."))
            self._sync_preview()
        else:
            self.refresh_devices()  # then starts the preview automatically

    def _refresh_preview(self):
        """↻ in the preview: rescan devices (Windows/macOS) and restart the preview."""
        if SYSTEM == "Linux":
            self._restart_preview()
        else:
            self.refresh_devices()

    def refresh_devices(self):
        if not self.ffmpeg:
            return
        try:
            if SYSTEM == "Windows":
                cmd = [self.ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
            else:
                cmd = [self.ffmpeg, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""]
            r = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                               timeout=20, creationflags=NO_WINDOW)
        except Exception as e:  # noqa: BLE001
            self._log(tr("Device list failed: {e}", e=e))
            return
        text = r.stderr + r.stdout
        if SYSTEM == "Windows":
            v, a = parse_dshow(text)
            self.video_map = {n: n for n in v}
            self.audio_map = {n: n for n in a}
        else:
            v, a = parse_avfoundation(text)
            self.video_map = {f"[{i}] {n}": i for i, n in v}
            self.audio_map = {f"[{i}] {n}": i for i, n in a}
        self.om_video.configure(values=list(self.video_map) or [tr(NO_DEVICE)])
        self.om_audio.configure(values=[tr(NO_AUDIO_DEV)] + list(self.audio_map))
        if self.video_map:
            if self.dev_video.get() not in self.video_map:
                pick = next((n for n in self.video_map if "dv" in n.lower() or "vcr" in n.lower()),
                            next(iter(self.video_map)))
                self.dev_video.set(pick)
        else:
            self.dev_video.set(tr(NO_DEVICE))
        self._log(tr("Found {v} video and {a} audio devices.", v=len(self.video_map), a=len(self.audio_map)))
        if not self.video_map:
            self._log(tr("No camcorder detected. Switch the camera on in VCR/Play mode, "
                         "check the cable and click ↻."))
        self._restart_preview()

    # ------------------------------------------------------- Build commands
    def _minutes(self):
        try:
            return max(0, int(self.stop_min.get().strip() or 0))
        except ValueError:
            return 0

    def _encode_args(self):
        vf = []
        if self.deint.get():
            vf.append("yadif=0:-1:0")
        if self.square.get():
            vf += ["scale=w=trunc(ih*dar/2)*2:h=ih", "setsar=1"]
        args = []
        if vf:
            args += ["-vf", ",".join(vf)]
        args += ["-c:v", "libx264", "-preset", PRESET[self._key(PRESET, self.preset.get())],
                 "-crf", str(QUALITY[self._key(QUALITY, self.quality.get())]), "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart"]
        return args

    def _limit_args(self):
        if self._minutes() > 0 and self._is_capture():
            return ["-t", str(self._minutes() * 60)]
        return []

    def _preview_args(self):
        """Second ffmpeg output: small MJPEG frames via stdout (preview only).
        Camcorder: full frame rate (25/30 fps) for smooth video. File: 8 fps is enough."""
        vf = [] if self._is_capture() else ["fps=8"]
        if self.deint.get():
            vf.append("yadif=0:-1:0")
        vf += ["scale=w=trunc(ih*dar/2)*2:h=ih", "setsar=1",
               f"scale={PW}:{PH}:force_original_aspect_ratio=decrease",
               f"pad={PW}:{PH}:(ow-iw)/2:(oh-ih)/2"]
        return ["-an", "-vf", ",".join(vf), "-c:v", "mjpeg", "-q:v", "5",
                "-strict", "unofficial", "-flush_packets", "1", "-f", "image2pipe"]

    def _build_commands(self, out, preview_only=False):
        """Returns (dvgrab command or None, ffmpeg command, preview on?)."""
        ff = [self.ffmpeg, "-hide_banner", "-y"]
        if preview_only:  # live preview: report errors only, buffer as little as possible
            ff += ["-loglevel", "error", "-nostats", "-fflags", "nobuffer", "-flags", "low_delay"]
        extra = shlex.split(self.extra.get(), posix=(SYSTEM != "Windows"))
        limit = [] if preview_only else self._limit_args()
        use_preview = bool(self.show_preview.get() or preview_only)

        outs = []
        if not preview_only:
            outs += self._encode_args() + limit + [out]
        if use_preview:
            outs += self._preview_args() + limit + ["pipe:1"]

        if not self._is_capture():
            src = self.src_file.get().strip()
            if not os.path.isfile(src):
                raise ValueError(tr("Please choose an existing input file."))
            return None, ff + extra + ["-i", src] + outs, use_preview

        if SYSTEM == "Linux":
            hdv = self.cam_format.get().startswith("HDV")
            if self.dvgrab:
                dv = [self.dvgrab, "--format", "hdv" if hdv else "raw"]
                if self.card.get().strip():
                    dv += ["--card", self.card.get().strip()]
                dv += ["-"]
                return (dv, ff + ["-f", "mpegts" if hdv else "dv"] + extra + ["-i", "pipe:0"] + outs,
                        use_preview)
            return None, ff + ["-f", "iec61883"] + extra + ["-i", "auto"] + outs, use_preview

        v = self.video_map.get(self.dev_video.get())
        if not v:
            raise ValueError(tr("No camcorder found. Switch it on (VCR mode) and click ↻."))
        # the preview alone does not open an audio device
        a = None if preview_only else self.audio_map.get(self.dev_audio.get())
        if SYSTEM == "Windows":
            spec = f"video={v}" + (f":audio={a}" if a else "")
            return (None, ff + ["-f", "dshow", "-rtbufsize", "256M"] + extra + ["-i", spec] + outs,
                    use_preview)
        spec = f"{v}:{a if a else 'none'}"
        return None, ff + ["-f", "avfoundation"] + extra + ["-i", spec] + outs, use_preview

    # ------------------------------------------------------------ Live preview
    def _want_preview(self):
        return bool(self._ready and self.ffmpeg and self._is_capture()
                    and self.show_preview.get() and not self.preview_failed)

    def _sync_preview(self):
        """Starts or stops the live preview, depending on whether it is currently wanted."""
        if self._after_idle is not None:
            return
        if self.running:
            if self.preview_only and not self._want_preview():
                self._kill_current()
            return
        if self._want_preview():
            self._begin_preview()
        elif not self.preview_failed:
            self._show_placeholder(self._idle_text())

    def _restart_preview(self, *_):
        """After a device/setting change: rebuild the preview (reset the error state)."""
        self.preview_failed = False
        if self.running and self.preview_only:
            if self._after_idle is None:
                self._after_idle = self._sync_preview
                self._kill_current()
        else:
            self._sync_preview()

    def _begin_preview(self):
        try:
            dv_cmd, ff_cmd, _ = self._build_commands(None, preview_only=True)
        except ValueError as e:
            self._hold_status = False
            self._show_placeholder(tr("No camcorder found"))
            self._set_status(str(e))
            return
        self._begin(None, dv_cmd, ff_cmd, True, preview_only=True)

    def _kill_current(self):
        """Ends the running process immediately (preview: no file to finalize)."""
        self.stopping = True
        for p in (self.dv, self.ff):
            try:
                if p and p.poll() is None:
                    p.terminate()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------ Start / stop
    def start(self):
        if (self.running and not self.preview_only) or self._after_idle is not None:
            return
        if not self.ffmpeg:
            messagebox.showerror(tr("ffmpeg missing"), tr("ffmpeg was not found. Please install it (see log)."))
            return
        out = self.outfile.get().strip()
        if not out:
            messagebox.showerror(tr("Output file"), tr("Please specify an output file."))
            return
        if not out.lower().endswith(".mp4"):
            out += ".mp4"
            self.outfile.set(out)
        if os.path.exists(out) and not messagebox.askyesno(tr("File exists"), tr("Overwrite\n{out}?", out=out)):
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            dv_cmd, ff_cmd, use_preview = self._build_commands(out)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(tr("Error"), str(e))
            return

        def job():
            self._begin(out, dv_cmd, ff_cmd, use_preview, preview_only=False)

        if self.running:
            # The camera can only be opened by one process:
            # stop the preview, then the recording starts automatically.
            self._after_idle = job
            self._set_status(tr("Handing camera over to recording …"))
            self._update_buttons()
            self._kill_current()
        else:
            job()

    def _begin(self, out, dv_cmd, ff_cmd, use_preview, preview_only):
        self._gen += 1
        self.preview_only = preview_only
        self.use_preview = use_preview
        self.current_out = out or ""
        self.running, self.stopping = True, False
        self.total_secs = None
        self._frame = self._shown = None
        self._last_dv = None
        if preview_only:
            self._show_placeholder(tr("Waiting for picture …\n\nSwitch the camcorder on (VCR mode) and press Play"))
            if not self._hold_status:
                self._set_status(tr("Starting preview …"))
        else:
            self._hold_status = False
            if not use_preview:
                self._show_placeholder(tr("Preview is turned off"))
            # otherwise the last preview frame stays until new frames arrive
            self.btn_folder.configure(state="disabled")
            self.lbl_timer.configure(text="00:00:00")
            self.lbl_size.configure(text=" ")
            self._set_status(tr("Starting …"))
            self._pb_indeterminate()
            if self._is_capture():
                self._log(tr("Recording started – play the tape on the camcorder (Play) "
                             "if it doesn't start automatically."))
        self._update_buttons()
        threading.Thread(target=self._run, args=(dv_cmd, ff_cmd, use_preview, self._gen), daemon=True).start()

    def _pump(self, stream, tag):
        buf = b""
        while True:
            chunk = stream.read1(1024)
            if not chunk:
                break
            buf += chunk
            parts = re.split(rb"[\r\n]+", buf)
            buf = parts.pop()
            for p in parts:
                if p.strip():
                    self.q.put((tag, p.decode("utf-8", "replace").strip()))
        if buf.strip():
            self.q.put((tag, buf.decode("utf-8", "replace").strip()))

    def _run(self, dv_cmd, ff_cmd, use_preview, gen):
        rc = -1
        dv = None
        try:
            if dv_cmd:
                self.q.put(("log", "$ " + fmt_cmd(dv_cmd) + " | " + fmt_cmd(ff_cmd)))
                dv = subprocess.Popen(dv_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      creationflags=NO_WINDOW)
                self.dv = dv
                threading.Thread(target=self._pump, args=(dv.stderr, "dv"), daemon=True).start()
                ff_stdin = dv.stdout
            else:
                self.q.put(("log", "$ " + fmt_cmd(ff_cmd)))
                ff_stdin = subprocess.PIPE
            ff = subprocess.Popen(ff_cmd, stdin=ff_stdin,
                                  stdout=subprocess.PIPE if use_preview else subprocess.DEVNULL,
                                  stderr=subprocess.PIPE, creationflags=NO_WINDOW)
            self.ff = ff
            if dv:
                dv.stdout.close()
            if self.stopping and self.preview_only:  # cancel arrived before the processes were running
                self._kill_current()
            if use_preview:
                threading.Thread(target=self._pump_preview, args=(ff.stdout, gen), daemon=True).start()
            t = threading.Thread(target=self._pump, args=(ff.stderr, "ff"), daemon=True)
            t.start()
            rc = ff.wait()
            t.join(timeout=2)
            if dv and dv.poll() is None:
                dv.terminate()
            if dv:  # really release the camera before continuing
                try:
                    dv.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    dv.kill()
        except FileNotFoundError as e:
            self.q.put(("log", tr("Program not found: {e}", e=e)))
        except Exception as e:  # noqa: BLE001
            self.q.put(("log", tr("Error: {e}", e=e)))
        self.q.put(("done", (gen, rc)))

    def stop(self):
        if not self.running:
            return
        self.stopping = True
        self._set_status(tr("Stopping and finalizing MP4 file …"))
        try:
            if self.dv and self.dv.poll() is None:
                self.dv.terminate()  # ffmpeg gets EOF and finalizes the file
            elif self.ff and self.ff.poll() is None:
                self.ff.stdin.write(b"q")
                self.ff.stdin.flush()
        except Exception:  # noqa: BLE001
            if self.ff and self.ff.poll() is None:
                self.ff.terminate()
        self.after(15000, self._force_kill)

    def _force_kill(self):
        if self.running and self.ff and self.ff.poll() is None:
            self.ff.terminate()

    def tape(self, command):
        def work():
            try:
                r = subprocess.run([self.dvcont, command], capture_output=True, text=True, timeout=15)
                self.q.put(("log", f"dvcont {command}: " + (r.stdout + r.stderr).strip()))
            except Exception as e:  # noqa: BLE001
                self.q.put(("log", tr("dvcont {command} failed: {e}", command=command, e=e)))
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ Event loop
    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self._log(data)
                elif kind == "dv":
                    # don't write dvgrab's progress lines to the log
                    if "timecode" not in data and data != self._last_dv:
                        self._last_dv = data
                        self._log("[dvgrab] " + data)
                elif kind == "ff":
                    self._ff_line(data)
                elif kind == "done":
                    self._finished(*data)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _ff_line(self, line):
        m = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
        if m and ("frame=" in line or "size=" in line):
            h, mi, s_ = int(m.group(1)), int(m.group(2)), float(m.group(3))
            secs = h * 3600 + mi * 60 + s_
            self.lbl_timer.configure(text=f"{h:02d}:{mi:02d}:{int(s_):02d}")
            sz = re.search(r"size=\s*(\S+)", line)
            if sz and sz.group(1) != "N/A" and not self.preview_only:
                self.lbl_size.configure(text=tr("File size: {size}", size=sz.group(1)))
            if not self.stopping:
                if self.preview_only:
                    pass
                elif self.total_secs:
                    frac = min(1.0, secs / self.total_secs)
                    self.pb.set(frac)
                    self._set_status(tr("Converting … {pct:.0f} %", pct=frac * 100))
                else:
                    self._set_status(tr("Recording …") if self._is_capture() else tr("Converting …"))
            return
        d = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
        if d and not self._is_capture() and self.total_secs is None:
            total = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
            if total > 0:
                self.total_secs = total
                self._pb_determinate(0)
        self._log(line)

    def _finished(self, gen, rc):
        if gen != self._gen:
            return  # message from an older run
        was_preview = self.preview_only
        self.running = False
        self.preview_only = False
        self.dv = self.ff = None
        self._frame = None
        cb, self._after_idle = self._after_idle, None

        if was_preview:
            if cb:  # camera is handed to the recording, or the preview restarts
                self._update_buttons()
                cb()
                return
            self._update_buttons()
            if self.stopping:
                self._show_placeholder(self._idle_text())
            else:
                # preview stopped by itself → don't restart endlessly
                self.preview_failed = True
                self._hold_status = False
                self._show_placeholder(tr("No picture from camcorder"))
                self._set_status(tr("No preview – switch the camcorder on (VCR mode) and click ↻."))
                self._log(tr("Preview ended: no signal from camcorder. Tips: VCR mode? Cable/driver OK?"))
            return

        self._update_buttons()
        self._show_placeholder(self._idle_text())
        self._hold_status = True
        have_file = os.path.isfile(self.current_out) and os.path.getsize(self.current_out) > 0
        if have_file and (rc == 0 or self.stopping):
            mb = os.path.getsize(self.current_out) / 1e6
            self._pb_determinate(1)
            self._set_status(tr("Done: {name} ({mb:.1f} MB)", name=os.path.basename(self.current_out), mb=mb), "ok")
            self._log(tr("Done: {name} ({mb:.1f} MB)", name=self.current_out, mb=mb))
            self.btn_folder.configure(state="normal")
            self.outfile.set(self._default_output())
        else:
            self._pb_determinate(0)
            self._set_status(tr("Failed (code {rc}) – details in the log.", rc=rc), "err")
            self._log(tr("No valid MP4 file was created. Tips: camcorder in VCR mode? "
                         "Cable/driver OK? Extra input options may be needed."))
        self._sync_preview()  # resume the live preview

    def _on_close(self):
        if self.running and not self.preview_only:
            if not messagebox.askyesno(tr("Quit"), tr("A recording/conversion is still running. Really quit?")):
                return
        for p in (self.dv, self.ff):
            try:
                if p and p.poll() is None:
                    p.terminate()
            except Exception:  # noqa: BLE001
                pass
        self.destroy()


def selftest(result_path):
    """Checks without a window whether a usable ffmpeg (with libx264 and AAC) is found.
    Usage:  FireWire2MP4 --selftest result.txt   (used by the build script)"""
    lines, ok = [], False
    exe = find_ffmpeg()
    lines.append(f"ffmpeg: {exe}")
    if exe:
        try:
            enc = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True, text=True,
                                 errors="replace", timeout=30, creationflags=NO_WINDOW)
            out = enc.stdout + enc.stderr
            has_x264, has_aac = "libx264" in out, " aac " in out
            lines.append(f"libx264: {has_x264}, aac: {has_aac}")
            ok = has_x264 and has_aac
        except Exception as e:  # noqa: BLE001
            lines.append(f"Error: {e}")
    lines.append("SELFTEST OK" if ok else "SELFTEST FAILED")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        raise SystemExit(selftest(sys.argv[2]))
    App().mainloop()
