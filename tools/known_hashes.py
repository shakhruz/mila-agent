#!/usr/bin/env python3
"""known_hashes.py — sha256 всех прошлых версий файлов ядра → known-hashes.json в корне релиза.

Зачем: в домах живут старые версии файлов ядра, поставленные не обновлением (до первого version.json, шаблоном рождения).
updater считал их «отличается» и не брал без --take. С этим файлом updater узнаёт «нашу прошлую версию» и обновляет её как обычно.
Источники: (1) каждый тег — папки и файлы зон его манифеста; (2) для файлов — ВСЕ коммиты, где файл менялся (версии между тегами);
(3) known-hashes.extra.json в репо — проверенные хеши версий, которых нет в истории (например, шаблон рождения на сервере),
каждый с полем «откуда»; меняется только ревью, как код.

  python3 tools/known_hashes.py [--repo .] [--out known-hashes.json] [--tags v1.5.1,v1.6.5]   (по умолчанию — все теги v*)

Ключ — место назначения из манифеста ТОГО тега ({claude}/hooks/send-guard.py, {claude}/skills/<навык>, …), значение — отсортированный
список хешей той же функцией sha(), что у updater (первые 16 знаков sha256; папка — по путям и содержимому). Текущая версия тоже входит — это не вредно.
Строит скрипт выпуска, не человек; файл лежит в релизе рядом с release.json."""
import argparse, glob, io, json, os, re, subprocess, sys, tarfile, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "skills", "mila-update"))
os.environ.setdefault("MILA_HOME", tempfile.gettempdir())          # update.py при импорте ничего не пишет; дом не нужен
from update import sha   # noqa: E402  — тот же алгоритм, что у updater


def tags(repo):
    out = subprocess.run(["git", "-C", repo, "tag", "--list", "v*"], capture_output=True, text=True, check=True).stdout.split()
    return sorted((t for t in out if re.fullmatch(r"v\d+\.\d+\.\d+", t)), key=lambda t: [int(x) for x in t[1:].split(".")])


def extract(repo, tag, dst):
    data = subprocess.run(["git", "-C", repo, "archive", "--format=tar", tag], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        for m in t.getmembers():
            if m.issym() or m.islnk() or m.name.startswith("/") or ".." in m.name.split("/"): continue   # архив своего репо, но всё равно
            t.extract(m, dst, filter="data") if hasattr(tarfile, "data_filter") else t.extract(m, dst)


def hashes_of(tree):
    try: m = json.load(open(os.path.join(tree, "release.json"), encoding="utf-8"))
    except (OSError, ValueError): return {}
    out = {}
    for z in m.get("zones", []):
        if not isinstance(z, dict) or ".." in str(z.get("src", "")).split("/"): continue
        for s in sorted(glob.glob(os.path.join(tree, z["src"]))):
            name = os.path.basename(s.rstrip("/"))
            if name == "__pycache__" or any(__import__("fnmatch").fnmatch(name, k) for k in z.get("skip", [])): continue
            if z.get("kind") == "dir" and not os.path.isdir(s): continue
            if z.get("kind") == "file" and not os.path.isfile(s): continue
            h = sha(s)
            if h: out.setdefault(z["dst"].replace("*", name), set()).add(h)
    return out


def file_zones(tree):
    """relpath файла в репо → место назначения (только зоны kind=file)."""
    try: m = json.load(open(os.path.join(tree, "release.json"), encoding="utf-8"))
    except (OSError, ValueError): return {}
    out = {}
    for z in m.get("zones", []):
        if not isinstance(z, dict) or z.get("kind") != "file": continue
        for s in glob.glob(os.path.join(tree, z["src"])):
            if os.path.isfile(s): out[os.path.relpath(s, tree)] = z["dst"].replace("*", os.path.basename(s))
    return out


def file_history(repo, rel):
    import hashlib
    revs = subprocess.run(["git", "-C", repo, "log", "--all", "--format=%H", "--", rel], capture_output=True, text=True).stdout.split()
    out = set()
    for r in revs:
        b = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (r, rel)], capture_output=True)
        if b.returncode == 0: out.add(hashlib.sha256(b.stdout).hexdigest()[:16])   # как sha() у updater: 16 знаков
    return out


def extra(repo):
    p = os.path.join(repo, "known-hashes.extra.json")
    try: d = json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return {}
    out = {}
    for row in d.get("files", []):
        k, h, src = row.get("dst"), row.get("sha256"), row.get("from")
        if not (isinstance(k, str) and k.startswith(("{claude}/", "{work}/", "{home}/")) and isinstance(h, str) and re.fullmatch(r"[0-9a-f]{16}|[0-9a-f]{64}", h) and src):
            raise SystemExit("known-hashes.extra.json: строка без dst/sha256/from или не по форме: %r" % row)
        out.setdefault(k, set()).add(h[:16])
    return out


def build(repo, only=None):
    allh, rels = {}, {}
    for tag in (only or tags(repo)):
        with tempfile.TemporaryDirectory() as d:
            extract(repo, tag, d)
            for k, v in hashes_of(d).items(): allh.setdefault(k, set()).update(v)
            rels.update(file_zones(d))
    for rel, k in sorted(rels.items()): allh.setdefault(k, set()).update(file_history(repo, rel))
    for k, v in extra(repo).items(): allh.setdefault(k, set()).update(v)
    return {k: sorted(v) for k, v in sorted(allh.items())}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--repo", default=os.path.join(HERE, "..")); ap.add_argument("--out", default="known-hashes.json")
    ap.add_argument("--tags"); a = ap.parse_args(argv)
    res = build(a.repo, a.tags.split(",") if a.tags else None)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump({"format": 1, "files": res}, f, ensure_ascii=False, indent=0, sort_keys=True); f.write("\n")
    os.replace(tmp, a.out)
    print("known-hashes: %d мест, %d хешей" % (len(res), sum(len(v) for v in res.values())))


if __name__ == "__main__":
    main()
