import os, sys, time, queue
os.environ["APPDATA"] = "/tmp/avixgui"
import shutil; shutil.rmtree("/tmp/avixgui", ignore_errors=True)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import avix_drink as A
from fakebox import FakeBox, FakePort
A.keyboard = None
box = FakeBox("v2")
ports = [FakePort(box.slave_name)]
A.serial.tools.list_ports.comports = lambda: ports
app = A.App(link_factory=lambda ev: A.BoxLink(ev, port_lister=lambda: ports))
fails = []
def check(c, m):
    print(("ok  " if c else "FAIL") + "  " + m, flush=True)
    if not c: fails.append(m)
def pump(ms):
    t0 = time.time()
    while time.time() - t0 < ms / 1000:
        app.update(); time.sleep(0.01)
def shot(name):
    pump(300)
    try:
        from PIL import ImageGrab
        x, y, w, h = app.winfo_rootx(), app.winfo_rooty(), app.winfo_width(), app.winfo_height()
        ImageGrab.grab(bbox=(x, y, x + w, y + h), xdisplay=os.environ.get("DISPLAY")).save(f"/tmp/shot_{name}.png")
    except Exception as e:
        print("shot", name, e)

pump(800); shot("tuto0")
check(app.cur_page == "tuto", "tuto affiché au 1er lancement")
t0 = time.time()
while app.link_state != "connected" and time.time() - t0 < 12: pump(100)
check(app.link_state == "connected", "box connectée dans l'UI")
app.tuto_i = 1; app._tuto_render(); shot("tuto1")
app._tuto_finish(); pump(200); check(app.s["tuto_done"] and app.cur_page == "home", "tuto terminé -> accueil")
shot("home")
# capture d'une touche
app.show_page("button"); app.start_listening(); app.events.put(("key", "f", True)); pump(200)
check(app.s["binding"] == {"type": "keyboard", "key": "f", "scan": None}, "touche F capturée")
app.events.put(("key", "f", False)); pump(100)
shot("button")
# une dose
app._set_dose(1000); box.cmds.clear()
app.events.put(("key", "f", True)); pump(150); app.events.put(("key", "f", False))
pump(300); check(app.pump == "on" and box.cmds[-1:] == ["1"], f"appui -> pompe ON {box.cmds}")
pump(1200); check(app.pump == "off" and box.cmds[-1:] == ["0"], f"fin de dose -> OFF {box.cmds}")
check(app.session_sips == 1, "gorgée comptée")
# répétition clavier ignorée + 2e appui pendant dose = arrêt
box.cmds.clear()
app.events.put(("key", "f", True)); app.events.put(("key", "f", True)); app.events.put(("key", "f", True)); pump(200)
check(box.cmds.count("1") == 1, "auto-répétition ignorée")
app.events.put(("key", "f", False)); pump(50); app.events.put(("key", "f", True)); pump(200)
check(app.pump == "off" and box.cmds[-1:] == ["0"], "2e appui pendant la dose = arrêt")
app.events.put(("key", "f", False)); pump(100)
# mode maintien
app._on_mode("Tant que j'appuie"); box.cmds.clear()
app.events.put(("key", "f", True)); pump(300); check(app.pump == "on", "maintien : ON")
app.events.put(("key", "f", False)); pump(300); check(app.pump == "off" and box.cmds[-1:] == ["0"], "maintien : relâché -> OFF")
# autre touche : ignorée
app.events.put(("key", "g", True)); pump(200); check(app.pump == "off", "autre touche ignorée")
app.events.put(("key", "g", False))
# bouton du capot (annoncé par le firmware)
box.w("PUMP:ON (bouton)\r\n"); pump(400); check(app.pump == "on" and app.pump_src == "capot", "capot : UI suit")
box.w("PUMP:OFF (bouton)\r\n"); pump(400); check(app.pump == "off", "capot relâché : UI suit")
# purge + cooldown
app.show_page("pump"); box.cmds.clear(); app.purge(); pump(200)
check(app.pump == "rev" and box.cmds[-1:] == ["2"], "purge : '2'")
shot("pump_purge")
app.purge(); pump(100); check(box.cmds.count("2") == 1, "pas de double purge")
pump(3200); check(app.pump == "off" and box.cmds[-1:] == ["0"] and not app.purge_ready, "fin de purge + attente")
# STOP
app._on_mode("Une dose par appui"); app._set_dose(8000)
app.test_dose(); pump(300); app.emergency_stop(); pump(300)
check(app.pump == "off" and box.cmds[-1:] == ["0"], "STOP")
# calibration
app.show_page("hydra"); app.calib_entry.insert(0, "85"); app.calib_save(); pump(100)
check(abs(app.s["ml_per_s"] - 8.5) < 1e-6, "calibration 85 ml / 10 s = 8.5 ml/s")
shot("hydra")
app.show_page("settings"); shot("settings")
app.show_page("log"); shot("log")
app.show_page("home"); shot("home2")

# ---- régressions (relecture) ----
app._on_mode("Tant que j'appuie"); box.cmds.clear()
app.events.put(("key", "f", True)); app.events.put(("key", "f", False)); pump(600)
check(app.pump == "off", "tap très court + écho de la box : reste à l'arrêt")
app.events.put(("key", "f", True)); pump(200)
check(box.cmds.count("1") == 2, f"appui suivant bien envoyé {box.cmds}")
app.events.put(("key", "f", False)); pump(200)
app._on_mode("Une dose par appui"); app._set_dose(2000)
app.test_dose(); pump(200); app.prime(True); pump(100); app.prime(False); pump(2300)
check(app.pump == "off", "Amorcer pendant une dose : la dose s'arrête bien à la fin")
app._on_mode("Tant que j'appuie"); app.events.put(("key", "f", True)); pump(200)
app.start_listening(); pump(200); check(app.pump == "off", "capture pendant un maintien : pompe coupée")
app._stop_listening(None)
app.events.put(("key", "f", False)); pump(100)
app._on_mode("Une dose par appui")
app.calib_start(); pump(300); app.events.put(("key", "f", True)); pump(100); app.events.put(("key", "f", False)); pump(1800)
check(app.pump == "on" and app.pump_src == "calib", "appui pendant la calibration ignoré")
app.emergency_stop(); pump(200)
check(app.calib_btn.cget("state") == "normal", "calibration interrompue -> bouton réactivé")
app._purge_ready(); app.purge(); pump(300); app.test_dose(); pump(200)
check(app.pump == "off" and "purge_end" not in app._timers, "dose pendant la purge : purge arrêtée proprement")
app._purge_ready(); app._set_dose(4000); app.test_dose(); pump(300)
box.w("=== AVIX DRINK SYSTEM V2 - pret ===\r\n"); pump(400)
check(app.pump == "off", "box redémarrée en pleine dose -> UI à l'arrêt")
app.s["binding"] = {"type": "keyboard", "key": "&", "scan": 2}; box.cmds.clear()
app.events.put(("key", "1", True, 2)); pump(200)
check(app.pump == "on", "AZERTY : même touche physique avec Maj -> déclenche")
app.events.put(("key", "1", False, 2)); pump(100); app.emergency_stop(); pump(100)
app.s["binding"] = {"type": "keyboard", "key": "f", "scan": None}

# débranchement pendant une dose
app.test_dose(); pump(300); box.alive = False; ports.clear()
t0 = time.time()
while app.link_state == "connected" and time.time() - t0 < 10: pump(100)
check(app.link_state != "connected" and app.pump == "off", "débranchée en pleine dose -> UI à l'arrêt")
shot("home_lost")
app.quit_app()
print("ECHECS:", len(fails), fails)
