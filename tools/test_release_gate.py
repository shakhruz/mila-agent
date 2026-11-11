#!/usr/bin/env python3
"""release_gate.py and release_files.py: a tag becomes a release only when it is an annotated vX.Y.Z on a commit of main whose
release.json and CHANGELOG say that version, not withdrawn, signed when main lists signers, and with a green run of the tests
for exactly that commit; the files of the release are the same bytes from the script and from the workflow.
Repositories are temp folders; the list of runs is a fake. Run: python3 tools/test_release_gate.py"""
import hashlib, json, os, shutil, subprocess, sys, tempfile
sys.dont_write_bytecode = True
H = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(H); sys.path.insert(0, H)
import release_gate as G, release_files as F
T = tempfile.mkdtemp(prefix="relgate-"); ok = n = 0
def chk(m, c, x=""):
    global ok, n
    n += 1; ok += bool(c); print(("✅ " if c else "❌ ") + m + ("" if c else "  ← " + str(x)[:400]))
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.org", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.org",
           GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull, HOME=T)
os.environ.update({k: ENV[k] for k in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "HOME")})
def g(*a, cwd):
    r = subprocess.run(["git", *a], cwd=cwd, env=ENV, capture_output=True, text=True)
    assert r.returncode == 0, (a, r.stderr)
    return r.stdout.strip()
GET = '#!/bin/sh\nPIN_REF=""\nPIN_SHA=""\necho install\n'
CL = "# CHANGELOG\n\n## v%s · today\n\n**For the owner**\n- one line\n\n**For Milas**\n- another\n\n## v0.9.0\n\n**For the owner**\n- old\n"
def repo(name, ver="1.2.3", changelog=None, rj=None, yanked="[]", extra=None):
    """A clone with main at a release commit of «ver», origin/main at the same place."""
    d = os.path.join(T, name); os.makedirs(os.path.join(d, "install")); g("init", "-q", "-b", "main", cwd=d)
    w = lambda p, s: (os.makedirs(os.path.dirname(os.path.join(d, p)) or d, exist_ok=True), open(os.path.join(d, p), "w", encoding="utf-8").write(s))
    w("install/get.sh", GET); w("yanked.json", "[]"); w("CHANGELOG.md", CL % "0.9.1"); w("release.json", json.dumps({"version": "0.9.1", "tag": "v0.9.1"}))
    g("add", "-A", cwd=d); g("commit", "-qm", "base", cwd=d)
    w("CHANGELOG.md", changelog if changelog is not None else CL % ver)
    w("release.json", rj if rj is not None else json.dumps({"version": ver, "tag": "v" + ver}))
    w("yanked.json", yanked)
    for p, s in (extra or {}).items(): w(p, s)
    g("add", "-A", cwd=d); g("commit", "-qm", "release v" + ver, cwd=d)
    g("update-ref", "refs/remotes/origin/main", "HEAD", cwd=d)
    return d
def gate(d, tag, main="origin/main"):
    cwd = os.getcwd(); os.chdir(d)
    try: return G.local_checks(tag, main)
    finally: os.chdir(cwd)
def refused(name, d, tag, has):
    why, notes, sha = gate(d, tag); chk(name + " — отказ", any(has in x for x in why), (why, notes))

