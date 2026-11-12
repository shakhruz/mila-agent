#!/usr/bin/env python3
"""hod-stream.py: the work progress stream. While Mila works on a turn the owner started in his private chat, one Telegram
message in that chat shows what she is doing right now, and it is edited in place (never a feed of messages):
  PreToolUse     the step, in human words (a Bash step: its description; any other tool: a short phrase by tool kind,
                 never a raw command or a path)
  PostToolUse    a one-line result of the step (Bash only), cut short
  Stop           the message becomes "Done" and gets a collapsed quote with the turn summary (MarkdownV2 expandable quote)
  UserPromptSubmit   the owner's command in his private chat: /hod on | /hod off | /hod status

On by default. Off: the flag file `hod.off` in the channel state folder (the same folder as the bot token and access.json).
Goes ONLY to the owner's private chat, and only for a turn that came from that chat: a group, a guest, a client, a scheduled
turn or a terminal turn never produce a message. The bot token is read from the channel folder and is never printed, never
written to the state file, never put in a message. Everything that leaves is passed through a secret mask first.
Any failure (network, bad input, any exception) is silent: the hook always ends with code 0 and prints nothing to stdout,
except the one-line context after an owner command. Standard library only."""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CLAUDE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def _inside(path, base):
    try:
        a, b = os.path.realpath(path), os.path.realpath(base)
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False


# The channel folder counts only when it lies inside this Mila's own config dir (the rule install/mila applies to the birth page):
# a TELEGRAM_STATE_DIR left in the shell by another Mila must not point the hook at someone else's token. Otherwise: silence.
STATE_DIR = os.environ.get("TELEGRAM_STATE_DIR") or os.path.join(CLAUDE, "channels", "telegram")
STATE_OK = _inside(STATE_DIR, CLAUDE)
API = os.environ.get("MILA_TG_API", "https://api.telegram.org")
TIMEOUT = 4          # seconds for one request
MIN_EDIT_GAP = float(os.environ.get("MILA_HOD_GAP", "1.5"))   # seconds between two edits of the same message (Telegram flood limits)
BACKOFF = 60         # seconds without trying after a failed request
MAX_STEPS = 60
SHOWN_STEPS = 22
WINDOW = int(os.environ.get("MILA_HOD_WINDOW", "3000000"))   # bytes of transcript read the first time
LIMIT = 3900         # characters of the final MarkdownV2 text (Telegram allows 4096)

OFF_NAME = "hod.off"
STATE_NAME = "hod-stream.json"

# Embedded English defaults: used when the locale files are not next to the hook (the real strings live in locales/*.json).
DEFAULTS = {
    "hod.working": "Working", "hod.done": "Done", "hod.step": "step {n}", "hod.steps": "{n} steps", "hod.min": "{n} min",
    "hod.summary": "Turn summary",
    "hod.on": "The work progress stream is ON: while I work you see what I am doing in one message that updates.",
    "hod.off": "The work progress stream is OFF. Turn it on again with /hod on.",
    "hod.status_on": "The work progress stream is ON. Switch it off with /hod off.",
    "hod.status_off": "The work progress stream is OFF. Switch it on with /hod on.",
    "hod.tool.bash": "running a command", "hod.tool.agent": "a helper is working", "hod.tool.skill": "skill {name}",
    "hod.tool.write": "writing a file", "hod.tool.edit": "editing a file", "hod.tool.read": "reading a file",
    "hod.tool.files": "searching files", "hod.tool.search": "searching the web", "hod.tool.fetch": "reading a page",
    "hod.tool.plan": "planning the steps", "hod.tool.browser": "working in the browser", "hod.tool.service": "using a connected service",
    "hod.tool.other": "working",
    "hod.res.ok": "ok · {n} lines", "hod.res.exit": "exit {n}", "hod.res.fail": "failed",
}

_I18N = None


