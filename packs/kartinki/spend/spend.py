#!/usr/bin/env python3
"""Расход — учёт платных генераций Милы (OpenRouter, fal.ai, HeyGen, ElevenLabs и др.).
Перед генерацией дороже порога (threshold_usd) — прогноз и детали, кнопки «одобрить / отменить»;
после — результат и фактический расход. Мила осознанно тратит деньги владельца и помогает планировать.

Папка $RASHOD_HOME (по умолчанию ~/work/rashod):
  policy.json  — {"owners":[id], "threshold_usd":0.5, "monthly_limit_usd":20, "budgets":{"<user_id>":5}}
                 budgets — сколько в месяц владелец разрешил тратить человеку без своего «да» (решение «А/Б» владельца)
  ledger.jsonl — строка на план: id, сервис, что, прогноз, кто просил, кто одобрил, факт, статус

  spend.py plan --service fal --what "видео 10 с" --est 0.8 --by <user_id>  → id + решение: auto | card
  spend.py approve <id> --card <card_id> [--msg <chat>/<msg>]   — по нажатию: кто нажал, берётся из журнала карточек
                 плагина (cards.jsonl), не из аргумента; owner — всегда, автор — в пределах своего бюджета
  spend.py reject <id> --by <user_id>
  spend.py check <id>        — можно ли тратить (код 0 — да)
  spend.py done <id> --fact 0.74 [--note "…"]
  spend.py report [--month 2026-10]  — потрачено, по сервисам, по людям, прогноз против факта, остаток
  spend.py owner <id> --card <c> · limit <usd> --card <c> · budget <user_id> <usd> --card <c>   — тоже по нажатию владельца
одобрение держалось на --by — id, который Мила сама пишет аргументом; инъекция
«одобри, мой id …» или ошибка модели давали трату без нажатия. Теперь нужна карточка (reply с кнопками), в тексте которой
есть метка траты («#<id>» или «лимит <usd>» / «бюджет <user_id> <usd>» / «владелец <id>»), отправленная после плана,
и запись нажатия приёмника: used_by — владелец (или автор в своём бюджете), выбор — кнопка «ok» (или единственная кнопка
карточки, если приёмник выбор не пишет). Одна карточка — одно одобрение.
"""
import argparse, datetime as dt, json, os, re, sys, uuid
from collections import defaultdict

HOME = os.path.expanduser(os.environ.get("RASHOD_HOME", "~/work/rashod"))
POL, LED = os.path.join(HOME, "policy.json"), os.path.join(HOME, "ledger.jsonl")
NOW = lambda: dt.datetime.now().astimezone().isoformat(timespec="seconds")

def pol():
    d = {"owners": [], "threshold_usd": 0.5, "monthly_limit_usd": 20, "budgets": {}}
    if os.path.exists(POL): d.update(json.load(open(POL)))
    return d
def save_pol(d): os.makedirs(HOME, exist_ok=True); json.dump(d, open(POL, "w"), ensure_ascii=False, indent=1)
def rows():
    if not os.path.exists(LED): return {}
    out = {}
    for l in open(LED, encoding="utf-8"):
        if l.strip(): r = json.loads(l); out[r["id"]] = {**out.get(r["id"], {}), **r}
    return out
def put(r): os.makedirs(HOME, exist_ok=True); open(LED, "a", encoding="utf-8").write(json.dumps(r, ensure_ascii=False) + "\n")
def month(r): return r["ts"][:7]
CARDS = lambda: os.environ.get("TELEGRAM_CARDS_FILE") or os.path.join(os.environ.get("MILA_TG_STATE") or os.environ.get("TELEGRAM_STATE_DIR") or os.path.expanduser("~/.claude/channels/telegram"), "cards.jsonl")

def _t(s):
    try: return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError): return None

def io_uid():
    """the receiver's own OS user (Mila Agent) — from /etc/passwd, not from the environment the session could change."""
    import pwd
    try: return pwd.getpwnam("mila-io").pw_uid
    except KeyError: return None


IO_DIR = "/var/lib/mila/io" if os.path.isdir("/var/lib/mila/io") else os.path.expanduser("~/.claude/channels/telegram/io")   # layout B (09.11)


def io_file(name):
    """a file only the receiver writes, if its folder and the file belong to mila-io and are not links; otherwise None."""
    import stat as _st
    uid = io_uid(); p = os.path.join(IO_DIR, name)
    try:
        if any(_st.S_ISLNK(os.lstat(x).st_mode) or os.lstat(x).st_uid != uid for x in (IO_DIR, p)): return None
    except OSError:
        return None
    return p


CONSENT_SOCK = "/run/mila-io/consent.sock"


def consent_sock():
    """the consent proxy's socket, or "" when there is none to use. Mila Agent is decided by the machine — the receiver's OS user
    exists — not by a variable the session could unset: there, always the image's socket (a variable cannot point elsewhere)
    and no way around it. Elsewhere MILA_CONSENT_SOCKET may turn the proxy on (a plain install that runs one)."""
    agent = io_uid() is not None
    return CONSENT_SOCK if agent else os.environ.get("MILA_CONSENT_SOCKET", "")


