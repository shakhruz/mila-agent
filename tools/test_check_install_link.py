#!/usr/bin/env python3
"""check_install_link.py against a local fake GitHub: README links found; 302 → 200 passes; 404 fails with the file and README
named; no answer fails; a `latest` get.sh older than release.json here, or not pinned, fails though every link answers. Run: python3 test_check_install_link.py"""
import http.server, os, shutil, subprocess, sys, tempfile, threading
H = os.path.dirname(os.path.abspath(__file__)); ok = n = 0
def check(name, c, x=""):
    global ok, n; n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))
GETSH = ""   # what the fake release serves as get.sh
SEEN = []
GOOD = {"/o/r/releases/latest/download/get.sh", "/o/r/releases/latest/download/SHA256SUMS"}
class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_HEAD(self):
        if self.path in GOOD:
            self.send_response(302); self.send_header("Location", "/assets" + self.path); self.end_headers()
        elif self.path.startswith("/assets/"):
            if GETSH == "GONE" and self.path.endswith("/get.sh"):   # the ping gets its 200, the read after it does not
                SEEN.append(1)
                if len(SEEN) > 1: self.send_response(500); self.end_headers(); return
            b = (GETSH if self.path.endswith("/get.sh") and self.command == "GET" else "").encode()
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        else:
            self.send_response(404); self.end_headers()
    do_GET = do_HEAD   # urllib follows a redirect with GET
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
T = tempfile.mkdtemp(prefix="instlink-"); os.makedirs(os.path.join(T, "tools")); shutil.copy(os.path.join(H, "check_install_link.py"), os.path.join(T, "tools"))
def run(readmes, base="http://127.0.0.1:%d" % srv.server_port, tag=None, getsh=""):
    global GETSH; GETSH = getsh; del SEEN[:]
    rj = os.path.join(T, "release.json")
    if os.path.exists(rj): os.remove(rj)
    if tag is not None: open(rj, "w").write(tag if tag.startswith("{") or tag == "broken" else '{"tag": "%s"}' % tag)
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
# the release behind `latest`: read, not only pinged
ONE = {"README.md": "curl -fsSL %sget.sh | bash\ncurl -fsSLO %sSHA256SUMS\n" % (G, G)}
pin = lambda v: '#!/usr/bin/env bash\nset -e\nPIN_REF="%s"\nPIN_SHA="0123abcd"\n' % v
r = run(ONE, tag="v1.7.7", getsh=pin("v1.7.7")); check("latest = версия репозитория — код 0, версия названа", r.returncode == 0 and "not behind v1.7.7" in r.stdout, r.stdout)
r = run(ONE, tag="v1.7.7", getsh=pin("v1.7.1"))
check("latest отстал (v1.7.1 при v1.7.7), ссылки отвечают — код 1, обе версии названы", r.returncode == 1 and "installs v1.7.1" in r.stdout and "is at v1.7.7" in r.stdout, r.stdout)
r = run(ONE, tag="v1.7.10", getsh=pin("v1.7.9")); check("сравнение числами, не строками: v1.7.9 старше v1.7.10 — код 1", r.returncode == 1 and "installs v1.7.9" in r.stdout, r.stdout)
r = run(ONE, tag="v1.7.9", getsh=pin("v1.7.10")); check("…а v1.7.10 при v1.7.9 в репозитории (старая копия) — код 0", r.returncode == 0, r.stdout)
r = run(ONE, tag="v1.7.7", getsh=pin("")); check("get.sh без привязки (PIN_REF пуст) — код 1, «not pinned»", r.returncode == 1 and "not pinned" in r.stdout, r.stdout)
r = run(ONE, tag="v1.7.7", getsh="echo hi\n"); check("get.sh без строки PIN_REF — код 1", r.returncode == 1 and "not pinned" in r.stdout, r.stdout)
r = run(ONE, tag="v1.7.7", getsh='echo PIN_REF="v9.9.9"\n'); check("PIN_REF не в начале строки не считается привязкой — код 1", r.returncode == 1 and "not pinned" in r.stdout, r.stdout)
r = run(ONE, tag=None, getsh=pin("v1.7.1")); check("release.json нет — сверять не с чем, код 0 как раньше", r.returncode == 0 and "2 install link" in r.stdout, r.stdout)
r = run(ONE, tag="broken", getsh=pin("v1.7.1")); check("release.json не разобрался — код 0, не падение", r.returncode == 0 and "Traceback" not in r.stderr, r.stdout + r.stderr)
r = run(ONE, tag="main", getsh=pin("v1.7.1")); check("тег не вида vX.Y.Z — сверки нет, код 0", r.returncode == 0, r.stdout)
r = run(ONE, tag="{\"tag\": null}", getsh=pin("v1.7.1")); check("в release.json тег пуст — сверки нет, код 0", r.returncode == 0 and "Traceback" not in r.stderr, r.stdout + r.stderr)
r = run(ONE, tag="v1.7.7", getsh="GONE"); check("ссылка отвечает, а файл не читается — код 1, «could not be read»", r.returncode == 1 and "could not be read" in r.stdout, r.stdout)
r = run({"README.md": "curl -fsSLO %sSHA256SUMS\n" % G}, tag="v1.7.7", getsh=pin("v1.7.1")); check("ссылки на get.sh в README нет — читать нечего, код 0", r.returncode == 0, r.stdout)
srv.shutdown(); shutil.rmtree(T, ignore_errors=True); print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
