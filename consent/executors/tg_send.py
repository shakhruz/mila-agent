#!/usr/bin/env python3
"""Executor for the consent proxy: send a message from the owner's bot to the named chats — after the owner's «yes» to this
exact text and these recipients. Runs as mila-io; in Mila Agent the bot goes through the key keeper (BOT_TOKEN is a
placeholder, TELEGRAM_API_ROOT the keeper's address), so the token never reaches the session.

stdin: {"text": "...", "targets": ["<chat id>", …]}   (attachments are not sent by this executor)
stdout: {"ok": bool, "sent": [{"chat": id, "message_id": n}], "failed": [{"chat": id, "error": "..."}]}; no token printed."""
import json, os, re, sys, urllib.error, urllib.parse, urllib.request


def main():
    tok = os.environ.get("BOT_TOKEN", "")
    root = (os.environ.get("TELEGRAM_API_ROOT") or "https://api.telegram.org").rstrip("/")
    if not tok:
        print(json.dumps({"ok": False, "error": "no bot for the proxy"})); return 1
    p = json.load(sys.stdin)
    if p.get("attachments"):
        print(json.dumps({"ok": False, "error": "attachments are not sent by this executor"})); return 1
    text = str(p.get("text") or "")
    targets = [str(t) for t in (p.get("targets") or [])]
    if not text or not targets or any(not re.fullmatch(r"-?[0-9]{1,20}", t) for t in targets):
        print(json.dumps({"ok": False, "error": "a text and numeric chat ids are needed"})); return 1
    sent, failed = [], []
    for chat in targets:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request("%s/bot%s/sendMessage" % (root, tok), data=data), timeout=30) as r:
                d = json.loads(r.read().decode() or "{}")
            if d.get("ok"): sent.append({"chat": chat, "message_id": (d.get("result") or {}).get("message_id")})
            else: failed.append({"chat": chat, "error": str(d.get("description") or "not ok")[:120]})
        except urllib.error.HTTPError as e:
            failed.append({"chat": chat, "error": "HTTP %d" % e.code})
        except (OSError, ValueError) as e:
            failed.append({"chat": chat, "error": type(e).__name__})
    print(json.dumps({"ok": not failed, "sent": sent, "failed": failed}))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
