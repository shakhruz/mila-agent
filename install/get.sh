#!/usr/bin/env bash
# Mila — one-command install / установка одной командой:
#   curl -fsSL https://github.com/shakhruz/mila-agent/releases/latest/download/get.sh | bash
# Checks what is needed (Claude Code, Bun, git), clones the kit to ~/mila (or updates it; an older ~/mila-companion is updated in place), runs install/install.sh.
# Then installs the Telegram plugin: claude plugin marketplace add shakhruz/mila-telegram + claude plugin install mila-telegram@mila.
# The screen stays short (a greeting, five check marks, one next step); every detail goes to ~/.claude/mila-install.log.
# Flags: --verbose (or MILA_INSTALL_VERBOSE=1) prints the details on the screen too.
# Env: MILA_DIR (where to clone), MILA_REF (branch/tag; default — latest stable tag vX.Y.Z, canary: MILA_REF=main), MILA_REPO, MILA_INSTALL_ARGS,
#      MILA_PLUGIN_MARKET (default shakhruz/mila-telegram), MILA_SKIP_PLUGIN=1 — without the plugin step.
set -euo pipefail
REPO="${MILA_REPO:-https://github.com/shakhruz/mila-agent}"
DIR="${MILA_DIR:-}"
if [ -z "$DIR" ]; then [ -d "$HOME/mila-companion/.git" ] && DIR="$HOME/mila-companion" || DIR="$HOME/mila"; fi   # старая установка обновляется на месте
# Release asset only: tools/release.sh stamps the tag and the commit it points to; in the repo both stay empty.
PIN_REF=""
PIN_SHA=""
REF="${MILA_REF:-}"   # пусто → последний стабильный тег vX.Y.Z (как в README: стабильная — Releases); main — только по MILA_REF=main
VERBOSE=0
for _a in "$@" ${MILA_INSTALL_ARGS:-}; do
  case "$_a" in --verbose|--dry-run) VERBOSE=1 ;; esac
done
[[ "${MILA_INSTALL_VERBOSE:-}" == "1" ]] && VERBOSE=1
DRYRUN=0
[[ " ${MILA_INSTALL_ARGS:-} " == *" --dry-run "* ]] && DRYRUN=1
# What this script does before install.sh (version, clone, update) goes to a buffer that install.sh puts at the top of its log
# (nothing is written to the home on a dry run); with --verbose it is on the screen as well.
PRE_LOG=""
glog() {
  if [[ -n "$PRE_LOG" ]]; then printf '%s\n' "$*" >> "$PRE_LOG"; fi
  if [[ $VERBOSE -eq 1 ]]; then printf '%s\n' "$*"; fi
  return 0
}
printf '\n  ✦  M I L A\n  hello · привет · salom · 你好\n\n  Preparing her home…\n'
miss=0
need() { command -v "$1" >/dev/null 2>&1 || { printf '  ✗ %s — %s\n' "$1" "$2"; miss=1; }; }
if [[ "${MILA_SKIP_CHECKS:-0}" != "1" ]]; then
  need claude "Claude Code: https://docs.claude.com/en/docs/claude-code"
  need bun    "Bun: curl -fsSL https://bun.sh/install | bash"
fi
need git "git: https://git-scm.com/downloads"
[[ $miss -eq 0 ]] || { echo "Install the missing tools above and run the same command again."; exit 1; }
if [[ $DRYRUN -eq 0 ]]; then PRE_LOG="$(mktemp "${TMPDIR:-/tmp}/mila-get.XXXXXX")"; trap 'rm -f "$PRE_LOG"' EXIT; fi
if [[ -z "$REF" && -n "$PIN_REF" ]]; then REF="$PIN_REF"; glog "  version: $REF (this get.sh was released for it)"; fi
if [[ -z "$REF" ]]; then
  REF=$(git ls-remote --tags --sort=-v:refname "$REPO" 'v*' 2>/dev/null | grep -v '\^{}' | sed 's#.*refs/tags/##' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)
  REF="${REF:-main}"
  glog "  version: $REF"
