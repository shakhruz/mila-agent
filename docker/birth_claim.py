#!/usr/bin/env python3
"""Birth code → this Mila's bot token, once (the person never copies a token).
  python3 birth_claim.py   → writes $MILA_AUTH_DIR/bot_token (600) and owner_id; prints nothing secret. Exit 0 ok, 1 refused, 2 bad env.
Env: BIRTH_CODE (MILA-XXXX-XXXX-XXXX), BIRTH_RELAY (default https://tv.milagpt.io/birth/api/claim), MILA_AUTH_DIR. Only stdlib.
The relay hands the token out once and forgets it; this container keeps it in its own volume only."""
import json, os, re, sys, urllib.error, urllib.request

CODE = (os.environ.get("BIRTH_CODE") or "").strip().upper()
RELAY = os.environ.get("BIRTH_RELAY", "https://tv.milagpt.io/birth/api/claim")
AUTH = os.path.expanduser(os.environ.get("MILA_AUTH_DIR", "~/.mila-auth"))


def put(name, val):
    p = os.path.join(AUTH, name); tmp = p + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(val + "\n")
    os.replace(tmp, p)


def main():
    if not re.fullmatch(r"MILA-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", CODE):
        print("BIRTH_CODE does not look like MILA-XXXX-XXXX-XXXX"); return 2
    if not RELAY.startswith("https://") and not os.environ.get("BIRTH_RELAY_INSECURE_TEST"):
        print("BIRTH_RELAY must be https"); return 2
    rq = urllib.request.Request(RELAY, data=json.dumps({"code": CODE}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(rq, timeout=20) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print("birth code refused (%d): used, expired or mistyped — ask for a new one" % e.code if e.code == 404 else "birth relay answered %d — try again later" % e.code)
        return 1
    except (urllib.error.URLError, OSError, ValueError) as e:
        print("birth relay unreachable: %s — try again later" % type(e).__name__); return 1
    tok, owner = str(d.get("bot_token") or ""), str(d.get("owner_id") or "")
    if not re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{30,}", tok):
        print("birth relay gave no bot token"); return 1
    os.makedirs(AUTH, mode=0o700, exist_ok=True); os.chmod(AUTH, 0o700)
    put("bot_token", tok)
    if re.fullmatch(r"\d{3,15}", owner):
        put("owner_id", owner)
    print("birth code accepted: bot token saved in the volume%s" % (", owner set" if owner else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
