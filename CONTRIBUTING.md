# Contributing

Thanks for helping. Mila is a kit of skills (Markdown), hooks and small
Python/shell tools around Claude Code and a Telegram channel.

## Hack on Mila
Before: Python 3.12, [Bun](https://bun.sh), ffmpeg and the DejaVu font, and `pip install pyyaml pillow numpy telethon==1.45.0`
(the same set the CI workflow installs; a test whose tool is missing reports 0/0 and is shown as ⚠️, not green). Install the
packages into the interpreter or a virtualenv, not with `pip install --user`: the throwaway `HOME` below hides the user site,
and tests then fail with «No module named 'yaml'». If your packages are in the user site, put it first on the same line —
`PYTHONUSERBASE=$HOME/.local HOME=$(mktemp -d) bash tests/run_all.sh` (in this order: the shell reads `$HOME` left to right).
Then three commands:
```sh
git clone https://github.com/shakhruz/mila-agent.git && cd mila-agent
HOME=$(mktemp -d) bash tests/run_all.sh   # every test in the repo, with a throwaway HOME — the script itself does not replace it
python3 tools/kitchen_lint.py             # no internal notes in public files — must stay clean
```
With the tools above everything is green before you change anything.
What is where:

| Folder | What lives there |
|---|---|
| `skills/` | the skills every Mila has: a `SKILL.md` and, where needed, its scripts and tests |
| `packs/` | roles on top of the core (a manager, a content expert, ads…): sets of skills installed by the owner's «yes» |
| `templates/home/.claude/hooks/` | the hooks that guard what Mila sends, says and reads; each has a test next to it |
| `templates/work/` | the files a newborn Mila starts with |
| `install/` | the installer, the `mila` command, birth, the background service, the Scheduler, the doctor |
| `tools/` | linters, the release gate, the library builder |
| `tests/` | `run_all.sh`, the CI twin `run_ci_local.sh`, checks of the docs and READMEs |
| `docs/`, `docker/`, `deploy/` | the documentation, the container image, a server and cloud setup |

**Contributions in English are welcome. Skill texts are Russian — we help with the translation. Hooks, tests, the installer
and the docs need no Russian at all.**

What we hope people will do: try Mila on Linux and WSL and tell us what broke; check the hooks; translate skills and docs;
make the installer work beyond macOS.

## Ground rules
- One logical change per pull request; small commits.
- No secrets, no real chat ids, no names of real customers or people in code,
  examples or tests - use the fake values in `tests/fixtures/fake_people.py`; token-shaped strings are glued at run time.
- No internal notes in public files or commit messages: no task codes, message numbers or reviewer timestamps
  (`python3 tools/kitchen_lint.py` must be clean). A commit message says what changed and what a person gets.
- Skills: `SKILL.md` needs valid frontmatter. Check with
  `python3 tools/check_frontmatter.py skills templates`.
- JS/HTML: `python3 tools/check_comments.py <files>` (no code after `//` on one line).

## Who writes the code
Most commits here are written by AI agents — Claude Code sessions working as Milas — and marked `Co-Authored-By: Claude`.
A person decides what to build, a separate reviewing agent checks each change against the tests and its own probes, and a
maintainer reads it and pushes. Pull requests from people are reviewed the same way; say in yours whether an agent wrote it.

## Tests
`HOME=$(mktemp -d) bash tests/run_all.sh` runs every test in the repo plus the frontmatter check (the throwaway `HOME` is yours
to give: the script does not replace it, and without it the tests run in your real home) — all green before a
pull request, also with `CI=true` and through `bash tests/run_ci_local.sh` (clean HOME, UTC, exactly the workflow's Python
packages). CI runs the same script, plus gitleaks on the whole history. A test that needs a new library adds it to the
`pip install` line in `.github/workflows/tests.yml`. To run one test while you work:
```sh
python3 templates/home/.claude/hooks/test_send_guard.py
bash skills/mila-update/test_update.sh
```

## Language
Skill text is mostly Russian (the author's working language); README and code
comments in English are welcome. Translations of skills are welcome as `SKILL.<lang>.md`.

## License
By contributing you agree your work is licensed under Apache-2.0 (see LICENSE).

## Releases
- Channels: `stable` = tags `vX.Y.Z` (no `-rc`), `canary` = `main`. Milas update themselves from the channel they are set to (`~/.claude/mila-update.json`).
- Before a release: bump the «Current release» line in all four README files, publish a GitHub Release for the tag.
- Before a release: add `## vX.Y.Z` to `CHANGELOG.md` with a **For the owner** block (up to 3 plain lines: it becomes the "What is new" card) and a **For Milas** block.
- `tools/release.sh X.Y.Z` runs the tests, bumps `release.json`, commits `release vX.Y.Z` and tags it (signed with `git tag -s` when `user.signingkey` is set, otherwise an unsigned annotated tag, which the script says). It never pushes. The release files go to `dist/vX.Y.Z/`: `get.sh` stamped with the tag and its commit SHA, and `SHA256SUMS`. A release is cut from `main` only. After `git push origin main && git push origin vX.Y.Z` the GitHub release with these two files is made by the `release` workflow — once the tests of that commit are green (`tools/release_gate.py` is the gate; run it by hand before pushing: `python3 tools/release_gate.py vX.Y.Z --main main`). `gh release create` by hand is no longer needed.
- Withdraw a bad release: add its tag to `yanked.json` on `main` (list of tags or `{"yanked":[{"tag":"v1.2.0","reason":"..."}]}`). Milas never install a yanked tag; one that already has it gets a warning card.
- Pre-release candidates: `vX.Y.Z-rc1` (not picked up by `stable`).
