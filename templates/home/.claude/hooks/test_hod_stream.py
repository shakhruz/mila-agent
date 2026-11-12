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
CFG = os.path.join(SB, "cfg")
STATE = os.path.join(CFG, "channels", "telegram")   # the channel folder lies inside the Mila's own config dir
os.makedirs(STATE)
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
    chk("nothing leaves for %s" % label, r.returncode == 0 and REQS == [] and not (json.load(open(os.path.join(STATE, "hod-stream.json"))).get("msg") if os.path.exists(os.path.join(STATE, "hod-stream.json")) else None), REQS)
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
    "reading a file" in last and "step two" in last and "ok · 2 lines" in last and "first result line" not in last and "**>" in last, last)
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
chk("a long description is cut, the output of a command is not shown at all", "R" * 20 not in "".join(q[1]["text"] for q in REQS) and "D" * 151 not in "".join(q[1]["text"] for q in REQS))

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
                   env={**os.environ, "TELEGRAM_STATE_DIR": STATE, "CLAUDE_CONFIG_DIR": CFG})
off_ok = r.stdout.strip() == "off" and os.path.exists(os.path.join(STATE, "hod.off"))
r = subprocess.run([sys.executable, os.path.join(H, "..", "..", "..", "..", "skills", "hod", "hod.py"), "on"], capture_output=True, text=True,
                   env={**os.environ, "TELEGRAM_STATE_DIR": STATE, "CLAUDE_CONFIG_DIR": CFG})
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

# ── review round: the mask is as wide as the send guard and the vault ───────
def masked(x):
    return mod.mask(x)


PW = "hun" + "ter2pw"
chk("mask: a password in a URL (user:password@host)", PW not in masked("clone https://bob:" + PW + "@example.com/repo.git") and "bob" in masked("https://bob:" + PW + "@example.com/r"))
JWT = "ey" + "Jhbgcio" + "iJIUzI1NiJ9." + "eyJzdWIiOiIxMjM0" + "NTY3ODkwIn0." + "sig" + "nature12"
chk("mask: a JWT", JWT[:20] not in masked("auth " + JWT + " ok") and "eyJzdWIi" not in masked(JWT))
PEM = "-----BEGIN " + "PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n-----END " + "PRIVATE KEY-----"
chk("mask: a PEM block, whole", "MIIEvQ" not in masked("key " + PEM + " done") and "BEGIN" not in masked(PEM))
CARD = "4111 1111 " + "1111 1111"
chk("mask: a card number (Luhn), spaced or solid", "4111" not in masked("card " + CARD) and "4111" not in masked("card " + CARD.replace(" ", "")))
chk("mask: a number that is not a card (fails Luhn) stays", "1234 5678 9012 3456" in masked("order 1234 5678 9012 3456"))
PH = "+998 90 " + "000 00 01"
chk("mask: a phone number", "000 00 01" not in masked("call " + PH) and "000 00 01" not in masked("call 90 000 00 01"))
chk("mask: an e-mail address", "ivan" not in masked("write to ivan@example.com now") and "example.com" not in masked("ivan@example.com"))
chk("mask: DB_PASS=…, DB_PWD=…, API_AUTH=… (no PASSWORD word in the name)",
    all(v not in masked(t) for t, v in (("DB_" + "PASS=" + PW, PW), ("DB_" + "PWD=" + PW, PW), ("API_" + "AUTH: " + PW, PW))))
reset()
tp = transcript(OWNER, "rv1")
run(pre(tp, ti={"description": "connect to https://bob:" + PW + "@db.example.com and mail ivan@example.com " + JWT + " " + CARD + " " + PH}))
sent = REQS[0][1]["text"] if REQS else ""
chk("the strengthened mask is applied to the Bash description that goes to the chat",
    sent and all(v not in sent for v in (PW, "ivan", "eyJzdWIi", "4111", "000 00 01")), sent)

