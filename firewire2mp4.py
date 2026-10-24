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

MODE_CAP = "Record camcorder"
MODE_FILE = "Convert file"
QUALITY = {"High (CRF 18)": 18, "Good (CRF 21)": 21, "Compact (CRF 24)": 24}
PRESET = {"Fast (larger file)": "veryfast", "Medium (recommended)": "medium", "Slow (smaller file)": "slow"}
NO_AUDIO_DEV = "(in video stream / none)"
NO_DEVICE = "(no device found)"
PW, PH = 448, 252  # preview size (16:9)
PREVIEW_BG = "#121212"

GREEN = ("#2e9e5b", "#2e9e5b")
RED = ("#c94040", "#c94040")
COL_INFO = ("gray30", "gray75")
COL_OK = ("#1e7a45", "#4cc38a")
COL_ERR = ("#b3261e", "#ff6b6b")
COL_HINT = ("gray40", "gray60")


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
        super().__init__()
        self.title("Cam2MP4")
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
        self.dev_video = tk.StringVar(value=NO_DEVICE)
        self.dev_audio = tk.StringVar(value=NO_AUDIO_DEV)
        self.cam_format = tk.StringVar(value="DV")
        self.card = tk.StringVar()
        self.outfile = tk.StringVar(value=self._default_output())
        self.quality = tk.StringVar(value="Good (CRF 21)")
        self.preset = tk.StringVar(value="Medium (recommended)")
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
        return self.mode_btn.get() == MODE_CAP

    def _set_theme(self, value):
        ctk.set_appearance_mode({"Light": "light", "Dark": "dark", "Auto": "system"}[value])

    def _card(self, parent, title):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.pack(fill="x", pady=6)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(fill="x", padx=16, pady=(12, 4))
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 14))
        return body

    @staticmethod
    def _lbl(parent, text, **kw):
        return ctk.CTkLabel(parent, text=text, anchor="w", **kw)

    # -------------------------------------------------------------------- UI
    def _build(self):
        self.columnconfigure(0, weight=0, minsize=480)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        # Header
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=22, pady=(18, 6))
        head.columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="Cam2MP4", anchor="w",
                     font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(head, text="Keep your memories alive – digitize camcorder tapes straight to MP4", anchor="w",
                     text_color=COL_HINT).grid(row=1, column=0, sticky="w")
        self.theme_btn = ctk.CTkSegmentedButton(head, values=["Light", "Dark", "Auto"],
                                                command=self._set_theme, width=180)
        self.theme_btn.set("Auto")
        self.theme_btn.grid(row=0, column=1, rowspan=2, sticky="e")

        # Left column: settings
        left = ctk.CTkScrollableFrame(self, width=450, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=(0, 16))

        self.mode_btn = ctk.CTkSegmentedButton(left, values=[MODE_CAP, MODE_FILE],
                                               command=self._mode_changed, height=36)
        self.mode_btn.set(MODE_CAP)
        self.mode_btn.pack(fill="x", pady=(0, 6))

        # Source
        body = self._card(left, "Source")
        body.columnconfigure(0, weight=1)

        self.cap_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.cap_frame.columnconfigure(1, weight=1)
        if SYSTEM == "Linux":
            self._lbl(self.cap_frame, "Format").grid(row=0, column=0, sticky="w", pady=4)
            ctk.CTkOptionMenu(self.cap_frame, variable=self.cam_format, dynamic_resizing=False,
                              command=lambda _v: self._restart_preview(),
                              values=["DV", "HDV (experimental)"]).grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=4)
            self._lbl(self.cap_frame, "FireWire card").grid(row=1, column=0, sticky="w", pady=4)
            ctk.CTkEntry(self.cap_frame, textvariable=self.card, width=70).grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)
            hint = "Leave card empty = automatic. Switch the camcorder on in VCR/Play mode."
            hint_row = 2
        else:
            self._lbl(self.cap_frame, "Camcorder").grid(row=0, column=0, sticky="w", pady=4)
            self.om_video = ctk.CTkOptionMenu(self.cap_frame, variable=self.dev_video,
                                              command=lambda _v: self._restart_preview(),
                                              dynamic_resizing=False, values=[NO_DEVICE])
            self.om_video.grid(row=0, column=1, sticky="ew", padx=(10, 6), pady=4)
            ctk.CTkButton(self.cap_frame, text="↻", width=36, command=self.refresh_devices).grid(row=0, column=2, pady=4)
            self._lbl(self.cap_frame, "Audio").grid(row=1, column=0, sticky="w", pady=4)
            self.om_audio = ctk.CTkOptionMenu(self.cap_frame, variable=self.dev_audio,
                                              dynamic_resizing=False, values=[NO_AUDIO_DEV])
            self.om_audio.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=4)
            hint = "Switch the camcorder on in VCR/Play mode, then click ↻."
            hint_row = 2
        self._lbl(self.cap_frame, hint, text_color=COL_HINT, wraplength=390,
                  justify="left").grid(row=hint_row, column=0, columnspan=3, sticky="w", pady=(4, 0))

        self.file_frame = ctk.CTkFrame(body, fg_color="transparent")
        self.file_frame.columnconfigure(0, weight=1)
        ctk.CTkEntry(self.file_frame, textvariable=self.src_file).grid(row=0, column=0, sticky="ew", pady=4)
        ctk.CTkButton(self.file_frame, text="Browse …", width=110,
                      command=self._pick_src).grid(row=0, column=1, padx=(8, 0), pady=4)
        self._lbl(self.file_frame, "DV, AVI, MOV, M2T, MTS, MPG …", text_color=COL_HINT).grid(
            row=1, column=0, columnspan=2, sticky="w")

        # Output
        body = self._card(left, "Output file (MP4)")
        body.columnconfigure(0, weight=1)
        ctk.CTkEntry(body, textvariable=self.outfile).grid(row=0, column=0, sticky="ew", pady=4)
        ctk.CTkButton(body, text="Change …", width=90, command=self._pick_out).grid(row=0, column=1, padx=(8, 0), pady=4)

        # Quality
        body = self._card(left, "Quality & options")
        body.columnconfigure(1, weight=1)
        self._lbl(body, "Quality").grid(row=0, column=0, sticky="w", pady=4)
        ctk.CTkOptionMenu(body, variable=self.quality, values=list(QUALITY),
                          dynamic_resizing=False).grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=4)
        self._lbl(body, "Encoding speed").grid(row=1, column=0, sticky="w", pady=4)
        ctk.CTkOptionMenu(body, variable=self.preset, values=list(PRESET),
                          dynamic_resizing=False).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=4)
        ctk.CTkSwitch(body, text="Remove interlacing (deinterlace)",
                      variable=self.deint).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 4))
        ctk.CTkSwitch(body, text="Square pixels (correct 4:3 / 16:9)",
                      variable=self.square).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)
        self._lbl(body, "Auto stop (min)").grid(row=4, column=0, sticky="w", pady=(10, 4))
        ctk.CTkEntry(body, textvariable=self.stop_min, width=70).grid(row=4, column=1, sticky="w", padx=(10, 0), pady=(10, 4))
        self._lbl(body, "Advanced").grid(row=5, column=0, sticky="w", pady=4)
        ctk.CTkEntry(body, textvariable=self.extra).grid(row=5, column=1, sticky="ew", padx=(10, 0), pady=4)
        self._lbl(body, "Auto stop 0 = off · \"Advanced\" = extra ffmpeg input options",
                  text_color=COL_HINT, wraplength=390, justify="left").grid(row=6, column=0, columnspan=2, sticky="w")

        # Right column: preview, status, controls, log
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 22), pady=(0, 16))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)
        bold14 = ctk.CTkFont(size=14, weight="bold")

        # Preview
        pv = ctk.CTkFrame(right, corner_radius=12)
        pv.grid(row=0, column=0, sticky="ew", pady=6)
        ph = ctk.CTkFrame(pv, fg_color="transparent")
        ph.pack(fill="x", padx=16, pady=(10, 6))
        ph.columnconfigure(0, weight=1)
        ctk.CTkLabel(ph, text="Live preview", anchor="w", font=bold14).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(ph, text="↻", width=30, height=26, command=self._refresh_preview).grid(
            row=0, column=1, sticky="e", padx=(0, 8))
        ctk.CTkSwitch(ph, text="", variable=self.show_preview, width=46,
                      command=self._restart_preview).grid(row=0, column=2, sticky="e")
        # Plain tk.Label + reused PhotoImage: much smoother than one CTkImage per frame
        self._blank_ph = ImageTk.PhotoImage(Image.new("RGB", (PW, PH), (18, 18, 18)))
        self._video_ph = ImageTk.PhotoImage(Image.new("RGB", (PW, PH), (18, 18, 18)))
        self.lbl_prev = tk.Label(pv, image=self._blank_ph, text="No preview", compound="center",
                                 bg=PREVIEW_BG, fg="#9a9a9a", bd=0, highlightthickness=0)
        self.lbl_prev.pack(pady=(0, 14))

        # Status
        sc = ctk.CTkFrame(right, corner_radius=12)
        sc.grid(row=1, column=0, sticky="ew", pady=6)
        self.lbl_timer = ctk.CTkLabel(sc, text="00:00:00", font=ctk.CTkFont(size=40, weight="bold"))
        self.lbl_timer.pack(pady=(12, 0))
        self.lbl_size = ctk.CTkLabel(sc, text=" ", text_color=COL_HINT)
        self.lbl_size.pack()
        self.pb = ctk.CTkProgressBar(sc)
        self.pb.set(0)
        self.pb.pack(fill="x", padx=24, pady=(8, 6))
        self.lbl_status = ctk.CTkLabel(sc, text="Ready.", text_color=COL_INFO, wraplength=440)
        self.lbl_status.pack(pady=(0, 12), padx=16)

        # Start / stop
        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", pady=6)
        bar.columnconfigure((0, 1), weight=1, uniform="b")
        self.btn_start = ctk.CTkButton(bar, text="", height=44, fg_color=GREEN, hover_color="#247a46",
                                       font=ctk.CTkFont(size=15, weight="bold"), command=self.start)
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_stop = ctk.CTkButton(bar, text="■  Stop", height=44, fg_color=RED, hover_color="#a03232",
                                      font=ctk.CTkFont(size=15, weight="bold"), state="disabled", command=self.stop)
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Extra buttons
        extras = ctk.CTkFrame(right, fg_color="transparent")
        extras.grid(row=3, column=0, sticky="ew")
        self.btn_folder = ctk.CTkButton(extras, text="Open folder", width=110, state="disabled",
                                        fg_color="transparent", border_width=1,
                                        text_color=("gray10", "gray90"), command=self.open_folder)
        self.btn_folder.pack(side="left")
        if self.dvcont:
            for label, cmd in (("■", "stop"), ("▶", "play"), ("◀◀", "rewind")):
                ctk.CTkButton(extras, text=label, width=44, command=lambda c=cmd: self.tape(c)).pack(side="right", padx=2)
            ctk.CTkLabel(extras, text="Tape:", text_color=COL_HINT).pack(side="right", padx=(0, 6))

        # Log
        lg = ctk.CTkFrame(right, corner_radius=12)
        lg.grid(row=4, column=0, sticky="nsew", pady=(6, 0))
        lg.columnconfigure(0, weight=1)
        lg.rowconfigure(1, weight=1)
        ctk.CTkLabel(lg, text="Log", anchor="w", font=bold14).grid(
            row=0, column=0, sticky="w", padx=16, pady=(10, 2))
        self.txt = ctk.CTkTextbox(lg, wrap="word", height=80, font=ctk.CTkFont(family="Courier", size=12))
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
        self.btn_start.configure(state="disabled" if (busy or pending) else "normal")
        self.btn_stop.configure(state="normal" if busy else "disabled")

    def _show_placeholder(self, text="No preview"):
        self._video_on = False
        self.lbl_prev.configure(image=self._blank_ph, text=text)

    def _idle_text(self):
        if not self._is_capture():
            return "Preview appears during conversion"
        if not self.show_preview.get():
            return "Preview is turned off"
        return "No preview"

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
                        self._set_status("Preview running – ready to record.")
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
            self.btn_start.configure(text="●  Start recording")
        else:
            self.cap_frame.grid_remove()
            self.file_frame.grid(row=0, column=0, sticky="ew")
            self.btn_start.configure(text="▶  Start conversion")
        self._update_buttons()
        self._restart_preview()

    def _pick_src(self):
        p = filedialog.askopenfilename(title="Choose input file", filetypes=[
            ("Video files", "*.dv *.avi *.mov *.m2t *.mts *.m2ts *.ts *.mpg *.mkv *.mp4"), ("All files", "*.*")])
        if p:
            self.src_file.set(p)
            if os.path.basename(self.outfile.get()).startswith("Camcorder_"):
                self.outfile.set(os.path.splitext(p)[0] + ".mp4")

    def _pick_out(self):
        p = filedialog.asksaveasfilename(title="Save MP4 as", defaultextension=".mp4",
                                         initialfile=os.path.basename(self.outfile.get()),
                                         filetypes=[("MP4 video", "*.mp4")])
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
            self._log(f"Could not open folder: {e}")

    # --------------------------------------------------------------- Devices
    def _startup_checks(self):
        if not self.ffmpeg:
            self._set_status("ffmpeg not found – see log.", "err")
            self._log("ERROR: ffmpeg was not found. Installation:\n"
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
                self._log("Note: dvgrab is missing (sudo apt install dvgrab). "
                          "Falling back to ffmpeg's iec61883 input.")
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
            self._log(f"Device list failed: {e}")
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
        self.om_video.configure(values=list(self.video_map) or [NO_DEVICE])
        self.om_audio.configure(values=[NO_AUDIO_DEV] + list(self.audio_map))
        if self.video_map:
            if self.dev_video.get() not in self.video_map:
                pick = next((n for n in self.video_map if "dv" in n.lower() or "vcr" in n.lower()),
                            next(iter(self.video_map)))
                self.dev_video.set(pick)
        else:
            self.dev_video.set(NO_DEVICE)
        self._log(f"Found {len(self.video_map)} video and {len(self.audio_map)} audio devices.")
        if not self.video_map:
            self._log("No camcorder detected. Switch the camera on in VCR/Play mode, "
                      "check the cable and click ↻.")
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
        args += ["-c:v", "libx264", "-preset", PRESET[self.preset.get()],
                 "-crf", str(QUALITY[self.quality.get()]), "-pix_fmt", "yuv420p",
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
                raise ValueError("Please choose an existing input file.")
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
            raise ValueError("No camcorder found. Switch it on (VCR mode) and click ↻.")
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
            self._show_placeholder("No camcorder found")
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
            messagebox.showerror("ffmpeg missing", "ffmpeg was not found. Please install it (see log).")
            return
        out = self.outfile.get().strip()
        if not out:
            messagebox.showerror("Output file", "Please specify an output file.")
            return
        if not out.lower().endswith(".mp4"):
            out += ".mp4"
            self.outfile.set(out)
        if os.path.exists(out) and not messagebox.askyesno("File exists", f"Overwrite\n{out}?"):
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            dv_cmd, ff_cmd, use_preview = self._build_commands(out)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", str(e))
            return

        def job():
            self._begin(out, dv_cmd, ff_cmd, use_preview, preview_only=False)

        if self.running:
            # The camera can only be opened by one process:
            # stop the preview, then the recording starts automatically.
            self._after_idle = job
            self._set_status("Handing camera over to recording …")
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
            self._show_placeholder("Waiting for picture …\n\nSwitch the camcorder on (VCR mode) and press Play")
            if not self._hold_status:
                self._set_status("Starting preview …")
        else:
            self._hold_status = False
            if not use_preview:
                self._show_placeholder("Preview is turned off")
            # otherwise the last preview frame stays until new frames arrive
            self.btn_folder.configure(state="disabled")
            self.lbl_timer.configure(text="00:00:00")
            self.lbl_size.configure(text=" ")
            self._set_status("Starting …")
            self._pb_indeterminate()
            if self._is_capture():
                self._log("Recording started – play the tape on the camcorder (Play) "
                          "if it doesn't start automatically.")
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
            self.q.put(("log", f"Program not found: {e}"))
        except Exception as e:  # noqa: BLE001
            self.q.put(("log", f"Error: {e}"))
        self.q.put(("done", (gen, rc)))

    def stop(self):
        if not self.running:
            return
        self.stopping = True
        self._set_status("Stopping and finalizing MP4 file …")
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
                self.q.put(("log", f"dvcont {command} failed: {e}"))
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
                self.lbl_size.configure(text=f"File size: {sz.group(1)}")
            if not self.stopping:
                if self.preview_only:
                    pass
                elif self.total_secs:
                    frac = min(1.0, secs / self.total_secs)
                    self.pb.set(frac)
                    self._set_status(f"Converting … {frac * 100:.0f} %")
                else:
                    self._set_status("Recording …" if self._is_capture() else "Converting …")
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
                self._show_placeholder("No picture from camcorder")
                self._set_status("No preview – switch the camcorder on (VCR mode) and click ↻.")
                self._log("Preview ended: no signal from camcorder. Tips: VCR mode? Cable/driver OK?")
            return

        self._update_buttons()
        self._show_placeholder(self._idle_text())
        self._hold_status = True
        have_file = os.path.isfile(self.current_out) and os.path.getsize(self.current_out) > 0
        if have_file and (rc == 0 or self.stopping):
            mb = os.path.getsize(self.current_out) / 1e6
            self._pb_determinate(1)
            self._set_status(f"Done: {os.path.basename(self.current_out)} ({mb:.1f} MB)", "ok")
            self._log(f"Done: {self.current_out} ({mb:.1f} MB)")
            self.btn_folder.configure(state="normal")
            self.outfile.set(self._default_output())
        else:
            self._pb_determinate(0)
            self._set_status(f"Failed (code {rc}) – details in the log.", "err")
            self._log("No valid MP4 file was created. Tips: camcorder in VCR mode? "
                      "Cable/driver OK? Extra input options may be needed.")
        self._sync_preview()  # resume the live preview

    def _on_close(self):
        if self.running and not self.preview_only:
            if not messagebox.askyesno("Quit", "A recording/conversion is still running. Really quit?"):
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
