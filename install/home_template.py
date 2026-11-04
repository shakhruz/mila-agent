#!/usr/bin/env python3
"""Our files in a Mila's home reach her after an image or kit update, the owner's edits stay.

    home_template.py <kit> <home work dir>

templates/work/CLAUDE.md → ~/work/CLAUDE.md, CONSTITUTION.md and CONSTITUTION.en.md → ~/work/canon/:
- missing → copied;
- the home's file is one we shipped (its sha256 is in templates/work/SHIPPED.sha256, digits written as g–p) and differs from the new one →
  replaced, the old one kept as <name>.bak-<date>;
- the owner edited it (sha not in the list) → left as is, the new one put beside as <name>.new and named in one line.
USER.md is the owner's: only copied when missing. Prints one line per change; exit 0 always (a start must not stop here)."""
import hashlib, os, shutil, string, sys, time

FILES = (("templates/work/CLAUDE.md", "CLAUDE.md"), ("CONSTITUTION.md", "canon/CONSTITUTION.md"), ("CONSTITUTION.en.md", "canon/CONSTITUTION.en.md"))
OWNER_ONLY = (("templates/work/USER.md", "USER.md"),)


DIG = str.maketrans(string.digits, "ghijklmnop")   # sha256 hex with digits written as letters: no long digit runs in the repo


def sha(p):
    with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest().translate(DIG)


def shipped(kit):
    try: return {l.split()[0] for l in open(os.path.join(kit, "templates", "work", "SHIPPED.sha256"), encoding="utf-8") if l.strip() and not l.startswith("#")}
    except OSError: return set()


def main(kit, work):
    known = shipped(kit); stamp = time.strftime("%Y%m%d-%H%M%S")
    for src, rel in FILES + OWNER_ONLY:
        s, d = os.path.join(kit, src), os.path.join(work, rel)
        if not os.path.isfile(s): continue
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if os.path.islink(d): print("home: %s is a link — left as is" % rel); continue
        if not os.path.exists(d):
            shutil.copyfile(s, d); print("home: %s added" % rel); continue
        if (src, rel) in OWNER_ONLY: continue
        new, cur = sha(s), sha(d)
        if new == cur: continue
        if cur in known:
            shutil.copyfile(d, d + ".bak-" + stamp); shutil.copyfile(s, d); print("home: %s updated (old kept as %s.bak-%s)" % (rel, os.path.basename(rel), stamp))
        elif not os.path.exists(d + ".new") or sha(d + ".new") != new:
            shutil.copyfile(s, d + ".new"); print("home: %s has the owner's edits — the new version is beside it as %s.new" % (rel, os.path.basename(rel)))


if __name__ == "__main__":
    if len(sys.argv) != 3: sys.exit(__doc__)
    try: main(sys.argv[1], sys.argv[2])
    except Exception as e: print("home: template update skipped — %s" % e)
