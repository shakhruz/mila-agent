#!/usr/bin/env python3
"""Does the install command in the READMEs work right now? Run before pushing a README change and after a release.

  python3 tools/check_install_link.py            # exit 0 — every releases/…/download/<file> link answers 200; 1 — list of broken
The READMEs point at `releases/latest/download/get.sh`; until the latest release carries get.sh and SHA256SUMS that link is a
404 for everyone who opens the repository. So: push a README that points at a release only together with that release.
Only stdlib. CHECK_INSTALL_BASE replaces https://github.com in tests."""
import glob, os, re, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/releases/(?:latest/download|download/v[\w.-]+)/[\w.-]+")


def links(root=ROOT):
    out = {}
    for p in sorted(glob.glob(os.path.join(root, "README*.md"))):
        for m in LINK.findall(open(p, encoding="utf-8").read()):
            out.setdefault(m, []).append(os.path.basename(p))
    return out


def status(url, timeout=15):
    base = os.environ.get("CHECK_INSTALL_BASE")
    if base:
        url = url.replace("https://github.com", base.rstrip("/"))
    rq = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "mila-check-install-link"})
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:   # follows the redirect to the release asset
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError):
        return 0


def main(argv=None):
    ls = links()
    if not ls:
        print("no release download links in README*.md"); return 0
    bad = [(u, f, s) for u, f in ls.items() for s in [status(u)] if s != 200]
    for u, f, s in bad:
        print("✗ %s → %s  (in %s)" % (u, s or "no answer", ", ".join(sorted(set(f)))))
    if bad:
        print("The install command is broken for readers: publish the release with these files, or do not push the README yet.")
        return 1
    print("✓ %d install link(s) answer 200" % len(ls)); return 0


if __name__ == "__main__":
    sys.exit(main())
