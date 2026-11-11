#!/usr/bin/env python3
"""Чтение сейфа Милы (work/secrets/<имя>.env, его пишет seif.py по одноразовой ссылке). Значения не печатает никогда.
  safe_read.py <имя> --check ПОЛЕ[,ПОЛЕ…]   → {"ok": true, "есть": [...], "нет": [...], "маска": {"CARD_NUMBER": "****1234"}}
  в коде: from safe_read import read_safe, mask; v = read_safe("login")["CARD_NUMBER"]
Файл с правами шире 600 — отказ (кто-то открыл сейф). Папка — SAFE_DIR или ~/work/secrets."""
import json, os, re, sys

SAFE_DIR = os.path.expanduser(os.environ.get("SAFE_DIR", "~/work/secrets"))


class SafeError(Exception):
    pass


def read_safe(name):
    if not re.fullmatch(r"[a-z0-9_-]{1,40}", name or ""):
        raise SafeError("имя сейфа — латиница, цифры, - и _")
    p = os.path.join(SAFE_DIR, name + ".env")
    # первым правилом, до прав: симлинк и путь вне папки сейфа — отказ
    if os.path.islink(p) or not os.path.realpath(p).startswith(os.path.realpath(SAFE_DIR) + os.sep):
        raise SafeError("сейф «%s» — ссылка или путь вне папки сейфа — не читаю, сказать администратору" % name)
    if not os.path.exists(p):
        raise SafeError("сейфа «%s» нет — попросить ссылку сейфа у администратору" % name)
    if os.stat(p).st_mode & 0o077:
        raise SafeError("сейф «%s» открыт для других (права не 600) — не читаю, сказать администратору" % name)
    out = {}
    try:
        lines = open(p, encoding="utf-8").read().split("\n")
    except (OSError, UnicodeDecodeError):
        raise SafeError("файл сейфа «%s» не читается" % name)
    for ln in lines:   # файл пишет seif.py или человек руками: CRLF, пробелы, export, "…" — понимаем все
        m = re.match(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$", ln.rstrip("\r\n"))
        if m:
            v = m.group(2)
            if len(v) >= 2 and v[0] == v[-1] == "'":
                v = v[1:-1].replace("'\\''", "'")
            elif len(v) >= 2 and v[0] == v[-1] == '"':
                v = v[1:-1]
            out[m.group(1)] = v
    return out


SECRET_SEG = {"PASS", "PASSWORD", "PASSWD", "PWD", "KEY", "TOKEN", "SECRET", "PIN", "CVV", "CVC"}


def mask(field, v):
    """Куски значения — только у явных полей (по целому сегменту имени); всё секретное и короткое — «••••»."""
    v = str(v or "")
    seg = set(field.upper().split("_"))
    if seg & SECRET_SEG:
        return "••••"
    if any(x.startswith("EXPIR") for x in seg):
        return "есть"
    digits = re.sub(r"\D", "", v)
    if "PAN" in seg or {"CARD", "NUMBER"} <= seg:
        return "****" + digits[-4:] if len(digits) > 8 else "••••"
    if seg & {"LOGIN", "USER", "USERNAME", "EMAIL", "PHONE"}:
        return v[:3] + "…" if len(v) > 4 else "••••"
    return "••••"


def main():
    a = sys.argv[1:]
    if not a or "--check" not in a:
        sys.exit(__doc__)
    i = a.index("--check")
    fields = [f for f in (a[i + 1].split(",") if i + 1 < len(a) else []) if f]
    if not fields:
        print(json.dumps({"ok": False, "error": "не указаны поля для --check"}, ensure_ascii=False)); sys.exit(2)
    try:
        d = read_safe(a[0])
    except SafeError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)); sys.exit(2)
    have = [f for f in fields if d.get(f)]
    print(json.dumps({"ok": len(have) == len(fields), "есть": have, "нет": [f for f in fields if f not in have],
                      "маска": {f: mask(f, d[f]) for f in have}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
