"""
AVIX Drink System — application Windows v4
AVIX 3D © 2026 — avix3d.com

Pilote la drink box (Arduino Nano + pompe) depuis un bouton de volant, une touche clavier
ou le bouton du capot.

Principes :
- Instance unique : relancer l'appli ramène la fenêtre existante au premier plan.
- Tous les accès Tk se font dans le thread principal. Les threads (port série, icône de la
  barre des tâches, clavier, mise à jour) passent par une file d'événements.
- La box est détectée et reconnectée automatiquement (handshake avec le firmware).
"""

import json
import os
import queue
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from datetime import date, datetime

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# indispensable : sans ça, SDL ignore le volant quand le jeu a le focus
os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

import tkinter as tk
import customtkinter as ctk
import serial
import serial.tools.list_ports

try:
    import pygame
except Exception:            # pragma: no cover
    pygame = None
try:
    import keyboard          # hook clavier global (Windows)
except Exception:            # pragma: no cover
    keyboard = None
try:
    import winreg
except Exception:
    winreg = None

APP_NAME = "AVIX Drink System"
APP_VERSION = "4.0.0"
GITHUB_REPO = "AviX3D/AVIX-Drink-System"
BAUD = 115200
IPC_PORT = 47391                       # canal local "ramène la fenêtre" entre instances

# ── PALETTE AVIX ──────────────────────────────────────────────────────────────
YEL, YEL_DK, YEL_DIM = "#C1C107", "#8C8C05", "#24240A"
BG, BG2, BG3, BG4 = "#0D0D0D", "#151515", "#1C1C1C", "#242424"
BORDER = "#2E2E2E"
TEXT, TEXT2, MUTED, MUTED2 = "#FFFFFF", "#CFCFCF", "#8A8A8A", "#5A5A5A"
GREEN, GREEN_DIM = "#22C55E", "#12301E"
RED, RED_DIM = "#EF4444", "#3A1212"
ORANGE, BLUE = "#F97316", "#3B82F6"

# ── POLICES (style du logo : condensée, grasse, italique) ─────────────────────
# Barlow / Barlow Condensed — SIL Open Font License (fonts/OFL.txt), embarquées avec l'appli.
FONT_FILES = ("BarlowCondensed-ExtraBoldItalic.ttf", "BarlowCondensed-BoldItalic.ttf",
              "Barlow-Medium.ttf", "Barlow-SemiBold.ttf")
_FAM = {"display": ("Segoe UI", "bold"), "head": ("Segoe UI", "bold"),
        "body": ("Segoe UI", ""), "bodyb": ("Segoe UI", "bold")}


def D(size):
    """Titres et gros chiffres : comme le logo (extra-grasse, italique, condensée)."""
    fam, st = _FAM["display"]
    return (fam, size, *st.split())


def H(size):
    """Intertitres, boutons, menu."""
    fam, st = _FAM["head"]
    return (fam, size, *st.split())


def T(size):
    """Texte courant."""
    fam, st = _FAM["body"]
    return (fam, size, *st.split())


def TB(size):
    fam, st = _FAM["bodyb"]
    return (fam, size, *st.split())


F_TITLE = F_H1 = F_H2 = F_BODY = F_SMALL = None
F_MONO = ("Consolas", 11)


def register_fonts():
    """Charge les polices embarquées pour ce processus (sans les installer dans Windows)."""
    folder = resource_path("fonts")
    if sys.platform != "win32":
        return
    try:
        import ctypes
        for name in FONT_FILES:
            p = os.path.join(folder, name)
            if os.path.exists(p):
                ctypes.windll.gdi32.AddFontResourceExW(p, 0x10, 0)      # FR_PRIVATE
    except Exception as e:
        file_log(f"polices: {e}")


def setup_fonts(root):
    """Choisit les polices réellement disponibles (repli sur Segoe UI si besoin)."""
    global F_TITLE, F_H1, F_H2, F_BODY, F_SMALL
    from tkinter import font as tkfont
    fams = set(tkfont.families(root))
    if "Barlow Condensed ExtraBold" in fams:
        _FAM["display"] = ("Barlow Condensed ExtraBold", "italic")
    elif "Barlow Condensed" in fams:
        _FAM["display"] = ("Barlow Condensed", "bold italic")
    if "Barlow Condensed" in fams:
        _FAM["head"] = ("Barlow Condensed", "bold italic")
    if "Barlow Medium" in fams:
        _FAM["body"] = ("Barlow Medium", "")
    elif "Barlow" in fams:
        _FAM["body"] = ("Barlow", "")
    if "Barlow SemiBold" in fams:
        _FAM["bodyb"] = ("Barlow SemiBold", "")
    elif "Barlow" in fams:
        _FAM["bodyb"] = ("Barlow", "bold")
    F_TITLE, F_H1, F_H2, F_BODY, F_SMALL = D(32), H(21), H(18), T(13), T(12)

# ── LIMITES ───────────────────────────────────────────────────────────────────
DOSE_MIN_MS, DOSE_MAX_MS = 500, 15000
HOLD_MAX_MS = 20000                    # maintien : coupure auto (le firmware V2 coupe aussi à 20 s)
PURGE_MS, PURGE_COOLDOWN_MS = 3000, 10000
PRIME_MAX_MS = 20000
CALIB_MS = 10000

# Puces USB-série des Nano et clones
KNOWN_USB = {(0x1A86, 0x7523), (0x1A86, 0x5523), (0x1A86, 0x55D4), (0x0403, 0x6001),
             (0x10C4, 0xEA60), (0x2341, 0x0043), (0x2341, 0x0001), (0x2A03, 0x0043), (0x2341, 0x0058)}


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════
def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AVIX3D")
SETTINGS_FILE = os.path.join(DATA_DIR, "drink_settings.json")
LOG_FILE = os.path.join(DATA_DIR, "drink.log")