def _load_i18n():
    """(mila_i18n module, locales dict, language) or None. The strings are skills/hod/locales/*.json; the loader mila_i18n.py is
    next to the hook (installed) or in the repository's install/ folder."""
    global _I18N
    if _I18N is not None:
        return _I18N or None
    _I18N = False
    repo = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
    mods = [d for d in (HERE, os.path.join(repo, "install")) if os.path.isfile(os.path.join(d, "mila_i18n.py"))]
    locs = [os.environ.get("MILA_LOCALES") or "", os.path.join(CLAUDE, "skills", "hod", "locales"),
            os.path.join(repo, "skills", "hod", "locales")]
    locs = [d for d in locs if d and os.path.isdir(d)]
    if mods and locs:
        try:
            sys.path.insert(0, mods[0])
            import mila_i18n
            loc = mila_i18n.load(locs[0])
            lang = None if os.environ.get("MILA_LANG") else mila_i18n.owner_lang(loc, os.path.expanduser("~"))
            lang = lang or mila_i18n.pick(loc, os.environ.get("MILA_LANG"), os.environ.get("LC_ALL"), os.environ.get("LANG"))
            _I18N = (mila_i18n, loc, lang)
        except Exception:
            _I18N = False
    return _I18N or None


def L(key, **kw):
    i = _load_i18n()
    s = None
    if i:
        try:
            s = i[0].t(i[1], i[2], key, **kw)
            if s == key:
                s = None
        except Exception:
            s = None
    if s is None:
        s = DEFAULTS.get(key, key)
        try:
            s = s.format(**kw) if kw else s
        except Exception:
            pass
    return s


# ── masking ─────────────────────────────────────────────────────────────────
# Same coverage as the send guard (keys, tokens) and the personal-data vault (card, phone, e-mail, PINFL): the patterns are copied
# from templates/home/.claude/hooks/send-guard.py (SECRETS, card by Luhn) and skills/pd-vault/pd_vault.py (PAT), because a hook is a
# single installed file and cannot import a skill. Plus what those two do not see in a step text: a password in a URL, a JWT, a PEM block.
DOTS = "•••"
_LUHN_RX = re.compile(r"(?<!\d)(?:\d{4}[ -]?){3}\d{4}(?!\d)|(?<![\d+])(?:\d[ -]?){12,}\d(?!\d)")
_PHONE_RX = [
    re.compile(r"(?<![\w+])(?:\+?998[ -]?\(?\d{2}\)?|\+\d{1,3}[ -]?\(?\d{2,4}\)?|\b8[ -]?\(?\d{3}\)?)[ -]?\d{2,3}[ -]?\d{2}[ -]?\d{2,3}(?!\d)"),
    re.compile(r"(?<![\w+])\(?(?:20|33|50|55|6[1-9]|7[0-9]|88|9[0-9])\)?[ -]\d{3}[ -]?\d{2}[ -]?\d{2}(?!\d)"),
]
_PHONE_CTX = re.compile(r"(?i)(?:тел|номер|phone|tel|nomer|raqam|звон|позвон|whats\s?app|ватсап|вотсап|aloqa\s+uchun|qo['ʻ’]ng['ʻ’]iroq)\w*"
                        r"(?:[ \t]+[^\W\d]+){0,3}?[:.]?[ \t]*(?P<v>\d{9})(?!\d)")
