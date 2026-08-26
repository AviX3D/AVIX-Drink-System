"""
AVIX Drink System Controller v3.0
Application Windows — AVIX_3D c 2026
"""

import customtkinter as ctk
import tkinter as tk
import serial, serial.tools.list_ports
import pygame, threading, keyboard, time
import json, os, sys, winreg, pystray
import urllib.request, webbrowser
from PIL import Image
from datetime import datetime

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── VERSION / MISE A JOUR ──────────────────────────────────────────────────────
APP_VERSION = "3.0.0"
# ⚠️ Remplace par ton repo GitHub une fois créé (ex: "ton-pseudo/avix-drink-system")
GITHUB_REPO = "AviX3D/AVIX-Drink-System"

def _version_tuple(v):
    v = v.strip().lstrip("vV")
    parts = []
    for p in v.split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)

# ── PALETTE ───────────────────────────────────────────────────────────────────
RED      = "#E8000F"
RED_DRK  = "#A8000B"
RED_DIM  = "#2A0003"
BG       = "#0D0D0D"
BG2      = "#141414"
BG3      = "#1A1A1A"
BG4      = "#202020"
BORDER   = "#2E2E2E"
BRED     = "#4A0008"
TEXT     = "#FFFFFF"
TEXT2    = "#CCCCCC"
MUTED    = "#888888"
MUTED2   = "#555555"
GREEN    = "#22C55E"
GREEN_DK = "#15803D"
ORANGE   = "#F97316"
BLUE     = "#3B82F6"

FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_H1     = ("Segoe UI", 15, "bold")
FONT_H2     = ("Segoe UI", 13, "bold")
FONT_BODY   = ("Segoe UI", 12)
FONT_SMALL  = ("Segoe UI", 11)
FONT_MONO   = ("Courier New", 11)
FONT_MONO_S = ("Courier New", 10)

# ── UTILS ─────────────────────────────────────────────────────────────────────
def resource_path(p):
    try: base = sys._MEIPASS
    except: base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, p)

APPDATA   = os.environ.get("APPDATA", os.path.expanduser("~"))
SAVE_FILE = os.path.join(APPDATA, "AVIX3D", "drink_settings.json")

def load_settings():
    try:
        with open(SAVE_FILE) as f: return json.load(f)
    except: return {}

def save_settings(d):
    try:
        os.makedirs(os.path.dirname(SAVE_FILE), exist_ok=True)
        with open(SAVE_FILE, "w") as f: json.dump(d, f, indent=2)
    except: pass

def set_autostart(on):
    kp = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, kp, 0, winreg.KEY_SET_VALUE)
        if on:
            exe = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
            winreg.SetValueEx(k, "AVIXDrinkSystem", 0, winreg.REG_SZ, f'"{exe}" --minimized')
        else:
            try: winreg.DeleteValue(k, "AVIXDrinkSystem")
            except: pass
        winreg.CloseKey(k); return True
    except: return False

def get_autostart():
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        winreg.QueryValueEx(k, "AVIXDrinkSystem"); winreg.CloseKey(k); return True
    except: return False


# ── WIDGETS CUSTOM ────────────────────────────────────────────────────────────

class Sep(ctk.CTkFrame):
    def __init__(self, p, **kw):
        super().__init__(p, height=1, fg_color=BORDER, corner_radius=0, **kw)

class Card(ctk.CTkFrame):
    def __init__(self, p, **kw):
        super().__init__(p, fg_color=BG2, border_width=1, border_color=BORDER,
                         corner_radius=8, **kw)

_TAG_BG = {"#22C55E": "#1a3d2a", "#E8000F": "#2a0003",
           "#3B82F6": "#0f1f3d", "#555555": "#222222",
           "#888888": "#222222"}

class Tag(ctk.CTkLabel):
    """Petit badge colore."""
    def __init__(self, p, text, color=GREEN, **kw):
        bg = _TAG_BG.get(color, "#1a1a1a")
        super().__init__(p, text=text, font=("Segoe UI", 10, "bold"),
                         text_color=color, fg_color=bg,
                         corner_radius=4, padx=8, pady=2, **kw)

class NavBtn(ctk.CTkButton):
    def __init__(self, p, icon, label, cmd, **kw):
        super().__init__(p, text=f"  {icon}  {label}", anchor="w",
                         font=("Segoe UI", 13), text_color=MUTED,
                         fg_color="transparent", hover_color=BG3,
                         corner_radius=6, height=42, command=cmd, **kw)
    def set_active(self, active):
        if active:
            self.configure(text_color=TEXT, fg_color=BG3)
        else:
            self.configure(text_color=MUTED, fg_color="transparent")

class BigBtn(ctk.CTkButton):
    def __init__(self, p, **kw):
        super().__init__(p, fg_color=RED, hover_color=RED_DRK,
                         text_color=TEXT, font=("Segoe UI", 13, "bold"),
                         corner_radius=8, height=44, **kw)

class OutlineBtn(ctk.CTkButton):
    def __init__(self, p, **kw):
        super().__init__(p, fg_color="transparent", hover_color=BG3,
                         text_color=TEXT2, font=("Segoe UI", 12),
                         border_width=1, border_color=BORDER,
                         corner_radius=8, height=38, **kw)


# ── APP ───────────────────────────────────────────────────────────────────────

