import os
import sys, time, queue
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import avix_drink as A
from fakebox import FakeBox, FakePort
A.DATA_DIR = "/tmp/avixtest"; A.LOG_FILE = "/tmp/avixtest/drink.log"
fails = 0
def check(c, m):
    global fails
    print(("ok  " if c else "FAIL") + "  " + m); fails += 0 if c else 1
def wait_ev(q, pred, t=10):
    t0 = time.time()
    while time.time() - t0 < t:
        try:
            ev = q.get(timeout=0.1)
            if pred(ev): return ev
        except queue.Empty: pass
    return None

# 1. V2 : détection + commandes + débranchement
box = FakeBox("v2"); ports = [FakePort(box.slave_name)]
q = queue.Queue()
link = A.BoxLink(q, port_lister=lambda: ports); link.start()
ev = wait_ev(q, lambda e: e[0] == "link" and e[1] == "connected")
check(ev is not None and ev[2]["fw"] == "v2", f"V2 détectée ({ev[2] if ev else None})")
time.sleep(0.2); box.cmds.clear()
link.send("1"); ev = wait_ev(q, lambda e: e[0] == "rx" and "PUMP:ON" in e[1], 3)
check(ev is not None and box.cmds[:1] == ["1"], "commande '1' -> PUMP:ON reçu")
link.send("SPD:180\n"); time.sleep(0.8); check("SPD:180" in box.cmds, f"SPD transmis {box.cmds}")
t0 = time.time(); box.alive = False; ports.clear()
ev = wait_ev(q, lambda e: e[0] == "link" and e[1] == "lost", 10)
check(ev is not None, f"perte détectée en {time.time() - t0:.1f} s")
check(not link.connected and not link.send("1"), "send refusé quand déconnecté")
# rebranchement
box2 = FakeBox("v2"); ports.append(FakePort(box2.slave_name))
ev = wait_ev(q, lambda e: e[0] == "link" and e[1] == "connected", 25)
check(ev is not None, "reconnexion automatique")
link.stop(); link.join(3); check(not link.is_alive(), "thread arrêté proprement")
check(box2.cmds[-1:] == ["0"], "pompe coupée à la fermeture")

# 2. V1 (bannière sans PONG)
box = FakeBox("v1"); q = queue.Queue()
link = A.BoxLink(q, port_lister=lambda: [FakePort(box.slave_name)]); link.start()
ev = wait_ev(q, lambda e: e[0] == "link" and e[1] == "connected", 10)
check(ev is not None and ev[2]["fw"] == "v1", "ancien firmware accepté (v1)")
link.stop(); link.join(3)

# 3. Appareil étranger (VID inconnu, pas de bannière) : on ne doit rien lui écrire
box = FakeBox("foreign"); q = queue.Queue()
link = A.BoxLink(q, port_lister=lambda: [FakePort(box.slave_name, vid=0x1234, pid=0x0001, desc="GPS")]); link.start()
ev = wait_ev(q, lambda e: e[0] == "link" and e[1] == "connected", 5)
check(ev is None and getattr(box, "raw", b"") == b"", f"appareil inconnu ignoré, rien écrit")
link.stop(); link.join(3)

# 4. Settings : migration v3
import json, os
os.makedirs("/tmp/avixtest", exist_ok=True)
p = "/tmp/avixtest/s.json"
json.dump({"input_mode": "gamepad", "assigned_btn": 7, "dose_ms": 99999, "pump_mode": "push_to_drink"}, open(p, "w"))
s = A.Settings(p)
check(s["binding"] == {"type": "gamepad", "guid": None, "name": "Gamepad", "button": 7}, "migration bouton v3")
check(s["dose_ms"] == A.DOSE_MAX_MS and s["pump_mode"] == "hold", "dose bornée + mode migré")
open(p, "w").write("{corrompu"); s = A.Settings(p); check(s["pump_mode"] == "one_push", "fichier corrompu -> défauts")
print("ECHECS:", fails); sys.exit(fails)
