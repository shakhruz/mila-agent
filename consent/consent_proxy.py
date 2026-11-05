#!/usr/bin/env python3
"""Consent proxy (RU: «согласие без терминала») — an outside action runs only after the owner said yes to THAT action in Telegram.

Why a proxy and not just a hook: if the session holds the service key, it can repeat the same call with curl from Bash and no hook
sees it. So the keys live only with this proxy, which runs as a separate OS user (mila-io); the session asks the proxy, the proxy
shows the owner a card it draws itself, and executes only with a fresh, single-use consent for the exact payload hash.

  consent_proxy.py serve --config /etc/mila-io/<mila>/consent.json     # the service (as mila-io)

Two unix sockets:
  session socket (the Mila may connect): {"op": "request", "category": "...", "payload": {...}}
      → {"status": "done", "result": …} | {"status": "asked", "id": …} | {"status": "waiting", "id": …} | {"status": "denied", "why": …}
  io socket (only mila-io: the Telegram receiver forwards button presses here; the owner's category switches come here too):
      {"op": "callback", "data": "consent:<id>.<sig>", "from_id": "...", "chat_id": "..."}   → {"status": "granted" | "declined" | "ignored"}
      {"op": "category", "name": "...", "enabled": true|false, "from_id": "..."}              → owner turns a category on or off
Every step goes to decisions.jsonl — a hash chain (decisions.py), no payload, only hash and a short preview. Fail closed: anything unclear means no.
Config keys, all paths absolute: owner_id_env, bot_token_env, home (the Mila's home — attachments only from inside it),
state_dir, session_socket, io_socket, ttl_min (15), max_attachment_mb (20),
categories: {name: {"enabled": bool, "exec": [command…], "title": "…"}}. Only stdlib."""
import argparse, hashlib, hmac, json, os, re, secrets, socket, stat, subprocess, sys, tempfile, threading, time, unicodedata, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decisions   # the hash chain of the owner's decisions

PREFIX = "consent:"
BUF = 64 * 1024
INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿]")


FIELDS = ("text", "targets", "when", "attachments")   # what a card shows; a category may narrow it with "fields"
MANDATE_DAYS = 7                                       # a standing permission lives at most a week (the owner's word)
MANDATE_USD_DAY = 10.0                                 # … and spends at most this a day, unless the owner's config says less
DECLINE_MEMORY = 86400                                 # a «no» holds for a day: the same action is not asked again
CARD_TEXT = 3000                                       # longer text goes in parts before the card (Telegram: 4096 per message)
PART = 3500