class AVIXDrinkApp(ctk.CTk):

    MODE_GP  = "gamepad"
    MODE_KB  = "keyboard"
    PAGES    = ["accueil", "config", "pompe", "journal"]

    def __init__(self, start_minimized=False):
        super().__init__()
        self.title("AVIX Drink System")
        self.geometry("1100x720")
        self.minsize(900, 620)
        self.configure(fg_color=BG)
        try: self.iconbitmap(default=resource_path("avix.ico"))
        except: pass
        self.tray_icon  = None
        self.cur_page   = "accueil"
        self.page_frames = {}

        s = load_settings()
        self.serial_port  = None
        self.connected    = False
        self.input_mode   = s.get("input_mode", self.MODE_GP)
        self.gp_index     = None
        self.assigned_btn = s.get("assigned_btn", None)
        self.last_btn_st  = {}
        self.btn_press_t  = {}
        self.DEBOUNCE     = 80
        self.assigned_key      = s.get("assigned_key", None)
        self.assigned_key_name = s.get("assigned_key_name", None)
        self.key_pressed  = False
        self.pump_on      = False
        self.dose_ms      = s.get("dose_ms", 5000)
        self.dose_timer   = None
        self.pump_mode    = s.get("pump_mode", "one_push")
        self.listening    = False
        self._purge_cd    = False
        self._log_entries = []

        pygame.init(); pygame.joystick.init()
        self._build_ui()
        self._restore()
        self._refresh_ports()
        self._input_loop()
        self._setup_tray()
        if start_minimized:
            self.after(200, self._hide_to_tray)
        threading.Thread(target=self._check_for_update, daemon=True).start()

    # ── MISE A JOUR ───────────────────────────────────────────────────────────

    def _check_for_update(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.load(r)
            latest_tag = data.get("tag_name", "")
            latest_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")
            if latest_tag and _version_tuple(latest_tag) > _version_tuple(APP_VERSION):
                self.after(0, self._show_update_banner, latest_tag, latest_url)
        except Exception:
            pass  # pas de connexion / repo pas encore public -> silencieux

    def _show_update_banner(self, latest_tag, latest_url):
        if getattr(self, "_update_banner", None):
            return
        b = ctk.CTkButton(self.nav_frame, text=f"⭱ Mise à jour {latest_tag}",
                           fg_color=ORANGE, hover_color="#C2570F", text_color="#000000",
                           font=("Segoe UI", 10, "bold"), height=26, corner_radius=4,
                           command=lambda: webbrowser.open(latest_url))
        b.pack(fill="x", pady=(0, 8))
        if self.nav_btns:
            b.pack_configure(before=next(iter(self.nav_btns.values())))
        self._update_banner = b

    # ── TRAY ──────────────────────────────────────────────────────────────────

    def _setup_tray(self):
        try:
            img = Image.open(resource_path("avix.ico"))
            menu = pystray.Menu(
                pystray.MenuItem("Ouvrir", self._show_from_tray, default=True),
                pystray.MenuItem("Quitter", lambda i, it: self.after(0, self.on_close)))
            self.tray_icon = pystray.Icon("AVIX", img, "AVIX Drink System", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except: self.tray_icon = None

    def _hide_to_tray(self): self.withdraw()
    def _show_from_tray(self, *_):
        self.after(0, self.deiconify); self.after(0, self.lift)

    # ── SAVE ──────────────────────────────────────────────────────────────────

    def _save(self):
        save_settings({"input_mode": self.input_mode, "assigned_btn": self.assigned_btn,
                        "assigned_key": self.assigned_key,
                        "assigned_key_name": self.assigned_key_name,
                        "dose_ms": self.dose_ms,
                        "pump_mode": self.pump_mode})

    # ── BUILD UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, fg_color=BG2,
                                     corner_radius=0, border_width=1,
                                     border_color=BORDER)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        # Contenu
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        # Pages
        for name in self.PAGES:
            f = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0)
            self.page_frames[name] = f
            getattr(self, f"_build_{name}")(f)

        self._show_page("accueil")

    def _build_sidebar(self):
        # Logo
        logo = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=70)
        logo.pack(fill="x")
        logo.pack_propagate(False)
        mark = ctk.CTkFrame(logo, width=4, height=46, fg_color=RED, corner_radius=0)
        mark.place(x=0, y=12)
        ctk.CTkLabel(logo, text="AVIX", font=("Segoe UI", 18, "bold"),
                     text_color=TEXT).place(x=20, y=14)
        ctk.CTkLabel(logo, text="DRINK SYSTEM", font=("Segoe UI", 8, "bold"),
                     text_color=RED).place(x=20, y=40)

        Sep(self.sidebar).pack(fill="x")

        # Navigation
        nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav.pack(fill="x", padx=8, pady=12)
        self.nav_frame = nav

        self.nav_btns = {}
        pages = [
            ("accueil", "⬤", "Accueil"),
            ("config",  "◈", "Configuration"),
            ("pompe",   "◉", "Pompe"),
            ("journal", "≡", "Journal"),
        ]
        for key, icon, label in pages:
            btn = NavBtn(nav, icon, label, lambda k=key: self._show_page(k))
            btn.pack(fill="x", pady=2)
            self.nav_btns[key] = btn

        # Status connexion en bas
        Sep(self.sidebar).pack(fill="x", side="bottom")
        self.sidebar_status = ctk.CTkFrame(self.sidebar, fg_color="transparent", height=56)
        self.sidebar_status.pack(side="bottom", fill="x", padx=12, pady=10)
        self.sidebar_status.pack_propagate(False)

        self.sb_dot = ctk.CTkLabel(self.sidebar_status, text="●",
                                    font=("Segoe UI", 10), text_color=MUTED2, width=16)
        self.sb_dot.place(x=0, y=18)
        self.sb_port_lbl = ctk.CTkLabel(self.sidebar_status, text="Non connecte",
                                         font=("Segoe UI", 11), text_color=MUTED)
        self.sb_port_lbl.place(x=20, y=16)
        self.sb_mode_lbl = ctk.CTkLabel(self.sidebar_status, text="Gamepad",
                                         font=("Segoe UI", 10), text_color=MUTED2)
        self.sb_mode_lbl.place(x=20, y=34)

    def _show_page(self, name):
        for k, f in self.page_frames.items():
            f.pack_forget()
        self.page_frames[name].pack(fill="both", expand=True)
        self.cur_page = name
        for k, b in self.nav_btns.items():
            b.set_active(k == name)

    # ── PAGE ACCUEIL ──────────────────────────────────────────────────────────

    def _build_accueil(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color=BG, scrollbar_button_color=BG3)
        scroll.pack(fill="both", expand=True)
        p = ctk.CTkFrame(scroll, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=32, pady=24)

        # Titre
        hdr = ctk.CTkFrame(p, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 24))
        ctk.CTkLabel(hdr, text="Tableau de bord", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left")
        self.acc_status_tag = Tag(hdr, "  Non connecte  ", MUTED2)
        self.acc_status_tag.pack(side="right", pady=6)

        # Cartes statut
        cards_row = ctk.CTkFrame(p, fg_color="transparent")
        cards_row.pack(fill="x", pady=(0, 20))
        cards_row.columnconfigure((0,1,2), weight=1)

        self._stat_arduino = self._stat_card(cards_row, "Arduino", "Non connecte", MUTED, 0)
        self._stat_bouton  = self._stat_card(cards_row, "Bouton assigne", "Aucun", MUTED, 1)
        self._stat_dose    = self._stat_card(cards_row, "Dose reglée", f"{self.dose_ms/1000:.1f}s", BLUE, 2)

        # Connexion rapide
        ctk.CTkLabel(p, text="Connexion rapide", font=FONT_H1,
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))
        conn_card = Card(p)
        conn_card.pack(fill="x", pady=(0, 20))

        row = ctk.CTkFrame(conn_card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=16)

        self.port_var = ctk.StringVar()
        self.port_combo = ctk.CTkComboBox(
            row, variable=self.port_var, width=260,
            fg_color=BG3, border_color=BORDER,
            button_color=BG4, button_hover_color=BG3,
            dropdown_fg_color=BG2, text_color=TEXT2,
            font=FONT_MONO, corner_radius=6,
            values=["-- Selectionne un port COM --"])
        self.port_combo.pack(side="left", padx=(0, 8))

        OutlineBtn(row, text="↺", width=38, command=self._refresh_ports).pack(side="left", padx=(0, 8))

        self.btn_connect = BigBtn(row, text="Connecter", width=130, command=self._connect)
        self.btn_connect.pack(side="left", padx=(0, 8))

        self.btn_disconnect = OutlineBtn(row, text="Deconnecter", width=130,
                                         state="disabled", command=self._disconnect)
        self.btn_disconnect.pack(side="left")

        # Pompe rapide
        ctk.CTkLabel(p, text="Controle rapide", font=FONT_H1,
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))
        pump_card = Card(p)
        pump_card.pack(fill="x")

        inner = ctk.CTkFrame(pump_card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)

        # Grand indicateur pompe
        self.acc_pump_ring = ctk.CTkFrame(inner, width=80, height=80,
                                           fg_color=BG3, corner_radius=40,
                                           border_width=3, border_color=BORDER)
        self.acc_pump_ring.pack(side="left", padx=(0, 20))
        self.acc_pump_ring.pack_propagate(False)
        self.acc_pump_ico = ctk.CTkLabel(self.acc_pump_ring, text="💧",
                                          font=("Segoe UI", 28))
        self.acc_pump_ico.place(relx=0.5, rely=0.5, anchor="center")

        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        self.acc_pump_lbl = ctk.CTkLabel(info, text="ARRET", font=("Segoe UI", 20, "bold"),
                                          text_color=TEXT)
        self.acc_pump_lbl.pack(anchor="w")
        self.acc_pump_sub = ctk.CTkLabel(info, text="En attente d'action",
                                          font=FONT_BODY, text_color=MUTED)
        self.acc_pump_sub.pack(anchor="w")
        self.acc_dose_bar = ctk.CTkProgressBar(info, height=4, corner_radius=2,
                                                fg_color=BG4, progress_color=RED)
        self.acc_dose_bar.set(0)
        self.acc_dose_bar.pack(fill="x", pady=(8, 0))

        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(side="right", padx=(20, 0))
        BigBtn(btns, text="Test pompe", width=130, command=self._test_pump).pack(pady=(0, 8))
        OutlineBtn(btns, text="Purge tube", width=130, command=self._purge_pump).pack()

    def _stat_card(self, parent, title, value, color, col):
        f = Card(parent)
        f.grid(row=0, column=col, padx=(0 if col==0 else 8, 0), sticky="nsew")
        ctk.CTkLabel(f, text=title, font=FONT_SMALL, text_color=MUTED).pack(anchor="w", padx=16, pady=(14,0))
        lbl = ctk.CTkLabel(f, text=value, font=FONT_H2, text_color=color)
        lbl.pack(anchor="w", padx=16, pady=(2, 14))
        return lbl

    # ── PAGE CONFIG ───────────────────────────────────────────────────────────

    def _build_config(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color=BG, scrollbar_button_color=BG3)
        scroll.pack(fill="both", expand=True)
        p = ctk.CTkFrame(scroll, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=32, pady=24)

        ctk.CTkLabel(p, text="Configuration", font=FONT_TITLE,
                     text_color=TEXT).pack(anchor="w", pady=(0, 24))

        # Type de peripherique
        ctk.CTkLabel(p, text="Type de peripherique", font=FONT_H1,
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))

        mode_card = Card(p)
        mode_card.pack(fill="x", pady=(0, 20))

        mrow = ctk.CTkFrame(mode_card, fg_color="transparent")
        mrow.pack(fill="x", padx=20, pady=16)

        self.mode_var = ctk.StringVar(value=self.input_mode)
        for val, icon, title, sub in [
            (self.MODE_GP,  "🎮", "Volant / Manette", "Gamepad, manette Xbox, PS, volant sim racing"),
            (self.MODE_KB,  "⌨", "Clavier",           "Fonctionne en arriere-plan"),
        ]:
            opt = ctk.CTkFrame(mrow, fg_color=BG3, border_width=1,
                               border_color=BORDER, corner_radius=8)
            opt.pack(side="left", fill="x", expand=True, padx=(0, 8))
            rb = ctk.CTkRadioButton(opt, text=f"{icon}  {title}", value=val,
                                     variable=self.mode_var, font=FONT_H2,
                                     text_color=TEXT, fg_color=RED,
                                     hover_color=RED_DRK, border_color=MUTED2,
                                     command=self._on_mode_change)
            rb.pack(anchor="w", padx=16, pady=(14, 2))
            ctk.CTkLabel(opt, text=sub, font=FONT_SMALL,
                         text_color=MUTED).pack(anchor="w", padx=16, pady=(0, 14))

        # Peripherique detecte
        ctk.CTkLabel(p, text="Peripherique detecte", font=FONT_H1,
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))
        self.dev_card = Card(p)
        self.dev_card.pack(fill="x", pady=(0, 20))
        self._render_dev_card()

        # Assignation
        ctk.CTkLabel(p, text="Assigner un bouton / touche", font=FONT_H1,
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))
        assign_card = Card(p)
        assign_card.pack(fill="x", pady=(0, 20))

        ac = ctk.CTkFrame(assign_card, fg_color="transparent")
        ac.pack(fill="x", padx=20, pady=16)

        self.listen_btn = ctk.CTkButton(
            ac, text="Clique ici puis appuie sur le bouton a assigner",
            font=FONT_H2, fg_color=BG3, hover_color=BG4,
            text_color=MUTED, border_width=1, border_color=BORDER,
            corner_radius=8, height=52, command=self._start_listening)
        self.listen_btn.pack(fill="x", pady=(0, 12))

        self.assigned_frame = ctk.CTkFrame(ac, fg_color=RED_DIM,
                                            border_width=1, border_color=BRED,
                                            corner_radius=8)

        left = ctk.CTkFrame(self.assigned_frame, fg_color="transparent")
        left.pack(side="left", padx=16, pady=14)
        self.assigned_num = ctk.CTkLabel(left, text="—",
                                          font=("Segoe UI", 40, "bold"),
                                          text_color=RED, width=70)
        self.assigned_num.pack()

        mid = ctk.CTkFrame(self.assigned_frame, fg_color="transparent")
        mid.pack(side="left", fill="x", expand=True)
        self.assigned_type = ctk.CTkLabel(mid, text="Bouton assigne",
                                           font=FONT_SMALL, text_color=MUTED)
        self.assigned_type.pack(anchor="w")
        ctk.CTkLabel(mid, text="1 APPUI = DOSE COMPLETE",
                     font=FONT_H2, text_color=TEXT).pack(anchor="w")

        right_f = ctk.CTkFrame(self.assigned_frame, fg_color="transparent")
        right_f.pack(side="right", padx=12)
        OutlineBtn(right_f, text="Changer", width=90,
                   command=self._start_listening).pack(pady=(0, 6))
        OutlineBtn(right_f, text="Reset", width=90,
                   command=self._clear_assign).pack()

        # Systeme
        ctk.CTkLabel(p, text="Systeme", font=FONT_H1,
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))
        sys_card = Card(p)
        sys_card.pack(fill="x")
        srow = ctk.CTkFrame(sys_card, fg_color="transparent")
        srow.pack(fill="x", padx=20, pady=16)

        self.autostart_var = ctk.BooleanVar(value=get_autostart())
        ctk.CTkCheckBox(srow, text="Demarrer avec Windows (dans le tray)",
                        variable=self.autostart_var, font=FONT_BODY,
                        text_color=TEXT2, fg_color=RED, hover_color=RED_DRK,
                        border_color=MUTED2,
                        command=lambda: set_autostart(self.autostart_var.get())).pack(side="left")
        OutlineBtn(srow, text="Minimiser dans le tray", width=180,
                   command=self._hide_to_tray).pack(side="right")

    def _render_dev_card(self):
        for w in self.dev_card.winfo_children(): w.destroy()
        row = ctk.CTkFrame(self.dev_card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=14)
        if self.input_mode == self.MODE_KB:
            ctk.CTkLabel(row, text="⌨", font=("Segoe UI", 24)).pack(side="left", padx=(0,12))
            i = ctk.CTkFrame(row, fg_color="transparent"); i.pack(side="left")
            ctk.CTkLabel(i, text="Clavier systeme", font=FONT_H2, text_color=TEXT).pack(anchor="w")
            ctk.CTkLabel(i, text="Toutes les touches — fonctionne en arriere-plan",
                         font=FONT_SMALL, text_color=MUTED).pack(anchor="w")
        elif self.gp_index is not None:
            try:
                js = pygame.joystick.Joystick(self.gp_index); js.init()
                name = js.get_name()[:52]
                ctk.CTkLabel(row, text="🎮", font=("Segoe UI", 24)).pack(side="left", padx=(0,12))
                i = ctk.CTkFrame(row, fg_color="transparent"); i.pack(side="left")
                ctk.CTkLabel(i, text=name, font=FONT_H2, text_color=TEXT).pack(anchor="w")
                ctk.CTkLabel(i, text=f"Index {self.gp_index} — {js.get_numbuttons()} boutons",
                             font=FONT_SMALL, text_color=MUTED).pack(anchor="w")
            except: pass
        else:
            ctk.CTkLabel(row, text="Appuie sur un bouton du volant pour le detecter",
                         font=FONT_BODY, text_color=MUTED).pack()

    # ── PAGE POMPE ────────────────────────────────────────────────────────────

    def _build_pompe(self, parent):
        scroll = ctk.CTkScrollableFrame(parent, fg_color=BG, scrollbar_button_color=BG3)
        scroll.pack(fill="both", expand=True)
        p = ctk.CTkFrame(scroll, fg_color="transparent")
        p.pack(fill="both", expand=True, padx=32, pady=24)

        ctk.CTkLabel(p, text="Reglages pompe", font=FONT_TITLE,
                     text_color=TEXT).pack(anchor="w", pady=(0, 24))

        # ── Selecteur de mode ────────────────────────────────────────────────
        ctk.CTkLabel(p, text="Mode de declenchement", font=FONT_H1,
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))
        mode_card = Card(p)
        mode_card.pack(fill="x", pady=(0, 20))
        mrow = ctk.CTkFrame(mode_card, fg_color="transparent")
        mrow.pack(fill="x", padx=20, pady=16)

        self.pump_mode_var = ctk.StringVar(value=self.pump_mode)

        # One Push
        op_f = ctk.CTkFrame(mrow, fg_color=BG3, border_width=1,
                             border_color=BORDER, corner_radius=8)
        op_f.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkRadioButton(op_f, text="One Push", value="one_push",
                           variable=self.pump_mode_var,
                           font=FONT_H2, text_color=TEXT,
                           fg_color=RED, hover_color=RED_DRK, border_color=MUTED2,
                           command=self._on_pump_mode_change).pack(anchor="w", padx=14, pady=(14,2))
        ctk.CTkLabel(op_f, text="1 appui = dose complete (timer)",
                     font=FONT_SMALL, text_color=MUTED).pack(anchor="w", padx=14, pady=(0,14))

        # Push to Drink
        ptd_f = ctk.CTkFrame(mrow, fg_color=BG3, border_width=1,
                              border_color=BORDER, corner_radius=8)
        ptd_f.pack(side="left", fill="x", expand=True)
        ctk.CTkRadioButton(ptd_f, text="Push to Drink", value="push_to_drink",
                           variable=self.pump_mode_var,
                           font=FONT_H2, text_color=TEXT,
                           fg_color=RED, hover_color=RED_DRK, border_color=MUTED2,
                           command=self._on_pump_mode_change).pack(anchor="w", padx=14, pady=(14,2))
        ctk.CTkLabel(ptd_f, text="Maintien = coule, relache = arret",
                     font=FONT_SMALL, text_color=MUTED).pack(anchor="w", padx=14, pady=(0,14))

        # Indicateur mode actif
        self.pump_mode_lbl = ctk.CTkLabel(mode_card,
                                           text=self._pump_mode_desc(),
                                           font=FONT_SMALL, text_color=MUTED)
        self.pump_mode_lbl.pack(anchor="w", padx=20, pady=(0, 12))

        # ── Duree de dose (masquee en push_to_drink) ─────────────────────────
        # Dose
        ctk.CTkLabel(p, text="Duree de dose", font=FONT_H1,
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))
        dose_card = Card(p)
        dose_card.pack(fill="x", pady=(0, 20))

        dc = ctk.CTkFrame(dose_card, fg_color="transparent")
        dc.pack(fill="x", padx=20, pady=20)

        # Affichage valeur
        val_row = ctk.CTkFrame(dc, fg_color="transparent")
        val_row.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(val_row, text="DOSE", font=("Segoe UI", 11, "bold"),
                     text_color=MUTED).pack(side="left")
        self.dose_big_lbl = ctk.CTkLabel(val_row,
                                          text=f"{self.dose_ms/1000:.1f}s",
                                          font=("Segoe UI", 32, "bold"),
                                          text_color=RED)
        self.dose_big_lbl.pack(side="right")

        self.dose_slider = ctk.CTkSlider(dc, from_=500, to=15000,
                                          number_of_steps=145,
                                          fg_color=BG4, progress_color=RED,
                                          button_color=RED,
                                          button_hover_color=RED_DRK,
                                          command=self._on_dose_change)
        self.dose_slider.set(self.dose_ms)
        self.dose_slider.pack(fill="x")

        marks = ctk.CTkFrame(dc, fg_color="transparent")
        marks.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(marks, text="0.5s", font=("Segoe UI", 10),
                     text_color=MUTED2).pack(side="left")
        ctk.CTkLabel(marks, text="Defaut : 5s", font=("Segoe UI", 10),
                     text_color=MUTED2).pack(side="left", expand=True)
        ctk.CTkLabel(marks, text="15s", font=("Segoe UI", 10),
                     text_color=MUTED2).pack(side="right")

        self.dose_note_lbl = ctk.CTkLabel(dc,
                     text=self._dose_note(),
                     font=FONT_SMALL, text_color=MUTED)
        self.dose_note_lbl.pack(anchor="w", pady=(12, 0))

        # Presets
        ctk.CTkLabel(p, text="Presets rapides", font=FONT_H1,
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))
        preset_card = Card(p)
        preset_card.pack(fill="x", pady=(0, 20))
        prow = ctk.CTkFrame(preset_card, fg_color="transparent")
        prow.pack(fill="x", padx=20, pady=16)
        for label, ms in [("Petite gorge", 2000), ("Gorge normale", 5000),
                           ("Grande gorge", 8000), ("Max", 15000)]:
            OutlineBtn(prow, text=label, width=140,
                       command=lambda m=ms: self._set_dose(m)).pack(side="left", padx=(0, 8))

        # Actions maintenance
        ctk.CTkLabel(p, text="Maintenance", font=FONT_H1,
                     text_color=TEXT).pack(anchor="w", pady=(0, 10))
        maint_card = Card(p)
        maint_card.pack(fill="x")
        mc = ctk.CTkFrame(maint_card, fg_color="transparent")
        mc.pack(fill="x", padx=20, pady=20)

        # Test
        test_f = ctk.CTkFrame(mc, fg_color=BG3, border_width=1,
                               border_color=BORDER, corner_radius=8)
        test_f.pack(fill="x", pady=(0, 10))
        tr = ctk.CTkFrame(test_f, fg_color="transparent")
        tr.pack(fill="x", padx=16, pady=14)
        ti = ctk.CTkFrame(tr, fg_color="transparent"); ti.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(ti, text="Test pompe", font=FONT_H2, text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(ti, text="Lance la pompe pendant la duree reglée",
                     font=FONT_SMALL, text_color=MUTED).pack(anchor="w")
        BigBtn(tr, text="Lancer le test", width=150, command=self._test_pump).pack(side="right")

        # Purge
        purge_f = ctk.CTkFrame(mc, fg_color=BG3, border_width=1,
                                border_color=BORDER, corner_radius=8)
        purge_f.pack(fill="x")
        pr = ctk.CTkFrame(purge_f, fg_color="transparent")
        pr.pack(fill="x", padx=16, pady=14)
        pi = ctk.CTkFrame(pr, fg_color="transparent"); pi.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(pi, text="Purge du tube", font=FONT_H2, text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(pi, text="Inverse la pompe 3s pour vider le tube — cooldown 10s",
                     font=FONT_SMALL, text_color=MUTED).pack(anchor="w")
        self.purge_btn = OutlineBtn(pr, text="Purger", width=150, command=self._purge_pump)
        self.purge_btn.pack(side="right")

        # Stop
        Sep(mc).pack(fill="x", pady=12)
        stop_row = ctk.CTkFrame(mc, fg_color="transparent")
        stop_row.pack(fill="x")
        ctk.CTkLabel(stop_row, text="Arret d'urgence",
                     font=FONT_SMALL, text_color=MUTED).pack(side="left")
        ctk.CTkButton(stop_row, text="STOP", width=100, height=34,
                      fg_color="#7f1d1d", hover_color="#991b1b",
                      text_color=TEXT, font=("Segoe UI", 12, "bold"),
                      corner_radius=6, command=self._force_stop).pack(side="right")

    def _pump_mode_desc(self):
        if self.pump_mode == "one_push":
            return "Mode actif : One Push — 1 appui lance une dose de duree fixe"
        return "Mode actif : Push to Drink — maintenir le bouton pour boire"

    def _dose_note(self):
        if self.pump_mode == "one_push":
            return "1 appui = pompe active pendant la duree reglee, puis arret automatique."
        return "En mode Push to Drink, le timer n'est pas utilise — le slider est ignore."

    def _on_pump_mode_change(self):
        self.pump_mode = self.pump_mode_var.get()
        self.pump_mode_lbl.configure(text=self._pump_mode_desc())
        self.dose_note_lbl.configure(text=self._dose_note())
        # Griser le slider en push_to_drink
        state = "normal" if self.pump_mode == "one_push" else "disabled"
        self.dose_slider.configure(state=state)
        # Update stat card accueil
        if hasattr(self, "_stat_dose"):
            if self.pump_mode == "one_push":
                self._stat_dose.configure(text=f"{self.dose_ms/1000:.1f}s", text_color=BLUE)
            else:
                self._stat_dose.configure(text="Push to Drink", text_color=ORANGE)
        self._save()
        self.log(f"Mode : {'One Push' if self.pump_mode == 'one_push' else 'Push to Drink'}", "info")

    def _set_dose(self, ms):
        self.dose_ms = ms
        self.dose_slider.set(ms)
        self.dose_big_lbl.configure(text=f"{ms/1000:.1f}s")
        if hasattr(self, '_stat_dose'):
            self._stat_dose.configure(text=f"{ms/1000:.1f}s")
        self._save()

    # ── PAGE JOURNAL ──────────────────────────────────────────────────────────

    def _build_journal(self, parent):
        top = ctk.CTkFrame(parent, fg_color=BG2, height=52,
                           corner_radius=0, border_width=1, border_color=BORDER)
        top.pack(fill="x")
        top.pack_propagate(False)
        ctk.CTkLabel(top, text="Journal d'activite", font=FONT_H1,
                     text_color=TEXT).pack(side="left", padx=20, pady=12)
        OutlineBtn(top, text="Effacer", width=90,
                   command=self._clear_log).pack(side="right", padx=16, pady=8)

        self.log_text = tk.Text(
            parent, bg=BG2, fg=TEXT2,
            font=("Courier New", 12),
            relief="flat", bd=0, padx=20, pady=12,
            state="disabled", cursor="arrow",
            selectbackground=BG3,
            insertbackground=BG,
            wrap="word", spacing1=2, spacing3=4)
        self.log_text.pack(fill="both", expand=True)

        sb = tk.Scrollbar(parent, command=self.log_text.yview,
                          bg=BG3, troughcolor=BG, relief="flat", width=8)
        self.log_text.configure(yscrollcommand=sb.set)

        self.log_text.tag_config("time",   foreground=MUTED2)
        self.log_text.tag_config("ok",     foreground=GREEN)
        self.log_text.tag_config("err",    foreground=RED)
        self.log_text.tag_config("info",   foreground=BLUE)
        self.log_text.tag_config("act",    foreground=TEXT)
        self.log_text.tag_config("warn",   foreground=ORANGE)
        self.log_text.tag_config("muted",  foreground=MUTED)

    # ── RESTORE ───────────────────────────────────────────────────────────────

    def _restore(self):
        self.mode_var.set(self.input_mode)
        self.autostart_var.set(get_autostart())
        self.sb_mode_lbl.configure(
            text="Gamepad" if self.input_mode == self.MODE_GP else "Clavier")

        if self.input_mode == self.MODE_KB and self.assigned_key:
            self._show_assigned(self.assigned_key_name, "clavier")
            self._register_keyboard_hook()
            self.log(f"Touche '{self.assigned_key_name}' restauree.", "ok")
        elif self.input_mode == self.MODE_GP and self.assigned_btn is not None:
            self._show_assigned(str(self.assigned_btn), "gamepad")
            self.log(f"Bouton {self.assigned_btn} restaure.", "ok")

        if self.input_mode == self.MODE_KB:
            self._render_dev_card()

        # Restaurer le mode pompe (fait apres _build_ui donc widgets existent)
        if hasattr(self, "pump_mode_var"):
            self.pump_mode_var.set(self.pump_mode)
            if hasattr(self, "pump_mode_lbl"):
                self.pump_mode_lbl.configure(text=self._pump_mode_desc())
            if hasattr(self, "dose_note_lbl"):
                self.dose_note_lbl.configure(text=self._dose_note())
            if hasattr(self, "dose_slider"):
                state = "normal" if self.pump_mode == "one_push" else "disabled"
                self.dose_slider.configure(state=state)
            if hasattr(self, "_stat_dose"):
                if self.pump_mode == "push_to_drink":
                    self._stat_dose.configure(text="Push to Drink", text_color=ORANGE)

    # ── MODE ──────────────────────────────────────────────────────────────────

    def _on_mode_change(self):
        self.input_mode = self.mode_var.get()
        self._clear_assign(silent=True)
        self.gp_index = None if self.input_mode == self.MODE_KB else self.gp_index
        self._render_dev_card()
        self.sb_mode_lbl.configure(
            text="Gamepad" if self.input_mode == self.MODE_GP else "Clavier")
        self._save()

    # ── ASSIGNATION ───────────────────────────────────────────────────────────

    def _start_listening(self):
        if self.input_mode == self.MODE_GP and self.gp_index is None:
            self.log("Aucun gamepad detecte.", "err"); return
        self.listening = True
        self.listen_btn.configure(
            text="En attente... appuie sur le bouton",
            fg_color=RED_DIM, border_color=BRED, text_color=RED)
        if self.input_mode == self.MODE_KB:
            self.focus_force()
            self.bind("<KeyPress>", self._on_key_capture)

    def _on_key_capture(self, event):
        if not self.listening or self.input_mode != self.MODE_KB: return
        self.assigned_key      = event.keysym
        self.assigned_key_name = event.keysym.upper()
        self.unbind("<KeyPress>")
        self._show_assigned(self.assigned_key_name, "clavier")
        self.listening = False
        self.listen_btn.configure(text="Changer la touche",
                                   fg_color=BG3, border_color=BORDER, text_color=MUTED)
        self._register_keyboard_hook()
        self._save()
        self.log(f"Touche '{self.assigned_key_name}' assignee.", "act")

    def _register_keyboard_hook(self):
        try: keyboard.unhook_all()
        except: pass
        if not self.assigned_key: return
        key = self.assigned_key.lower()
        def on_press(e):
            if self.input_mode != self.MODE_KB or self.listening: return
            if e.name and e.name.lower() == key and not self.key_pressed:
                self.key_pressed = True
                self.after(0, self._pump_on)
        def on_release(e):
            if self.input_mode != self.MODE_KB or self.listening: return
            if e.name and e.name.lower() == key and self.pump_mode == "push_to_drink":
                self.key_pressed = False
                self.after(0, self._pump_off)
        keyboard.on_press(on_press)
        keyboard.on_release(on_release)

    def _assign_btn(self, i):
        self.listening = False
        self.assigned_btn = i
        self.listen_btn.configure(text="Changer le bouton",
                                   fg_color=BG3, border_color=BORDER, text_color=MUTED)
        self._show_assigned(str(i), "gamepad")
        self._save()
        self.log(f"Bouton {i} assigne.", "act")

    def _show_assigned(self, label, kind):
        self.assigned_num.configure(text=label[:6] if len(label) > 6 else label)
        self.assigned_type.configure(
            text="Bouton gamepad" if kind == "gamepad" else f"Touche [ {label} ]")
        self.assigned_frame.pack(fill="x", pady=(0, 0))
        # Stat card
        if hasattr(self, '_stat_bouton'):
            self._stat_bouton.configure(text=label[:8], text_color=GREEN)

    def _clear_assign(self, silent=False):
        self.assigned_btn = self.assigned_key = self.assigned_key_name = None
        self.key_pressed = self.listening = False
        try: keyboard.unhook_all()
        except: pass
        self.unbind("<KeyPress>"); self.unbind("<KeyRelease>")
        self.assigned_frame.pack_forget()
        self.listen_btn.configure(text="Clique ici puis appuie sur le bouton a assigner",
                                   fg_color=BG3, border_color=BORDER, text_color=MUTED)
        if hasattr(self, '_stat_bouton'):
            self._stat_bouton.configure(text="Aucun", text_color=MUTED)
        if not silent:
            self.log("Assignation effacee.", "info"); self._save()

    def _on_key_press(self, e): pass
    def _on_key_release(self, e): pass

    # ── LOG ───────────────────────────────────────────────────────────────────

    def log(self, msg, kind=""):
        def _do():
            t = datetime.now().strftime("%H:%M:%S")
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"{t}  ", "time")
            self.log_text.insert("end", msg + "\n", kind if kind else "muted")
            self.log_text.configure(state="disabled")
            self.log_text.see("end")
        self.after(0, _do)

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ── SERIAL ────────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        vals = [f"{p.device}  —  {p.description}" for p in ports]
        if not vals:
            vals = ["-- Aucun port COM --"]
            self.log("Aucun port COM detecte.", "err")
        else:
            self.log(f"{len(vals)} port(s) COM detecte(s).", "info")
        self.port_combo.configure(values=vals)
        self.port_combo.set(vals[0])

    def _get_port(self):
        val = self.port_var.get()
        for p in serial.tools.list_ports.comports():
            if val.startswith(p.device): return p.device
        return None

    def _connect(self):
        port = self._get_port()
        if not port: self.log("Selectionne un port valide.", "err"); return
        try:
            self.serial_port = serial.Serial(port, 115200, timeout=1)
            self.connected = True
            self._set_status(True, port)
            self.log(f"Arduino connecte — {port}", "ok")
            self.btn_connect.configure(state="disabled")
            self.btn_disconnect.configure(state="normal")
            threading.Thread(target=self._read_serial, daemon=True).start()
        except Exception as e:
            self.log(f"Erreur : {e}", "err")

    def _disconnect(self):
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            self.connected = False
            self._set_status(False)
            self.log("Deconnecte.", "info")
            self.btn_connect.configure(state="normal")
            self.btn_disconnect.configure(state="disabled")
        except Exception as e:
            self.log(f"Erreur : {e}", "err")

    def _read_serial(self):
        while self.connected and self.serial_port and self.serial_port.is_open:
            try:
                line = self.serial_port.readline().decode("utf-8", errors="ignore").strip()
                if line: self.log(f"Arduino → {line}", "info")
            except: break

    def _send(self, cmd):
        if not self.connected or not self.serial_port: return False
        try:
            self.serial_port.write(cmd.encode("utf-8")); return True
        except: return False

    def _set_status(self, on, port=""):
        if on:
            self.sb_dot.configure(text_color=GREEN)
            self.sb_port_lbl.configure(text=port, text_color=GREEN)
            self.acc_status_tag.configure(text="  Connecte  ", text_color=GREEN,
                                           fg_color="#1a3d2a")
            if hasattr(self, '_stat_arduino'):
                self._stat_arduino.configure(text=port, text_color=GREEN)
        else:
            self.sb_dot.configure(text_color=MUTED2)
            self.sb_port_lbl.configure(text="Non connecte", text_color=MUTED)
            self.acc_status_tag.configure(text="  Non connecte  ", text_color=MUTED2,
                                           fg_color="#222222")
            if hasattr(self, '_stat_arduino'):
                self._stat_arduino.configure(text="Non connecte", text_color=MUTED)

    # ── INPUT LOOP ────────────────────────────────────────────────────────────

    def _input_loop(self):
        if self.input_mode == self.MODE_GP:
            pygame.event.pump()
            count = pygame.joystick.get_count()
            if count > 0 and self.gp_index is None:
                for i in range(count):
                    try:
                        js = pygame.joystick.Joystick(i); js.init()
                        for b in range(js.get_numbuttons()):
                            if js.get_button(b):
                                self.gp_index = i
                                self.log(f"Detecte : {js.get_name()}", "ok")
                                self._render_dev_card()
                                break
                        if self.gp_index is not None: break
                    except: pass
            elif self.gp_index is not None:
                try:
                    js = pygame.joystick.Joystick(self.gp_index); js.init()
                    now = time.time() * 1000
                    for b in range(min(js.get_numbuttons(), 64)):
                        pressed = bool(js.get_button(b))
                        was = self.last_btn_st.get(b, False)
                        if pressed != was:
                            if now - self.btn_press_t.get(b, 0) < self.DEBOUNCE: continue
                            self.btn_press_t[b] = now
                            if self.listening and pressed:
                                self._assign_btn(b)
                            elif not self.listening and b == self.assigned_btn:
                                if pressed:
                                    self._pump_on()
                                elif not pressed and self.pump_mode == "push_to_drink":
                                    self._pump_off()
                            self.last_btn_st[b] = pressed
                except:
                    self.gp_index = None; self._render_dev_card()
        self.after(16, self._input_loop)

    # ── POMPE ─────────────────────────────────────────────────────────────────

    def _on_dose_change(self, val):
        self.dose_ms = int(val)
        self.dose_big_lbl.configure(text=f"{self.dose_ms/1000:.1f}s")
        if hasattr(self, '_stat_dose'):
            self._stat_dose.configure(text=f"{self.dose_ms/1000:.1f}s")
        self._save()

    def _pump_on(self):
        if self.pump_on: return
        if self.dose_timer: self.after_cancel(self.dose_timer); self.dose_timer = None
        self.pump_on = True
        self.key_pressed = False
        self._send("1")
        self._set_pump_ui(True)
        if self.pump_mode == "one_push":
            secs = self.dose_ms / 1000
            self.log(f"Pompe ON [One Push] — dose {secs:.1f}s", "act")
            self._animate_dose_bar(0)
            self.dose_timer = self.after(self.dose_ms, self._pump_off)
        else:
            self.log("Pompe ON [Push to Drink] — maintien actif", "act")

    def _pump_off(self):
        if not self.pump_on: return
        if self.dose_timer: self.after_cancel(self.dose_timer); self.dose_timer = None
        self.pump_on = False
        self._send("0")
        self._set_pump_ui(False)
        self.log("Pompe OFF", "info")

    def _force_stop(self):
        if self.dose_timer: self.after_cancel(self.dose_timer); self.dose_timer = None
        self.pump_on = True; self._pump_off()

    def _test_pump(self):
        if not self.connected: self.log("Connecte d'abord l'Arduino.", "err"); return
        if self.dose_timer: self.after_cancel(self.dose_timer); self.dose_timer = None
        self.pump_on = False
        self.log(f"Test pompe {self.dose_ms/1000:.1f}s...", "info")
        self._pump_on()

    def _purge_pump(self):
        if not self.connected: self.log("Connecte d'abord l'Arduino.", "err"); return
        if self._purge_cd:
            self.log("Purge en cooldown — attends avant de relancer.", "warn"); return
        self._purge_cd = True
        self.log("Purge — inversion 3s...", "info")
        if hasattr(self, 'purge_btn'):
            self.purge_btn.configure(state="disabled", text="Cooldown 10s...")
        self._send("2"); self._set_pump_ui(True, "PURGE")
        def _end():
            self._send("0"); self._set_pump_ui(False)
            self.log("Purge terminee. Cooldown 10s.", "ok")
            self.after(10000, self._reset_purge_cd)
        self.after(3000, _end)

    def _reset_purge_cd(self):
        self._purge_cd = False
        if hasattr(self, 'purge_btn'):
            self.purge_btn.configure(state="normal", text="Purger")
        self.log("Purge disponible.", "info")

    def _set_pump_ui(self, on, label=None):
        if on:
            self.acc_pump_ring.configure(border_color=RED, fg_color=RED_DIM)
            self.acc_pump_lbl.configure(text=label or "POMPE ON", text_color=RED)
            self.acc_pump_sub.configure(text="Eau en cours...")
        else:
            self.acc_pump_ring.configure(border_color=BORDER, fg_color=BG3)
            self.acc_pump_lbl.configure(text="ARRET", text_color=TEXT)
            self.acc_pump_sub.configure(text="En attente d'action")
            self.acc_dose_bar.set(0)

    def _animate_dose_bar(self, elapsed_ms):
        if not self.pump_on: return
        progress = min(elapsed_ms / self.dose_ms, 1.0)
        self.acc_dose_bar.set(progress)
        if progress < 1.0:
            self.after(50, lambda: self._animate_dose_bar(elapsed_ms + 50))

    def _on_speed_change(self, val): pass

    # ── FERMETURE ─────────────────────────────────────────────────────────────

    def on_close(self):
        if self.pump_on: self._send("0")
        if self.serial_port and self.serial_port.is_open: self.serial_port.close()
        try: keyboard.unhook_all()
        except: pass
        if self.tray_icon: self.tray_icon.stop()
        pygame.quit(); self._save(); self.destroy()


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    minimized = "--minimized" in sys.argv
    app = AVIXDrinkApp(start_minimized=minimized)
    app.protocol("WM_DELETE_WINDOW", app._hide_to_tray)
    app.mainloop()
