#!/usr/bin/env python3
"""hod-stream.py: the work progress stream. A fake Telegram API on a local port records every request; the hook runs as a subprocess
in a sandbox (its own state folder and config dir). Checks: the secret mask, the switch (flag file and /hod commands), nothing
leaves when the turn is not from the owner's private chat, one message that is edited (not a new one), the cut of long output,
a dead network does not break the hook, the bot token never reaches the state file, a message or the output."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

H = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(H, "hod-stream.py")
ok = n = 0
OWNER = "555" + "000111"
GUEST = "555" + "000222"
GROUP = "-100" + "12345" + "67890"
TOKEN = "123456789" + ":" + "AAH" + "x" * 20 + "Y" * 17   # a made-up token of the real shape, glued
REQS = []


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        p = {k: v[0] for k, v in parse_qs(body).items()}
        method = self.path.rsplit("/", 1)[-1]
        REQS.append((method, p, self.path))
        out = {"ok": True, "result": {"message_id": 777}}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(out).encode())


srv = HTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
API = "http://127.0.0.1:%d" % srv.server_port


def chk(name, c, x=""):
    global ok, n
    n += 1
    ok += bool(c)
    print(("✅ " if c else "❌ ") + name + ("" if c else "  ← " + str(x)[:300]))


SB = tempfile.mkdtemp()
STATE = os.path.join(SB, "state")
CFG = os.path.join(SB, "cfg")
os.makedirs(STATE)
os.makedirs(CFG)
open(os.path.join(STATE, ".env"), "w").write("TELEGRAM_BOT_TOKEN=%s\n" % TOKEN)
json.dump({"allowFrom": [OWNER]}, open(os.path.join(STATE, "access.json"), "w"))


def transcript(chat, uuid="u1", text="do it", assistant=""):
    p = os.path.join(SB, "t-%s-%s.jsonl" % (chat or "term", uuid))
    body = ('<channel source="telegram" chat_id="%s" message_id="5" user="X" ts="t">%s</channel>' % (chat, text)) if chat else text
    rows = [{"type": "user", "uuid": uuid, "message": {"content": body}}]
    if assistant:
        rows.append({"type": "assistant", "message": {"content": [{"type": "text", "text": assistant}]}})
    open(p, "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def run(ev, env_extra=None, api=None, stdin=None):
    env = {**os.environ, "TELEGRAM_STATE_DIR": STATE, "CLAUDE_CONFIG_DIR": CFG, "OWNER_ID": OWNER, "MILA_TG_API": api or API,
           "MILA_LANG": "en", "MILA_HOD_GAP": "0", "HOME": SB, **(env_extra or {})}
    t0 = time.time()
    r = subprocess.run([sys.executable, HOOK], input=stdin if stdin is not None else json.dumps(ev), capture_output=True, text=True,
                       env=env, timeout=30)
    return r, time.time() - t0


def pre(tp, tool="Bash", ti=None, sid="s1"):
    return {"hook_event_name": "PreToolUse", "session_id": sid, "transcript_path": tp, "tool_name": tool, "tool_input": ti or {}}


def post(tp, tool="Bash", resp=None, sid="s1"):
    return {"hook_event_name": "PostToolUse", "session_id": sid, "transcript_path": tp, "tool_name": tool, "tool_response": resp or {}}


def stop(tp, sid="s1"):
    return {"hook_event_name": "Stop", "session_id": sid, "transcript_path": tp}


def reset():
    del REQS[:]
    for f in os.listdir(STATE):
        if f.startswith("hod"):
            os.unlink(os.path.join(STATE, f))


# ── the mask ────────────────────────────────────────────────────────────────
spec = importlib.util.spec_from_file_location("hod_stream", HOOK)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SK = "sk" + "-or-v1-" + "a1b2c3d4e5f6a7b8c9d0"
m = mod.mask("token " + TOKEN + " end")
chk("mask: a bot token becomes dots", TOKEN not in m and "•••" in m, m)
m = mod.mask("key " + SK)
chk("mask: an sk- key becomes dots", "a1b2c3d4" not in m and "•••" in m, m)
m = mod.mask("export API_" + "KE" + "Y=hunter2value and PASS" + "WOR" + "D=abc123 TO" + "KEN: xyz SEC" + "RE" + "T='top secret'")
chk("mask: values after KEY= PASSWORD= TOKEN= SECRET= become dots, names stay",
    all(v not in m for v in ("hunter2value", "abc123", "xyz", "top secret")) and "API_KEY=•••" in m, m)
m = mod.mask("hash " + "ab12cd34" * 5 + " end")
chk("mask: a long hex string becomes dots", "ab12cd34ab12" not in m, m)
m = mod.mask("blob " + "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo" * 2 + "== end")
chk("mask: a long base64 string becomes dots", "QUJDREVG" not in m, m)
chk("mask: ordinary words stay", mod.mask("running the tests in the project") == "running the tests in the project")

# ── whose turn ──────────────────────────────────────────────────────────────
reset()
tp = transcript(OWNER)
r, _ = run(pre(tp, ti={"description": "checking the build"}))
chk("owner's private chat: the first step is sent (sendMessage, to the owner, MarkdownV2)",
    r.returncode == 0 and r.stdout == "" and len(REQS) == 1 and REQS[0][0] == "sendMessage" and REQS[0][1]["chat_id"] == OWNER
    and REQS[0][1]["parse_mode"] == "MarkdownV2" and "checking the build" in REQS[0][1]["text"], (r.returncode, r.stdout, REQS))
for label, tpx in (("a group", transcript(GROUP, "g1")), ("another private chat (a guest)", transcript(GUEST, "g2")),
                   ("a terminal turn (no chat at all)", transcript(None, "g3"))):
    reset()
    r, _ = run(pre(tpx, ti={"description": "x"}))
    chk("nothing leaves for %s" % label, r.returncode == 0 and REQS == [] and not os.path.exists(os.path.join(STATE, "hod-stream.json")), REQS)
reset()
mixed = os.path.join(SB, "mixed.jsonl")
open(mixed, "w").write(json.dumps({"type": "user", "uuid": "m1", "message": {"content": '<channel chat_id="%s">a</channel>\n<channel chat_id="%s">b</channel>' % (OWNER, GROUP)}}) + "\n")
r, _ = run(pre(mixed, ti={"description": "x"}))
chk("a batch with the owner AND a group message: nothing leaves", REQS == [], REQS)
reset()
r, _ = run(pre(tp, ti={"description": "x"}), env_extra={"OWNER_ID": ""})
chk("no OWNER_ID but one person in allowFrom: he is the owner", len(REQS) == 1, REQS)
reset()
json.dump({"allowFrom": [OWNER, GUEST]}, open(os.path.join(STATE, "access.json"), "w"))
r, _ = run(pre(tp, ti={"description": "x"}), env_extra={"OWNER_ID": ""})
chk("two people in allowFrom and no OWNER_ID: the owner is unknown, nothing leaves", REQS == [], REQS)
json.dump({"allowFrom": [OWNER]}, open(os.path.join(STATE, "access.json"), "w"))
reset()
r, _ = run({**pre(tp, ti={"description": "x"}), "agent_id": "a1"})
chk("a step of a helper (sub-agent) is not shown", REQS == [], REQS)
reset()
r, _ = run(pre(tp, tool="mcp__plugin_telegram_telegram__reply", ti={"text": "hi"}))
chk("Mila's own reply tool is not shown as a step", REQS == [], REQS)

# ── one message, edited in place ────────────────────────────────────────────
reset()
tp = transcript(OWNER, "turn1", assistant="All done. " + "The summary of the turn is here. " * 4)
run(pre(tp, ti={"description": "step one"}))
run(post(tp, resp={"stdout": "first result line\nsecond"}))
run(pre(tp, ti={"description": "step two"}))
run(pre(tp, tool="Read", ti={"file_path": "/home/someone/private/notes.txt"}))
kinds = [q[0] for q in REQS]
chk("one send, then edits of the same message (message_id from the first reply)",
    kinds[0] == "sendMessage" and kinds.count("sendMessage") == 1 and len(kinds) == 4 and all(q[1].get("message_id") == "777" for q in REQS[1:] if q[0] == "editMessageText"), kinds)
last = REQS[-1][1]["text"]
chk("the current step is shown, earlier steps and the result of a step are in the quote",
    "reading a file" in last and "step two" in last and "first result line" in last and "**>" in last, last)
chk("a path of the tool input is not shown", "someone" not in last and "notes.txt" not in last, last)
run(stop(tp))
fin = REQS[-1]
chk("Stop edits the same message: Done, the steps and the turn summary in an expandable quote",
    fin[0] == "editMessageText" and "Done" in fin[1]["text"] and "Turn summary" in fin[1]["text"] and fin[1]["text"].count("**>") == 2
    and fin[1]["text"].rstrip().endswith("||") and "The summary of the turn" in fin[1]["text"], fin[1]["text"])
cnt = len(REQS)
run(stop(tp))
chk("a second Stop of the same turn does nothing", len(REQS) == cnt)
tp2 = transcript(OWNER, "turn2")
run(pre(tp2, ti={"description": "new turn"}))
chk("the owner's next turn starts a NEW message", REQS[-1][0] == "sendMessage" and "new turn" in REQS[-1][1]["text"], REQS[-1])

# ── throttle: two quick edits inside the gap are one request ────────────────
reset()
tp = transcript(OWNER, "turn3")
run(pre(tp, ti={"description": "a"}), env_extra={"MILA_HOD_GAP": "30"})
run(pre(tp, ti={"description": "b"}), env_extra={"MILA_HOD_GAP": "30"})
chk("edits inside the minimum gap are held back (one request), the step is kept for the next one", len(REQS) == 1, REQS)

# ── the cut of long output ──────────────────────────────────────────────────
reset()
tp = transcript(OWNER, "turn4", assistant="Z" * 9000 + " tail")
run(pre(tp, ti={"description": "D" * 900}))
run(post(tp, resp={"stdout": "R" * 5000}))
for i in range(40):
    run(pre(tp, ti={"description": "step number %d with some words in it" % i}))
run(stop(tp))
lens = [len(q[1]["text"]) for q in REQS]
chk("every message stays under the Telegram limit (4096), the long summary and 40 steps included", max(lens) <= 4096, max(lens))
chk("a long result line is cut", "R" * 91 not in "".join(q[1]["text"] for q in REQS) and "D" * 151 not in "".join(q[1]["text"] for q in REQS))

# ── secrets in what leaves ──────────────────────────────────────────────────
reset()
tp = transcript(OWNER, "turn5", assistant="The key is " + SK + " and the token " + TOKEN + " as agreed with the owner today.")
run(pre(tp, ti={"description": "calling the API with " + SK + " and API_" + "KE" + "Y=hunter2value"}))
run(post(tp, resp={"stdout": "token " + TOKEN}))
run(stop(tp))
alltext = "".join(q[1].get("text", "") for q in REQS)
chk("secrets of a description, a result and a summary are masked in every message",
    all(s not in alltext for s in (SK, TOKEN, "hunter2value", "a1b2c3d4")) and "•••" in alltext, alltext)

# ── the token never leaves except in the request path ───────────────────────
st = open(os.path.join(STATE, "hod-stream.json")).read()
chk("the bot token is not in the state file", TOKEN not in st and "AAH" not in st, st[:200])
chk("the bot token is not in any message text or body field", all(TOKEN not in json.dumps(q[1]) for q in REQS))
r, _ = run(pre(tp, ti={"description": "x"}))
chk("the bot token is not in stdout or stderr of the hook", TOKEN not in r.stdout + r.stderr)
mode = os.stat(os.path.join(STATE, "hod-stream.json")).st_mode & 0o777
chk("the state file is closed to others (600)", mode == 0o600, oct(mode))

# ── the switch ──────────────────────────────────────────────────────────────
reset()
tp = transcript(OWNER, "turn6")
open(os.path.join(STATE, "hod.off"), "w").write("off\n")
r, _ = run(pre(tp, ti={"description": "x"}))
chk("flag file hod.off: nothing is sent", r.returncode == 0 and REQS == [], REQS)
os.unlink(os.path.join(STATE, "hod.off"))


def prompt(chat, text):
    return {"hook_event_name": "UserPromptSubmit", "session_id": "s1",
            "prompt": '<channel source="telegram" chat_id="%s" message_id="9" user="X" ts="t">%s</channel>' % (chat, text)}


r, _ = run(prompt(OWNER, "/hod off"))
ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""
chk("owner's /hod off in his private chat: flag created, Mila gets a note to confirm", os.path.exists(os.path.join(STATE, "hod.off")) and "OFF" in ctx, (r.stdout, r.stderr))
r, _ = run(prompt(GROUP, "/hod on"))
chk("/hod on from a group is ignored (flag stays, silence)", os.path.exists(os.path.join(STATE, "hod.off")) and r.stdout == "")
r, _ = run(prompt(GUEST, "/hod on"))
chk("/hod on from another private chat is ignored", os.path.exists(os.path.join(STATE, "hod.off")) and r.stdout == "")
r, _ = run(prompt(OWNER, "/hod status"))
chk("/hod status says it is off", "OFF" in r.stdout, r.stdout)
r, _ = run(prompt(OWNER, "/hod on"))
chk("owner's /hod on: flag removed", not os.path.exists(os.path.join(STATE, "hod.off")) and "ON" in r.stdout, r.stdout)
r, _ = run(prompt(OWNER, "please switch hod off when you can"))
chk("an ordinary sentence is not a command", r.stdout == "" and not os.path.exists(os.path.join(STATE, "hod.off")))
r = subprocess.run([sys.executable, os.path.join(H, "..", "..", "..", "..", "skills", "hod", "hod.py"), "off"], capture_output=True, text=True,
                   env={**os.environ, "TELEGRAM_STATE_DIR": STATE})
off_ok = r.stdout.strip() == "off" and os.path.exists(os.path.join(STATE, "hod.off"))
r = subprocess.run([sys.executable, os.path.join(H, "..", "..", "..", "..", "skills", "hod", "hod.py"), "on"], capture_output=True, text=True,
                   env={**os.environ, "TELEGRAM_STATE_DIR": STATE})
chk("skills/hod/hod.py off|on switches the same flag file", off_ok and r.stdout.strip() == "on" and not os.path.exists(os.path.join(STATE, "hod.off")))

# ── language of the owner ───────────────────────────────────────────────────
reset()
tp = transcript(OWNER, "turn7")
run(pre(tp, ti={"description": "step"}), env_extra={"MILA_LANG": "ru"})
chk("the words around the steps are in the owner's language (ru)", "Работаю" in REQS[0][1]["text"], REQS)

# ── the network ─────────────────────────────────────────────────────────────
reset()
tp = transcript(OWNER, "turn8")
r, dt = run(pre(tp, ti={"description": "x"}), api="http://127.0.0.1:9")
chk("a dead network: code 0, empty stdout, no traceback, fast", r.returncode == 0 and r.stdout == "" and r.stderr == "" and dt < 10, (r.returncode, r.stderr, dt))
r, dt = run(pre(tp, ti={"description": "y"}), api="http://127.0.0.1:9")
chk("after a failure the hook is quiet for a while (no new attempt on the next step)", r.returncode == 0 and dt < 3, dt)
for bad in ("{oops", "", "[]", "null"):
    r, _ = run(None, stdin=bad)
    chk("bad input %r: code 0, empty stdout" % bad, r.returncode == 0 and r.stdout == "" and REQS == [], (r.returncode, r.stdout))
shutil.rmtree(SB, ignore_errors=True)
print("итог %d/%d" % (ok, n))
sys.exit(0 if ok == n else 1)
