#!/usr/bin/env python3
"""Birth code → bot token and owner id, once, from the birth relay. Shared by docker/birth_claim.py and install/birth.py.
The relay hands the token out once and forgets it. Only stdlib. Nothing here prints or logs the token."""
import json
import os
import re
import urllib.error
import urllib.request

DEFAULT_RELAY = "https://tv.milagpt.io/birth/api/claim"
CODE_RE = re.compile(r"MILA-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}")
BOT_TOKEN_RE = re.compile(r"\d{5,}:[A-Za-z0-9_-]{30,}")


def normalize_code(text):
    """Any case, with or without dashes and spaces → MILA-XXXX-XXXX-XXXX, or None."""
    s = re.sub(r"[^A-Za-z0-9]", "", str(text or "")).upper()
    if len(s) == 12:
        s = "MILA" + s
    if len(s) != 16 or not s.startswith("MILA"):
        return None
    code = "MILA-%s-%s-%s" % (s[4:8], s[8:12], s[12:16])
    return code if CODE_RE.fullmatch(code) else None


def claim(code, relay=None, timeout=20):
    """Exchange a birth code. Returns {"ok": True, "bot_token": ..., "owner_id": "" or digits} or
    {"ok": False, "error": "format" | "insecure" | "refused" | "relay_http" | "unreachable" | "no_token", "status": int}."""
    code = normalize_code(code)
    if not code:
        return {"ok": False, "error": "format"}
    relay = relay or os.environ.get("BIRTH_RELAY", DEFAULT_RELAY)
    if not relay.startswith("https://") and not os.environ.get("BIRTH_RELAY_INSECURE_TEST"):
        return {"ok": False, "error": "insecure"}
    rq = urllib.request.Request(relay, data=json.dumps({"code": code}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "refused" if e.code == 404 else "relay_http", "status": e.code}
    except (urllib.error.URLError, OSError, ValueError):
        return {"ok": False, "error": "unreachable"}
    if not isinstance(d, dict):
        return {"ok": False, "error": "no_token"}
    tok, owner = str(d.get("bot_token") or ""), str(d.get("owner_id") or "")
    if not BOT_TOKEN_RE.fullmatch(tok):
        return {"ok": False, "error": "no_token"}
    return {"ok": True, "bot_token": tok, "owner_id": owner if re.fullmatch(r"\d{3,15}", owner) else ""}
