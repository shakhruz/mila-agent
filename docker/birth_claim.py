#!/usr/bin/env python3
"""Birth code → this Mila's bot token, once (the person never copies a token).
  python3 birth_claim.py   → writes $MILA_AUTH_DIR/bot_token (600) and owner_id; prints nothing secret. Exit 0 ok, 1 refused, 2 bad env.
Env: BIRTH_CODE (MILA-XXXX-XXXX-XXXX), BIRTH_RELAY (default https://tv.milagpt.io/birth/api/claim), MILA_AUTH_DIR. Only stdlib.
The relay hands the token out once and forgets it; this container keeps it in its own volume only.
The claim itself lives in install/birth_relay.py (shared with the birth page)."""
import os, sys
for _d in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "install"), os.path.join(os.environ.get("MILA_KIT", "/opt/mila/kit"), "install")):
    if os.path.isfile(os.path.join(_d, "birth_relay.py")):
        sys.path.insert(0, _d); break
import birth_relay

CODE = (os.environ.get("BIRTH_CODE") or "").strip().upper()
RELAY = os.environ.get("BIRTH_RELAY", birth_relay.DEFAULT_RELAY)
AUTH = os.path.expanduser(os.environ.get("MILA_AUTH_DIR", "~/.mila-auth"))


def put(name, val):
    p = os.path.join(AUTH, name); tmp = p + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(val + "\n")
    os.replace(tmp, p)


def main():
    if not birth_relay.normalize_code(CODE):
        print("BIRTH_CODE does not look like MILA-XXXX-XXXX-XXXX"); return 2
    r = birth_relay.claim(CODE, RELAY)
    if not r["ok"]:
        e = r["error"]
        if e == "insecure":
            print("BIRTH_RELAY must be https"); return 2
        if e == "refused":
            print("birth code refused (%d): used, expired or mistyped — ask for a new one" % r["status"]); return 1
        if e == "relay_http":
            print("birth relay answered %d — try again later" % r["status"]); return 1
        if e == "unreachable":
            print("birth relay unreachable — try again later"); return 1
        print("birth relay gave no bot token"); return 1
    tok, owner = r["bot_token"], r["owner_id"]
    os.makedirs(AUTH, mode=0o700, exist_ok=True); os.chmod(AUTH, 0o700)
    put("bot_token", tok)
    if owner:
        put("owner_id", owner)
    print("birth code accepted: bot token saved in the volume%s" % (", owner set" if owner else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
