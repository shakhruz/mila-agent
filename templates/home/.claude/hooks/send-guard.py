#!/usr/bin/env python3
"""send-guard.py — a PreToolUse hook on reply / edit_message: the last check before a message leaves.
It sits on the send path because a rule in the prompt does not fix a text that is already written.
Blocks: a recipient who is not the owner or a connected chat · keys and tokens · ids of other chats · internals (server paths,
container names, raw provider errors) · markdown without format=markdownv2. Prints no secrets.
Fail closed (the hook itself, not only the settings field): input it cannot read, or any unexpected error inside the guard → exit 2
and a deny — the message is not sent. Not our tool → exit 0. This guard catches the model's mistakes; it is not a security boundary
against a hostile sender (see docs/THREAT-MODEL.md)."""
import json, os, re, sys


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
if not (tool.endswith("__reply") or tool.endswith("__edit_message")):
    sys.exit(0)
args = p.get("tool_input") or {}
_body = str(args.get("text") or "")
_cap = str(args.get("caption") or "")   # a photo/album caption goes to Telegram too — checked with the text
text = (_body + "\n" + _cap).strip() if _cap else _body
chat_id = str(args.get("chat_id") or "").strip()
owner = (os.environ.get("OWNER_ID") or "").strip()
fmt = (args.get("format") or "text").lower()
why = []

# besides the owner, allowed are the groups in access.json (the owner connects Mila there with a card)
# and private chats of allowed people (allowFrom).
_allowed = set()
_card_allow = set()
try:
    _acc = json.load(open(os.path.expanduser("~/.claude/channels/telegram/access.json"), encoding="utf-8"))
    _allowed = {str(k) for k in (_acc.get("groups") or {}).keys()} | {str(x) for x in (_acc.get("allowFrom") or [])}
    _card_allow = {re.sub(r"\D", "", str(x)) for x in (_acc.get("cardAllow") or [])}   # the owner's own payment details (not masked)
except Exception:
    pass
# no OWNER_ID — access.json (allowFrom + groups) is enough;
# neither — no recipient check (Mila is not connected yet; the only place to write is the reply itself)
if chat_id and (owner or _allowed) and chat_id != owner and chat_id not in _allowed:
    why.append("адресат %s — не хозяин и не подключённый чат: говорю только там, куда меня подключили" % chat_id)

SECRETS = [
    (r"\b(?:sk|pk)[-_][A-Za-z0-9\-_]{16,}", "ключ провайдера (sk-/sk_/pk_)"),
    (r"\b\d{6,12}:[A-Za-z0-9_-]{30,50}\b", "токен Telegram-бота"),
    (r"\bAKIA[0-9A-Z]{16}\b", "ключ AWS"),
    (r"\bgh[pous]_[A-Za-z0-9]{20,}\b", "токен GitHub"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "токен Slack"),
    (r"\bcmp_[A-Za-z0-9]{16,}\b", "токен API"),
]
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
if _card_hits and chat_id.startswith("-"):
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
# not «sorry»). Exception: the development chat and a text with a defect number (D-0xxx) — that is a report.
_APOLOGY = re.compile(r"(?:\bизвин\w*|\bпрост(?:и|ите)\b|прошу прощения|\bмо[яй] (?:ошибк|вин|дыр)\w*|\bвиноват\w*|с опозданием|\bоправд\w*|к сожалению,? (?:я )?не (?:успел|смогл)\w*|\bsorry\b|\bapolog\w*)", re.I)
if chat_id != os.environ.get("MILA_DEV_CHAT", "") and not re.search(r"\bD-0\d{3}\b", text):
    _m = _APOLOGY.search(text)
    if _m:
        why.append("извинение/оправдание («%s») — в чат не уходит: человеку только дело и следующий шаг (закон 7)" % _m.group(0))

if fmt != "markdownv2":
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

if not why:
    if _card_hits:   # private chat / owner: sent, with the card masked
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                                 "permissionDecisionReason": "номер карты заменён маской",
                                                 "updatedInput": dict(args, text=mask_cards(_body), **({"caption": mask_cards(_cap)} if _cap else {}))}}, ensure_ascii=False))
    sys.exit(0)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                         "permissionDecisionReason": "Не отправляю: " + "; ".join(why)}},
                 ensure_ascii=False))