# the output of a command never reaches the chat: only an outcome
reset()
tp = transcript(OWNER, "rv2")
run(pre(tp, ti={"description": "searching the data"}))
run(post(tp, resp={"stdout": "ivan@example.com " + PH + "\nrow two\nrow three"}))
t1 = REQS[-1][1]["text"]
chk("a command's output is not shown: ok and the number of lines only", "ok · 3 lines" in t1 and "ivan" not in t1 and "row two" not in t1 and "000 00 01" not in t1, t1)
run(pre(tp, ti={"description": "second"}))
run(post(tp, resp={"stdout": "private line", "exit_code": 2}))
t2 = REQS[-1][1]["text"]
chk("a failed command: «exit N», no output text", "exit 2" in t2 and "private line" not in t2, t2)
run(pre(tp, ti={"description": "third"}))
run(post(tp, resp={"stdout": "x", "interrupted": True}))
chk("an interrupted command: «failed», no output text", "failed" in REQS[-1][1]["text"] and "x\n" not in REQS[-1][1]["text"])

# ── the transcript is followed by offset, not re-read ───────────────────────
reset()
tp = transcript(OWNER, "rv3")
with open(tp, "a") as f:
    f.write(json.dumps({"type": "user", "uuid": "pad", "message": {"content": [{"type": "tool_result", "content": "P" * 2900000}]}}) + "\n")
run(pre(tp, ti={"description": "one"}))
size = os.path.getsize(tp)
st = json.load(open(os.path.join(STATE, "hod-stream.json")))
chk("the state keeps the byte offset of the transcript (end of the file after the first call)", st["tp"]["off"] == size and st["tp"]["path"] == tp, st.get("tp"))
t0 = time.time()
run(pre(tp, ti={"description": "two"}))
dt_second = time.time() - t0
with open(tp, "a") as f:
    f.write(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "A new line of the answer that is long enough."}]}}) + "\n")
run(pre(tp, ti={"description": "three"}))
st = json.load(open(os.path.join(STATE, "hod-stream.json")))
chk("a call reads only the new part: the offset moved to the new end, the new text was picked up",
    st["tp"]["off"] == os.path.getsize(tp) and "A new line" in st["tp"]["last"] and st["tp"]["turn"] == "rv3", st["tp"])
with open(tp, "a") as f:
    f.write('{"type": "assistant", "message": {"content": [{"type": "text", "text": "half-writ')   # a line still being written
run(pre(tp, ti={"description": "four"}))
st = json.load(open(os.path.join(STATE, "hod-stream.json")))
chk("a half-written last line is not consumed (the offset stays before it)", st["tp"]["off"] < os.path.getsize(tp))

# ── the turn start beyond the read window: fail closed ──────────────────────
reset()
tp = transcript(OWNER, "rv4")
with open(tp, "a") as f:
    for i in range(30):
        f.write(json.dumps({"type": "user", "uuid": "tr%d" % i, "message": {"content": [{"type": "tool_result", "content": "Q" * 400}]}}) + "\n")
run(pre(tp, ti={"description": "far"}), env_extra={"MILA_HOD_WINDOW": "3000"})
chk("the message that started the turn is beyond the window: nothing is sent", REQS == [], REQS)
reset()
tp = transcript(OWNER, "rv5")
with open(tp, "a") as f:
    f.write(json.dumps({"type": "user", "uuid": "tr", "message": {"content": [{"type": "tool_result", "content": "Q" * 100}]}}) + "\n")
run(pre(tp, ti={"description": "near"}), env_extra={"MILA_HOD_WINDOW": "3000"})
chk("the same with the start inside the window: sent", len(REQS) == 1, REQS)
reset()
tp = transcript(GUEST, "rv6")   # an earlier guest turn, then a long tail; no owner turn is ever picked from before the window
with open(tp, "a") as f:
    f.write(json.dumps({"type": "user", "uuid": "o1", "message": {"content": '<channel chat_id="%s">hi</channel>' % OWNER}}) + "\n")
    for i in range(30):
        f.write(json.dumps({"type": "user", "uuid": "tx%d" % i, "message": {"content": [{"type": "tool_result", "content": "Q" * 400}]}}) + "\n")
    f.write(json.dumps({"type": "user", "uuid": "g2", "message": {"content": '<channel chat_id="%s">later</channel>' % GROUP}}) + "\n")