_MASKS = [
    re.compile(r"-----BEGIN [A-Z0-9 ]+-----[\s\S]*?(?:-----END [A-Z0-9 ]+-----|$)"),     # PEM blocks (keys, certificates)
    re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]*"),            # JWT
    re.compile(r"\b\d{5,}:[A-Za-z0-9_-]{30,}"),                                        # bot tokens
    re.compile(r"\b(?:sk|pk)[-_][A-Za-z0-9_-]{8,}"),                                   # provider keys
    re.compile(r"\b(?:gh[pous]_|xox[baprs]-|AK" + r"IA|cmp_)[A-Za-z0-9-]{10,}"),             # GitHub, Slack, AWS, API
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),                           # e-mail
    re.compile(r"(?<!\d)[3-6]\d{13}(?!\d)"),                                           # PINFL
] + _PHONE_RX + [
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),                                               # long hex
    re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),                                           # long base64
    re.compile(r"\b[A-Za-z0-9_-]{36,}\b"),                                             # any long opaque string
]
_URLCRED = re.compile(r"(\b[A-Za-z][A-Za-z0-9+.-]*://[^\s:/@]*:)[^\s@/]+(@)")        # scheme://user:password@host
_ASSIGN = re.compile(r"(?i)(\b[\w.-]*(?:KEY|TOKEN|PASS|PWD|SECRET|CRED|AUTH|PRIVATE|DSN)[\w.-]*\s*[=:]\s*)(?:\"[^\"]*\"|'[^']*'|\S+)")
_PATH = re.compile(r"(?:~|/)[\w.\-@+]*(?:/[\w.\-@+]+){2,}")


def _luhn(d):
    t = 0
    for i, ch in enumerate(reversed(d)):
        x = int(ch)
        if i % 2:
            x = x * 2 - 9 if x > 4 else x * 2
        t += x
    return t % 10 == 0


def _card(m):
    d = re.sub(r"\D", "", m.group(0))
    return DOTS if 13 <= len(d) <= 19 and len(set(d)) > 1 and _luhn(d) else m.group(0)


def mask(s):
    s = str(s)
    s = _URLCRED.sub(lambda m: m.group(1) + DOTS + m.group(2), s)
    s = _ASSIGN.sub(lambda m: m.group(1) + DOTS, s)
    for rx in _MASKS[:7]:
        s = rx.sub(DOTS, s)
    s = _LUHN_RX.sub(_card, s)
    for rx in _MASKS[7:]:
        s = rx.sub(DOTS, s)
    s = _PHONE_CTX.sub(lambda m: m.group(0)[:m.start("v") - m.start(0)] + DOTS, s)
    return s


def one(s, n, paths=True):
    s = re.sub(r"\s+", " ", str(s)).strip()
    s = mask(s)
    if paths:
        s = _PATH.sub("…", s)
    return s[:n]


# ── MarkdownV2 ──────────────────────────────────────────────────────────────
_MD2 = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def esc(s):
    return _MD2.sub(r"\\\1", str(s))


def quote(lines):
    """Expandable blockquote: first line `**>`, the next `>`, the last ends with `||`."""
    lines = [esc(x) for x in lines if x != ""] or [esc("…")]
    out = []
    for i, ln in enumerate(lines):
        out.append(("**>" if i == 0 else ">") + ln)
    out[-1] += "||"
    return "\n".join(out)


# ── owner, token, flag ──────────────────────────────────────────────────────
def owner_id():
    o = (os.environ.get("OWNER_ID") or "").strip()
    if o:
        return o
    try:
        a = json.load(open(os.path.join(STATE_DIR, "access.json"), encoding="utf-8"))
        af = [str(x) for x in (a.get("allowFrom") or [])]
        return af[0] if len(af) == 1 else ""
    except (OSError, ValueError, AttributeError):
        return ""


