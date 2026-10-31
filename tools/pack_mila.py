#!/usr/bin/env python3
"""Ready-made Mila pack (RU: «пакет готовой Милы»): one zip a person installs on top of Mila Agent.

  python3 tools/pack_mila.py <role> [--out dist/] [--core-version X]   # packs/<role>/ → mila-pack-<role>-<version>.zip + manifest
  python3 tools/pack_mila.py <role> --doc OFFER.md                    # + the seller's document (checked by the same secret scanner)
  python3 tools/pack_mila.py --list                                    # roles that have packs/<role>/pack.json

A pack holds: ROLE.md (who this Mila is, her limits), WHAT.md (what she does, ru/en), pack-only skills (packs/<role>/<skill>/),
install.sh (puts them in place without overwriting — backups — and runs mila doctor), INSTALL.md and manifest.json
(every file with sha256, the core skills the role relies on, the minimal core version). Core skills are not copied: they come
with the core, install.sh only checks they are there.
Before writing the zip every file goes through the core's secret scanner (skills/mila-export) — a finding stops the build.
No secrets, no other clients' data: a pack is built only from packs/<role>/ of this repository. Only stdlib."""
import argparse, hashlib, importlib.util, io, json, os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXED_TIME = (2026, 1, 1, 0, 0, 0)         # the same pack → the same zip bytes


INSTALL_SH = r"""#!/usr/bin/env bash
# Install this ready-made Mila on top of Mila Agent. Nothing is overwritten: existing files get a .bak-<time> copy first.
#   bash install.sh [--dry-run]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DRY=0; [[ "${1:-}" == "--dry-run" ]] && DRY=1
CLAUDE="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; WORK="${MILA_WORK:-$HOME/work}"
command -v python3 >/dev/null 2>&1 || { echo "python3 is needed (it comes with Mila Agent's requirements)"; exit 4; }
say() { printf '%s\n' "$*"; }
run() { if [[ $DRY -eq 1 ]]; then say "would: $*"; else "$@"; fi; }
if [[ ! -d "$CLAUDE/skills/mila-update" ]]; then
  say "Mila Agent is not installed yet. First: curl -fsSL https://raw.githubusercontent.com/shakhruz/mila-agent/main/install/get.sh | bash"
  exit 2
fi
missing=()
for s in $(python3 -c 'import json,sys;print(" ".join(json.load(open(sys.argv[1]))["core_skills"]))' "$HERE/manifest.json"); do
  [[ -d "$CLAUDE/skills/$s" ]] || missing+=("$s")
done
if (( ${#missing[@]} )); then say "core skills missing: ${missing[*]} — update the core: mila update"; exit 3; fi
stamp=$(date +%Y%m%d-%H%M%S)
put() {   # put SRC DST
  if [[ -e "$2" ]] && ! cmp -s "$1" "$2"; then run cp -p "$2" "$2.bak-$stamp"; say "backup: $2.bak-$stamp"; fi
  run mkdir -p "$(dirname "$2")"; run cp "$1" "$2"
}
run mkdir -p "$WORK"
put "$HERE/ROLE.md" "$WORK/ROLE.md"
put "$HERE/WHAT.md" "$WORK/WHAT.md"
if [[ -d "$HERE/skills" ]]; then
  while IFS= read -r f; do put "$HERE/skills/$f" "$CLAUDE/skills/$f"; done < <(cd "$HERE/skills" && find . -type f | sed 's|^\./||')
fi
line="Read ~/work/ROLE.md right after the constitution — it is my role (installed from a ready-made Mila pack)."
if ! grep -qsF "$line" "$WORK/CLAUDE.md"; then
  if [[ $DRY -eq 1 ]]; then say "would: append the ROLE.md line to $WORK/CLAUDE.md"; else printf '\n%s\n' "$line" >> "$WORK/CLAUDE.md"; fi
fi
say "installed: $(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["title"]["en"], d["version"])' "$HERE/manifest.json")"
if command -v mila >/dev/null 2>&1 && [[ $DRY -eq 0 ]]; then mila doctor || true; else say "check: mila doctor"; fi
"""

INSTALL_MD = """# Install · Установка — {title_en} / {title_ru} {version}

**EN.** 1) Mila Agent first (one command, see the core README): `curl -fsSL https://raw.githubusercontent.com/shakhruz/mila-agent/main/install/get.sh | bash`,
then `mila onboard` (your Telegram bot token, your own Claude sign-in). 2) Unpack this zip and run `bash install.sh --dry-run`, then
`bash install.sh`: it puts ROLE.md and WHAT.md into ~/work, the pack's skills into ~/.claude/skills (anything existing is backed up),
adds one line to ~/work/CLAUDE.md and runs `mila doctor`. 3) Restart: `mila`. Write to your bot — Mila offers her first three tasks.
Needs core {core} or newer; core skills used: {skills}.

**RU.** 1) Сначала Mila Agent (одна команда из README ядра), затем `mila onboard` — токен вашего бота и ваш вход в Claude.
2) Распакуйте архив: `bash install.sh --dry-run`, затем `bash install.sh` — ROLE.md и WHAT.md в ~/work, навыки пакета в
~/.claude/skills (существующее — с резервной копией), строка в ~/work/CLAUDE.md, проверка `mila doctor`. 3) Перезапуск: `mila`.
Напишите боту — Мила предложит первые три дела. Ядро не ниже {core}.
"""


