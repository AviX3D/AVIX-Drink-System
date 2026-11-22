"""Fausse box sur un pseudo-terminal : émule le firmware V2 (ou V1 / appareil étranger)."""
import os, pty, threading, time, tty

class FakeBox:
    def __init__(self, mode="v2"):
        self.master, slave = pty.openpty()
        tty.setraw(slave)
        self.slave_name = os.ttyname(slave)
        self._slave_fd = slave          # garder ouvert pour que le pty existe
        self.mode = mode
        self.rx = b""
        self.alive = True
        self.cmds = []
        threading.Thread(target=self._run, daemon=True).start()

    def w(self, s):
        try: os.write(self.master, s.encode())
        except OSError: pass

    def _run(self):
        last_banner = 0
        pinged = False
        while self.alive:
            if self.mode in ("v1", "v2") and not pinged and time.time() - last_banner > 0.8:
                self.w("=== AVIX DRINK SYSTEM V2 - pret ===\r\n"); last_banner = time.time()
            import select
            r, _, _ = select.select([self.master], [], [], 0.05)
            if not r: continue
            try: data = os.read(self.master, 256)
            except OSError: return
            for ch in data.decode(errors="ignore"):
                at_start = getattr(self, "_linelen", 0) == 0
                self._linelen = 0 if ch in "\r\n" else (getattr(self, "_linelen", 0) + (0 if (at_start and ch in "012") else 1))
                if not (ch in "012" and at_start):
                    self.rx += ch.encode()
                if ch in "012" and at_start and self.mode in ("v1", "v2"):
                    self.cmds.append(ch)
                    if self.mode == "v2":
                        self.w({"1": "PUMP:ON (appli)\r\n", "0": "PUMP:OFF (appli)\r\n", "2": "PUMP:REV (appli)\r\n"}[ch])
            self.raw = getattr(self, "raw", b"") + data
            while b"\n" in self.rx:
                line, _, self.rx = self.rx.partition(b"\n")
                l = line.decode(errors="ignore").strip()
                if l == "PING":
                    pinged = True
                    if self.mode == "v2": self.w("PONG\r\n")
                elif l.startswith("SPD:"):
                    self.cmds.append(l)
                    if self.mode == "v2": self.w("OK:SPD\r\n")

class FakePort:
    def __init__(self, dev, vid=0x1A86, pid=0x7523, desc="USB-SERIAL CH340"):
        self.device, self.vid, self.pid, self.description, self.hwid = dev, vid, pid, desc, f"USB VID:PID={vid:04X}:{pid:04X}"
