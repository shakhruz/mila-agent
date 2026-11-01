#!/usr/bin/env python3
"""check_install_link.py against a local fake GitHub: README links found; 302 → 200 passes; 404 fails with the file and README
named; no answer fails. Run: python3 test_check_install_link.py"""
import http.server, os, shutil, subprocess, sys, tempfile, threading
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
GOOD = {"/o/r/releases/latest/download/get.sh", "/o/r/releases/latest/download/SHA256SUMS"}
class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_HEAD(self):
        if self.path in GOOD:
            self.send_response(302); self.send_header("Location", "/assets" + self.path); self.end_headers()
        elif self.path.startswith("/assets/"):
            self.send_response(200); self.send_header("Content-Length", "0"); self.end_headers()
        else:
            self.send_response(404); self.end_headers()
    do_GET = do_HEAD   # urllib follows a redirect with GET
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
T = tempfile.mkdtemp(prefix="instlink-"); os.makedirs(os.path.join(T, "tools")); shutil.copy(os.path.join(H, "check_install_link.py"), os.path.join(T, "tools"))
def run(readmes, base="http://127.0.0.1:%d" % srv.server_port):
    for f in os.listdir(T):
        if f.startswith("README"): os.remove(os.path.join(T, f))
    for name, text in readmes.items(): open(os.path.join(T, name), "w").write(text)
    return subprocess.run([sys.executable, os.path.join(T, "tools", "check_install_link.py")], capture_output=True, text=True, env=dict(os.environ, CHECK_INSTALL_BASE=base))
G = "https://github.com/o/r/releases/latest/download/"
r = run({"README.md": "curl -fsSL %sget.sh | bash\ncurl -fsSLO %sSHA256SUMS\n" % (G, G), "README.ru.md": "curl -fsSL %sget.sh | bash\n" % G})
check("ссылки есть и отвечают 200 (через 302) — код 0", r.returncode == 0 and "2 install link" in r.stdout, r.stdout)
r = run({"README.md": "curl -fsSL %sget.sh | bash\n" % G, "README.uz.md": "curl -fsSL %sgetx.sh | bash\n" % G})
check("404 — код 1, названы файл и README", r.returncode == 1 and "getx.sh → 404" in r.stdout and "README.uz.md" in r.stdout, r.stdout)
r = run({"README.md": "curl -fsSL %sget.sh | bash\n" % G}, base="http://127.0.0.1:1")
check("нет ответа — код 1, «no answer»", r.returncode == 1 and "no answer" in r.stdout, r.stdout)
r = run({"README.md": "no links here\n"})
check("ссылок на выпуск нет — код 0", r.returncode == 0 and "no release download links" in r.stdout, r.stdout)
srv.shutdown(); shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