def file_log(msg):
    """Journal disque (diagnostic), jamais bloquant."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 512_000:
            os.replace(LOG_FILE, LOG_FILE + ".1")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")
    except Exception:
        pass


def version_tuple(v):
    out = []
    for p in v.strip().lstrip("vV").split("."):
        d = "".join(c for c in p if c.isdigit())
        out.append(int(d) if d else 0)
    return tuple(out)


DEFAULTS = {
    "binding": None,                  # {"type": "gamepad", "guid", "name", "button"} | {"type": "keyboard", "key"}
    "pump_mode": "one_push",          # one_push | hold
    "dose_ms": 4000,
    "speed": 255,                     # firmware V2 uniquement
    "ml_per_s": 0.0,                  # calibration (0 = non calibré)
    "last_port": None,
    "forced_port": None,              # avancé : port imposé (firmware ancien)
    "tuto_done": False,
    "reminder_min": 0,                # rappel hydratation (0 = désactivé)
    "today": "",
    "today_s": 0.0,                   # secondes de pompage aujourd'hui
    "today_sips": 0,
    "close_hint_shown": False,
}


class Settings:
    def __init__(self, path=SETTINGS_FILE):
        self.path = path
        self.data = dict(DEFAULTS)
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                self._migrate(raw)
                for k, v in raw.items():
                    if k in DEFAULTS and (DEFAULTS[k] is None or v is None or isinstance(v, type(DEFAULTS[k]))
                                          or (isinstance(DEFAULTS[k], float) and isinstance(v, int))):
                        self.data[k] = v
        except Exception:
            pass
        if not self._valid_binding(self.data["binding"]):
            self.data["binding"] = None
        self.data["dose_ms"] = int(min(max(self.data["dose_ms"], DOSE_MIN_MS), DOSE_MAX_MS))
        self.data["speed"] = int(min(max(self.data["speed"], 60), 255))
        if self.data["pump_mode"] not in ("one_push", "hold"):
            self.data["pump_mode"] = "one_push"

    @staticmethod
    def _valid_binding(b):
        if b is None:
            return True
        if not isinstance(b, dict):
            return False
        if b.get("type") == "keyboard":
            return isinstance(b.get("key"), str) and b["key"] != ""
        if b.get("type") == "gamepad":
            return isinstance(b.get("button"), int) and b["button"] >= 0
        return False

    @staticmethod
    def _migrate(raw):
        """Reprend les réglages de la v3 (assigned_btn / assigned_key / push_to_drink)."""
        if "binding" not in raw:
            if raw.get("input_mode") == "keyboard" and raw.get("assigned_key"):
                raw["binding"] = {"type": "keyboard", "key": str(raw["assigned_key"]).lower()}
            elif raw.get("assigned_btn") is not None:
                raw["binding"] = {"type": "gamepad", "guid": None, "name": "Gamepad", "button": int(raw["assigned_btn"])}
        if raw.get("pump_mode") == "push_to_drink":
            raw["pump_mode"] = "hold"

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)          # écriture atomique : jamais de fichier corrompu
        except Exception as e:
            file_log(f"save settings: {e}")


def set_autostart(on):
    if winreg is None:
        return False
    kp = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, kp, 0, winreg.KEY_SET_VALUE)
        if on:
            if getattr(sys, "frozen", False):
                cmd = f'"{sys.executable}" --minimized'
            else:
                cmd = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}" --minimized'
            winreg.SetValueEx(k, "AVIXDrinkSystem", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, "AVIXDrinkSystem")
            except OSError:
                pass
        winreg.CloseKey(k)
        return True
    except OSError:
        return False


def get_autostart():
    if winreg is None:
        return False
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        winreg.QueryValueEx(k, "AVIXDrinkSystem")
        winreg.CloseKey(k)
        return True
    except OSError:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  INSTANCE UNIQUE
# ══════════════════════════════════════════════════════════════════════════════
class SingleInstance:
    """Verrou système (mutex Windows / flock ailleurs) + canal local pour réveiller la 1re instance."""

    def __init__(self, name="AVIX_Drink_System_SingleInstance"):
        self.name = name
        self._handle = None
        self._lockfile = None
        self.server = None

    def acquire(self):
        if sys.platform == "win32":
            import ctypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateMutexW.restype = ctypes.c_void_p
            self._handle = k32.CreateMutexW(None, False, "Local\\" + self.name)
            err = ctypes.get_last_error()
            # 183 : déjà ouvert · 5 : mutex d'une instance lancée en administrateur
            return bool(self._handle) and err not in (183, 5)
        import fcntl
        os.makedirs(DATA_DIR, exist_ok=True)
        self._lockfile = open(os.path.join(DATA_DIR, self.name + ".lock"), "w")
        try:
            fcntl.flock(self._lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    @staticmethod
    def wake_existing():
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(-1)   # laisse la 1re instance passer devant
            except Exception:
                pass
        try:
            with socket.create_connection(("127.0.0.1", IPC_PORT), timeout=1.0) as s:
                s.sendall(b"SHOW")
            return True
        except OSError:
            return False

    def serve(self, on_show):
        """Thread qui attend les "SHOW" des instances suivantes."""
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            excl = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
            if excl is not None:
                srv.setsockopt(socket.SOL_SOCKET, excl, 1)
            srv.bind(("127.0.0.1", IPC_PORT))
            srv.listen(2)
            self.server = srv
        except OSError as e:
            file_log(f"IPC indisponible: {e}")
            return

        def loop():
            while True:
                try:
                    c, _ = srv.accept()
                except OSError:
                    return
                try:
                    c.settimeout(1.0)
                    if c.recv(16).startswith(b"SHOW"):
                        on_show()
                except OSError:
                    pass
                finally:
                    c.close()
        threading.Thread(target=loop, name="ipc", daemon=True).start()

    def close(self):
        try:
            if self.server:
                self.server.close()
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  LIAISON SÉRIE : détection auto + reconnexion (thread dédié)
# ══════════════════════════════════════════════════════════════════════════════
class BoxLink(threading.Thread):
    """Seul ce thread touche au port série. Il envoie ses événements dans `events` :
       ("link", state, info)  state ∈ searching | connected | lost
       ("rx", line)           ligne reçue du firmware"""

    HANDSHAKE_BANNER_S = 3.2      # la Nano redémarre à l'ouverture du port (~2 s de bootloader)
    PING_TIMEOUT_S = 1.2
    HEARTBEAT_S = 2.0
    SILENCE_LOST_S = 6.5

    def __init__(self, events, preferred=None, forced=None, port_lister=None, opener=None):
        super().__init__(name="box-link", daemon=True)
        self.events = events
        self.preferred = preferred
        self.forced = forced
        self._lister = port_lister or (lambda: list(serial.tools.list_ports.comports()))
        self._opener = opener or (lambda dev: serial.Serial(dev, BAUD, timeout=0.05, write_timeout=1.0))
        self._cmd = queue.Queue()
        self._stop_ev = threading.Event()
        self._retarget = threading.Event()
        self.ser = None
        self.port = None
        self.fw = None            # "v2" (PING/PONG) | "v1" (ancien firmware)
        self.connected = False
        self._failed = {}         # port -> instant du dernier échec (évite de le resonder en boucle)
        self._buf = b""
        self._last_list = 0.0
        self._seen = set()

    # ---- API thread principal ----
    def send(self, cmd):
        if not self.connected:
            return False
        self._cmd.put(cmd)
        return True

    def set_forced(self, port):
        self.forced = port or None
        self._retarget.set()

    def stop(self):
        self._stop_ev.set()

    # ---- thread ----
    def _emit(self, *ev):
        self.events.put(ev)

    def run(self):
        self._emit("link", "searching", None)
        while not self._stop_ev.is_set():
            try:
                if self.ser is None:
                    if not self._search():
                        self._stop_ev.wait(1.5)
                else:
                    self._service()
            except Exception as e:                      # ne jamais laisser mourir le thread
                file_log("link: " + traceback.format_exc())
                self._drop(f"erreur : {e}")
        self._close(send_off=True)

    def _candidates(self):
        ports = []
        try:
            ports = self._lister()
        except Exception:
            pass
        now = time.time()

        def score(p):
            vidpid = (getattr(p, "vid", None), getattr(p, "pid", None))
            s = 0
            if p.device == self.preferred:
                s -= 100
            if vidpid in KNOWN_USB:
                s -= 50
            return s
        keep = []
        for p in ports:
            hwid = (getattr(p, "hwid", "") or "").upper()
            if "BTHENUM" in hwid or "BLUETOOTH" in (getattr(p, "description", "") or "").upper():
                continue
            new = p.device not in self._seen
            known = (getattr(p, "vid", None), getattr(p, "pid", None)) in KNOWN_USB
            # ports silencieux : on ne les rouvre pas en boucle (ça redémarre les Arduino de SimHub, etc.)
            backoff = 5 if p.device == self.preferred else (30 if known else 90)
            if not new and now - self._failed.get(p.device, -1e9) < backoff:
                continue
            keep.append(p)
        self._seen = {p.device for p in ports}
        keep.sort(key=score)
        return keep

    def _search(self):
        if self.forced:
            return self._try_port(self.forced, known=True, forced=True)
        for p in self._candidates():
            if self._stop_ev.is_set() or self._retarget.is_set():
                break
            known = (getattr(p, "vid", None), getattr(p, "pid", None)) in KNOWN_USB
            if self._try_port(p.device, known=known):
                return True
        self._retarget.clear()
        return False

    def _readline(self, ser):
        """Lit une ligne complète (tampon : jamais de ligne coupée en deux par le timeout)."""
        if b"\n" not in self._buf:
            chunk = ser.read(max(1, getattr(ser, "in_waiting", 0) or 0))
            if chunk:
                self._buf += chunk
        if b"\n" in self._buf:
            raw, _, self._buf = self._buf.partition(b"\n")
            return raw.decode("utf-8", "ignore").strip()
        if len(self._buf) > 512:
            self._buf = b""
        return ""

    def _try_port(self, dev, known=False, forced=False):
        try:
            ser = self._opener(dev)
        except Exception:
            self._failed[dev] = time.time()            # occupé (SimHub…) ou absent
            return False
        fw = None
        self._buf = b""
        try:
            t0 = time.time()
            banner = False
            while time.time() - t0 < self.HANDSHAKE_BANNER_S and not self._stop_ev.is_set():
                line = self._readline(ser)
                if "AVIX" in line.upper():
                    banner = True
                    break
            if banner or forced or dev == self.preferred:
                # on n'écrit que sur un port qui s'est présenté comme une box AVIX (ou déjà connu)
                ser.reset_input_buffer()
                ser.write(b"PING\n")
                t1 = time.time()
                while time.time() - t1 < self.PING_TIMEOUT_S:
                    if self._readline(ser).upper() == "PONG":
                        fw = "v2"
                        break
                if fw is None and banner:
                    fw = "v1"
            if fw is None and forced:
                fw = "v1"
        except Exception:
            fw = None
        if fw is None:
            try:
                ser.close()
            except Exception:
                pass
            self._failed[dev] = time.time()
            return False
        self.ser, self.port, self.fw, self.connected = ser, dev, fw, True
        self._last_rx = time.time()
        self._last_ping = 0.0
        while not self._cmd.empty():                    # pas de vieille commande au branchement
            self._cmd.get_nowait()
        try:
            ser.write(b"0")                             # pompe arrêtée par sécurité
        except Exception:
            pass
        self._emit("link", "connected", {"port": dev, "fw": fw})
        return True

    def _service(self):
        if self._retarget.is_set():
            self._retarget.clear()
            self._drop("changement de port")
            return
        ser = self.ser
        line = self._readline(ser)                      # timeout 50 ms
        now = time.time()
        if line:
            self._last_rx = now
            if line.upper() != "PONG":
                self._emit("rx", line)
        while not self._cmd.empty():
            ser.write(self._cmd.get_nowait().encode("ascii"))
        if self.fw == "v2":
            if now - self._last_ping > self.HEARTBEAT_S:
                ser.write(b"PING\n")
                self._last_ping = now
            if now - self._last_rx > self.SILENCE_LOST_S:
                self._drop("la box ne répond plus")
        elif now - self._last_list > 2.0:
            self._last_list = now                      # firmware V1 : on vérifie que le port existe encore
            try:
                if self.port not in [p.device for p in self._lister()]:
                    self._drop("débranchée")
            except Exception:
                pass

    def _close(self, send_off=False):
        if self.ser is not None:
            try:
                if send_off:
                    self.ser.write(b"0")
                    self.ser.flush()
            except Exception:
                pass
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.connected = False

    def _drop(self, why):
        was = self.connected
        port = self.port
        self._close(send_off=True)
        if was:
            self._emit("link", "lost", {"port": port, "why": why})
            self._emit("link", "searching", None)


# ══════════════════════════════════════════════════════════════════════════════
#  WIDGETS
# ══════════════════════════════════════════════════════════════════════════════
class Card(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", BG2)
        super().__init__(master, border_width=1, border_color=BORDER, corner_radius=10, **kw)


def label(master, text, font=None, color=TEXT, **kw):
    return ctk.CTkLabel(master, text=text, font=font or F_BODY, text_color=color, justify="left", **kw)


def primary_btn(master, text, cmd, **kw):
    kw.setdefault("height", 40)
    return ctk.CTkButton(master, text=text, command=cmd, fg_color=YEL, hover_color=YEL_DK, text_color="#000000",
                         font=H(16), corner_radius=8, **kw)


def ghost_btn(master, text, cmd, **kw):
    kw.setdefault("height", 36)
    return ctk.CTkButton(master, text=text, command=cmd, fg_color=BG3, hover_color=BG4, border_width=1,
                         border_color=BORDER, text_color=TEXT2, font=H(15), corner_radius=8, **kw)


class StatusPill(ctk.CTkLabel):
    COLORS = {"ok": (GREEN, GREEN_DIM), "warn": (ORANGE, "#3A2410"), "err": (RED, RED_DIM),
              "off": (MUTED, BG4), "info": (BLUE, "#0F1F3D")}

    def __init__(self, master, text="", kind="off"):
        super().__init__(master, text=text, font=TB(12), corner_radius=6, padx=10, pady=3)
        self.set(text, kind)

    def set(self, text, kind):
        fg, bg = self.COLORS.get(kind, self.COLORS["off"])
        self.configure(text=f"● {text}", text_color=fg, fg_color=bg)


# ══════════════════════════════════════════════════════════════════════════════
#  APPLICATION
# ══════════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    PAGES = [("home", "Accueil"), ("button", "Bouton"), ("pump", "Pompe"), ("hydra", "Hydratation"),
             ("tuto", "Tuto"), ("settings", "Réglages"), ("log", "Journal")]

    def __init__(self, instance=None, start_minimized=False, link_factory=None):
        register_fonts()
        super().__init__()
        setup_fonts(self)
        self.instance = instance
        self.s = Settings()
        self.events = queue.Queue()
        self._closing = False
        self._timers = {}

        # état
        self.link_state = "searching"
        self.link_info = {}
        self.pump = "off"              # off | on | rev
        self.pump_src = ""             # app | capot | prime | calib | test
        self.pump_t0 = 0.0
        self.purge_ready = True
        self.listening = False
        self.session_s = 0.0
        self.session_sips = 0
        self.last_sip = None
        self.input_down = False
        self.joysticks = {}            # instance_id -> pygame Joystick
        self.js_names = {}
        self._log_lines = []
        self._roll_day()

        self.title(APP_NAME)
        self.geometry("1080x720")
        self.minsize(940, 640)
        self.configure(fg_color=BG)
        try:
            self.iconbitmap(default=resource_path("avix.ico"))
        except Exception:
            pass
        self.report_callback_exception = self._tk_error

        self._build()
        self._init_inputs()
        self.link = (link_factory or (lambda ev: BoxLink(ev, self.s["last_port"], self.s["forced_port"])))(self.events)
        self.link.start()
        self.tray = None
        self._setup_tray()
        if instance:
            instance.serve(lambda: self.events.put(("show",)))
        threading.Thread(target=self._check_update, name="update", daemon=True).start()

        self.protocol("WM_DELETE_WINDOW", self._on_close_button)
        self.bind("<FocusOut>", lambda e: self.prime(False) if e.widget is self else None)
        self.bind("<Unmap>", lambda e: self.prime(False) if e.widget is self else None)
        self.after(25, self._pump_events)
        self.after(16, self._poll_gamepads)
        self.after(1000, self._tick)
        self.log(f"{APP_NAME} {APP_VERSION} démarré", "ok")
        if start_minimized and self.tray:
            self.withdraw()
        elif not self.s["tuto_done"]:
            self.after(300, lambda: self.show_page("tuto"))

    # ------------------------------------------------------------------ outils
    def _tk_error(self, exc, val, tb):
        file_log("Tk: " + "".join(traceback.format_exception(exc, val, tb)))
        self.log(f"Erreur interne : {val} (détails dans le journal)", "err")

    def later(self, key, ms, fn):
        """after() nommé et annulable : un seul timer par clé."""
        self.cancel(key)
        self._timers[key] = self.after(ms, lambda: (self._timers.pop(key, None), fn()))

    def cancel(self, key):
        t = self._timers.pop(key, None)
        if t:
            try:
                self.after_cancel(t)
            except Exception:
                pass

    def log(self, msg, kind="muted"):
        t = datetime.now().strftime("%H:%M:%S")
        self._log_lines.append(f"{t}  {msg}")
        del self._log_lines[:-2000]
        file_log(msg)
        if hasattr(self, "logbox"):
            tb = self.logbox
            tb.configure(state="normal")
            tb.insert("end", f"{t}  ", "time")
            tb.insert("end", msg + "\n", kind)
            if int(tb.index("end-1c").split(".")[0]) > 2000:
                tb.delete("1.0", "200.0")
            tb.configure(state="disabled")
            tb.see("end")

    def toast(self, msg, kind="info", ms=4000):
        fg, bg = StatusPill.COLORS.get(kind, StatusPill.COLORS["info"])
        self.toast_lbl.configure(text=msg, text_color=fg, fg_color=bg)
        self.toast_lbl.place(relx=0.5, rely=1.0, y=-18, anchor="s")
        self.toast_lbl.lift()
        self.later("toast", ms, self.toast_lbl.place_forget)

    # ------------------------------------------------------------------ UI
    def _build(self):
        self.sidebar = ctk.CTkFrame(self, width=210, fg_color=BG2, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        logo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo.pack(fill="x", pady=(16, 12))
        self.logo_img = self._load_logo(180)
        if self.logo_img is not None:
            ctk.CTkLabel(logo, text="", image=self.logo_img).pack(padx=14, anchor="w")
        else:
            label(logo, "AVIX", D(28)).pack(padx=20, anchor="w")
        label(logo, "DRINK SYSTEM", H(15), YEL).pack(padx=22, anchor="w", pady=(6, 0))
        ctk.CTkFrame(self.sidebar, height=1, fg_color=BORDER).pack(fill="x")

        nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=12)
        self.nav = {}
        for key, name in self.PAGES:
            b = ctk.CTkButton(nav, text=name, anchor="w", height=38, corner_radius=8, font=H(17),
                              fg_color="transparent", hover_color=BG3, text_color=TEXT2,
                              command=lambda k=key: self.show_page(k))
            b.pack(fill="x", pady=2)
            self.nav[key] = b
        self.update_btn = None

        # bas de la barre : état de la box + STOP toujours visible
        bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=12, pady=12)
        self.side_status = StatusPill(bottom, "Recherche de la box…", "warn")
        self.side_status.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(bottom, text="STOP", height=44, fg_color=RED, hover_color="#B91C1C", text_color="#FFFFFF",
                      font=D(22), corner_radius=8, command=self.emergency_stop).pack(fill="x")

        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)
        self.pages = {}
        for key, _ in self.PAGES:
            f = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0)
            self.pages[key] = f
            getattr(self, f"_page_{key}")(f)
        self.toast_lbl = ctk.CTkLabel(self, text="", font=TB(13), corner_radius=8, padx=14, pady=8)
        self.show_page("home")
        self._refresh_all()

    @staticmethod
    def _load_logo(width):
        try:
            from PIL import Image
            img = Image.open(resource_path("logo.png"))
            h = round(width * img.height / img.width)
            return ctk.CTkImage(light_image=img, dark_image=img, size=(width, h))
        except Exception as e:
            file_log(f"logo: {e}")
            return None

    def show_page(self, key):
        for k, f in self.pages.items():
            f.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        for k, b in self.nav.items():
            on = k == key
            b.configure(fg_color=YEL_DIM if on else "transparent", text_color=YEL if on else TEXT2)
        self.cur_page = key
        if key == "tuto":
            self._tuto_render()

    def _page_frame(self, parent, title, subtitle=None):
        sc = ctk.CTkScrollableFrame(parent, fg_color=BG, scrollbar_button_color=BG3)
        sc.pack(fill="both", expand=True)
        p = ctk.CTkFrame(sc, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=30, pady=22)
        label(p, title, F_TITLE).pack(anchor="w")
        if subtitle:
            label(p, subtitle, F_BODY, MUTED).pack(anchor="w", pady=(2, 16))
        return p

    # ---------------- Accueil
    def _page_home(self, parent):
        p = self._page_frame(parent, "Tableau de bord", "Tout ce qu'il faut voir en un coup d'œil.")
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", pady=(0, 16))
        row.columnconfigure((0, 1, 2), weight=1, uniform="c")
        self.card_box = self._stat(row, 0, "Box", "Recherche…")
        self.card_btn = self._stat(row, 1, "Déclencheur", "Aucun")
        self.card_mode = self._stat(row, 2, "Mode", "—")

        main = Card(p)
        main.pack(fill="x", pady=(0, 16))
        inner = ctk.CTkFrame(main, fg_color="transparent")
        inner.pack(fill="x", padx=22, pady=20)
        self.ring = ctk.CTkFrame(inner, width=150, height=150, corner_radius=75, fg_color=BG3,
                                 border_width=4, border_color=BORDER)
        self.ring.pack(side="left")
        self.ring.pack_propagate(False)
        self.ring_lbl = label(self.ring, "ARRÊT", D(26))
        self.ring_lbl.place(relx=0.5, rely=0.44, anchor="center")
        self.ring_sub = label(self.ring, "prêt", F_SMALL, MUTED)
        self.ring_sub.place(relx=0.5, rely=0.62, anchor="center")
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=(24, 0))
        self.home_hint = label(right, "", F_BODY, TEXT2, wraplength=520)
        self.home_hint.pack(anchor="w", pady=(4, 10))
        self.dose_bar = ctk.CTkProgressBar(right, height=10, progress_color=YEL, fg_color=BG4)
        self.dose_bar.set(0)
        self.dose_bar.pack(fill="x", pady=(0, 14))
        btns = ctk.CTkFrame(right, fg_color="transparent")
        btns.pack(anchor="w")
        primary_btn(btns, "Boire une dose", self.test_dose, width=160).pack(side="left", padx=(0, 8))
        self.purge_btn_home = ghost_btn(btns, "Purger le tuyau", self.purge, width=150)
        self.purge_btn_home.pack(side="left")

        stats = Card(p)
        stats.pack(fill="x")
        st = ctk.CTkFrame(stats, fg_color="transparent")
        st.pack(fill="x", padx=22, pady=16)
        st.columnconfigure((0, 1, 2), weight=1, uniform="s")
        self.st_session = self._mini(st, 0, "Cette session")
        self.st_today = self._mini(st, 1, "Aujourd'hui")
        self.st_last = self._mini(st, 2, "Dernière gorgée")

    def _stat(self, row, col, title, value):
        c = Card(row)
        c.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0 if col == 2 else 6))
        label(c, title.upper(), H(13), MUTED).pack(anchor="w", padx=16, pady=(14, 2))
        v = label(c, value, D(24))
        v.pack(anchor="w", padx=16)
        sub = label(c, "", F_SMALL, MUTED)
        sub.pack(anchor="w", padx=16, pady=(0, 14))
        return v, sub

    def _mini(self, parent, col, title):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, sticky="w")
        label(f, title, F_SMALL, MUTED).pack(anchor="w")
        v = label(f, "—", D(22))
        v.pack(anchor="w")
        return v

    # ---------------- Bouton
    def _page_button(self, parent):
        p = self._page_frame(parent, "Bouton de déclenchement",
                             "Choisis le bouton du volant (ou une touche) qui envoie la boisson.")
        c = Card(p)
        c.pack(fill="x", pady=(0, 14))
        i = ctk.CTkFrame(c, fg_color="transparent")
        i.pack(fill="x", padx=22, pady=20)
        label(i, "Bouton actuel", F_SMALL, MUTED).pack(anchor="w")
        self.bind_lbl = label(i, "Aucun", D(28))
        self.bind_lbl.pack(anchor="w", pady=(0, 12))
        self.listen_btn = primary_btn(i, "Choisir un bouton", self.start_listening, width=260)
        self.listen_btn.pack(anchor="w")
        self.listen_hint = label(i, "Clique, puis appuie sur le bouton du volant ou sur une touche du clavier.\n"
                                    "Ça marche même si la fenêtre du jeu est au premier plan.", F_SMALL, MUTED)
        self.listen_hint.pack(anchor="w", pady=(8, 8))
        ghost_btn(i, "Effacer", self.clear_binding, width=120).pack(anchor="w")

        d = Card(p)
        d.pack(fill="x")
        di = ctk.CTkFrame(d, fg_color="transparent")
        di.pack(fill="x", padx=22, pady=16)
        label(di, "Périphériques détectés", F_H2).pack(anchor="w", pady=(0, 6))
        self.dev_lbl = label(di, "—", F_SMALL, TEXT2)
        self.dev_lbl.pack(anchor="w")
        label(di, "Le bouton du capot de la box marche toujours, sans réglage.", F_SMALL, MUTED).pack(anchor="w", pady=(8, 0))

    # ---------------- Pompe
    def _page_pump(self, parent):
        p = self._page_frame(parent, "Pompe", "Comment la boisson est envoyée.")
        c = Card(p)
        c.pack(fill="x", pady=(0, 14))
        i = ctk.CTkFrame(c, fg_color="transparent")
        i.pack(fill="x", padx=22, pady=18)
        label(i, "Mode", F_H2).pack(anchor="w")
        self.mode_seg = ctk.CTkSegmentedButton(i, values=["Une dose par appui", "Tant que j'appuie"],
                                               command=self._on_mode, selected_color=YEL_DK, selected_hover_color=YEL,
                                               unselected_color=BG3, text_color=TEXT, font=H(15), height=36)
        self.mode_seg.pack(anchor="w", pady=(6, 6))
        self.mode_desc = label(i, "", F_SMALL, MUTED, wraplength=640)
        self.mode_desc.pack(anchor="w")

        self.dose_card = Card(p)
        self.dose_card.pack(fill="x", pady=(0, 14))
        di = ctk.CTkFrame(self.dose_card, fg_color="transparent")
        di.pack(fill="x", padx=22, pady=18)
        top = ctk.CTkFrame(di, fg_color="transparent")
        top.pack(fill="x")
        label(top, "Dose", F_H2).pack(side="left")
        self.dose_val = label(top, "", D(26), YEL)
        self.dose_val.pack(side="right")
        self.dose_slider = ctk.CTkSlider(di, from_=DOSE_MIN_MS, to=DOSE_MAX_MS, number_of_steps=29,
                                         command=self._on_dose, progress_color=YEL, button_color=YEL,
                                         button_hover_color=YEL_DK)
        self.dose_slider.pack(fill="x", pady=(10, 4))
        presets = ctk.CTkFrame(di, fg_color="transparent")
        presets.pack(anchor="w", pady=(6, 0))
        for ms in (2000, 4000, 6000, 8000):
            ghost_btn(presets, f"{ms // 1000} s", lambda m=ms: self._set_dose(m), width=64, height=30).pack(side="left", padx=(0, 6))

        self.speed_card = Card(p)
        self.speed_card.pack(fill="x", pady=(0, 14))
        si = ctk.CTkFrame(self.speed_card, fg_color="transparent")
        si.pack(fill="x", padx=22, pady=18)
        top = ctk.CTkFrame(si, fg_color="transparent")
        top.pack(fill="x")
        label(top, "Débit", F_H2).pack(side="left")
        self.speed_val = label(top, "", D(20), YEL)
        self.speed_val.pack(side="right")
        self.speed_slider = ctk.CTkSlider(si, from_=60, to=255, number_of_steps=39, command=self._on_speed,
                                          progress_color=YEL, button_color=YEL, button_hover_color=YEL_DK)
        self.speed_slider.pack(fill="x", pady=(10, 4))
        self.speed_note = label(si, "", F_SMALL, MUTED)
        self.speed_note.pack(anchor="w")

        m = Card(p)
        m.pack(fill="x")
        mi = ctk.CTkFrame(m, fg_color="transparent")
        mi.pack(fill="x", padx=22, pady=18)
        label(mi, "Entretien", F_H2).pack(anchor="w", pady=(0, 8))
        r = ctk.CTkFrame(mi, fg_color="transparent")
        r.pack(anchor="w")
        self.prime_btn = ghost_btn(r, "Amorcer (maintenir)", None, width=180)
        self.prime_btn.pack(side="left", padx=(0, 8))
        self.prime_btn.bind("<ButtonPress-1>", lambda e: self.prime(True))
        self.prime_btn.bind("<ButtonRelease-1>", lambda e: self.prime(False))
        self.prime_btn.bind("<Leave>", lambda e: self.prime(False))
        self.purge_btn = ghost_btn(r, "Purger le tuyau (3 s)", self.purge, width=180)
        self.purge_btn.pack(side="left")
        label(mi, "Amorcer : garde le bouton appuyé jusqu'à ce que la boisson arrive à la tétine.\n"
                  "Purger : la pompe tourne à l'envers pour renvoyer la boisson dans la canette.", F_SMALL, MUTED
              ).pack(anchor="w", pady=(10, 0))

    # ---------------- Hydratation
    def _page_hydra(self, parent):
        p = self._page_frame(parent, "Hydratation", "Calibre la pompe pour voir les quantités en ml, et règle un rappel.")
        c = Card(p)
        c.pack(fill="x", pady=(0, 14))
        i = ctk.CTkFrame(c, fg_color="transparent")
        i.pack(fill="x", padx=22, pady=18)
        label(i, "Calibration du débit", F_H2).pack(anchor="w")
        self.calib_lbl = label(i, "", F_SMALL, MUTED, wraplength=640)
        self.calib_lbl.pack(anchor="w", pady=(4, 10))
        r = ctk.CTkFrame(i, fg_color="transparent")
        r.pack(anchor="w")
        self.calib_btn = primary_btn(r, "1. Lancer 10 s de pompage", self.calib_start, width=230)
        self.calib_btn.pack(side="left", padx=(0, 10))
        self.calib_entry = ctk.CTkEntry(r, placeholder_text="ml mesurés", width=120, height=40, font=F_BODY)
        self.calib_entry.pack(side="left", padx=(0, 8))
        ghost_btn(r, "2. Enregistrer", self.calib_save, width=130, height=40).pack(side="left")

        rc = Card(p)
        rc.pack(fill="x")
        ri = ctk.CTkFrame(rc, fg_color="transparent")
        ri.pack(fill="x", padx=22, pady=18)
        label(ri, "Rappel de boire", F_H2).pack(anchor="w")
        label(ri, "Une notification (et un bip) si tu n'as pas bu depuis…", F_SMALL, MUTED).pack(anchor="w", pady=(2, 8))
        self.rem_seg = ctk.CTkSegmentedButton(ri, values=["Désactivé", "10 min", "15 min", "20 min", "30 min"],
                                              command=self._on_reminder, selected_color=YEL_DK, selected_hover_color=YEL,
                                              unselected_color=BG3, text_color=TEXT, font=H(15), height=34)
        self.rem_seg.pack(anchor="w")
        ghost_btn(ri, "Remettre le compteur du jour à zéro", self.reset_today, width=280).pack(anchor="w", pady=(14, 0))

    # ---------------- Tuto
    TUTO_STEPS = [
        ("Bienvenue !",
         "Ce petit guide prend 2 minutes. À la fin, ta drink box sera prête pour la course.\n\n"
         "• La box envoie ta boisson jusqu'à la tétine quand tu appuies sur un bouton.\n"
         "• Tu peux utiliser un bouton de ton volant, une touche du clavier ou le bouton du capot.\n"
         "• Le gros bouton rouge STOP, en bas à gauche, coupe tout à tout moment."),
        ("1. Branche la box",
         "Branche le câble USB-C de la box sur ton PC. L'appli la trouve toute seule.\n\n"
         "Rien ne se passe ?\n"
         "• Essaie un autre câble : certains ne font que la charge.\n"
         "• Ferme l'Arduino IDE ou tout logiciel qui utilise déjà la box.\n"
         "• Le pilote CH340 est peut-être manquant (bouton ci-dessous)."),
        ("2. Choisis ton bouton",
         "Clique sur « Choisir un bouton », puis appuie sur le bouton du volant que tu veux utiliser.\n"
         "Tu peux aussi appuyer sur une touche du clavier."),
        ("3. Choisis le mode",
         "« Une dose par appui » : un appui envoie une gorgée de la durée choisie. C'est le plus simple en course.\n"
         "« Tant que j'appuie » : la boisson coule tant que tu gardes le bouton appuyé (20 s maximum)."),
        ("4. Amorce le tuyau",
         "Mets ta canette, place la tétine au-dessus d'un verre, puis garde « Amorcer » appuyé "
         "jusqu'à ce que la boisson arrive au bout du tuyau.\n\n"
         "Après la session, « Purger » renvoie la boisson dans la canette avant de ranger. "
         "Pense à rincer les tuyaux à l'eau."),
        ("C'est prêt !",
         "• Fermer la fenêtre ne quitte pas l'appli : elle reste près de l'horloge, à côté de l'icône AVIX. "
         "Clic droit sur l'icône pour quitter.\n"
         "• Active « Lancer au démarrage de Windows » dans Réglages pour ne plus y penser.\n"
         "• Pas de boissons gazeuses : elles font mousser la pompe.\n\n"
         "Bonne course !"),
    ]

    def _page_tuto(self, parent):
        self.tuto_i = 0
        wrap = ctk.CTkFrame(parent, fg_color=BG)
        wrap.pack(fill="both", expand=True, padx=30, pady=22)
        label(wrap, "Tuto de démarrage", F_TITLE).pack(anchor="w")
        self.tuto_dots = ctk.CTkFrame(wrap, fg_color="transparent")
        self.tuto_dots.pack(anchor="w", pady=(10, 14))
        self.tuto_card = Card(wrap)
        self.tuto_card.pack(fill="both", expand=True)
        ci = ctk.CTkFrame(self.tuto_card, fg_color="transparent")
        ci.pack(fill="both", expand=True, padx=28, pady=24)
        self.tuto_title = label(ci, "", F_H1, YEL)
        self.tuto_title.pack(anchor="w", pady=(0, 10))
        self.tuto_text = label(ci, "", T(14), TEXT2, wraplength=700)
        self.tuto_text.pack(anchor="w")
        self.tuto_live = ctk.CTkFrame(ci, fg_color="transparent")
        self.tuto_live.pack(anchor="w", fill="x", pady=(18, 0))
        nav = ctk.CTkFrame(wrap, fg_color="transparent")
        nav.pack(fill="x", pady=(14, 0))
        self.tuto_prev = ghost_btn(nav, "← Précédent", lambda: self._tuto_go(-1), width=140)
        self.tuto_prev.pack(side="left")
        self.tuto_next = primary_btn(nav, "Suivant →", lambda: self._tuto_go(1), width=160)
        self.tuto_next.pack(side="right")
        self.tuto_skip = ghost_btn(nav, "Passer le tuto", self._tuto_finish, width=140)
        self.tuto_skip.pack(side="right", padx=8)

    def _tuto_go(self, d):
        self.tuto_i = max(0, min(len(self.TUTO_STEPS) - 1, self.tuto_i + d))
        self._tuto_render()

    def _tuto_finish(self):
        self.s["tuto_done"] = True
        self.tuto_i = 0
        self.show_page("home")
        self.toast("Tuto terminé. Tu peux le relancer depuis le menu « Tuto ».", "ok")

    def _tuto_render(self):
        i = self.tuto_i
        n = len(self.TUTO_STEPS)
        for w in self.tuto_dots.winfo_children():
            w.destroy()
        for k in range(n):
            ctk.CTkFrame(self.tuto_dots, width=36 if k == i else 12, height=8, corner_radius=4,
                         fg_color=YEL if k <= i else BG4).pack(side="left", padx=3)
        title, text = self.TUTO_STEPS[i]
        self.tuto_title.configure(text=title)
        self.tuto_text.configure(text=text)
        for w in self.tuto_live.winfo_children():
            w.destroy()
        lv = self.tuto_live
        if i == 0:
            big = getattr(self, "logo_big", None) or self._load_logo(320)
            self.logo_big = big
            if big is not None:
                ctk.CTkLabel(lv, text="", image=big).pack(anchor="w", pady=(4, 0))
        elif i == 1:
            self.tuto_box_pill = StatusPill(lv, "", "warn")
            self.tuto_box_pill.pack(anchor="w", pady=(0, 10))
            ghost_btn(lv, "Télécharger le pilote CH340", lambda: webbrowser.open("https://www.wch-ic.com/downloads/CH341SER_EXE.html"),
                      width=240).pack(anchor="w")
        elif i == 2:
            self.tuto_bind_lbl = label(lv, "", H(20))
            self.tuto_bind_lbl.pack(anchor="w", pady=(0, 10))
            primary_btn(lv, "Choisir un bouton", self.start_listening, width=220).pack(anchor="w")
        elif i == 3:
            seg = ctk.CTkSegmentedButton(lv, values=["Une dose par appui", "Tant que j'appuie"], command=self._on_mode,
                                         selected_color=YEL_DK, selected_hover_color=YEL, unselected_color=BG3,
                                         text_color=TEXT, font=H(15), height=36)
            seg.set("Une dose par appui" if self.s["pump_mode"] == "one_push" else "Tant que j'appuie")
            seg.pack(anchor="w")
        elif i == 4:
            b = primary_btn(lv, "Amorcer (maintenir)", None, width=220)
            b.pack(anchor="w")
            b.bind("<ButtonPress-1>", lambda e: self.prime(True))
            b.bind("<ButtonRelease-1>", lambda e: self.prime(False))
            b.bind("<Leave>", lambda e: self.prime(False))
        self.tuto_prev.configure(state="normal" if i > 0 else "disabled")
        last = i == n - 1
        self.tuto_next.configure(text="Terminer" if last else "Suivant →",
                                 command=self._tuto_finish if last else (lambda: self._tuto_go(1)))
        self._refresh_all()

    # ---------------- Réglages
    def _page_settings(self, parent):
        p = self._page_frame(parent, "Réglages")
        c = Card(p)
        c.pack(fill="x", pady=(0, 14))
        i = ctk.CTkFrame(c, fg_color="transparent")
        i.pack(fill="x", padx=22, pady=18)
        self.autostart_var = tk.BooleanVar(value=get_autostart())
        if self.autostart_var.get():
            set_autostart(True)                    # met à jour le chemin si l'exe a été déplacé
        ctk.CTkSwitch(i, text="Lancer au démarrage de Windows (réduite près de l'horloge)", variable=self.autostart_var,
                      command=self._on_autostart, progress_color=YEL, font=F_BODY).pack(anchor="w", pady=4)
        if winreg is None:
            label(i, "(disponible sous Windows uniquement)", F_SMALL, MUTED).pack(anchor="w")

        a = Card(p)
        a.pack(fill="x", pady=(0, 14))
        ai = ctk.CTkFrame(a, fg_color="transparent")
        ai.pack(fill="x", padx=22, pady=18)
        label(ai, "Connexion de la box", F_H2).pack(anchor="w")
        label(ai, "Par défaut, la box est détectée automatiquement. Choisis un port seulement si ta box "
                  "a un ancien firmware qui ne répond pas.", F_SMALL, MUTED, wraplength=640).pack(anchor="w", pady=(2, 8))
        r = ctk.CTkFrame(ai, fg_color="transparent")
        r.pack(anchor="w")
        self.port_menu = ctk.CTkOptionMenu(r, values=["Automatique"], command=self._on_port_choice, fg_color=BG3,
                                           button_color=BG4, button_hover_color=BORDER, width=260, font=F_BODY)
        self.port_menu.pack(side="left", padx=(0, 8))
        ghost_btn(r, "Actualiser", self._refresh_port_menu, width=110).pack(side="left")
        self._refresh_port_menu()

        d = Card(p)
        d.pack(fill="x")
        di = ctk.CTkFrame(d, fg_color="transparent")
        di.pack(fill="x", padx=22, pady=18)
        label(di, "Aide et version", F_H2).pack(anchor="w")
        label(di, f"Version {APP_VERSION}", F_SMALL, MUTED).pack(anchor="w", pady=(2, 8))
        r = ctk.CTkFrame(di, fg_color="transparent")
        r.pack(anchor="w")
        ghost_btn(r, "Copier le diagnostic", self.copy_diag, width=170).pack(side="left", padx=(0, 8))
        ghost_btn(r, "Ouvrir le dossier des journaux", lambda: self._open_path(DATA_DIR), width=230).pack(side="left", padx=(0, 8))
        ghost_btn(r, "avix3d.com", lambda: webbrowser.open("https://avix3d.com"), width=120).pack(side="left")

    # ---------------- Journal
    def _page_log(self, parent):
        wrap = ctk.CTkFrame(parent, fg_color=BG)
        wrap.pack(fill="both", expand=True, padx=30, pady=22)
        top = ctk.CTkFrame(wrap, fg_color="transparent")
        top.pack(fill="x", pady=(0, 12))
        label(top, "Journal", F_TITLE).pack(side="left")
        ghost_btn(top, "Effacer", self._clear_log, width=90).pack(side="right")
        ghost_btn(top, "Copier", self._copy_log, width=90).pack(side="right", padx=8)
        self.logbox = ctk.CTkTextbox(wrap, fg_color=BG2, border_width=1, border_color=BORDER, font=F_MONO,
                                     text_color=TEXT2, corner_radius=10)
        self.logbox.pack(fill="both", expand=True)
        for tag, col in (("time", MUTED2), ("ok", GREEN), ("err", RED), ("warn", ORANGE), ("info", BLUE),
                         ("act", YEL), ("muted", TEXT2)):
            self.logbox.tag_config(tag, foreground=col)
        self.logbox.configure(state="disabled")

    # ------------------------------------------------------------------ rafraîchissement
    def _refresh_all(self):
        s = self.s
        # box
        if self.link_state == "connected":
            fw = self.link_info.get("fw")
            port = self.link_info.get("port", "")
            self.side_status.set(f"Box connectée ({port})", "ok")
            self.card_box[0].configure(text="Connectée", text_color=GREEN)
            self.card_box[1].configure(text=f"{port} · firmware {'V2' if fw == 'v2' else 'ancien'}")
            pill = ("Box connectée sur " + port, "ok")
        else:
            self.side_status.set("Recherche de la box…", "warn")
            self.card_box[0].configure(text="Non connectée", text_color=ORANGE)
            self.card_box[1].configure(text="branche-la en USB : détection auto")
            pill = ("Recherche de la box… (branche le câble USB)", "warn")
        if getattr(self, "tuto_box_pill", None) is not None:
            try:
                self.tuto_box_pill.set(*pill)
            except tk.TclError:
                self.tuto_box_pill = None
        # bouton
        b = s["binding"]
        txt = self._binding_text(b)
        if b:
            short = f"Touche {b['key'].upper()}" if b["type"] == "keyboard" else f"Bouton {b['button'] + 1}"
            dev = "clavier" if b["type"] == "keyboard" else (b.get("name") or "volant")
            self.card_btn[0].configure(text=short, text_color=TEXT)
            self.card_btn[1].configure(text=dev if len(dev) <= 26 else dev[:25] + "…")
        else:
            self.card_btn[0].configure(text="Aucun", text_color=MUTED)
            self.card_btn[1].configure(text="seul le bouton du capot marche")
        self.bind_lbl.configure(text=txt if b else "Aucun", text_color=TEXT if b else MUTED)
        if getattr(self, "tuto_bind_lbl", None) is not None:
            try:
                self.tuto_bind_lbl.configure(text=("Choisi : " + txt) if b else "Aucun bouton choisi")
            except tk.TclError:
                self.tuto_bind_lbl = None
        # mode / dose
        one = s["pump_mode"] == "one_push"
        self.mode_seg.set("Une dose par appui" if one else "Tant que j'appuie")
        self.mode_desc.configure(text=("Un appui = une dose de la durée réglée ci-dessous. Un nouvel appui pendant la dose l'arrête."
                                       if one else "La boisson coule tant que le bouton est appuyé. Coupure automatique après 20 s."))
        self.dose_slider.set(s["dose_ms"])
        self.dose_slider.configure(state="normal" if one else "disabled")
        self.dose_val.configure(text=self._dose_text(s["dose_ms"]) if one else "—")
        self.card_mode[0].configure(text="Une dose" if one else "Maintien")
        self.card_mode[1].configure(text=self._dose_text(s["dose_ms"]) if one else "20 s max")
        # débit
        v2 = self.link_state == "connected" and self.link_info.get("fw") == "v2"
        self.speed_slider.set(s["speed"])
        self.speed_val.configure(text=f"{round(s['speed'] / 2.55)} %")
        self.speed_slider.configure(state="normal" if v2 else "disabled")
        self.speed_note.configure(text="Réduis si la boisson arrive trop vite." if v2 else
                                  "Nécessite le firmware V2 sur la box (sinon la pompe tourne à fond).")
        # hydratation
        mps = s["ml_per_s"]
        self.calib_lbl.configure(text=(f"Débit calibré : {mps:.1f} ml/s. Les doses s'affichent en ml." if mps > 0 else
                                       "Pas encore calibré. Mets la tétine dans un verre doseur, lance 10 s de pompage, "
                                       "puis entre la quantité obtenue."))
        rm = s["reminder_min"]
        self.rem_seg.set("Désactivé" if rm == 0 else f"{rm} min")
        self._refresh_stats()
        self.home_hint.configure(text=self._home_hint())

    def _home_hint(self):
        if self.link_state != "connected":
            return "Branche la box en USB : elle sera détectée automatiquement."
        if not self.s["binding"]:
            return "La box est prête. Choisis un bouton dans l'onglet « Bouton » (le bouton du capot marche déjà)."
        return f"Prêt. Appuie sur {self._binding_text(self.s['binding'])} pour boire."

    def _refresh_stats(self):
        self.st_session.configure(text=self._qty(self.session_s, self.session_sips))
        self.st_today.configure(text=self._qty(self.s["today_s"], self.s["today_sips"]))
        if self.last_sip is None:
            self.st_last.configure(text="—")
        else:
            m = int((time.time() - self.last_sip) // 60)
            self.st_last.configure(text="à l'instant" if m < 1 else f"il y a {m} min")

    def _qty(self, secs, sips):
        mps = self.s["ml_per_s"]
        q = f"{secs * mps:.0f} ml" if mps > 0 else f"{secs:.0f} s de pompe"
        return f"{q} · {sips} gorgée{'s' if sips > 1 else ''}"

    def _dose_text(self, ms):
        mps = self.s["ml_per_s"]
        return f"{ms / 1000:.1f} s" + (f" ≈ {ms / 1000 * mps:.0f} ml" if mps > 0 else "")

    @staticmethod
    def _binding_text(b):
        if not b:
            return "Aucun"
        if b["type"] == "keyboard":
            return f"Touche {b['key'].upper()}"
        name = b.get("name") or "Volant"
        return f"Bouton {b['button'] + 1} · {name[:28]}"

    def _set_ring(self, mode):
        if mode == "on":
            self.ring.configure(border_color=GREEN, fg_color=GREEN_DIM)
            self.ring_lbl.configure(text="ÇA COULE", text_color=GREEN)
        elif mode == "rev":
            self.ring.configure(border_color=BLUE, fg_color="#0F1F3D")
            self.ring_lbl.configure(text="PURGE", text_color=BLUE)
        else:
            self.ring.configure(border_color=BORDER, fg_color=BG3)
            self.ring_lbl.configure(text="ARRÊT", text_color=TEXT)
            self.ring_sub.configure(text="prêt" if self.link_state == "connected" else "box absente")
            self.dose_bar.set(0)

    # ------------------------------------------------------------------ événements des threads
    def _pump_events(self):
        if self._closing:
            return
        try:
            for _ in range(200):
                ev = self.events.get_nowait()
                try:
                    self._handle(ev)
                except Exception:
                    file_log("event: " + traceback.format_exc())
        except queue.Empty:
            pass
        self.after(25, self._pump_events)

    def _handle(self, ev):
        kind = ev[0]
        if kind == "link":
            _, state, info = ev
            self.link_state = "connected" if state == "connected" else "searching"
            if state == "connected":
                self.link_info = info
                self.s["last_port"] = info["port"]
                self.log(f"Box connectée sur {info['port']} (firmware {'V2' if info['fw'] == 'v2' else 'ancien'})", "ok")
                self.toast("Box connectée ✓", "ok")
                if info["fw"] == "v2":
                    self.link.send(f"SPD:{self.s['speed']}\n")
            elif state == "lost":
                self.log(f"Box déconnectée ({info.get('why')})", "warn")
                self.toast("Box déconnectée : reconnexion automatique…", "warn")
                self._pump_reset_ui()
            self._refresh_all()
        elif kind == "rx":
            self._on_rx(ev[1])
        elif kind == "key":
            self._on_input(("keyboard", ev[1], ev[3] if len(ev) > 3 else None), ev[2])
        elif kind == "show":
            self.show_window()
        elif kind == "tray":
            {"open": self.show_window, "stop": self.emergency_stop, "purge": self.purge, "quit": self.quit_app}[ev[1]]()
        elif kind == "update":
            self._show_update(ev[1], ev[2])

    def _on_rx(self, line):
        u = line.upper()
        if u.startswith("PUMP:"):
            # le firmware V2 annonce ses changements d'état (utile pour le bouton du capot)
            st = u[5:].split(" ")[0]
            src = line[line.find("(") + 1:line.find(")")] if "(" in line else ""
            # les échos de nos propres commandes (appli/serie) sont ignorés : l'appli est déjà à jour
            if st == "ON" and self.pump == "off" and "bouton" in src:
                self._pump_started("capot")
            elif st == "OFF" and self.pump != "off" and (self.pump_src == "capot" or "securite" in src):
                self._pump_stopped()
            if "securite" in src:
                self.log("La box a coupé la pompe (sécurité 20 s)", "warn")
            return
        if u.startswith("BTN:"):
            self.log("Bouton du capot " + ("appuyé" if u.endswith("1") else "relâché"), "info")
            return
        if u.startswith("WARN") or u.startswith("ERR"):
            self.log("Box : " + line, "warn")
            return
        if "AVIX" in u:
            if self.link_state == "connected":       # la Nano a redémarré toute seule (chute de tension…)
                self.log("La box a redémarré", "warn")
                self._pump_reset_ui()
                if self.link_info.get("fw") == "v2":
                    self.link.send(f"SPD:{self.s['speed']}\n")
            return
        self.log("Box → " + line, "muted")

    # ------------------------------------------------------------------ pompe
    def _require_box(self):
        if self.link_state != "connected":
            self.toast("Branche la box d'abord.", "warn")
            return False
        return True

    def _pump_started(self, src):
        self.pump = "on"
        self.pump_src = src
        self.pump_t0 = time.time()
        self._set_ring("on")
        self.ring_sub.configure(text={"capot": "bouton du capot", "prime": "amorçage", "calib": "calibration"}.get(src, "dose"))
        self.later("safety", HOLD_MAX_MS + 500, lambda: self._pump_off("sécurité 20 s"))

    def _pump_stopped(self):
        if self.pump == "on" and self.pump_src not in ("prime", "calib"):
            dt = min(time.time() - self.pump_t0, HOLD_MAX_MS / 1000)
            self._count(dt)
        if "calib_end" in self._timers:          # calibration interrompue : on ne demande pas de ml faux
            self.cancel("calib_end")
            self.calib_btn.configure(state="normal", text="1. Lancer 10 s de pompage")
            self.toast("Calibration interrompue, relance-la.", "warn")
        if self.pump == "rev":                   # purge interrompue : son timer de fin ne doit plus couper une dose
            self.cancel("purge_end")
            self._purge_cooldown()
        self.pump = "off"
        self.pump_src = ""
        self.cancel("dose")
        self.cancel("dose_anim")
        self.cancel("safety")
        self._set_ring("off")

    def _count(self, secs):
        if secs < 0.15:
            return
        self._roll_day()
        self.session_s += secs
        self.session_sips += 1
        self.s.data["today_s"] = self.s["today_s"] + secs
        self.s.data["today_sips"] = self.s["today_sips"] + 1
        self.s.save()
        self.last_sip = time.time()
        self._refresh_stats()

    def _pump_on(self, src="app"):
        if not self._require_box():
            return False
        if self.pump == "rev":
            return False
        if self.pump == "on":
            return self.pump_src == src     # déjà en marche pour une autre raison : on ne la "reprend" pas
        if self.link.send("1"):
            self._pump_started(src)
            self.log("Pompe : marche" + {"app": "", "prime": " (amorçage)", "calib": " (calibration)"}.get(src, ""), "act")
            return True
        return False

    def _pump_off(self, why=None):
        if self.pump == "off":
            return
        self.link.send("0")
        self._pump_stopped()
        self.log("Pompe : arrêt" + (f" ({why})" if why else ""), "info")

    def _pump_reset_ui(self):
        if self.pump != "off":
            self._pump_stopped()

    def emergency_stop(self):
        self.link.send("0")
        self._pump_stopped()
        self.log("STOP", "warn")
        self.toast("Pompe arrêtée", "err", 2500)

    def test_dose(self):
        if self.pump != "off":
            self._pump_off("appui")
            return
        self._dose(self.s["dose_ms"])

    def _dose(self, ms):
        if not self._pump_on("app"):
            return
        self.later("dose", ms, lambda: self._pump_off())
        t0 = time.time()

        def anim():
            if self.pump != "on":
                return
            self.dose_bar.set(min((time.time() - t0) * 1000 / ms, 1.0))
            self.later("dose_anim", 50, anim)
        anim()

    def prime(self, down):
        if down:
            if self.pump != "off":
                return
            if self._pump_on("prime"):
                self.later("dose", PRIME_MAX_MS, lambda: self._pump_off("amorçage 20 s max"))
        elif self.pump_src == "prime":
            self._pump_off()

    def purge(self):
        if not self._require_box():
            return
        if not self.purge_ready:
            self.toast("Purge disponible dans quelques secondes.", "info")
            return
        if self.pump == "on":
            self._pump_off()
        if not self.link.send("2"):
            return
        self.pump = "rev"
        self.pump_src = "purge"
        self.purge_ready = False
        self._set_ring("rev")
        self.ring_sub.configure(text="retour canette")
        for b in (self.purge_btn, self.purge_btn_home):
            b.configure(state="disabled", text="Purge…")
        self.log("Purge : 3 s à l'envers", "info")

        def end():
            self.link.send("0")
            self.pump = "off"
            self.pump_src = ""
            self._set_ring("off")
            self._purge_cooldown()
        self.later("purge_end", PURGE_MS, end)

    def _purge_cooldown(self):
        for b in (self.purge_btn, self.purge_btn_home):
            b.configure(state="disabled", text="Purge (attente 10 s)")
        self.later("purge_cd", PURGE_COOLDOWN_MS, self._purge_ready)

    def _purge_ready(self):
        self.purge_ready = True
        self.purge_btn.configure(state="normal", text="Purger le tuyau (3 s)")
        self.purge_btn_home.configure(state="normal", text="Purger le tuyau")

    # ------------------------------------------------------------------ entrées
    def _init_inputs(self):
        self.pg_ok = False
        if pygame is not None:
            try:
                pygame.display.init()
                pygame.joystick.init()
                self.pg_ok = True
            except Exception as e:
                self.log(f"Manettes indisponibles : {e}", "err")
        self._kb_hooked = False
        self._kb_update_hook()
        self._update_dev_list()

    def _kb_update_hook(self):
        """Le hook clavier global n'est posé que s'il sert (touche assignée ou capture en cours)."""
        if keyboard is None:
            return
        need = self.listening or (self.s["binding"] or {}).get("type") == "keyboard"
        try:
            if need and not self._kb_hooked:
                keyboard.hook(self._kb_hook)        # thread du hook -> file d'événements
                self._kb_hooked = True
            elif not need and self._kb_hooked:
                keyboard.unhook_all()
                self._kb_hooked = False
        except Exception as e:
            self.log(f"Clavier global indisponible : {e}", "warn")

    def _kb_hook(self, e):
        # appelé dans le thread du module keyboard : AUCUN accès Tk ici
        try:
            if e.name or e.scan_code:
                self.events.put(("key", (e.name or "").lower(), e.event_type == "down", e.scan_code))
        except Exception:
            pass

    def _poll_gamepads(self):
        if self._closing:
            return
        if self.pg_ok:
            try:
                for ev in pygame.event.get():
                    if ev.type == pygame.JOYDEVICEADDED:
                        try:
                            js = pygame.joystick.Joystick(ev.device_index)
                            self.joysticks[js.get_instance_id()] = js
                            self.js_names[js.get_instance_id()] = js.get_name()
                            self.log(f"Périphérique branché : {js.get_name()}", "info")
                        except Exception:
                            pass
                        self._update_dev_list()
                    elif ev.type == pygame.JOYDEVICEREMOVED:
                        js = self.joysticks.pop(ev.instance_id, None)
                        name = self.js_names.pop(ev.instance_id, "périphérique")
                        if js is not None:
                            self.log(f"Périphérique débranché : {name}", "warn")
                            # par sécurité, n'importe quel débranchement coupe un maintien en cours
                            if self.input_down and (self.s["binding"] or {}).get("type") == "gamepad":
                                self.input_down = False
                                if self.pump == "on" and self.pump_src == "app" and self.s["pump_mode"] == "hold":
                                    self._pump_off("volant débranché")
                        self._update_dev_list()
                    elif ev.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                        js = self.joysticks.get(ev.instance_id)
                        if js is not None:
                            self._on_input(("gamepad", js, ev.button), ev.type == pygame.JOYBUTTONDOWN)
            except Exception:
                file_log("gamepad: " + traceback.format_exc())
        self.after(16, self._poll_gamepads)

    def _matches_device(self, js):
        b = self.s["binding"]
        if not b or b["type"] != "gamepad":
            return False
        guid = b.get("guid")
        try:
            return guid is None or js.get_guid() == guid
        except Exception:
            return False

    def _on_input(self, src, down):
        if self.listening:
            if not down:
                return
            if src[0] == "keyboard":
                if src[1] in ("esc", "escape"):
                    self._stop_listening("Annulé")
                    return
                self.s["binding"] = {"type": "keyboard", "key": src[1] or f"code {src[2]}", "scan": src[2]}
            else:
                js, btn = src[1], src[2]
                try:
                    guid = js.get_guid()
                except Exception:
                    guid = None
                self.s["binding"] = {"type": "gamepad", "guid": guid, "name": js.get_name(), "button": int(btn)}
            self._stop_listening(None)
            self.log(f"Déclencheur : {self._binding_text(self.s['binding'])}", "act")
            self.toast(f"{self._binding_text(self.s['binding'])} enregistré ✓", "ok")
            self.input_down = True        # ignore le relâchement de l'appui de capture
            return
        b = self.s["binding"]
        if not b:
            return
        if src[0] == "keyboard":
            if b["type"] != "keyboard":
                return
            # code physique de la touche : insensible à Maj/AltGr (sur AZERTY, « & » et « 1 » sont la même touche)
            if b.get("scan") is not None and src[2] is not None:
                if src[2] != b["scan"]:
                    return
            elif src[1] != b["key"]:
                return
            if down and isinstance(self.focus_get(), tk.Entry):
                return                     # on tape dans un champ de l'appli : pas de pompe
        else:
            if b["type"] != "gamepad" or src[2] != b["button"] or not self._matches_device(src[1]):
                return
        if down:
            if self.input_down:            # répétition automatique du clavier
                return
            self.input_down = True
            if self.pump_src in ("calib", "prime", "purge"):
                return
            if self.s["pump_mode"] == "one_push":
                if self.pump == "on" and self.pump_src == "app":
                    self._pump_off("appui")
                else:
                    self._dose(self.s["dose_ms"])
            else:
                self._pump_on("app")
        else:
            was = self.input_down
            self.input_down = False
            if was and self.s["pump_mode"] == "hold" and self.pump_src == "app":
                self._pump_off()

    def start_listening(self):
        if self.pump == "on" and self.pump_src == "app":
            self._pump_off()
        self.input_down = False
        self.listening = True
        self._kb_update_hook()
        self.listen_btn.configure(text="Appuie sur le bouton… (Échap pour annuler)", fg_color=YEL_DIM, text_color=YEL)
        self.toast("Appuie sur le bouton du volant ou une touche…", "info", 8000)
        self.later("listen_to", 15000, lambda: self._stop_listening("Aucun bouton reçu"))

    def _stop_listening(self, msg):
        self.listening = False
        self._kb_update_hook()
        self.cancel("listen_to")
        self.listen_btn.configure(text="Changer de bouton" if self.s["binding"] else "Choisir un bouton",
                                  fg_color=YEL, text_color="#000000")
        if msg:
            self.toast(msg, "warn")
        self._refresh_all()

    def clear_binding(self):
        if self.pump == "on" and self.pump_src == "app":
            self._pump_off()
        self.s["binding"] = None
        self.input_down = False
        self.log("Déclencheur effacé", "info")
        self._stop_listening(None)

    def _update_dev_list(self):
        names = []
        for js in self.joysticks.values():
            try:
                names.append(f"• {js.get_name()} ({js.get_numbuttons()} boutons)")
            except Exception:
                pass
        if keyboard is not None:
            names.append("• Clavier")
        if hasattr(self, "dev_lbl"):
            self.dev_lbl.configure(text="\n".join(names) if names else "Aucun volant détecté pour l'instant.")

    # ------------------------------------------------------------------ réglages
    def _on_mode(self, v):
        self.s["pump_mode"] = "one_push" if v.startswith("Une") else "hold"
        if self.pump == "on" and self.pump_src == "app":
            self._pump_off()
        self._refresh_all()

    def _on_dose(self, v):
        self.s.data["dose_ms"] = int(round(float(v) / 500) * 500)
        self.dose_val.configure(text=self._dose_text(self.s["dose_ms"]))
        self.later("save_dose", 400, lambda: (self.s.save(), self._refresh_all()))

    def _set_dose(self, ms):
        self.s["dose_ms"] = ms
        self._refresh_all()

    def _on_speed(self, v):
        self.s.data["speed"] = int(v)
        self.speed_val.configure(text=f"{round(int(v) / 2.55)} %")

        def apply():
            self.s.save()
            if self.link_info.get("fw") == "v2":
                self.link.send(f"SPD:{self.s['speed']}\n")
        self.later("save_speed", 300, apply)

    def _on_reminder(self, v):
        self.s["reminder_min"] = 0 if v == "Désactivé" else int(v.split()[0])
        self.last_remind = time.time()

    def _on_autostart(self):
        ok = set_autostart(self.autostart_var.get())
        if not ok:
            self.autostart_var.set(False)
            self.toast("Impossible de modifier le démarrage automatique.", "err")

    def _refresh_port_menu(self):
        try:
            ports = [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            ports = []
        self.port_menu.configure(values=["Automatique"] + ports)
        self.port_menu.set(self.s["forced_port"] or "Automatique")

    def _on_port_choice(self, v):
        port = None if v == "Automatique" else v
        self.s["forced_port"] = port
        self.link.set_forced(port)
        self.log("Connexion : " + (f"port imposé {port}" if port else "détection automatique"), "info")

    # ------------------------------------------------------------------ calibration / hydratation
    def calib_start(self):
        if self.pump != "off":
            return
        if self._pump_on("calib"):
            self.calib_btn.configure(state="disabled", text="Pompage… 10 s")
            self.later("calib_end", CALIB_MS, self._calib_end)

    def _calib_end(self):
        self._pump_off()
        self.calib_btn.configure(state="normal", text="1. Lancer 10 s de pompage")
        self.toast("Mesure la quantité dans le verre, puis entre-la en ml.", "info", 6000)
        self.calib_entry.focus_set()

    def calib_save(self):
        try:
            ml = float(self.calib_entry.get().replace(",", "."))
            if not 1 <= ml <= 1000:
                raise ValueError
        except ValueError:
            self.toast("Entre la quantité mesurée en ml (ex. 85).", "warn")
            return
        self.s["ml_per_s"] = round(ml / (CALIB_MS / 1000), 2)
        self.log(f"Calibration : {self.s['ml_per_s']} ml/s", "ok")
        self.toast(f"Débit enregistré : {self.s['ml_per_s']} ml/s ✓", "ok")
        self._refresh_all()

    def reset_today(self):
        self.s.data.update(today_s=0.0, today_sips=0)
        self.s.save()
        self._refresh_stats()

    def _roll_day(self):
        today = date.today().isoformat()
        if self.s["today"] != today:
            self.s.data.update(today=today, today_s=0.0, today_sips=0)
            self.s.save()

    def _tick(self):
        if self._closing:
            return
        self._refresh_stats()
        rm = self.s["reminder_min"]
        if rm:
            ref = max(self.last_sip or 0, getattr(self, "last_remind", 0) or 0, getattr(self, "_started", 0))
            if time.time() - ref > rm * 60:
                self.last_remind = time.time()
                self._notify("Pense à boire", f"Tu n'as pas bu depuis {rm} min.")
                self.bell()
                self.toast(f"Pense à boire : pas de gorgée depuis {rm} min", "info", 8000)
        self.after(1000, self._tick)

    # ------------------------------------------------------------------ fenêtre / tray
    def _setup_tray(self):
        self._started = time.time()
        try:
            import pystray
            from PIL import Image
            img = Image.open(resource_path("avix.ico"))
            put = self.events.put
            menu = pystray.Menu(
                pystray.MenuItem("Ouvrir", lambda *_: put(("tray", "open")), default=True),
                pystray.MenuItem("STOP pompe", lambda *_: put(("tray", "stop"))),
                pystray.MenuItem("Purger le tuyau", lambda *_: put(("tray", "purge"))),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quitter", lambda *_: put(("tray", "quit"))))
            self.tray = pystray.Icon("AVIX_Drink", img, APP_NAME, menu)
            self._tray_thread = threading.Thread(target=self.tray.run, name="tray", daemon=True)
            self._tray_thread.start()
        except Exception as e:
            self.tray = None
            file_log(f"tray indisponible: {e}")

    def _notify(self, title, msg):
        try:
            if self.tray is not None:
                self.tray.notify(msg, title)
        except Exception:
            pass

    def show_window(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.attributes("-topmost", True)
        self.after(150, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def _on_close_button(self):
        if self.tray is None:
            self.quit_app()
            return
        self.withdraw()
        if not self.s["close_hint_shown"]:
            self.s["close_hint_shown"] = True
            self._notify(APP_NAME, "L'appli continue près de l'horloge. Clic droit sur l'icône AVIX pour quitter.")

    def quit_app(self):
        if self._closing:
            return
        self._closing = True
        try:
            self.link.send("0")
            time.sleep(0.12)
            self.link.stop()
            self.link.join(timeout=2.0)
        except Exception:
            pass
        if keyboard is not None:
            try:
                keyboard.unhook_all()
            except Exception:
                pass
        if self.tray is not None:
            try:
                self.tray.stop()
                self._tray_thread.join(1.0)
            except Exception:
                pass
        if self.pg_ok:
            try:
                pygame.quit()
            except Exception:
                pass
        if self.instance:
            self.instance.close()
        self.s.save()
        file_log("fermeture")
        self.destroy()

    # ------------------------------------------------------------------ divers
    def _check_update(self):
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                                         headers={"Accept": "application/vnd.github+json", "User-Agent": "AVIX-Drink"})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.load(r)
            tag = data.get("tag_name", "")
            if tag and version_tuple(tag) > version_tuple(APP_VERSION):
                self.events.put(("update", tag, data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"))
        except Exception:
            pass

    def _show_update(self, tag, url):
        if self.update_btn is None:
            self.update_btn = ctk.CTkButton(self.sidebar, text=f"Mise à jour {tag} disponible", fg_color=ORANGE,
                                            hover_color="#C2570F", text_color="#000000", font=H(14),
                                            height=30, corner_radius=6, command=lambda: webbrowser.open(url))
            self.update_btn.pack(fill="x", padx=12, pady=(0, 6), after=list(self.sidebar.winfo_children())[1])
            self.log(f"Nouvelle version {tag} disponible", "info")

    def copy_diag(self):
        info = [f"{APP_NAME} {APP_VERSION}", f"Python {sys.version.split()[0]} · {sys.platform}",
                f"Box : {self.link_state} {self.link_info}", f"Déclencheur : {self.s['binding']}",
                f"Mode : {self.s['pump_mode']} · dose {self.s['dose_ms']} ms · débit {self.s['speed']}",
                f"Ports : {[p.device + ' ' + (p.description or '') for p in serial.tools.list_ports.comports()]}",
                f"Manettes : {[js.get_name() for js in self.joysticks.values()]}", "", "Journal :"] + self._log_lines[-60:]
        self.clipboard_clear()
        self.clipboard_append("\n".join(info))
        self.toast("Diagnostic copié : colle-le dans ton message au support.", "ok")

    def _copy_log(self):
        self.clipboard_clear()
        self.clipboard_append("\n".join(self._log_lines))
        self.toast("Journal copié", "ok")

    def _clear_log(self):
        self._log_lines.clear()
        self.logbox.configure(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.configure(state="disabled")

    @staticmethod
    def _open_path(p):
        try:
            os.makedirs(p, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(p)
            else:
                webbrowser.open("file://" + p)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
def main():
    inst = SingleInstance()
    if not inst.acquire():
        if "--minimized" in sys.argv:          # démarrage Windows en double : on ne fait rien
            return 0
        if not SingleInstance.wake_existing():
            # instance en cours de démarrage ou canal bloqué : on prévient sans lancer de doublon
            try:
                r = tk.Tk()
                r.withdraw()
                from tkinter import messagebox
                messagebox.showinfo(APP_NAME, "L'application est déjà ouverte.\nCherche l'icône AVIX près de l'horloge.")
                r.destroy()
            except Exception:
                pass
        return 0
    sys.excepthook = lambda *a: file_log("non géré: " + "".join(traceback.format_exception(*a)))
    ctk.set_appearance_mode("dark")
    app = App(instance=inst, start_minimized="--minimized" in sys.argv)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