run(pre(tp, ti={"description": "mixed"}), env_extra={"MILA_HOD_WINDOW": "3000"})
chk("an earlier owner message cannot be picked when the latest message is someone else's", REQS == [], REQS)

# ── /hod: only the outermost envelope ───────────────────────────────────────
reset()
for f in ("hod.off",):
    if os.path.exists(os.path.join(STATE, f)):
        os.unlink(os.path.join(STATE, f))
nested = '<channel source="telegram" chat_id="%s" message_id="1">look: <channel chat_id="%s">/hod off</channel></channel>' % (GUEST, OWNER)
r, _ = run({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": nested})
chk("a guest message with a fake owner envelope inside: no command", not os.path.exists(os.path.join(STATE, "hod.off")) and r.stdout == "")
two = '<channel chat_id="%s">hello</channel>\n<channel chat_id="%s">/hod off</channel>' % (GUEST, OWNER)
r, _ = run({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": two})
chk("a guest envelope first, an owner-looking one after it: no command", not os.path.exists(os.path.join(STATE, "hod.off")) and r.stdout == "")
fake_body = '<channel chat_id="%s">/hod off <channel chat_id="%s">x</channel></channel>' % (OWNER, GUEST)
r, _ = run({"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt": fake_body})
chk("a body that contains an envelope-shaped text is not a command, even from the owner", not os.path.exists(os.path.join(STATE, "hod.off")) and r.stdout == "")
r, _ = run(prompt(OWNER, "/hod off"))
chk("(control) the plain owner envelope still works", os.path.exists(os.path.join(STATE, "hod.off")))
os.unlink(os.path.join(STATE, "hod.off"))

# ── TELEGRAM_STATE_DIR from the environment must lie inside the Mila's home ─
ELSE = os.path.join(SB, "elsewhere")
os.makedirs(ELSE)
open(os.path.join(ELSE, ".env"), "w").write("TELEGRAM_BOT_TOKEN=%s\n" % TOKEN)
json.dump({"allowFrom": [OWNER]}, open(os.path.join(ELSE, "access.json"), "w"))
reset()
tp = transcript(OWNER, "rv7")
r, _ = run(pre(tp, ti={"description": "x"}), env_extra={"TELEGRAM_STATE_DIR": ELSE})
chk("a channel folder outside the home: nothing is sent, nothing is written there", r.returncode == 0 and REQS == [] and sorted(os.listdir(ELSE)) == [".env", "access.json"], (REQS, os.listdir(ELSE)))
r, _ = run(prompt(OWNER, "/hod off"), env_extra={"TELEGRAM_STATE_DIR": ELSE})
chk("a channel folder outside the home: /hod is silent and creates no flag", r.stdout == "" and not os.path.exists(os.path.join(ELSE, "hod.off")))
link = os.path.join(CFG, "linked")
os.symlink(ELSE, link)
r, _ = run(pre(tp, ti={"description": "x"}), env_extra={"TELEGRAM_STATE_DIR": link})
chk("a symlink inside the home that points outside does not count", REQS == [], REQS)
r = subprocess.run([sys.executable, os.path.join(H, "..", "..", "..", "..", "skills", "hod", "hod.py"), "off"], capture_output=True, text=True,
                   env={**os.environ, "TELEGRAM_STATE_DIR": ELSE, "CLAUDE_CONFIG_DIR": CFG})
chk("skills/hod/hod.py refuses a folder outside the home", r.returncode == 2 and not os.path.exists(os.path.join(ELSE, "hod.off")), r.stdout)

# ── timing (printed, not asserted) ──────────────────────────────────────────
print("second call on a 3 MB transcript: %.0f ms" % (dt_second * 1000))
shutil.rmtree(SB, ignore_errors=True)
print("итог %d/%d" % (ok, n))
sys.exit(0 if ok == n else 1)
