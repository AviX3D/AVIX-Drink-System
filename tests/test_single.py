import os, sys, time, subprocess
os.environ["APPDATA"] = "/tmp/avixsi"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import avix_drink as A
got = []
a = A.SingleInstance(); ok = a.acquire(); a.serve(lambda: got.append("show"))
code = "import os,sys;os.environ['APPDATA']='/tmp/avixsi';sys.path.insert(0," + repr(ROOT) + ");import avix_drink as A;s=A.SingleInstance();print(s.acquire(), A.SingleInstance.wake_existing())"
out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20).stdout.strip()
time.sleep(0.3)
print("1re instance acquiert:", ok, "| 2e instance (acquire, wake):", out, "| fenêtre réveillée:", got)
assert ok and out == "False True" and got == ["show"]
print("ok  instance unique")