try:
    # ── the tag and its commit
    d = repo("good"); g("tag", "-a", "v1.2.3", "-m", "Mila v1.2.3", cwd=d); head = g("rev-parse", "HEAD", cwd=d)
    why, notes, sha = gate(d, "v1.2.3")
    chk("аннотированный тег на коммите main, версия и раздел сходятся — проходит", why == [] and sha == head, why)
    chk("подпись не проверялась — сказано строкой, а не молча", any("not checked" in x for x in notes), notes)
    g("commit", "-q", "--allow-empty", "-m", "later work", cwd=d); g("update-ref", "refs/remotes/origin/main", "HEAD", cwd=d)
    chk("main ушёл вперёд, тег на прежнем его коммите — проходит", gate(d, "v1.2.3")[0] == [])
    for t in ("v1.2.3-rc1", "1.2.3", "v1.2", "release", "v1.2.3; echo x", ""):
        g("tag", "-a", t, "-m", "x", cwd=d) if t and " " not in t and ";" not in t else None
        refused("имя тега %r — не выпуск" % t, d, t, "not a release tag")
    refused("тега нет в клоне", d, "v9.9.9", "there is no tag")
    d = repo("light"); g("tag", "v1.2.3", cwd=d); refused("тег-имя без аннотации", d, "v1.2.3", "bare name")
    d = repo("side"); g("checkout", "-q", "-b", "side", cwd=d); g("commit", "-q", "--allow-empty", "-m", "side work", cwd=d); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d)
    refused("тег на коммите боковой ветки", d, "v1.2.3", "is not on origin/main")
    d = repo("orphan"); g("checkout", "-q", "--orphan", "lost", cwd=d); g("commit", "-qm", "nowhere", cwd=d); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d)
    refused("тег на коммите, которого нет ни в main, ни в его истории", d, "v1.2.3", "is not on origin/main")
    d = repo("ahead"); g("commit", "-q", "--allow-empty", "-m", "not pushed", cwd=d); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d)
    refused("тег на локальном коммите, которого ещё нет в origin/main", d, "v1.2.3", "is not on origin/main")
    d = repo("nomain"); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d); g("update-ref", "-d", "refs/remotes/origin/main", cwd=d)
    refused("в клоне нет origin/main", d, "v1.2.3", "there is no origin/main")

    # ── release.json, CHANGELOG, yanked
    d = repo("ver", rj=json.dumps({"version": "1.2.2", "tag": "v1.2.2"})); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d)
    refused("release.json говорит другую версию", d, "v1.2.3", "release.json")
    d = repo("vertag", rj=json.dumps({"version": "1.2.3", "tag": "v1.2.2"})); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d)
    refused("release.json: версия та, тег другой", d, "v1.2.3", "release.json")
    d = repo("tagver", rj=json.dumps({"version": "1.2.2", "tag": "v1.2.3"})); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d)
    refused("release.json: тег тот, версия другая", d, "v1.2.3", "release.json")
    d = repo("badjson", rj="{"); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d); refused("release.json не читается", d, "v1.2.3", "release.json")
    d = repo("nosec", changelog=CL % "1.2.2"); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d); refused("в CHANGELOG нет раздела версии", d, "v1.2.3", "no section")
    d = repo("prefix", changelog=CL % "1.2.30"); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d); refused("раздел v1.2.30 — не раздел v1.2.3", d, "v1.2.3", "no section")
    d = repo("noowner", changelog="## v1.2.3\n\n**For Milas**\n- x\n\n## v0.9.0\n\n**For the owner**\n- old\n"); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d)
    refused("в разделе нет блока для хозяина (блок соседнего раздела не в счёт)", d, "v1.2.3", "no block for the owner")
    d = repo("yank", yanked='["v1.2.3"]'); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d); refused("тег отозван (список строк)", d, "v1.2.3", "withdrawn")
    d = repo("yank2", yanked='[{"tag": "v1.2.3", "reason": "bad"}]'); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d); refused("тег отозван (список записей)", d, "v1.2.3", "withdrawn")
    d = repo("yank3"); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d)
    open(os.path.join(d, "yanked.json"), "w").write('["v1.2.3"]'); g("commit", "-qam", "yank", cwd=d); g("update-ref", "refs/remotes/origin/main", "HEAD", cwd=d)
    refused("тег отозван позже, в main (в коммите тега списка ещё не было)", d, "v1.2.3", "withdrawn")
    d = repo("yankbad", yanked="{"); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d); refused("yanked.json не читается", d, "v1.2.3", "unreadable")

    # ── the signature: the list of signers is main's, never the tag's own
    d = repo("signers"); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d)
    os.makedirs(os.path.join(d, ".github")); open(os.path.join(d, ".github", "allowed_signers"), "w").write("release@example.org ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFake\n")
    g("add", "-A", cwd=d); g("commit", "-qm", "signers", cwd=d); g("update-ref", "refs/remotes/origin/main", "HEAD", cwd=d)
    refused("в main есть список подписантов, тег без подписи (в коммите тега списка нет)", d, "v1.2.3", "no valid signature")
    d = repo("ownlist", extra={".github/allowed_signers": "x@example.org ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFake\n"})
    g("tag", "-a", "v1.2.3", "-m", "x", cwd=d); g("rm", "-q", ".github/allowed_signers", cwd=d); g("commit", "-qm", "no signers on main", cwd=d); g("update-ref", "refs/remotes/origin/main", "HEAD", cwd=d)
    why, notes, _ = gate(d, "v1.2.3"); chk("список подписантов только в коммите тега, в main его нет — берётся main: «не проверялась»", why == [] and any("not checked" in x for x in notes), (why, notes))
    if shutil.which("ssh-keygen"):
        key = os.path.join(T, "k"); subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "release@example.org", "-f", key], check=True)
        other = os.path.join(T, "o"); subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "other@example.org", "-f", other], check=True)
        pub = open(key + ".pub").read().split()
        d = repo("signed", extra={".github/allowed_signers": "release@example.org %s %s\n" % (pub[0], pub[1])})
        g("-c", "gpg.format=ssh", "-c", "user.signingkey=" + key + ".pub", "tag", "-s", "v1.2.3", "-m", "x", cwd=d)
        why, notes, _ = gate(d, "v1.2.3"); chk("тег подписан ключом из списка main — проходит, строка «valid»", why == [] and any("valid" in x for x in notes), (why, notes))
        d = repo("signed-other", extra={".github/allowed_signers": "release@example.org %s %s\n" % (pub[0], pub[1])})
        g("-c", "gpg.format=ssh", "-c", "user.signingkey=" + other + ".pub", "tag", "-s", "v1.2.3", "-m", "x", cwd=d)
        refused("тег подписан чужим ключом", d, "v1.2.3", "no valid signature")
    else:
        print("⏭  подпись ключом из списка и чужим ключом: здесь нет ssh-keygen — эти две проверки идут только там, где он есть (GitHub)")

    # ── the tests of exactly this commit
    S = "a" * 40
    class Clock:
        def __init__(self): self.t = 0.0; self.slept = 0
        def now(self): return self.t
        def sleep(self, s): self.t += s; self.slept += 1
    def tg(seq, wait=0):
        c = Clock(); it = iter(seq); last = [None]
        def runs_of(sha):
            assert sha == S
            try: last[0] = next(it)
            except StopIteration: pass
            if isinstance(last[0], Exception): raise last[0]
            return last[0]
        okk, line = G.tests_green(S, runs_of, wait, sleep=c.sleep, clock=c.now)
        return okk, line, c
    R = lambda *x: list(x)
    chk("есть успешный прогон этого коммита — да", tg([R(("completed", "success"))])[0] is True)
    okk, line, c = tg([R(("completed", "failure"))], wait=45); chk("последний прогон упал — нет, сразу, без ожидания", okk is False and "failure" in line and c.slept == 0, line)
    okk, line, c = tg([R(("completed", "cancelled"))], wait=45); chk("последний прогон отменён (очередь исполнителей) — нет, с подсказкой перезапустить", okk is False and "cancelled" in line and "rerun" in line, line)
    okk, line, c = tg([R()], wait=0); chk("прогонов по коммиту нет — нет: коммит не пушили в ветку", okk is False and "no run" in line, line)
    okk, line, c = tg([R(), R(("queued", None)), R(("in_progress", None)), R(("completed", "success"))], wait=45)
    chk("прогон ещё идёт — ворота ждут и пропускают, когда он позеленел", okk is True and c.slept == 3, (line, c.slept))
    okk, line, c = tg([R(("in_progress", None))], wait=3); chk("прогон идёт дольше срока ожидания — нет", okk is False and "still going" in line and c.slept == 3, (line, c.slept))
    okk, line, c = tg([R(("in_progress", None)), R(("completed", "failure"))], wait=45); chk("дождались — прогон упал — нет", okk is False and "failure" in line, line)
    okk, line, c = tg([R(("in_progress", None), ("completed", "success"))]); chk("идёт повторный прогон, а прежний этого же коммита зелёный — да", okk is True, line)
    okk, line, c = tg([R(("completed", "failure"), ("completed", "success"))]); chk("два прогона одного коммита, один зелёный — да (код тот же)", okk is True, line)
    okk, line, c = tg([OSError("network down")], wait=2); chk("список прогонов не читается — нет, с причиной", okk is False and "not read" in line and "network down" in line, line)
    okk, line, c = tg([OSError("flap"), R(("completed", "success"))], wait=5); chk("сеть моргнула, потом ответ — да", okk is True and c.slept == 1, line)
    okk, line, c = tg([ValueError("bad json")], wait=0); chk("ответ не разобрался — нет", okk is False, line)

    # ── main(): the reasons, one per line, and the exit code
    d = repo("cli"); g("tag", "-a", "v1.2.3", "-m", "x", cwd=d)
    def cli(*a, cwd=d):
        r = subprocess.run([sys.executable, "-I", os.path.join(H, "release_gate.py"), *a], cwd=cwd, env=ENV, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr
    rc, o = cli("v1.2.3"); chk("команда: годный тег — код 0 и строка с коммитом", rc == 0 and "✓ v1.2.3" in o and g("rev-parse", "HEAD", cwd=d) in o, o)
    rc, o = cli("v1.2.3", "--main", "main"); chk("команда: --main main — для проверки до пуша", rc == 0, o)
    g("tag", "v1.2.4", cwd=d); rc, o = cli("v1.2.4"); chk("команда: негодный тег — код 1, причины построчно, «No release»", rc == 1 and o.count("✗") >= 2 and "No release for v1.2.4" in o, o)

    # ── --tests end to end: the list of runs comes from a fake API; only runs of exactly this commit count
    import http.server, threading
    head = g("rev-parse", "HEAD", cwd=d); ANSWER = {"runs": [], "seen": []}
    class Api(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            ANSWER["seen"].append((self.path, self.headers.get("Authorization")))
            b = json.dumps({"workflow_runs": ANSWER["runs"]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Api); threading.Thread(target=srv.serve_forever, daemon=True).start()
    ENV["GITHUB_API_URL"] = "http://127.0.0.1:%d" % srv.server_port; ENV["GH_TOKEN"] = "fake-" + "t" * 8
    run = lambda sha, st, c, no: {"head_sha": sha, "status": st, "conclusion": c, "run_number": no}
    ANSWER["runs"] = [run(head, "completed", "success", 7)]
    rc, o = cli("v1.2.3", "--tests", "owner/repo"); path, auth = ANSWER["seen"][-1]
    chk("команда с --tests: зелёный прогон этого коммита — код 0, «tests green»", rc == 0 and "tests green" in o and "a successful run" in o, o)
    chk("запрос — к прогонам workflow tests по sha этого коммита, с токеном из окружения", path == "/repos/owner/repo/actions/workflows/tests.yml/runs?head_sha=%s&per_page=30" % head and auth == "Bearer fake-tttttttt", (path, auth))
    ANSWER["runs"] = [run("c" * 40, "completed", "success", 9), run(head, "completed", "failure", 8)]
    rc, o = cli("v1.2.3", "--tests", "owner/repo"); chk("зелёный прогон ЧУЖОГО коммита не в счёт, свой упал — код 1", rc == 1 and "failure" in o and "No release" in o, o)
    ANSWER["runs"] = [run(head, "completed", "failure", 3), run(head, "in_progress", None, 12)]
    rc, o = cli("v1.2.3", "--tests", "owner/repo"); chk("новейший прогон — по номеру, а не по порядку в ответе: он ещё идёт, ждать не велено — код 1", rc == 1 and "still going" in o, o)
    ANSWER["runs"] = []
    rc, o = cli("v1.2.3", "--tests", "owner/repo"); chk("прогонов нет — код 1", rc == 1 and "no run" in o, o)
    seen = len(ANSWER["seen"]); rc, o = cli("v1.2.4", "--tests", "owner/repo"); chk("негодный тег: тесты даже не спрашиваются", rc == 1 and len(ANSWER["seen"]) == seen, o)
    srv.shutdown()

    # ── the files of the release: the same bytes from the script and from the workflow
    src = os.path.join(T, "get.sh"); open(src, "w").write(GET); out = os.path.join(T, "out")
    h = F.build("v1.2.3", "b" * 40, out, src); body = open(os.path.join(out, "get.sh")).read()
    chk("get.sh выпуска: тег и коммит вписаны, остальное байт в байт", body == GET.replace('PIN_REF=""', 'PIN_REF="v1.2.3"').replace('PIN_SHA=""', 'PIN_SHA="%s"' % ("b" * 40)))
    chk("SHA256SUMS: сумма этого файла, имя как у файла выпуска", open(os.path.join(out, "SHA256SUMS")).read() == "%s  get.sh\n" % hashlib.sha256(body.encode()).hexdigest() == "%s  get.sh\n" % h)
    for name, a in (("тег не vX.Y.Z", ("v1.2", "b" * 40)), ("предвыпуск", ("v1.2.3-rc1", "b" * 40)), ("короткий sha", ("v1.2.3", "b" * 12)), ("sha не из шестнадцатеричных", ("v1.2.3", "g" * 40))):
        try: F.build(a[0], a[1], out, src); chk("сборщик: %s — отказ" % name, False)
        except SystemExit: chk("сборщик: %s — отказ" % name, True)
    open(src, "w").write(GET.replace('PIN_SHA=""', 'PIN_SHA="x"'))
    try: F.build("v1.2.3", "b" * 40, out, src); chk("сборщик: в get.sh уже что-то вписано — отказ", False)
    except SystemExit: chk("сборщик: в get.sh уже что-то вписано — отказ", True)
    real = open(os.path.join(REPO, "install", "get.sh"), encoding="utf-8").read()
    chk("настоящий install/get.sh годится сборщику: по одной пустой строке PIN_REF и PIN_SHA", real.count('\nPIN_REF=""\n') == 1 and real.count('\nPIN_SHA=""\n') == 1)
    rs = open(os.path.join(REPO, "tools", "release.sh"), encoding="utf-8").read()
    chk("release.sh собирает файлы тем же сборщиком и режет выпуск только с main", 'python3 tools/release_files.py "v$V" "$SHA" "$D"' in rs and "import hashlib" not in rs and '--abbrev-ref HEAD)" = main ]' in rs)
finally:
    shutil.rmtree(T, ignore_errors=True)
print("итог %d/%d" % (ok, n)); sys.exit(0 if ok == n else 1)