def load_scanner():
    spec = importlib.util.spec_from_file_location("mila_export", os.path.join(ROOT, "skills", "mila-export", "mila_export.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m.scan_bytes


def collect(role):
    base = os.path.join(ROOT, "packs", role)
    meta = json.load(open(os.path.join(base, "pack.json"), encoding="utf-8"))
    if meta.get("id") != role or not re.fullmatch(r"[a-z0-9-]{2,40}", role):
        raise SystemExit("pack.json id must equal the folder name")
    files = {"ROLE.md": open(os.path.join(base, "ROLE.md"), "rb").read(), "WHAT.md": open(os.path.join(base, "WHAT.md"), "rb").read()}
    for doc in meta.get("docs") or []:            # extra documents of the pack (a step-by-step course, …): plain names only
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}\.md", doc):
            raise SystemExit("docs: plain .md names only: %r" % doc)
        files[doc] = open(os.path.join(base, doc), "rb").read()
    for sk in meta.get("skills") or []:
        d = os.path.join(base, sk)
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for f in fn:
                p = os.path.join(dp, f)
                if os.path.islink(p):
                    continue
                files["skills/%s/%s" % (sk, os.path.relpath(p, d))] = open(p, "rb").read()
    missing = [s for s in meta.get("core_skills") or [] if not os.path.isdir(os.path.join(ROOT, "skills", s))]
    if missing:
        raise SystemExit("core skills not in this core: %s" % ", ".join(missing))
    return meta, files


def build(role, out, core_version=None, extra_docs=()):
    meta, files = collect(role)
    for path in extra_docs:                        # the seller's own documents (an offer, a hosting option) — not in this repo
        name = os.path.basename(path)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}\.md", name) or name in files:
            raise SystemExit("--doc: a new plain .md name only: %r" % name)
        files[name] = open(path, "rb").read()
    core = core_version or json.load(open(os.path.join(ROOT, "release.json"), encoding="utf-8")).get("version", meta.get("requires_core"))
    files["install.sh"] = INSTALL_SH.encode()
    files["INSTALL.md"] = INSTALL_MD.format(title_en=meta["title"]["en"], title_ru=meta["title"]["ru"], version=meta["version"],
                                            core=meta.get("requires_core"), skills=", ".join(meta["core_skills"])).encode()
    scan = load_scanner()
    hits = [(rel, n, kind) for rel, data in sorted(files.items()) for n, kind in scan(data, rel)]
    if hits:
        raise SystemExit("secret scanner found: " + "; ".join("%s:%d %s" % h for h in hits))
    manifest = {"format": 1, "id": meta["id"], "version": meta["version"], "title": meta["title"], "requires_core": meta.get("requires_core"),
                "built_with_core": core, "core_skills": meta["core_skills"], "first_tasks": meta.get("first_tasks"),
                "files": {rel: hashlib.sha256(data).hexdigest() for rel, data in sorted(files.items())}}
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode()
    os.makedirs(out, exist_ok=True)
    name = "mila-pack-%s-%s" % (meta["id"], meta["version"])
    path = os.path.join(out, name + ".zip")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(files):
            zi = zipfile.ZipInfo("%s/%s" % (name, rel), FIXED_TIME)
            zi.external_attr = (0o755 if rel == "install.sh" else 0o644) << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, files[rel])
    open(path, "wb").write(buf.getvalue())
    with open(os.path.join(out, name + ".manifest.json"), "w", encoding="utf-8") as f:
        f.write(files["manifest.json"].decode())
    return path, manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a ready-made Mila pack")
    ap.add_argument("role", nargs="?")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    ap.add_argument("--core-version")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--doc", action="append", default=[], help="add the seller's .md document to this build (e.g. a hosting offer)")
    a = ap.parse_args(argv)
    if a.list or not a.role:
        for r in sorted(os.listdir(os.path.join(ROOT, "packs"))):
            if os.path.isfile(os.path.join(ROOT, "packs", r, "pack.json")):
                print(r)
        return 0
    path, m = build(a.role, a.out, a.core_version, a.doc)
    print(json.dumps({"ok": True, "zip": path, "files": len(m["files"]) + 1, "version": m["version"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