class Proxy:
    def __init__(self, cfg, send=None, run=None, now=time.time):
        self.cfg, self.now = cfg, now
        self.state = cfg["state_dir"]
        os.makedirs(self.state, mode=0o700, exist_ok=True)
        self.key = self._key()
        self.send = send or self._tg_send
        self.run = run or self._exec
        self.lock = threading.Lock()
        self.ttl = float(cfg.get("ttl_min", 15)) * 60
        self.max_bytes = int(float(cfg.get("max_attachment_mb", 20)) * 1024 * 1024)
        self.cats = self._load("categories.json", None) or {k: bool(v.get("enabled")) for k, v in (cfg.get("categories") or {}).items()}

    # ── files ──
    def _key(self):
        p = os.path.join(self.state, "hmac.key")
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.write(fd, secrets.token_bytes(32)); os.close(fd)
        except FileExistsError:
            pass
        with open(p, "rb") as f:
            return f.read()

    def _load(self, name, default):
        try:
            with open(os.path.join(self.state, name), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    def _save(self, name, v):
        p = os.path.join(self.state, name)
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(v, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)

    def journal(self, row):
        decisions.append(os.path.join(self.state, "decisions.jsonl"), row, now=self.now())

    # ── attachments: the proxy reads with more rights than the session — only files inside the Mila's home ──
    def attachment(self, path):
        home = os.path.realpath(self.cfg["home"])
        p = os.path.abspath(os.path.join(home, str(path))) if not os.path.isabs(str(path)) else os.path.abspath(str(path))
        cur = "/"
        for part in p.strip("/").split("/"):
            cur = os.path.join(cur, part)
            if os.path.islink(cur):
                raise ValueError("attachment path has a symlink: %s" % os.path.basename(p))
        if os.path.realpath(p) != p or os.path.commonpath([p, home]) != home:
            raise ValueError("attachment outside the Mila's home: %s" % os.path.basename(p))
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as f:
            st = os.fstat(f.fileno())
            if not stat.S_ISREG(st.st_mode):
                raise ValueError("attachment is not a regular file: %s" % os.path.basename(p))
            if st.st_size > self.max_bytes:
                raise ValueError("attachment larger than %d MB: %s" % (self.max_bytes // 1048576, os.path.basename(p)))
            data = f.read(self.max_bytes + 1)
        return {"name": os.path.basename(p), "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "data": data}

    # ── what exactly the owner approves ──
    def hidden(self, v):
        """any string in the payload with characters the card would not show, or not in its NFC form"""
        if isinstance(v, str): return bool(INVISIBLE.search(v)) or unicodedata.normalize("NFC", v) != v
        if isinstance(v, dict): return any(self.hidden(x) for x in v.values()) or any(self.hidden(k) for k in v)
        if isinstance(v, (list, tuple)): return any(self.hidden(x) for x in v)
        return False

    def digest(self, category, payload):
        """→ (hash, attachments with content). The hash covers the category, the canonical payload and every attachment's content."""
        atts = [self.attachment(a) for a in (payload.get("attachments") or [])]
        body = {k: v for k, v in payload.items() if k != "attachments"}
        material = json.dumps({"category": category, "payload": body, "attachments": [(a["name"], a["sha256"]) for a in atts]},
                              ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(material.encode("utf-8")).hexdigest(), atts

    def preview(self, category, payload, atts):
        """→ list of messages: the owner sees the WHOLE text (long text — in parts before the card), the card with buttons is last."""
        clean = lambda s: INVISIBLE.sub("", unicodedata.normalize("NFC", str(s or "")))
        text = clean(payload.get("text"))
        where = ", ".join(clean(x) for x in (payload.get("targets") or [])) or "—"
        lines = ["Публикуем? · %s" % clean((self.cfg["categories"].get(category) or {}).get("title") or category),
                 "Куда: %s" % where, "Текст: %d знаков" % len(text)]
        parts = []
        if len(text) <= CARD_TEXT:
            lines.append(text)
        else:
            parts = [text[i:i + PART] for i in range(0, len(text), PART)]
            parts = ["Текст целиком, часть %d из %d:\n%s" % (k + 1, len(parts), t) for k, t in enumerate(parts)]
            lines.append("Текст целиком — в %d сообщениях выше; «Да, это» одобряет ровно его." % len(parts))
        if payload.get("when"):
            lines.append("Когда: %s" % clean(payload["when"]))
        for a in atts:
            lines.append("Вложение: %s, %d КБ" % (clean(a["name"]), max(1, a["size"] // 1024)))
        return parts + ["\n".join(lines)]

    def sig(self, cid, h):
        return hmac.new(self.key, ("%s:%s" % (cid, h)).encode(), hashlib.sha256).hexdigest()[:20]

    # ── session side ──
    def request(self, category, payload):
        if not isinstance(payload, dict) or category not in (self.cfg.get("categories") or {}):
            return {"status": "denied", "why": "unknown category"}
        fields = set((self.cfg["categories"][category] or {}).get("fields") or FIELDS)
        extra = sorted(set(payload) - fields)
        if extra:                                            # the owner's card shows only known fields — anything else would pass unseen
            self.journal({"ev": "denied", "category": category, "why": "unknown fields"})
            return {"status": "denied", "why": "unknown fields: %s" % ", ".join(str(x)[:40] for x in extra[:5])}
        if self.hidden(payload):   # what the owner sees must be exactly what runs: no invisible or direction-changing characters
            self.journal({"ev": "denied", "category": category, "why": "invisible characters"})
            return {"status": "denied", "why": "the text has invisible or direction-changing characters — remove them and ask again"}
        if not self.cats.get(category):
            self.journal({"ev": "denied", "category": category, "why": "category off"})
            return {"status": "denied", "why": "the owner turned this category off"}
        try:
            h, atts = self.digest(category, payload)
        except (ValueError, OSError) as e:
            self.journal({"ev": "denied", "category": category, "why": str(e)[:160]})
            return {"status": "denied", "why": str(e)[:200]}
        with self.lock:
            cons = self._load("consents.json", {})
            now = self.now()
            self.sweep(cons, now)
            # a «no» is remembered: the same exact action is refused for a day without a new card
            if any(c["hash"] == h and c.get("declined") and now - c["declined"] <= DECLINE_MEMORY for c in cons.values()):
                self.journal({"ev": "denied", "category": category, "hash": h[:16], "why": "declined within a day"})
                return {"status": "denied", "why": "the owner said no to this exact action within the last day"}
            # three «no» in a row for a kind: no more cards of that kind until the owner says otherwise (a grant or a day)
            tail = [c for c in sorted(cons.values(), key=lambda c: c["asked"]) if c.get("category") == category and (c.get("declined") or c.get("granted"))]
            streak = 0
            for c in reversed(tail):
                if not c.get("declined"): break
                streak += 1
            if streak >= 3 and now - tail[-1]["declined"] <= DECLINE_MEMORY:
                self.journal({"ev": "denied", "category": category, "why": "three refusals in a row"})
                return {"status": "denied", "why": "the owner refused this kind three times in a row — wait for the owner's word"}
            mid = self.mandate_fits(category, payload, now)
            if mid:
                ms = self._load("mandates.json", {}); m = ms[mid]
                cost = self.cost(payload); m.setdefault("uses", []).append([now, cost]); self._save("mandates.json", ms)
                self.journal({"ev": "mandate_use", "id": mid, "category": category, "hash": h[:16], "usd": cost})
                res = self.execute(category, payload, atts, mid)
                self.receipt(mid, category, payload, cost, res)
                return res
            for cid, c in cons.items():
                if c["hash"] != h or c.get("used") or c.get("declined") or c.get("expired") or c.get("mandate"):
                    continue
                if c.get("granted") and now - c["granted"] <= self.ttl:
                    c["used"] = now
                    self._save("consents.json", cons)
                    self.journal({"ev": "used", "id": cid, "category": category, "hash": h[:16]})
                    break
                if not c.get("granted") and now - c["asked"] <= self.ttl:
                    return {"status": "waiting", "id": cid}
            else:
                cid = secrets.token_hex(4)
                cons[cid] = {"hash": h, "category": category, "asked": now}
                self._save("consents.json", cons)
                msgs = self.preview(category, payload, atts)
                ok = all(self.send(m, []) for m in msgs[:-1]) and self.send(msgs[-1], [[
                    {"text": "Да, это", "callback_data": "%s%s.%s.y" % (PREFIX, cid, self.sig(cid, h))},
                    {"text": "Нет", "callback_data": "%s%s.%s.n" % (PREFIX, cid, self.sig(cid, h))}]])   # a part not shown → no card, no yes
                self.journal({"ev": "asked", "id": cid, "category": category, "hash": h[:16], "card_sent": bool(ok)})
                return {"status": "asked", "id": cid} if ok else {"status": "denied", "why": "could not show the card to the owner"}
        return self.execute(category, payload, atts, cid)

    # ── standing permissions (mandates) ──
    def cost(self, payload):
        try: return max(0.0, float(payload.get("cost_usd") or 0))
        except (TypeError, ValueError): return float("inf")

    def mandate_ask(self, category, targets, days, per_day, usd_day):
        """the session may only ASK; the proxy draws the card with the exact terms, the owner's press opens it"""
        cat = (self.cfg.get("categories") or {}).get(category) or {}
        if not cat.get("mandate_ok") or not self.cats.get(category):
            return {"status": "denied", "why": "no standing permission for this kind (only «every time»)"}
        try:
            targets = sorted({str(t)[:200] for t in targets}); days = float(days); per_day = int(per_day); usd_day = float(usd_day)
        except (TypeError, ValueError):
            return {"status": "denied", "why": "bad terms"}
        cap = min(MANDATE_USD_DAY, float(self.cfg.get("mandate_usd_day", MANDATE_USD_DAY)))
        if not targets or not 0 < days <= MANDATE_DAYS or not 0 < per_day <= 50 or not 0 <= usd_day <= cap:
            return {"status": "denied", "why": "terms over the ceiling: up to %d days, up to $%g a day, named targets" % (MANDATE_DAYS, cap)}
        now = self.now()
        terms = {"category": category, "targets": targets, "until": now + days * 86400, "per_day": per_day, "usd_day": usd_day}
        h = hashlib.sha256(json.dumps(dict(terms, kind="mandate"), sort_keys=True).encode()).hexdigest()
        with self.lock:
            cons = self._load("consents.json", {}); cid = secrets.token_hex(4)
            cons[cid] = {"hash": h, "category": category, "asked": now, "mandate": terms}; self._save("consents.json", cons)
        title = (self.cfg["categories"].get(category) or {}).get("title") or category
        text = ("Полномочие · %s\nКуда: %s\nСрок: %g дн.\nДо %d действий в день, до $%g в день\nКаждое действие — квитанция с кнопкой «Стоп»."
                % (title, ", ".join(targets), days, per_day, usd_day))
        ok = self.send(text, [[{"text": "Да, разрешаю", "callback_data": "%s%s.%s.y" % (PREFIX, cid, self.sig(cid, h))},
                               {"text": "Нет", "callback_data": "%s%s.%s.n" % (PREFIX, cid, self.sig(cid, h))}]])
        self.journal({"ev": "asked", "id": cid, "category": category, "hash": h[:16], "mandate": True, "card_sent": bool(ok)})
        return {"status": "asked", "id": cid} if ok else {"status": "denied", "why": "could not show the card to the owner"}

    def mandate_fits(self, category, payload, now):
        """an open, unexpired, unstopped permission of this kind whose targets cover the payload's and whose day still has room"""
        targets = {str(t) for t in (payload.get("targets") or [])}
        if not targets: return ""
        cost = self.cost(payload)
        for mid, m in self._load("mandates.json", {}).items():
            if m.get("category") != category or m.get("stopped") or now > m["until"] or not targets <= set(m["targets"]): continue
            day = [u for u in m.get("uses", []) if now - u[0] < 86400]
            if len(day) < m["per_day"] and sum(u[1] for u in day) + cost <= m["usd_day"]:
                return mid
        return ""

    def receipt(self, mid, category, payload, cost, res):
        ms = self._load("mandates.json", {}); m = ms.get(mid) or {}
        h = (self._load("consents.json", {}).get(mid) or {}).get("hash", "")
        day = [u for u in m.get("uses", []) if self.now() - u[0] < 86400]
        text = ("Сделано по полномочию · %s · %s\nСегодня: %d из %d, $%g из $%g"
                % ((self.cfg["categories"].get(category) or {}).get("title") or category, "ok" if (res.get("result") or {}).get("ok") else "не вышло",
                   len(day), m.get("per_day", 0), round(sum(u[1] for u in day), 2), m.get("usd_day", 0)))
        self.send(text, [[{"text": "Стоп полномочию", "callback_data": "%s%s.%s.s" % (PREFIX, mid, self.sig(mid, h))}]])

    def mandate_stop(self, mid, s):
        with self.lock:
            cons = self._load("consents.json", {}); c = cons.get(mid)
            if not c or not c.get("mandate") or not hmac.compare_digest(s, self.sig(mid, c["hash"])):
                return {"status": "ignored", "why": "unknown or forged"}
            ms = self._load("mandates.json", {})
            if mid not in ms or ms[mid].get("stopped"): return {"status": "ignored", "why": "not open"}
            ms[mid]["stopped"] = self.now(); self._save("mandates.json", ms)
        self.journal({"ev": "mandate_stop", "id": mid, "category": c["category"]})
        return {"status": "stopped"}

    def sweep(self, cons, now):
        """silence is not consent: a card nobody answered within the TTL becomes «expired», once, in the journal"""
        changed = False
        for cid, c in cons.items():
            if not (c.get("granted") or c.get("declined") or c.get("expired")) and now - c["asked"] > self.ttl:
                c["expired"] = now; changed = True
                self.journal({"ev": "expired", "id": cid, "category": c.get("category"), "hash": c["hash"][:16]})
        if changed: self._save("consents.json", cons)

    def execute(self, category, payload, atts, cid):
        with tempfile.TemporaryDirectory(prefix="consent-") as td:
            files = []
            for a in atts:                                   # the executor gets the checked copies, not the session's paths
                p = os.path.join(td, a["name"])
                with open(p, "wb") as f:
                    f.write(a["data"])
                files.append(p)
            body = dict({k: v for k, v in payload.items() if k != "attachments"}, attachments=files)
            res = self.run(self.cfg["categories"][category]["exec"], body)
        self.journal({"ev": "executed", "id": cid, "category": category, "ok": bool(res.get("ok"))})
        return {"status": "done", "result": res}

    # ── io side (receiver, owner) ──
    def callback(self, data, from_id, chat_id=None):
        owner = os.environ.get(self.cfg.get("owner_id_env") or "MILA_OWNER_ID", "")
        m = re.fullmatch(re.escape(PREFIX) + r"([0-9a-f]{8})\.([0-9a-f]{20})\.([yns])", str(data or ""))
        if not m:
            return {"status": "ignored", "why": "not a consent button"}
        cid, s, yn = m.groups()
        if not owner or str(from_id) != owner or (chat_id is not None and str(chat_id) != owner):
            self.journal({"ev": "rejected", "id": cid, "why": "not the owner in the owner's private chat"})
            return {"status": "ignored", "why": "only the owner in a private chat"}
        if yn == "s":
            return self.mandate_stop(cid, s)
        with self.lock:
            cons = self._load("consents.json", {})
            c = cons.get(cid)
            if not c or not hmac.compare_digest(s, self.sig(cid, c["hash"])):
                self.journal({"ev": "rejected", "id": cid, "why": "unknown id or bad signature"})
                return {"status": "ignored", "why": "unknown or forged"}
            if c.get("granted") or c.get("declined") or self.now() - c["asked"] > self.ttl:
                return {"status": "ignored", "why": "already answered or expired"}
            c["granted" if yn == "y" else "declined"] = self.now()
            self._save("consents.json", cons)
            if yn == "y" and c.get("mandate"):   # a standing permission opens only by this press on the proxy's own card
                ms = self._load("mandates.json", {}); ms[cid] = dict(c["mandate"], opened=self.now(), uses=[]); self._save("mandates.json", ms)
        self.journal({"ev": "granted" if yn == "y" else "declined", "id": cid, "hash": c["hash"][:16]})
        if yn == "y" and c.get("mandate"):
            self.journal({"ev": "mandate_open", "id": cid, "category": c["category"], "hash": c["hash"][:16], "until": c["mandate"]["until"],
                          "per_day": c["mandate"]["per_day"], "usd_day": c["mandate"]["usd_day"]})
        return {"status": "granted" if yn == "y" else "declined"}

    def category(self, name, enabled, from_id):
        owner = os.environ.get(self.cfg.get("owner_id_env") or "MILA_OWNER_ID", "")
        if not owner or str(from_id) != owner or name not in (self.cfg.get("categories") or {}):
            return {"status": "ignored"}
        before = self.cats.get(name)
        self.cats[name] = bool(enabled)
        self._save("categories.json", self.cats)
        self.journal({"ev": "category", "name": name, "was": before, "now": bool(enabled)})
        return {"status": "ok", "enabled": bool(enabled)}

    # ── outside world ──
    def _tg_send(self, text, keyboard):
        token = os.environ.get(self.cfg.get("bot_token_env") or "BOT_TOKEN", "")
        owner = os.environ.get(self.cfg.get("owner_id_env") or "MILA_OWNER_ID", "")
        if not token or not owner:
            return False
        data = urllib.parse.urlencode({"chat_id": owner, "text": text, "reply_markup": json.dumps({"inline_keyboard": keyboard})}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request((os.environ.get("TELEGRAM_API_ROOT") or "https://api.telegram.org") + "/bot%s/sendMessage" % token, data=data), timeout=20) as r:
                return bool(json.loads(r.read().decode()).get("ok"))
        except Exception:
            return False

    def _exec(self, cmd, body):
        try:
            r = subprocess.run(list(cmd), input=json.dumps(body, ensure_ascii=False), capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"ok": False, "error": type(e).__name__}
        try:
            out = json.loads(r.stdout or "{}")
        except ValueError:
            out = {"output": (r.stdout or "")[-500:]}
        out.setdefault("ok", r.returncode == 0)
        return out


def serve(px, path, handler, mode):
    # bind under a temporary name, set the mode, listen — only then rename into place: a client never meets a socket that
    # exists but does not accept yet (refused → «denied») or still has the umask's mode
    tmp = "%s.tmp-%d" % (path, os.getpid())
    if os.path.lexists(tmp):
        os.unlink(tmp)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(tmp); os.chmod(tmp, mode); s.listen(16)
    os.replace(tmp, path)
    def one(conn):
        with conn:
            try:
                conn.settimeout(10)
                raw = b""
                while not raw.endswith(b"\n") and len(raw) < 1 << 20:
                    chunk = conn.recv(BUF)
                    if not chunk:
                        break
                    raw += chunk
                res = handler(json.loads(raw.decode("utf-8")))
            except Exception as e:                       # fail closed: any error is a no
                res = {"status": "denied", "why": type(e).__name__}
            try:
                conn.sendall((json.dumps(res, ensure_ascii=False) + "\n").encode())
            except OSError:                                  # the client left before the answer: nothing to tell it
                pass
    while True:
        c, _ = s.accept()
        threading.Thread(target=one, args=(c,), daemon=True).start()


def session_handler(px):
    def h(q):
        if q.get("op") == "request": return px.request(q.get("category"), q.get("payload"))
        if q.get("op") == "mandate": return px.mandate_ask(q.get("category"), q.get("targets") or [], q.get("days"), q.get("per_day"), q.get("usd_day"))
        return {"status": "denied", "why": "unknown op"}
    return h


def io_handler(px):
    def h(q):
        if q.get("op") == "callback":
            return px.callback(q.get("data"), q.get("from_id"), q.get("chat_id"))
        if q.get("op") == "category":
            return px.category(q.get("name"), q.get("enabled"), q.get("from_id"))
        return {"status": "ignored"}
    return h


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["serve"])
    ap.add_argument("--config", required=True)
    a = ap.parse_args(argv)
    cfg = json.load(open(a.config, encoding="utf-8"))
    px = Proxy(cfg)
    threading.Thread(target=serve, args=(px, cfg["io_socket"], io_handler(px), 0o600), daemon=True).start()
    serve(px, cfg["session_socket"], session_handler(px), int(str(cfg.get("session_socket_mode", "660")), 8))
    return 0


if __name__ == "__main__":
    sys.exit(main())
