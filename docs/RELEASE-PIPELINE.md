# Release pipeline — «Milas update themselves»

Audit 21.10.2026: the core reached none of the running Milas — `mila-update` had never run and there was no «main → image» step. This is the target pipeline. Each step is reversible and leaves a trace.

## 1. Tag
- The READMEs install from `releases/latest/download/get.sh`: push a README change together with the release that carries
  `get.sh` and `SHA256SUMS`, then `python3 tools/check_install_link.py` must say ✓.
- A release = a tag `vX.Y.Z` on `main`, `release.json` → same version and tag, CHANGELOG section `## vX.Y.Z`.
- Before the tag: Quality accepts the bundle (history grep: secrets, our hosts, client and people names = 0; `tests/run_all.sh` ALL GREEN in a clean HOME; CI green).
- Pre-releases: `vX.Y.Z-rcN` — never picked up by Milas or by `get.sh`.
- The GitHub release with files is made by the workflow `release` (`.github/workflows/release.yml`) when the tag is pushed, and only through the gate `tools/release_gate.py`: the tag is annotated; its commit is on `main`; `release.json` and the CHANGELOG say this version; the tag is not in `yanked.json`; the workflow `tests` has a green run for exactly this commit (the gate waits up to 45 minutes for a run in progress); if `main` has `.github/allowed_signers`, the tag carries a valid signature of one of them. The gate and the file builder are taken from `main`, not from the tagged tree. Push order: the branch first, then the tag.
- What the gate does not do: it guards against a mistake (a tag on the wrong or untested commit), not against a person who may push tags and workflows — that is what a tag rule in the repository settings is for («only maintainers create `v*` tags»).

## 2. Test stand
- The stand Mila (test20) takes the tag first: `update.py apply --tag vX.Y.Z --yes "<who, when>"`, then `update.py health`.
- Quality runs the release checklist and the live exams on the stand. Red → no step 3; fix → new patch tag.

## 3. Image
- On a green stand: an automatic build of the companion image with labels `org.mila.core=vX.Y.Z` and `org.mila.commit=<sha>`.
- `CURRENT_IMAGE` is written by the build itself (not by hand) — one source of truth for what the fleet should run.

## 4. Roll (container level — plugin, engine, base files)
- At night, 3 Milas at a time.
- Before a restart: save the session crons (`state/crons.json`), wait for long processes to finish (no active turn, no render or upload in progress) or move the Mila to the next batch.
- After a restart: health check — the bot answers the owner's `/status`, the daemon is up, `mila doctor` has no red lines, crons are restored. Not healthy within 5 minutes → automatic rollback to the previous image and a red line in the morning panel.
- One red in a batch stops the roll for the night.

## 5. Skills and hooks — separate channel, no restart
- `mila-update nightly` by a timer on every Mila: compare the installed version with the latest stable tag, apply core zones (skills, hooks, launcher, constitution) with a backup, never touch memory, NOW, settings, secrets, personal skills.
- Hooks in `settings.json` are not touched by `mila-update`; new hook registrations go through `tools/hooks_sync.py` (idempotent, with a backup).
- A newborn is not updated before onboarding ends.
- Every apply is in `~/.claude/mila-update/journal.jsonl`; `update.py rollback` undoes the last one.

## 6. Who runs what — morning panel
- Each Mila reports `update.py status` (version, tag, when) to the fleet slice.
- Morning panel: table «Mila → core version → image → last update». Red if a Mila lags more than one release or the last nightly failed.

## Checks that exist today
| Step | Check |
|---|---|
| a tag may become a release: annotated, on `main`, version and CHANGELOG agree, not withdrawn, tests green for its commit | `python3 tools/release_gate.py vX.Y.Z` (`tools/test_release_gate.py`) |
| the README install command works (releases/…/download links answer 200) — the last step of the `release` workflow, and before pushing a README that points at a release | `python3 tools/check_install_link.py` |
| install on a clean home, rollback | `skills/mila-update/test_clean_home.sh` |
| apply, diff, never-touch, journal | `skills/mila-update/test_update.sh` |
| nightly | `skills/mila-update/test_nightly.sh` |
| renamed skills, incomplete skills | `test_renamed.sh`, `test_skill_files.sh` |
| one-command install picks the latest stable tag | `install/test_get.sh` |
| every test | `tests/run_all.sh` (CI on every push) |

## Not built yet
- Image auto-build with labels and `CURRENT_IMAGE` (server side).
- Night roll with health check and automatic rollback (server side).
- Fleet version slice in the morning panel.