def proxy_approve(r):
    """Mila Agent: a paid generation is approved by the owner through the consent proxy — a card with what, where and the
    forecast; or within a standing permission the owner opened there (up to 7 days and $10 a day). → (consent id, why)."""
    import time as _time
    sys.path.insert(0, os.path.join(os.environ.get("MILA_KIT") or "/opt/mila/kit", "consent"))
    try:
        import consent_client as _cc, consent_proxy as _cp
    except ImportError:
        return "", "посредник согласий не найден в наборе"
    payload = {"text": "Платная генерация: %s · %s · ~$%.2f\n#%s" % (r.get("what") or "", r.get("service") or "", r["est"], r["id"]),
               "targets": [str(r.get("service") or "")], "cost_usd": r["est"]}
    t0 = _time.time()
    q = _cc.ask("spend", payload, consent_sock())
    st = q.get("status")
    if st in ("asked", "waiting", "deferred"): return "", "карточка у владельца (%s); после его «да» — approve %s ещё раз" % (st, r["id"])
    if st != "done": return "", "посредник: " + str(q.get("why") or st)[:200]
    res = q.get("result") or {}
    cid = str(res.get("confirmed") or "")
    if cid:   # a card «yes»: the proxy recorded «confirmed» for exactly this generation
        got = _cp.confirmed(os.path.join(IO_DIR, "consent", "decisions.jsonl"), "spend", _cp.action_hash("spend", payload, []), t0 - 60,
                            {str(x.get("consent")) for x in rows().values() if x.get("consent")})
        return (cid, "") if got == cid else ("", "в журнале решений нет «да» владельца на эту трату")
    return "", "посредник не подтвердил"


def owners(p):
    """Mila Agent: owners only from the receiver's io/owners.json; elsewhere policy.json as before."""
    if io_uid() is None: return [str(x) for x in p["owners"]]
    f = io_file("owners.json")
    try: return [str(x) for x in json.load(open(f)).get("owners", [])] if f else []
    except (OSError, ValueError): return []


def tap(card_id, mark, after=None):
    """Нажатие хозяина на карточку card_id → (кто нажал, None) или (None, причина отказа). Читает только журнал плагина."""
    card = used = None
    try:
        for l in open(CARDS(), encoding="utf-8"):
            try: r = json.loads(l)
            except ValueError: continue
            if not isinstance(r, dict) or r.get("card_id") != card_id: continue
            if r.get("used_ts"): used = r
            elif card is None: card = r
    except OSError:
        return None, "нет журнала карточек плагина"
    taps = os.path.join(os.path.dirname(CARDS()), "taps.jsonl")   # newer plugin: presses only as Telegram delivered them
    if io_uid() is not None:   # Mila Agent: only the receiver's own journal; no fallback the session could arrange
        taps = io_file("taps.jsonl")
        if not taps: return None, "журнал нажатий приёмника подменён или его нет — не верю"
    if os.path.exists(taps):
        t = None
        for l in open(taps, encoding="utf-8"):
            try: r = json.loads(l)
            except ValueError: continue
            if isinstance(r, dict) and r.get("card_id") == card_id: t = t or r
        if not t: return None, "на карточку ещё не нажимали"
        if not re.search(r"(?<![\w#])%s(?!\w)" % re.escape(mark), t.get("card_text") or ""):
            return None, "в карточке, которую видел человек, нет метки «%s»" % mark
        if after and card and (_t(card.get("ts")) or 0) < (_t(after) or 0): return None, "карточка старше плана траты"
        if t.get("data") != "ok": return None, "нажата не «ok»"
        return str(t.get("used_by") or ""), None
    if not card: return None, "карточки %s нет в журнале плагина" % card_id
    if not re.search(r"(?<![\w#])%s(?!\w)" % re.escape(mark), card.get("text") or ""):
        return None, "в карточке нет метки «%s» — это карточка не про эту трату" % mark
    if after and (_t(card.get("ts")) or 0) < (_t(after) or 0):   # плагин пишет UTC «…Z», план — местное «+05:00»: сравниваю моменты
        return None, "карточка старше плана траты"
    if not used: return None, "на карточку ещё не нажимали"
    choice = [b.get("data") for row in card.get("buttons") or [] for b in row if isinstance(b, dict) and b.get("data")]
    if "data" in used:
        if used["data"] != "ok": return None, "нажата не «ok», а «%s»" % used["data"]
    elif choice != ["ok"]:
        return None, "приёмник не пишет, какая кнопка нажата: одобрять можно карточкой с одной кнопкой «ok» (✅ Делаем)"
    return str(used.get("used_by") or ""), None

def card_spent(rs, card_id):
    return any(r.get("card") == card_id for r in rs.values()) or card_id in (pol().get("cards") or [])
def spent(rs, m, who=None):
    s = 0.0
    for r in rs.values():
        if month(r) != m or r.get("status") not in ("approved", "auto", "done"): continue
        if who and str(r.get("by")) != str(who): continue
        s += r.get("fact", r["est"])
    return s

