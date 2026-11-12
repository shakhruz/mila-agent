#!/usr/bin/env python3
"""Build the pack library's index (RU: «индекс библиотеки паков») for the mila-library repository.

  python3 tools/build_library.py <mila-library checkout>      # packs/<id>/ → dist/<archive>.zip + library.json; prints the lock line

Every pack is a Market archive without install.sh (tools/pack_mila.py, library mode): manifest.json with the sha256 of each file,
the secret scanner over every file. The index lists each archive with its sha256; the sha256 of library.json itself goes into
the core release (skills/library/library.lock) — the core trusts no index but that one. pack.json gets: category
(znakomstvo | razminka | biznes | obrazovanie), free: true, for_whom {ru, en, uz} — one plain line ≤120 chars: no links, @, `, commands or
imperatives (the same check library.py makes when it reads). A pack that fails stops the build. Only stdlib."""
import hashlib, importlib.util, json, os, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel)); m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m); return m


PM = _load("pack_mila", "tools/pack_mila.py")
LIB = _load("mila_library", "skills/library/library.py")


def check_meta(pid, m):
    why = []
    if m.get("category") not in LIB.CATS: why.append("category: one of %s" % ", ".join(LIB.CATS))
    if m.get("free") is not True: why.append("free: true (the library holds free packs only)")
    fw = m.get("for_whom") or {}
    if not isinstance(fw, dict) or not fw.get("ru"): why.append("for_whom.ru is needed")
    for lang, t in (m.get("title") or {}).items():
        if LIB.clean_title(t, "") == "": why.append("title.%s: one plain line ≤60 chars, no links, @, `, commands or imperatives" % lang)
    for lang, line in (fw.items() if isinstance(fw, dict) else []):
        if not LIB.clean_for_whom(line): why.append("for_whom.%s: one plain line ≤120 chars, no links, @, `, commands or imperatives" % lang)
    return ["%s: %s" % (pid, w) for w in why]


def build(repo):
    root = os.path.join(repo, "packs"); dist = os.path.join(repo, "dist"); entries, errs = [], []
    for pid in sorted(os.listdir(root)):
        f = os.path.join(root, pid, "pack.json")
        if not os.path.isfile(f): continue
        m = json.load(open(f, encoding="utf-8")); e = check_meta(pid, m)
        if e: errs += e; continue
        path, man = PM.build(pid, dist, packs_root=root, library=True)
        entries.append({"id": pid, "version": man["version"], "category": m["category"], "title": m["title"], "for_whom": m["for_whom"],
                        "free": True, "needs_packs": m.get("needs_packs") or [], "requires_core": m.get("requires_core"),
                        "archive": "dist/" + os.path.basename(path), "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest()})
    if errs: raise SystemExit("library not built:\n" + "\n".join(errs))
    ix = {"v": 1, "built": time.strftime("%Y-%m-%d"), "packs": entries}
    b = (json.dumps(ix, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode()
    open(os.path.join(repo, "library.json"), "wb").write(b)
    return hashlib.sha256(b).hexdigest(), len(entries)


if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit(__doc__)
    sha, n = build(sys.argv[1])
    print(json.dumps({"packs": n, "index_sha256": sha, "lock": "skills/library/library.lock ← index_sha256 (with the core release)"}))