fi
# Папка занята чужим: не наш набор (нет install/get.sh и skills/mila-update) — не трогаем, честный отказ
ours(){ [[ -f "$1/install/get.sh" && -d "$1/skills/mila-update" ]]; }
if [[ -e "$DIR" ]] && ! ours "$DIR" && [[ -n "$(ls -A "$DIR" 2>/dev/null)" ]]; then
  echo "  ✗ $DIR is already used by something else (not the Mila kit) — I leave it untouched."
  echo "    Run again with another folder, e.g.: MILA_DIR=\$HOME/mila-kit bash <(curl -fsSL …/install/get.sh)"; exit 1
fi
if [[ $DRYRUN -eq 1 && ! -d "$DIR/.git" ]]; then   # пробный прогон ничего не оставляет в доме: набор — во временную папку
  DIR="$(mktemp -d)/mila"; glog "  dry run: the kit goes to a temporary folder $DIR (nothing is written to your home)"
fi
# git run quietly: a release tag is an annotated tag, and a newer git says «warning: refs/tags/vX.Y.Z … is not a commit!» while it
# clones by it — harmless, and frightening on a first install. That one line is dropped; anything else git says is shown, and its
# exit code is kept.
gitq() {
  local err rc
  err="$("$@" 2>&1 >/dev/null)" && rc=0 || rc=$?
  if [ -n "$err" ]; then printf '%s\n' "$err" | grep -v 'is not a commit!' >&2 || true; fi
  return $rc
}
if [[ -d "$DIR/.git" ]]; then
  glog "  updating $DIR"
  # a failed fetch must stop here: in «fetch && checkout» the shell did not stop on a failed fetch, and the old version was installed again as if it were the new one
  gitq git -C "$DIR" fetch -q --depth 1 origin "$REF" || { echo "  ✗ could not download $REF — nothing is changed. Check the network and run the same command again."; exit 1; }
  gitq git -C "$DIR" -c advice.detachedHead=false checkout -q FETCH_HEAD
else
  glog "  cloning into $DIR"; gitq git -c advice.detachedHead=false clone -q --depth 1 --branch "$REF" "$REPO" "$DIR"
fi
GOT="$(git -C "$DIR" rev-parse HEAD)"; glog "  commit: $GOT"
if [[ -n "$PIN_SHA" && "$REF" == "$PIN_REF" && "$GOT" != "$PIN_SHA" ]]; then   # тег сдвинули после выпуска — не ставим
  echo "  ✗ tag $REF now points to $GOT, but this get.sh was released for $PIN_SHA — stopping, nothing installed."
  echo "    Compare with the release notes and tell the maintainer: https://github.com/shakhruz/mila-agent/security"; exit 1
fi
# The Telegram plugin comes before install.sh so that its one screen line (and its failure, if any) is in the summary install.sh prints.
# Both claude steps are idempotent: a second run breaks nothing.
MARKET="${MILA_PLUGIN_MARKET:-shakhruz/mila-telegram}"
TG_STATE=""; TG_NOTE=""
if [[ "${MILA_SKIP_PLUGIN:-0}" == "1" ]]; then TG_STATE=skipped; glog "  Telegram plugin: skipped (MILA_SKIP_PLUGIN=1)"
elif [[ $DRYRUN -eq 1 ]]; then TG_STATE=skipped; printf '  dry run: would run  claude plugin marketplace add %s  and  claude plugin install mila-telegram@mila\n' "$MARKET"
elif ! command -v claude >/dev/null 2>&1; then TG_STATE=failed; TG_NOTE="claude not found — install Claude Code, then run the same command again"
elif claude plugin marketplace add "$MARKET" >/dev/null 2>&1 && claude plugin install mila-telegram@mila --scope user >/dev/null 2>&1; then
  TG_STATE=ok; glog "  Telegram plugin: mila-telegram@mila installed"
else TG_STATE=failed; TG_NOTE="the plugin was not installed — in a Claude Code session: /plugin marketplace add $MARKET, then /plugin install mila-telegram@mila"
fi
if [[ "$REF" =~ ^v[0-9] ]]; then CORE="$REF"; else CORE="$REF (${GOT:0:7})"; fi
MILA_CORE_LABEL="$CORE" MILA_TG_STATE="$TG_STATE" MILA_TG_NOTE="$TG_NOTE" MILA_PRE_LOG="$PRE_LOG" MILA_FROM_GET=1 \
  bash "$DIR/install/install.sh" "$@" ${MILA_INSTALL_ARGS:-}
