#!/usr/bin/env python3
"""skill-hint.py — UserPromptSubmit: одно короткое слово в личке владельца → подсказка, какой навык вызвать.

Навык подбирается моделью по описанию, а на одно слово («пульт», «календарь») описание не срабатывает: Мила отвечает своими
словами, навык молчит. Этот хук смотрит на сообщение целиком: если это ровно слово из карты (без знаков, без регистра; можно
с «/» в начале), добавляет строку «вызови навык X». Только если навык стоит у этой Милы. Ничего не блокирует, сбой — молчание.

Кто написал: подсказка только для владельца — терминал (без конверта) или конверт Telegram из его лички (chat_id = OWNER_ID,
иначе — единственный allowFrom в access.json). Группа, гость, чужая личка — молчание: «расход», «сейф», «подписка» в группе
не должны открывать навыки владельца. В группе тоже молчим: в конверте нет id автора, а имя может назваться кем угодно.

Карта: DEFAULT + ~/.claude/skill-hints.json {"слово": "имя-навыка"} поверх (каждая Мила дописывает свою карту).
Сообщение из Telegram приходит в конверте <channel …>текст</channel> — смотрим только последний конверт."""
import json, os, re, sys

DEFAULT = {"пульт": "pult-dnya", "пульт дня": "pult-dnya", "pult": "pult-dnya", "входящие": "inbox", "inbox": "inbox",
           "расписание": "raspisanie", "дела": "dela", "задачи": "tasks", "обновись": "mila-update", "версия": "mila-update",
           "сейф": "safe-link", "подписка": "subscription", "расход": "spend"}
CLAUDE = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def owner_id():
    o = (os.environ.get("OWNER_ID") or "").strip()
    if o: return o
    try:
        a = json.load(open(os.path.join(os.environ.get("TELEGRAM_STATE_DIR") or os.path.join(CLAUDE, "channels", "telegram"), "access.json")))
        af = [str(x) for x in (a.get("allowFrom") or [])]
        return af[0] if len(af) == 1 else ""
    except (OSError, ValueError, AttributeError):
        return ""


def word(prompt):
    """→ слово, если сообщение от владельца и короткое; иначе ""."""
    s = str(prompt or "")
    m = re.findall(r"<channel\b([^>]*)>(.*?)</channel>", s, re.S)
    if m:
        attrs, s = m[-1]
        chat = re.search(r'\bchat_id="(-?\d+)"', attrs)
        own = owner_id()
        if not chat or not own or chat.group(1) != own: return ""
    s = s.strip().lstrip("/").strip()
    s = re.sub(r"[\s.!?…,;:«»\"']+$", "", s).strip().lower().replace("ё", "е")
    return s if 0 < len(s) <= 30 and "\n" not in s else ""


def hints():
    try:
        d = json.load(open(os.path.join(CLAUDE, "skill-hints.json"), encoding="utf-8"))
        if isinstance(d, dict): return {**DEFAULT, **{str(k).lower().replace("ё", "е"): str(v) for k, v in d.items()}}   # своя карта поверх общей
    except (OSError, ValueError):
        pass
    return DEFAULT


def main():
    try:
        p = json.loads(sys.stdin.read() or "{}")
        w = word(p.get("prompt"))
        skill = hints().get(w) if w else None
        if skill and re.fullmatch(r"[a-z0-9:_-]{1,60}", skill) and os.path.isfile(os.path.join(CLAUDE, "skills", skill.split(":")[-1], "SKILL.md")):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                  "additionalContext": "Владелец написал одно слово «%s» — это навык %s: вызови его инструментом Skill (skill: \"%s\") до ответа." % (w, skill, skill)}},
                  ensure_ascii=False))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