def token():
    try:
        for ln in open(os.path.join(STATE_DIR, ".env"), encoding="utf-8"):
            if ln.startswith("TELEGRAM_BOT_TOKEN="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def off_path():
    return os.path.join(STATE_DIR, OFF_NAME)


def is_off():
    return os.path.exists(off_path())


def set_flag(on):
    os.makedirs(STATE_DIR, exist_ok=True)
    if on:
        try:
            os.unlink(off_path())
        except FileNotFoundError:
            pass
    else:
        with open(off_path(), "w") as f:
            f.write("off\n")


def api(method, **p):
    """One Bot API call. The token is used here and nowhere else; errors raise (the caller swallows them)."""
    tok = token()
    if not tok:
        raise RuntimeError("no token")
    data = urllib.parse.urlencode(p).encode()
    with urllib.request.urlopen("%s/bot%s/%s" % (API, tok, method), data, timeout=TIMEOUT) as r:
        return json.load(r)


# ── transcript: whose turn is this ──────────────────────────────────────────
def _read_new(path, off):
    """→ (complete lines after byte offset `off`, new offset, fresh). The first read (off None) takes the last WINDOW bytes and drops
    the cut first line; `fresh` is True then. A half-written last line is left for the next call. A file that shrank starts over."""
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            fresh = off is None or off > size or size - off > WINDOW
            start = max(0, size - WINDOW) if fresh else off
            f.seek(start)
            data = f.read()
    except Exception:
        return [], off, False
    if fresh and start > 0:
        k = data.find(b"\n")
        data, start = (data[k + 1:], start + k + 1) if k >= 0 else (b"", start + len(data))
    k = data.rfind(b"\n")
    if k < 0:
        return [], start, fresh
    return data[:k].decode("utf-8", "replace").splitlines(), start + k + 1, fresh


def turn_info(st, path, owner=""):
    """Follow the transcript with a byte offset kept in the state (st["tp"]), so a call reads only what is new.
    → (uuid of the latest real user message, set of chat ids in it, last assistant text of that turn).
    Fail closed: a turn whose start is not in what was read gives turn None, and nothing is sent."""
    tp = st.get("tp")
    if not isinstance(tp, dict) or tp.get("path") != path:
        tp = {"path": path, "off": None, "turn": None, "chats": [], "last": ""}
    lines, off, fresh = _read_new(path, tp.get("off"))
    if fresh:
        tp["turn"], tp["chats"], tp["last"] = None, [], ""
    tp["off"] = off
    for ln in lines:
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if not isinstance(d, dict) or d.get("isSidechain"):
            continue
        c = (d.get("message") or {}).get("content")
        if d.get("type") == "user":
            text = None
            if isinstance(c, str):
                text = c
            elif isinstance(c, list):
                parts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
                if parts:
                    text = "\n".join(parts)
            if text is not None:
                tp["turn"], tp["last"] = d.get("uuid"), ""
                tp["chats"] = sorted(set(re.findall(r'<channel\b[^>]*\bchat_id="(-?\d+)"', text)))
        elif d.get("type") == "assistant" and isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "text" and str(b.get("text", "")).strip() and tp["chats"] == [owner]:
                    tp["last"] = mask(b["text"].strip())[:4000]
    st["tp"] = tp
    return tp["turn"], set(tp["chats"]), tp["last"]


# ── step text ───────────────────────────────────────────────────────────────
SKIP = re.compile(r"telegram_telegram__|__(screenshot|find|read_page|get_page_text|tabs_context_mcp|list_connected_browsers"
                  r"|browser_snapshot|browser_take_screenshot|zoom)$|^ToolSearch$")


def step_label(name, ti):
    short = name.split("__")[-1]
    if short == "Bash":
        d = ti.get("description")
        return one(d, 150) if d and str(d).strip() else L("hod.tool.bash")
    if short in ("Agent", "Task"):
        return L("hod.tool.agent")
    if short == "Skill":
        nm = re.sub(r"[^\w:.-]", "", str(ti.get("skill", "")))[:40]
        return L("hod.tool.skill", name=nm) if nm else L("hod.tool.other")
    table = {"Write": "write", "Edit": "edit", "MultiEdit": "edit", "NotebookEdit": "edit", "Read": "read", "Grep": "files",
             "Glob": "files", "WebSearch": "search", "WebFetch": "fetch", "TodoWrite": "plan"}
    if short in table:
        return L("hod.tool." + table[short])
    if name.startswith("mcp__"):
        if re.search(r"chrome|playwright|browser|computer", name, re.I):
            if short in ("computer", "browser_wait_for") and ti.get("action") in ("wait", "hover", "scroll", "scroll_to"):
                return None
            return L("hod.tool.browser")
        return L("hod.tool.service")
    return L("hod.tool.other")


def result_line(resp):
    """A neutral outcome of a Bash step: exit status and the number of output lines. Never a word of the output itself:
    a grep or a cat over data would land in the chat."""
    code = None
    if isinstance(resp, dict):
        for k in ("exit_code", "exitCode", "returncode", "code"):
            if isinstance(resp.get(k), int) and not isinstance(resp.get(k), bool):
                code = resp[k]
                break
        text = resp.get("stdout") or resp.get("output") or ""
        if resp.get("interrupted") or resp.get("is_error"):
            return L("hod.res.fail") if code in (None, 0) else L("hod.res.exit", n=code)
    elif isinstance(resp, list):
        text = " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in resp)
    else:
        text = resp or ""
    if code:
        return L("hod.res.exit", n=code)
    return L("hod.res.ok", n=len([x for x in str(text).splitlines() if x.strip()]))


# ── rendering ───────────────────────────────────────────────────────────────
def render(st, done, summary=""):
    steps = st.get("steps", [])
    mins = max(1, int(round((time.time() - st.get("t0", time.time())) / 60.0)))
    n_total = st.get("n", len(steps))

    def line(s):
        return s["t"] + ((" → " + s["r"]) if s.get("r") else "")

    shown = SHOWN_STEPS
    while True:
        if done:
            head = "✅ *%s* · %s · %s" % (esc(L("hod.done")), esc(L("hod.steps", n=n_total)), esc(L("hod.min", n=mins)))
            old = steps
        else:
            head = "⚙️ *%s* · %s · %s" % (esc(L("hod.working")), esc(L("hod.step", n=n_total)), esc(L("hod.min", n=mins)))
            old = steps[:-1]
        body = head
        if not done and steps:
            body += "\n_" + esc(steps[-1]["t"]) + "_" + ((" → " + esc(steps[-1]["r"])) if steps[-1].get("r") else "")
        if old:
            body += "\n" + quote(["· " + line(s) for s in old[-shown:]])
        if done and summary:
            body += "\n\n*" + esc(L("hod.summary")) + "*\n" + quote(summary.splitlines())
        if len(body) <= LIMIT or (shown <= 1 and not summary):
            return body[:4090]
        if shown > 1:
            shown = max(1, shown // 2)
        else:
            summary = summary[: max(0, len(summary) // 2)]


# ── state ───────────────────────────────────────────────────────────────────
class Locked(object):
    def __init__(self):
        self.f = None

    def __enter__(self):
        try:
            import fcntl
            self.f = open(os.path.join(STATE_DIR, "hod-stream.lock"), "a")
            end = time.time() + 3
            while True:
                try:
                    fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.time() > end:
                        break
                    time.sleep(0.05)
        except Exception:
            pass
        return self

    def __exit__(self, *a):
        try:
            if self.f:
                self.f.close()
        except Exception:
            pass


def load_state():
    try:
        d = json.load(open(os.path.join(STATE_DIR, STATE_NAME), encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_state(st):
    p = os.path.join(STATE_DIR, STATE_NAME)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)


def push(st, body, owner, force=False):
    """Send the first message of the turn, edit it afterwards. A failure starts a quiet period (a dead network must not slow every step)."""
    now = time.time()
    if now < st.get("quiet_until", 0):
        return
    if not force and now - st.get("edit", 0) < MIN_EDIT_GAP:
        return
    try:
        if st.get("msg"):
            try:
                api("editMessageText", chat_id=owner, message_id=st["msg"], text=body, parse_mode="MarkdownV2",
                    disable_web_page_preview="true")
            except urllib.error.HTTPError as e:   # 400 "message is not modified" is fine; a deleted message gets a new one
                msg = ""
                try:
                    msg = e.read().decode("utf-8", "replace").lower()
                except Exception:
                    pass
                if "not modified" in msg:
                    pass
                elif e.code == 400 and ("not found" in msg or "can't be edited" in msg):
                    st["msg"] = None
                    raise
                else:
                    raise
        else:
            r = api("sendMessage", chat_id=owner, text=body, parse_mode="MarkdownV2", disable_notification="true",
                    disable_web_page_preview="true")
            st["msg"] = r["result"]["message_id"]
        st["edit"] = now
    except Exception:
        st["quiet_until"] = now + BACKOFF


# ── command from the owner ──────────────────────────────────────────────────
def command(ev):
    """/hod on|off|status in the owner's private chat → executes it and tells Mila to confirm in one line. Anything else: silence."""
    s = str(ev.get("prompt") or "").lstrip()
    # Only the FIRST (outermost) envelope counts, and its body must be plain text: a body that itself contains something shaped like
    # an envelope is somebody's text pretending to be one, never a command.
    m = re.match(r'<channel\b([^>]*)>', s)
    if not m:
        return          # a terminal prompt is not a chat command
    attrs = m.group(1)
    rest = s[m.end():]
    k = rest.find("</channel>")
    body = rest[:k] if k >= 0 else rest
    if "<channel" in body or "</channel" in body:
        return
    chat = re.search(r'\bchat_id="(-?\d+)"', attrs)
    own = owner_id()
    if not chat or not own or chat.group(1) != own:
        return
    c = re.match(r"^\s*/?hod(?:@\w+)?(?:\s+(on|off|status))?\s*[.!]?\s*$", body.strip().lower())
    if not c:
        return
    act = c.group(1) or "status"
    if act == "on":
        set_flag(True)
        txt = L("hod.on")
    elif act == "off":
        set_flag(False)
        txt = L("hod.off")
    else:
        txt = L("hod.status_off") if is_off() else L("hod.status_on")
    ctx = ("The owner sent the command /hod %s and it is already done. Confirm it to him in one short line, in his language, "
           "with this meaning: %s" % (act, txt))
    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}},
                                ensure_ascii=False))


def main():
    raw = sys.stdin.read()
    ev = json.loads(raw)
    if not isinstance(ev, dict):
        return
    kind = ev.get("hook_event_name")
    if not STATE_OK:
        return
    if kind == "UserPromptSubmit":
        command(ev)
        return
    if kind not in ("PreToolUse", "PostToolUse", "Stop"):
        return
    if is_off() or ev.get("agent_id") or ev.get("agent_type"):
        return
    name = str(ev.get("tool_name") or "")
    if name and SKIP.search(name):
        return
    owner = owner_id()
    if not owner:
        return
    os.makedirs(STATE_DIR, exist_ok=True)
    with Locked():
        st = load_state()
        turn, chats, last = turn_info(st, str(ev.get("transcript_path") or ""), owner)
        if not turn or chats != {owner}:   # only a turn that came from the owner's private chat, and from nowhere else
            save_state(st)
            return
        sess = ev.get("session_id")
        if kind == "PreToolUse":
            if st.get("session") != sess or st.get("turn") != turn:
                st = {"session": sess, "turn": turn, "msg": None, "steps": [], "n": 0, "t0": time.time(), "tp": st.get("tp")}
            lab = step_label(name, ev.get("tool_input") or {})
            if not lab:
                return
            st["steps"].append({"t": lab})
            st["n"] = st.get("n", 0) + 1
            st["steps"] = st["steps"][-MAX_STEPS:]
            push(st, render(st, False), owner)
        elif kind == "PostToolUse":
            if st.get("session") != sess or st.get("turn") != turn or not st.get("steps"):
                return
            if name.split("__")[-1] != "Bash":
                return
            r = result_line(ev.get("tool_response"))
            if not r:
                return
            st["steps"][-1]["r"] = r
            push(st, render(st, False), owner)
        else:
            if st.get("session") != sess or st.get("turn") != turn or not st.get("msg") or st.get("closed") == turn:
                return
            summ = one_block(last) if last and len(last) > 40 else ""
            push(st, render(st, True, summ), owner, force=True)
            st["closed"] = turn
        save_state(st)


def one_block(text, n=1500):
    """The turn summary: masked, paths hidden, lines kept (a quote shows them), cut to n characters."""
    t = "\n".join(_PATH.sub("…", mask(x)).rstrip() for x in str(text).splitlines())
    return t[:n]


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
