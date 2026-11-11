#!/usr/bin/env python3
"""send-guard.py — a PreToolUse hook on reply / edit_message / topic: the last check before a message or a topic name leaves.
It sits on the send path because a rule in the prompt does not fix a text that is already written.
Blocks: a recipient who is not the owner or a connected chat · keys and tokens · ids of other chats · internals (server paths,
container names, raw provider errors) · markdown without format=markdownv2. Prints no secrets.
Fail closed (the hook itself, not only the settings field): input it cannot read, or any unexpected error inside the guard → exit 2
and a deny — the message is not sent. Not our tool → exit 0. This guard catches the model's mistakes; it is not a security boundary
against a hostile sender (see docs/THREAT-MODEL.md)."""
import json, os, re, sys, time


def _block(reason):
    """Exit 2 = Claude Code blocks the tool call; the JSON deny says why (no secrets in the reason)."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": "Не отправляю: " + reason}}, ensure_ascii=False))
    sys.stderr.write("send-guard: blocked — %s\n" % reason)
    sys.exit(2)


sys.excepthook = lambda t, e, tb: _block("сторож отправки не смог проверить сообщение (%s) — не отправляю непроверенное" % t.__name__)

raw = sys.stdin.read()
try:
    p = json.loads(raw)
    if not isinstance(p, dict):
        raise ValueError("not an object")
except Exception:
    _block("вход сторожа не читается — не отправляю непроверенное")
tool = p.get("tool_name") or ""
TOPIC = tool.endswith("__topic")   # a forum topic's name (create / rename) is seen by everyone in the group
if not (tool.endswith("__reply") or tool.endswith("__edit_message") or TOPIC):
    sys.exit(0)
args = p.get("tool_input") or {}
if TOPIC and not str(args.get("name") or "").strip():
    sys.exit(0)   # list / close / reopen: no text leaves
_body = str(args.get("name") if TOPIC else args.get("text") or "")
_cap = str(args.get("caption") or "")   # a photo/album caption goes to Telegram too — checked with the text
text = (_body + "\n" + _cap).strip() if _cap else _body
chat_id = str(args.get("chat_id") or "").strip()
owner = (os.environ.get("OWNER_ID") or "").strip()
fmt = (args.get("format") or "text").lower()
why = []

# besides the owner, allowed are the groups in access.json (the owner connects Mila there with a card)
# and private chats of allowed people (allowFrom).
SECRETS = [
    (r"\b(?:sk|pk)[-_][A-Za-z0-9\-_]{16,}", "ключ провайдера (sk-/sk_/pk_)"),
    (r"\b\d{6,12}:[A-Za-z0-9_-]{30,50}\b", "токен Telegram-бота"),
    (r"\bAK" r"IA[0-9A-Z]{16}\b", "ключ AWS"),
    (r"\bgh[pous]_[A-Za-z0-9]{20,}\b", "токен GitHub"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "токен Slack"),
    (r"\bcmp_[A-Za-z0-9]{16,}\b", "токен API"),
]
SECRETS_EARLY = SECRETS

_allowed = set()
_card_allow = set()
_acc_ok = False
try:
    _acc = json.load(open(os.path.expanduser("~/.claude/channels/telegram/access.json"), encoding="utf-8"))
    _allowed = {str(k) for k in (_acc.get("groups") or {}).keys()} | {str(x) for x in (_acc.get("allowFrom") or [])}
    _card_allow = {re.sub(r"\D", "", str(x)) for x in (_acc.get("cardAllow") or [])}   # the owner's own payment details (not masked)
    _acc_ok = True
except Exception:
    pass
# no OWNER_ID — access.json (allowFrom + groups) is enough. Neither (no owner id, access.json missing or unreadable) — I do not
# know who may get messages, so nothing goes out: before pairing there is nobody to write to, after it a broken file is a fault.
if chat_id and not owner and not _acc_ok:
    why.append("не знаю, кому можно писать: нет OWNER_ID и не читается access.json — проверь подключение (mila doctor)")
elif chat_id and chat_id != owner and chat_id not in _allowed:
    why.append("адресат %s — не хозяин и не подключённый чат: говорю только там, куда меня подключили" % chat_id)

# files attached to a reply leave the machine too: only regular files inside the home or the temp folder, never keys or
# the agent's own wiring, and a text file with a key inside is not sent.
_HOME = os.path.realpath(os.path.expanduser("~"))
_TMP = [os.path.realpath(x) for x in {"/tmp", os.environ.get("TMPDIR") or "/tmp"}]
_SECRET_PATH = re.compile(r"(^|/)(\.env[^/]*|secrets?|\.ssh|\.gnupg|\.aws|\.config)(/|$)|\.credentials\.json$|(^|/)pd\.key$|\.(pem|key|p12|pfx)$|(^|/)(access|settings|permissions)\.json$", re.I)
_files = args.get("files") or []
if not isinstance(_files, list):
    _files = [_files]
for _f in _files[:20]:
    _rp = os.path.realpath(os.path.expanduser(str(_f)))
    _inside = os.path.commonpath([_rp, _HOME]) == _HOME or any(os.path.commonpath([_rp, t]) == t for t in _TMP)
    _claude = os.path.commonpath([_rp, os.path.join(_HOME, ".claude")]) == os.path.join(_HOME, ".claude") and "/inbox/" not in _rp
    if not _inside:
        why.append("файл %s — вне дома: отправляю только свои файлы" % os.path.basename(_rp)); continue
    if _SECRET_PATH.search(_rp) or _claude:
        why.append("файл %s — ключи и обвязка агента наружу не уходят" % os.path.basename(_rp)); continue
    try:
        if os.path.isfile(_rp) and os.path.getsize(_rp) <= 2 * 1024 * 1024:
            _head = open(_rp, "rb").read(2 * 1024 * 1024)
            if b"\x00" not in _head[:4096]:
                _ft = _head.decode("utf-8", "ignore")
                for _rx, _nm in SECRETS_EARLY:
                    if re.search(_rx, _ft):
                        why.append("в файле %s %s — такой файл не отправляю" % (os.path.basename(_rp), _nm)); break
    except OSError:
        why.append("файл %s не читается — непроверенное не отправляю" % os.path.basename(_rp))

for rx, name in SECRETS:
    if re.search(rx, text):
        why.append("в тексте %s — секреты в чат не пишем, хозяину: «перевыпустить»" % name)
# 13–19 digits in a row (spaces or dashes allowed) that pass the Luhn check → a card number. To a group — blocked, rewrite
# without it; to the owner or a private chat — sent, with the number masked as ****1234 (updatedInput). A phone with «+» is not a card.
_PAN = re.compile(r"(?<![\d+])(?:\d[ -]?){12,}\d(?![\d])")
def _luhn(d):
    t = 0
    for i, ch in enumerate(reversed(d)):
        x = int(ch)
        if i % 2:
            x = x * 2 - 9 if x > 4 else x * 2
        t += x
    return t % 10 == 0
def _cards(t):
    """[(начало, конец, цифры)] — окно групп цифр 13–19, Луна; сумма после номера («… 1234 100 USD») не мешает."""
    out = []
    for m in _PAN.finditer(t):
        txt = m.group(); parts = [g.span() for g in re.finditer(r"\d+", txt)]; i = 0
        while i < len(parts):
            cand = []
            for j in range(len(parts) - 1, i - 1, -1):
                d = re.sub(r"\D", "", txt[parts[i][0]:parts[j][1]])
                if 13 <= len(d) <= 19 and len(set(d)) > 1 and _luhn(d) and d not in _card_allow:
                    cand.append((j, d))
            hit = next((c for c in cand if len(c[1]) == 16), cand[0] if cand else None)   # 16 digits is the usual card length; otherwise the longest window
            if not hit:
                i += 1; continue
            out.append((m.start() + parts[i][0], m.start() + parts[hit[0]][1], hit[1])); i = hit[0] + 1
    return out
def mask_cards(t):
    for a, b, d in reversed(_cards(t)):
        t = t[:a] + "****" + d[-4:] + t[b:]
    return t
_card_hits = _cards(text)
if _card_hits and (chat_id.startswith("-") or TOPIC):
    why.append("в тексте номер банковской карты — в группу не отправляю; перепиши без номера (если нужно — только ****%s)" % _card_hits[0][2][-4:])
if re.search(r"(?<!\d)-100\d{10}(?!\d)", text):
    why.append("в тексте id чата (-100…) — внутренние номера наружу не показываем, называй чат по имени")

KITCHEN = [
    (r"/srv/|/home/companion|/opt/", "серверный путь"),
    (r"\bpodman\b|\bsystemctl\b|api\.sock|stream-json|\.credentials\.json", "устройство контейнера"),
    (r"Traceback \(most recent|Error calling LLM|rate_limit_error|overloaded_error|authentication_error|HTTP/?\s?\d{3}\b.*error", "сырая ошибка провайдера"),
    (r"hookSpecificOutput|tool_use|PreToolUse|PostToolUse", "внутренности хуков"),
]
for rx, name in KITCHEN:
    if re.search(rx, text, re.I):
        why.append("кухня наружу (%s) — скажи результат словами человека" % name)

# apologies and excuses do not go out — neither to a client nor to the owner (constitution, law 7: fact · conclusion · step,
# not «sorry»). Exception: the development chat, and a report on a problem from the problem journal (skill problemy): the text
# names a number P-0001 that IS in work/problemy.jsonl and is open, or was closed today — and only in the owner's chat. A number alone opens nothing — any text
# could carry one; a journal that cannot be read opens nothing either.
def _problem_report(text):
    nums = set(re.findall(r"(?<![\w-])P-\d{4,6}(?![\w-])", text))
    if not nums: return False
    path = os.path.join(os.path.expanduser(os.environ.get("MILA_WORK") or "~/work"), "problemy.jsonl")
    try:
        if os.path.getsize(path) > 8 * 1024 * 1024: return False
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return False
    st = {}
    for l in lines:
        try: r = json.loads(l)
        except ValueError: continue
        if not isinstance(r, dict) or r.get("n") not in nums: continue
        step = r.get("шаг")
        if step == "найдено":   # a whole line as problemy.py writes it: the fact and a pointer to evidence — a bare line typed by hand does not count
            if isinstance(r.get("что"), str) and r["что"].strip() and re.fullmatch(r"(msg|file|link|journal|kassa|commit):\S{1,300}", str(r.get("улика") or "")):
                st.setdefault(r["n"], "open")
        elif r["n"] in st and step == "закрыто": st[r["n"]] = str(r.get("ts") or "")[:10]
        elif r["n"] in st and step == "повтор": st[r["n"]] = "open"
    return any(v == "open" or v == time.strftime("%Y-%m-%d") for v in st.values())

_APOLOGY = re.compile(r"(?:\bизвин\w*|\bпрост(?:и|ите)\b|прошу прощения|\bмо[яй] (?:ошибк|вин|дыр)\w*|\bвиноват\w*|с опозданием|\bоправд\w*|к сожалению,? (?:я )?не (?:успел|смогл)\w*|\bsorry\b|\bapolog\w*)", re.I)
# A report on a problem goes to the owner: the number opens the filter only in the owner's own chat (OWNER_ID — the id the owners'
# list is made from), never in a group or a client's chat.
if not TOPIC and chat_id != os.environ.get("MILA_DEV_CHAT", "") and not (owner and chat_id == owner and _problem_report(text)):
    _m = _APOLOGY.search(text)
    if _m:
        why.append("извинение/оправдание («%s») — в чат не уходит: человеку только дело и следующий шаг (закон 7)" % _m.group(0))

if fmt != "markdownv2" and not TOPIC:
    marks = []
    if re.search(r"\*\*[^*\n]+\*\*", text): marks.append("**жирный**")
    if re.search(r"(?m)^\s*[-*] ", text): marks.append("списки через - или *")
    if re.search(r"`[^`\n]+`", text): marks.append("`код`")
    if re.search(r"\[[^\]\n]+\]\([^)\n]+\)", text): marks.append("[ссылки](адрес)")
    if marks:
        why.append("разметка (%s) без format=markdownv2 — получатель увидит сырые звёздочки; "
                   "собери через tg.py умения milagpt-chat или убери разметку" % ", ".join(marks))

# --- (D-NNNN, 20.09.2026) ---------------------------------------
# One session serves all chats, there is no wall between them. The lock on the way out: chat X does not get the @tag of a person
# or the title of a chat that never appeared in X but did in another chat. The owner and internal chats
# (~/.claude/hooks/internal-chats.json — a list of ids) may get anything. The register is built from the inbound journal;
# people seen in three or more chats count as the team.
try:
    _fc_internal = set()
    try:
        _fc_internal = {str(x) for x in json.load(open(os.path.expanduser("~/.claude/hooks/internal-chats.json"), encoding="utf-8"))}
    except Exception:
        pass
    # Chats of one matter — ~/.claude/hooks/same-case-chats.json, a list of id groups
    # ([["-100 Acme client group", "<id> Agency Work"], …]); inside a group people and chat titles are not «someone else's matter».
    # Per Mila (her own config), not global.
    _fc_groups = []
    try:
        _fc_groups = [{str(x) for x in g} for g in json.load(open(os.path.expanduser("~/.claude/hooks/same-case-chats.json"), encoding="utf-8")) if isinstance(g, list)]
    except Exception:
        pass
    _fc_same = lambda a, b: a == b or any(a in g and b in g for g in _fc_groups)
    if chat_id and chat_id != owner and chat_id not in _fc_internal:
        _fc_ev = os.path.join(os.environ.get("TELEGRAM_JOURNAL_DIR") or os.path.expanduser("~/.claude/channels/telegram"),
                              "inbound", "events.jsonl")
        _fc_users, _fc_titles = {}, {}
        with open(_fc_ev, "rb") as _fc_f:
            _fc_f.seek(0, 2); _fc_sz = _fc_f.tell(); _fc_f.seek(max(0, _fc_sz - 8_000_000))
            for _fc_line in _fc_f.read().decode("utf-8", "ignore").splitlines():
                try:
                    _fc_m = (json.loads(_fc_line).get("params") or {}).get("meta") or {}
                except Exception:
                    continue
                _fc_c = str(_fc_m.get("chat_id") or "")
                if not _fc_c:
                    continue
                _fc_u = str(_fc_m.get("user") or "").lower()
                if _fc_u:
                    _fc_users.setdefault(_fc_u, set()).add(_fc_c)
                _fc_t = str(_fc_m.get("chat_title") or "")
                if _fc_t:
                    _fc_titles[_fc_c] = _fc_t
        _fc_stop = {"milagpt", "рабочий", "рабочая", "группа", "group", "команда", "клуб", "business", "development"}
        _fc_low = text.lower()
        for _fc_tag in set(re.findall(r"@([A-Za-z][A-Za-z0-9_]{3,31})", text)):
            _fc_k = _fc_tag.lower()
            _fc_seen = _fc_users.get(_fc_k)
            if _fc_seen and not any(_fc_same(chat_id, x) for x in _fc_seen) and len(_fc_seen) < 3 and not _fc_k.endswith("bot"):
                why.append("в этом чате нет человека @%s — он из другого чата; чужое дело и чужого человека здесь не называю (закон о тайне)" % _fc_tag)
        for _fc_c, _fc_t in _fc_titles.items():
            if _fc_same(chat_id, _fc_c) or _fc_c in _fc_internal:
                continue
            for _fc_part in re.split(r"\s+[x×·|—–-]\s+|[«»\"()]", _fc_t):
                _fc_part = _fc_part.strip().lower()
                if len(_fc_part) < 5 or _fc_part in _fc_stop:
                    continue
                _fc_mine = str(_fc_titles.get(chat_id) or "").lower()
                if _fc_part in _fc_mine:
                    continue
                if re.search(r"(?<![\w])" + re.escape(_fc_part) + r"(?![\w])", _fc_low):
                    why.append("«%s» — название другого чата; в этом чате чужое дело не называю (закон о тайне)" % _fc_part)
                    break
except Exception:
    pass  # this optional lock must not break sending (its inputs are optional files)

# ── «Следующий ход»: every answer of Mila ends with two lines — «Мой ход» and «Ваш ход» ──────────────────────────────────────
# The form of an answer is not security: if this check itself breaks, the message GOES OUT, and the failure is written down
# (a line in work/state/next-move-fail.jsonl and, if the skill is there, a problem in the problem journal).
NM_MARK = (("Мой ход:", "Ваш ход:"), ("My move:", "Your move:"), ("Mening yurishim:", "Sizning yurishingiz:"))
NM_CONT = re.compile(r"^\(?(продолжение следует|continued|davomi bor)\)?\.?$", re.I)
NM_FORMS = ((1, r"делаю сейчас|doing now|hozir qilyapman"), (2, r"стоит в Планировщике|in the Scheduler|Rejalashtiruvchida"),
            (3, r"ничего не запущено|nothing is running|hech narsa ishga tushmagan"))
# a promise with a time, in the first person and in the future: «пришлю завтра», «напомню в 18:00», «вернусь через час»
NM_PROMISE = re.compile(r"(?i)(?<![а-яёa-z])(?:пришлю|напомню|вернусь|сделаю|отправлю|подготовлю|напишу|покажу|i(?:'ll| will) (?:send|remind|be back|do))(?![а-яё])"
                        r"[^.\n!?]{0,60}?(?:завтра|послезавтра|сегодня в|вечером|утром|в \d{1,2}[:.]\d{2}|через \d+ ?(?:минут|час|дн|недел)|tomorrow|at \d{1,2}[:.]\d{2}|in \d+ ?(?:min|hour|day))")
NM_EMPTY_BTN = re.compile(r"(?i)^\W*(?:принято|понятно|понял[аи]?|ок|ok|хорошо|спасибо|подробнее|ясно|got it|thanks|more|details)\W*$")
NM_IDLE = re.compile(r"(?i)ничего не нужно|иду дальше|продолжаю(?![а-яё])|nothing (?:is )?needed|moving on")
NM_DAYS = ("понедельник", "вторник", "сред", "четверг", "пятниц", "суббот", "воскресен")


def _nm_job(name, work):
    """the job with this name in the schedule → its next time (aware), or a reason why the promise does not stand."""
    import datetime as _d
    try: jobs = json.load(open(os.path.join(work, "schedule", "jobs.json"), encoding="utf-8")).get("jobs") or []
    except (OSError, ValueError, AttributeError): return None, "расписание не читается"
    job = next((j for j in jobs if isinstance(j, dict) and str(j.get("id")) == name), None)
    if not job: return None, "задачи «%s» в расписании нет" % name[:40]
    if job.get("enabled") is False: return None, "задача «%s» выключена" % name[:40]
    tz = _d.datetime.now().astimezone().tzinfo
    try:
        import zoneinfo
        m = re.search(r"Часовой пояс\s*[—-]\s*([A-Za-z_]+/[A-Za-z_]+)", open(os.path.join(work, "USER.md"), encoding="utf-8").read())
        if m: tz = zoneinfo.ZoneInfo(m.group(1))
    except Exception: pass
    v = os.environ.get("MILA_CRON_NOW")
    now = _d.datetime.fromisoformat(v).astimezone(tz) if v else _d.datetime.now(tz)
    if job.get("expires") and str(job["expires"])[:10] < now.date().isoformat(): return None, "задача «%s» истекла" % name[:40]
    for base in (os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "skills", "raspisanie"),
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "skills", "raspisanie")):
        if os.path.isfile(os.path.join(base, "cronspec.py")) and base not in sys.path: sys.path.insert(0, base)
    import cronspec
    nxt = cronspec.parse(str(job.get("cron") or "")).next_after(now)
    if nxt is None: return None, "у задачи «%s» нет следующего срока" % name[:40]
    return (nxt, now), None


def next_move(body, a, work):
    """reasons why this answer does not end with a proper «Мой ход / Ваш ход» — an empty list when it does."""
    lines = [re.sub(r"\\(.)", r"\1", l).strip(" \t*_•·") for l in body.split("\n")]
    lines = [l for l in lines if l]
    if not lines: return []
    if NM_CONT.match(lines[-1]): return []          # a part of a long answer: the two lines come in the last part
    mark = next((mk for mk in NM_MARK if len(lines) >= 2 and lines[-2].startswith(mk[0]) and lines[-1].startswith(mk[1])), None)
    if not mark:
        return ["ответ кончается двумя строками — «Мой ход: …» и «Ваш ход: …» (что делаю я и что советую вам); если это часть длинного ответа — последней строкой «(продолжение следует)»"]
    mine, yours, head = lines[-2][len(mark[0]):].strip(), lines[-1][len(mark[1]):].strip(), "\n".join(lines[:-2])
    out = []
    if len(mine) > 200 or len(yours) > 200: out.append("«Мой ход» и «Ваш ход» — по одной строке до 200 знаков")
    form = next((k for k, rx in NM_FORMS if re.match(r"(?i)\W*(?:%s)" % rx, mine)), None)
    if form is None:
        out.append("«Мой ход» — одна из трёх форм: «делаю сейчас — …», «стоит в Планировщике — «имя задачи», придёт …» или «ничего не запущено — …»")
    if form == 2:
        m = re.search(r"[«\"“]([^»\"”]{1,60})[»\"”]", mine)
        if not m: out.append("«стоит в Планировщике» — с именем задачи в кавычках: по нему сверяю расписание")
        else:
            got, err = _nm_job(m.group(1).strip(), work)
            if err: out.append("обещанное «само придёт» не стоит в расписании (%s) — сначала поставьте задачу (mila_cron.py add)" % err)
            else:
                nxt, now = got; low = mine.lower()
                hm = re.findall(r"\b(\d{1,2})[:.](\d{2})\b", mine)
                if not hm: out.append("«стоит в Планировщике» — со временем из расписания: ближайший срок %s" % nxt.strftime("%d.%m %H:%M"))
                elif not any((int(h), int(mi)) == (nxt.hour, nxt.minute) for h, mi in hm):
                    out.append("время в «Моём ходе» не совпадает с расписанием: ближайший срок задачи — %s" % nxt.strftime("%d.%m %H:%M"))
                day = next((i for i, w in enumerate(NM_DAYS) if w in low), None)
                if day is not None and day != nxt.weekday(): out.append("день недели в «Моём ходе» не совпадает с расписанием: ближайший срок — %s" % nxt.strftime("%d.%m %H:%M"))
                if "завтра" in low and (nxt.date() - now.date()).days != 1: out.append("«завтра» не совпадает с расписанием: ближайший срок — %s" % nxt.strftime("%d.%m %H:%M"))
                if "сегодня" in low and nxt.date() != now.date(): out.append("«сегодня» не совпадает с расписанием: ближайший срок — %s" % nxt.strftime("%d.%m %H:%M"))
    if form != 2 and NM_PROMISE.search(head + "\n" + mine):
        out.append("в ответе обещание со временем, а в «Моём ходе» нет задачи Планировщика — поставьте задачу и назовите её, или уберите обещание")
    if NM_IDLE.search(yours) or (form == 3 and NM_IDLE.search(mine)):
        out.append("«ничего не нужно, иду дальше» при пустом ходе хозяину непонятно — в «Вашем ходе» нужна рекомендация следующего шага")
    choices = [b for row in (a.get("buttons") or []) if isinstance(row, list) for b in row if isinstance(b, dict) and b.get("choice")]
    if a.get("multi") is not True:
        if not 2 <= len(choices) <= 3: out.append("под «Вашим ходом» — 2–3 кнопки-шага (сейчас %d); первая — рекомендуемая" % len(choices))
        elif choices[0].get("style") != "success": out.append("первая кнопка — рекомендуемый шаг, зелёная (style: success)")
    if any(NM_EMPTY_BTN.match(str(b.get("label") or "")) for b in choices):
        out.append("кнопка — шаг, который я сделаю сразу; пустые «Принято», «Подробнее», «Ок» — не кнопки")
    return out


if tool.endswith("__reply"):
    _nm_work = os.path.expanduser(os.environ.get("MILA_WORK") or "~/work")
    try:
        why += next_move(_body, args, _nm_work)
    except Exception as _nm_e:      # fail open: the answer goes, the failure is written down
        try:
            _nm_dir = os.path.join(_nm_work, "state"); os.makedirs(_nm_dir, exist_ok=True)
            _nm_f = os.path.join(_nm_dir, "next-move-fail.jsonl")
            with open(_nm_f, "a", encoding="utf-8") as _f:
                _f.write(json.dumps({"ts": __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"), "error": type(_nm_e).__name__, "chat_id": chat_id}, ensure_ascii=False) + "\n")
            _nm_n = sum(1 for _ in open(_nm_f, encoding="utf-8"))
            _nm_p = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "skills", "problemy", "scripts", "problemy.py")
            if os.path.isfile(_nm_p):
                import subprocess as _sp
                _sp.run([sys.executable, _nm_p, "add", "--chto", "проверка «Следующего хода» в стороже отправки сломалась: %s" % type(_nm_e).__name__, "--gde", "инструмент",
                         "--kto-nashel", "проверка", "--ulika", "journal:state/next-move-fail.jsonl:%d" % _nm_n], capture_output=True, timeout=10, env=dict(os.environ, MILA_WORK=_nm_work))
        except Exception:
            pass

if not why:
    if _card_hits:   # private chat / owner: sent, with the card masked
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                                 "permissionDecisionReason": "номер карты заменён маской",
                                                 "updatedInput": dict(args, text=mask_cards(_body), **({"caption": mask_cards(_cap)} if _cap else {}))}}, ensure_ascii=False))
    sys.exit(0)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                         "permissionDecisionReason": "Не отправляю: " + "; ".join(why)}},
                 ensure_ascii=False))
