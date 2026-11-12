#!/usr/bin/env python3
"""Свой Сейф из фонового сеанса: ключ коннектора — страницей на ЭТОМ компьютере, мимо чата.
  own_safe.py <connector-id> [--lang ru]   → {"ok": true, "url": "http://127.0.0.1:…/v/…/", "open": true|false, "expires_min": 10}
Фоновый сеанс пускает только скрипты из ~/.claude/skills и ~/.claude/hooks (хук run-allow.py), а страница сейфа — tools/seif/seif.py
own в папке набора (~/mila). Этот файл и есть мост между ними, поэтому он граница:
- seif.py берётся только из корня набора (~/mila, иначе ~/mila-companion): после всех ссылок файл лежит внутри корня, сам файл не
  ссылка, у файла, его папок и корня владелец — этот пользователь, и ни группа, ни все не могут их писать. Иначе — отказ, ничего не запущено.
- имя записи и поле — только из паспорта коннектора (connectors.py load, те же правила имён); в seif.py ничего другого не передаётся;
  запуск — списком аргументов, без оболочки.
- страница уходит в фон, команда возвращается сразу; браузер этого компьютера открывается сам (macOS open, Linux xdg-open).
  Не открылся (сервер без экрана) — "open": false, и Мила говорит одной строкой: «откройте ссылку на компьютере, где я работаю».
  С телефона ссылка не откроется — это адрес этого компьютера.
Ни ключа, ни ссылки в журналах нет; вывод — одна строка JSON со ссылкой для хозяина. Сохранил — seif пишет записку «в сейфе
появились …» без значения; дальше — connectors.py check <id>. Код выхода: 0 — страница открыта, 1 — отказ (причина в "why")."""
import json, os, shutil, stat, subprocess, sys

HERE = os.path.dirname(os.path.realpath(__file__))
SKILLS = os.path.dirname(os.path.dirname(HERE))


def out(d, code=0):
    print(json.dumps(d, ensure_ascii=False), flush=True); sys.exit(code)


def mine(p):
    """the path is this user's and nobody else can write it"""
    st = os.lstat(p)
    return st.st_uid == os.getuid() and not st.st_mode & 0o022


def kit_seif():
    """→ the real path of tools/seif/seif.py of the kit, or (None, why)."""
    home = os.path.expanduser("~")
    for root in (os.path.join(home, "mila"), os.path.join(home, "mila-companion")):
        p = os.path.join(root, "tools", "seif", "seif.py")
        if not os.path.lexists(p):
            continue
        r = os.path.realpath(root)
        if os.path.islink(p) or not os.path.isfile(p):
            return None, "seif.py набора — ссылка или не файл: не запускаю"
        real = os.path.realpath(p)
        if not real.startswith(r + os.sep):
            return None, "seif.py ведёт за пределы набора: не запускаю"
        chain = [real, os.path.dirname(real), os.path.dirname(os.path.dirname(real)), r]
        if not all(mine(x) for x in chain):
            return None, "seif.py или его папки чужие или открыты на запись другим: не запускаю"
        return real, ""
    return None, "в наборе нет страницы сейфа (tools/seif/seif.py) — обновите набор: mila update"


def passport(cid):
    sys.path.insert(0, os.path.join(SKILLS, "konnektory", "scripts"))
    try:
        import connectors
        d = connectors.load(cid)
    except Exception as e:   # connectors.Stop and a missing skill alike
        return None, str(e)[:200] or "навыка коннекторов нет"
    return d["safe"], ""


def open_browser(url):
    tool = "open" if sys.platform == "darwin" else "xdg-open"
    if not shutil.which(tool) or (tool == "xdg-open" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))):
        return False
    try:
        return subprocess.run([tool, url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15).returncode == 0
    except Exception:
        return False


def main(argv):
    if len(argv) < 2 or argv[1].startswith("-"):
        out({"ok": False, "why": "usage: own_safe.py <connector-id> [--lang ru]"}, 1)
    cid = argv[1]
    lang = argv[argv.index("--lang") + 1] if "--lang" in argv and argv.index("--lang") + 1 < len(argv) else ""
    safe, why = passport(cid)
    if not safe: out({"ok": False, "why": why}, 1)
    seif, why = kit_seif()
    if not seif: out({"ok": False, "why": why}, 1)
    cmd = [sys.executable, "-B", "-E", seif, "own", safe["field"], "--name", safe["name"]]
    if lang and lang.isalpha() and len(lang) <= 5: cmd += ["--lang", lang.lower()]
    r, w = os.pipe()
    env = {k: v for k, v in os.environ.items() if not k.startswith("SEIF_")}   # the page's folders are seif's own defaults, not the caller's
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=w, stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True,
                         cwd=os.path.expanduser("~"), env=env)
    os.close(w)
    first = b""
    with os.fdopen(r, "rb") as f:
        first = f.readline()   # seif own prints the link first; the page lives on in the background after we stop reading
    try:
        link = json.loads(first.decode("utf-8"))
    except ValueError:
        p.kill(); out({"ok": False, "why": "страница сейфа не поднялась"}, 1)
    if not link.get("ok") or not str(link.get("url", "")).startswith("http://127.0.0.1:"):
        p.kill(); out({"ok": False, "why": "страница сейфа ответила не ссылкой этого компьютера"}, 1)
    out({"ok": True, "url": link["url"], "open": open_browser(link["url"]), "expires_min": link.get("expires_min", 10),
         "say": "ссылка работает только на этом компьютере; после «сохранено» — connectors.py check %s" % cid})


if __name__ == "__main__":
    main(sys.argv)
