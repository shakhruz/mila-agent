#!/usr/bin/env python3
"""fleet_plan.py — одна таблица по многим домам перед раскаткой, только чтение.

  fleet_plan.py --homes-file HOMES --src <клон выпуска> [--json]

HOMES — строка на Милу: «имя  /абсолютный/путь/к/дому» (# — комментарий). Для каждого дома зовётся
`update.py plan --json --src …` с MILA_HOME=<дом>: без --offer план ничего не пишет ни в дом, ни в журнал.
Колонки: Мила · стоит · станет · риск · её правки · поставлено не обновлением · совет заменить сторожа.
Дом не читается или план упал — строка «нет плана: причина», остальные дома считаются дальше.
От root план идёт правами хозяина дома (uid/gid владельца папки дома): дом пишет Мила, и симлинк из него наружу
root читать не должен. Клон выпуска и этот файл должны быть читаемы хозяином дома. Только stdlib."""
import argparse, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
UPDATE = os.path.join(HERE, "update.py")


def read_homes(path):
    out = []
    for i, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or not os.path.isabs(parts[1].strip()):
            out.append({"name": parts[0], "home": "", "error": "строка %d: нужно «имя /абсолютный/путь»" % i})
            continue
        out.append({"name": parts[0], "home": parts[1].strip()})
    return out


def as_owner(home, euid=None):
    """От root — (uid, gid) хозяина дома для запуска плана; не от root — None (план идёт своими правами)."""
    if (os.geteuid() if euid is None else euid) != 0:
        return None
    st = os.stat(home)
    if st.st_uid == 0:
        raise PermissionError("дом принадлежит root — план от root по дому не запускаю")
    return st.st_uid, st.st_gid


def _drop(ids):
    def f():
        os.setgroups([]); os.setgid(ids[1]); os.setuid(ids[0])
    return f


def plan_one(home, src, timeout=180):
    if not os.path.isdir(home):
        return {"error": "дома нет или он не читается"}
    try:
        ids = as_owner(home)
    except (OSError, PermissionError) as e:
        return {"error": str(e)[:160]}
    env = dict(os.environ, MILA_HOME=home)
    for k in ("CLAUDE_CONFIG_DIR", "MILA_WORK", "MILA_CHOWN"):   # пути — только из дома; chown при чтении не нужен
        env.pop(k, None)
    try:
        if ids:
            env["HOME"] = home
        r = subprocess.run([sys.executable, UPDATE, "plan", "--json", "--src", src], capture_output=True, text=True, env=env, timeout=timeout,
                           preexec_fn=_drop(ids) if ids else None, cwd=home if ids else None)
    except subprocess.TimeoutExpired:
        return {"error": "план не уложился в %d с" % timeout}
    try:
        d = json.loads(r.stdout)
    except ValueError:
        tail = (r.stderr or r.stdout or "").strip().splitlines()
        return {"error": (tail[-1] if tail else "пустой ответ")[:160]}
    if not isinstance(d, dict) or d.get("error"):
        return {"error": str(d.get("error") if isinstance(d, dict) else d)[:160]}
    keep = d.get("keep") or {}
    return {"from": d.get("from") or "—", "to": d.get("to") or "—", "risk": d.get("risk") or "—",
            "mine": len(keep.get("ваша правка") or []), "other": len(keep.get("отличается") or []),
            "take": list(d.get("recommend_take") or []), "word": list(d.get("word") or [])}


def table(rows):
    head = ("Мила", "стоит", "станет", "риск", "её правки", "не обновлением", "совет")
    lines = [head]
    for r in rows:
        if r.get("error"):
            lines.append((r["name"], "нет плана: " + r["error"], "", "", "", "", ""))
            continue
        tip = "заменить сторожа" if r["take"] else ""
        if r["word"]:
            tip = (tip + "; " if tip else "") + "меняется канон — читать"
        lines.append((r["name"], r["from"], r["to"], r["risk"], str(r["mine"]), str(r["other"]), tip))
    w = [max(len(l[i]) for l in lines if not (i and l[1].startswith("нет плана"))) for i in range(len(head))]
    out = []
    for l in lines:
        out.append(l[0].ljust(w[0]) + "  " + l[1] if l[1].startswith("нет плана") else "  ".join(c.ljust(w[i]) for i, c in enumerate(l)).rstrip())
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="план обновления по многим домам (только чтение)")
    ap.add_argument("--homes-file", required=True); ap.add_argument("--src", required=True); ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isfile(os.path.join(a.src, "release.json")):
        sys.exit("--src: нет release.json — это не клон выпуска ядра")
    rows = []
    for h in read_homes(a.homes_file):
        rows.append(dict(h, **(plan_one(h["home"], os.path.abspath(a.src)) if not h.get("error") else {})))
    print(json.dumps(rows, ensure_ascii=False, indent=1) if a.json else table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
