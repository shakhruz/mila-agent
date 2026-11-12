#!/usr/bin/env python3
"""shell_name.py — is the word `mila` in the owner's OWN shell really Mila? (a function or an alias from an rc file wins over
any file on PATH, and an installer running in a plain bash never sees it).

  shell_name.py <path of our mila> [--json | --short]   → nothing and code 0 when `mila` is ours (or no shell to ask);
                                                 one plain report and code 1 when something else answers to `mila`

It asks the owner's interactive shell itself — `zsh -ic 'whence -v mila'` or `bash -ic 'type -t mila; declare -F mila'` — with a
time limit (5 s), stdin closed. It writes nothing itself; the shell's rc files do run, as when a terminal opens (they may
write their own history or start their agents). Found a function or an alias → it names the shell, the kind, the file and the
line(s), and prints the lines as they are, so the owner can see what to remove. It edits no file: a change of an rc file is the
owner's own step (Mila shows the lines and waits for his «yes»). Only stdlib."""
import json, os, re, shutil, subprocess, sys

TIMEOUT = 5
MARK = "__MILA_PROBE__"   # printed right before the query: a banner the rc file prints at start (fortune, neofetch) stays above it
DEF = re.compile(r"^\s*(?:function\s+mila(?:\s|\(|\{|$)|mila\s*\(\s*\)|alias\s+mila=)")


def ask(shell, query):
    exe = shutil.which(shell)
    if not exe: return None
    try:
        p = subprocess.Popen([exe, "-ic", "printf '%s\\n' " + MARK + "; " + query], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                             env=dict(os.environ, MILA_SHELL_PROBE="1"), start_new_session=True)
    except OSError:
        return None
    try:
        out, _ = p.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:   # an rc file that waits: stop the shell and everything it started, no false alarm
        try: os.killpg(p.pid, 9)
        except OSError: pass
        p.communicate(); return None
    out = out or ""
    i = out.rfind(MARK + "\n")
    return out[i + len(MARK) + 1:] if i >= 0 else None   # no mark — the shell never reached the query: nothing to say


def lines_of(path):
    """the definition lines of `mila` in that file: [(number, text)] — up to five"""
    try: src = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError: return []
    return [(i, l.rstrip()[:160]) for i, l in enumerate(src, 1) if DEF.match(l)][:5]


def tilde(p):
    h = os.path.expanduser("~")
    return "~" + p[len(h):] if p and (p == h or p.startswith(h + os.sep)) else p


def probe(ours, shells=None):
    """→ None when `mila` is ours or nothing could be asked; else {"shell", "kind", "file", "lines"}."""
    login = os.path.basename(os.environ.get("SHELL") or "")
    order = shells or ([login] if login in ("zsh", "bash") else []) + [s for s in ("zsh", "bash") if s != login]
    for sh in order:
        if sh == "zsh":
            out = ask("zsh", "whence -v mila")
            if not out: continue
            first = out.strip().splitlines()[0] if out.strip() else ""
            if "shell function" in first:
                m = re.search(r" from (/.+)$", first); f = m.group(1).strip() if m else ""
                return {"shell": "zsh", "kind": "function", "file": tilde(f), "lines": lines_of(f) if f else []}
            if "alias" in first:
                return {"shell": "zsh", "kind": "alias", "file": "", "lines": [(0, first[:160])]}
            m = re.match(r"mila is (/.+)$", first)
            if m and os.path.exists(m.group(1)) and os.path.exists(ours) and not os.path.samefile(m.group(1), ours):
                return {"shell": "zsh", "kind": "file", "file": tilde(m.group(1)), "lines": []}
            return None
        if sh == "bash":
            out = ask("bash", "type -t mila; shopt -s extdebug; declare -F mila; alias mila 2>/dev/null; type -P mila")
            if out is None: continue
            rows = [l for l in out.splitlines() if l.strip()]
            kind = rows[0].strip() if rows else ""
            if kind == "function":
                m = next((re.match(r"mila (\d+) (/.+)$", l) for l in rows if re.match(r"mila \d+ /", l)), None)
                f = m.group(2) if m else ""
                return {"shell": "bash", "kind": "function", "file": tilde(f), "lines": lines_of(f) if f else []}
            if kind == "alias":
                return {"shell": "bash", "kind": "alias", "file": "", "lines": [(0, next((l for l in rows if l.startswith("alias ")), "")[:160])]}
            if kind == "file":
                p = rows[-1].strip()
                if os.path.exists(p) and os.path.exists(ours) and not os.path.samefile(p, ours):
                    return {"shell": "bash", "kind": "file", "file": tilde(p), "lines": []}
            return None
    return None


def say(r, ours):
    what = {"function": "a shell function", "alias": "an alias", "file": "another program"}[r["kind"]]
    head = "`mila` in your %s is %s%s — not Mila." % (r["shell"], what, (" (%s)" % r["file"]) if r["file"] else "")
    body = ["  %s%s" % (("%d: " % n) if n else "", t) for n, t in r["lines"]]
    tail = ["Until it is removed, start her with the full path:  %s" % tilde(ours),
            "To take her off this computer:  %s uninstall" % tilde(ours)]
    if r["kind"] in ("function", "alias") and r["file"]:
        tail.insert(0, "Those lines are in %s — remove or rename them there yourself, then open a new terminal." % r["file"])
    return "\n".join([head] + body + tail)


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    ours = os.path.expanduser(argv[1]); r = probe(ours)
    if "--short" in argv:   # one line for the installer's screen: «zsh function in ~/.zshrc»
        if r: print("%s %s%s" % (r["shell"], r["kind"], (" in " + r["file"]) if r["file"] else ""))
        return 1 if r else 0
    if "--json" in argv:
        print(json.dumps(r or {}, ensure_ascii=False)); return 1 if r else 0
    if r: print(say(r, ours))
    return 1 if r else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