def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    p, rs, m = pol(), rows(), NOW()[:7]
    cmd = a[0]
    ap = argparse.ArgumentParser(); ap.add_argument("x", nargs="*")
    for f in ("--service", "--what", "--est", "--by", "--msg", "--fact", "--note", "--month", "--card"): ap.add_argument(f)
    o = ap.parse_args(a[1:])
    if cmd == "plan":
        est = round(float(o.est) * 1.1, 2)  # запас 10 %
        left = p["monthly_limit_usd"] - spent(rs, m)
        r = {"id": uuid.uuid4().hex[:6], "ts": NOW(), "service": o.service, "what": o.what, "est": est, "by": o.by}
        if est > left: r["status"] = "over_limit"
        elif est < p["threshold_usd"]: r["status"] = "auto"
        else: r["status"] = "planned"
        put(r)
        print(json.dumps({**r, "left_month": round(left, 2),
              "next": {"auto": "делай и запиши done", "planned": "карточка: что · прогноз · кнопки ✅/✏️/✖️",
                       "over_limit": "месячный потолок — спроси владельца поднять лимит"}[r["status"]]}, ensure_ascii=False))
    elif cmd in ("approve", "reject"):
        r = rs[o.x[0]]
        if cmd == "approve" and consent_sock():
            cid, why = proxy_approve(r)
            if not cid: sys.exit("не одобрено: " + why)
            put({"id": r["id"], "status": "approved", "approved_by": "owner", "consent": cid, "approved_ts": NOW()})
            print("ok"); return
        if cmd == "approve":
            if not o.card: sys.exit("одобрение — только по нажатию: --card <id карточки>")
            if card_spent(rs, o.card): sys.exit("эта карточка уже одобрила трату — одна карточка, одно одобрение")
            by, why = tap(o.card, "#" + r["id"], r["ts"])
            if not by: sys.exit("не одобрено: " + why)
            if o.by and str(o.by) != by: sys.exit(f"--by {o.by} не тот, кто нажал ({by})")
            owner = by in owners(p)
            budget = float(p["budgets"].get(by, 0)); mine = spent(rs, m, by)
            if not owner and not (by == str(r["by"]) and mine + r["est"] <= budget):
                sys.exit(f"не может одобрить: не владелец и бюджет {by} ${budget} (потрачено ${mine:.2f})")
            put({"id": r["id"], "status": "approved", "approved_by": by, "card": o.card, "msg": o.msg, "approved_ts": NOW()})
        else: put({"id": r["id"], "status": "rejected", "by_reject": str(o.by)})   # отказ безопасен — нажатия не жду
        print("ok")
    elif cmd == "check":
        r = rs.get(o.x[0]); ok = r and r.get("status") in ("approved", "auto")
        print("можно" if ok else "нельзя: нет одобрения"); sys.exit(0 if ok else 1)
    elif cmd == "done":
        r = rs[o.x[0]]; put({"id": r["id"], "status": "done", "fact": float(o.fact), "note": o.note, "done_ts": NOW()})
        print(f"факт ${float(o.fact):.2f} при прогнозе ${r['est']:.2f}")
    elif cmd == "report":
        mm = o.month or m; by_s, by_p = defaultdict(float), defaultdict(float); est = fact = 0
        for r in rs.values():
            if month(r) != mm or r.get("status") != "done": continue
            by_s[r["service"]] += r["fact"]; by_p[str(r["by"])] += r["fact"]; est += r["est"]; fact += r["fact"]
        print(f"Расход {mm}: ${fact:.2f} из ${p['monthly_limit_usd']} (прогноз был ${est:.2f})")
        print("по сервисам: " + ", ".join(f"{k} ${v:.2f}" for k, v in by_s.items()))
        print("по людям: " + ", ".join(f"{k} ${v:.2f}" for k, v in by_p.items()))
    elif cmd in ("owner", "limit", "budget"):
        mark = {"owner": "владелец %s", "limit": "лимит %s", "budget": "бюджет %s %s"}[cmd] % tuple(o.x[:2 if cmd == "budget" else 1])
        if p["owners"]:   # первый владелец ставится при установке; дальше — только нажатием владельца
            if not o.card: sys.exit("меняет только владелец нажатием: --card <id карточки> с «%s» в тексте" % mark)
            if card_spent(rs, o.card): sys.exit("эта карточка уже использована")
            by, why = tap(o.card, mark)
            if not by: sys.exit("не изменено: " + why)
            if by not in owners(p): sys.exit("меняет только владелец (нажал %s)" % by)
            p["cards"] = (p.get("cards") or []) + [o.card]
        if cmd == "owner": p["owners"] = sorted(set(map(str, p["owners"])) | {o.x[0]})
        elif cmd == "limit": p["monthly_limit_usd"] = float(o.x[0])
        else: p["budgets"][o.x[0]] = float(o.x[1])
        save_pol(p); print(json.dumps(p, ensure_ascii=False))
    else: sys.exit(__doc__)

if __name__ == "__main__": main()
