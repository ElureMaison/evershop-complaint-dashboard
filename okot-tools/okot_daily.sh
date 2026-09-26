#!/bin/bash
# okot_daily.sh — the whole unattended loop: collect, build, encrypt, publish.
#
# Run by launchd once a day (see com.okot.updates.plist). Safe to run by hand.
# Everything it needs lives in okot_config.json and token_gmail_okot.json;
# the push uses the osxkeychain credential already on this Mac.
set -uo pipefail
cd "$(dirname "$0")" || exit 1

LOG_DIR="$HOME/Documents/okot/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/daily-$(date +%Y-%m-%d).log"
SITE="$HOME/Documents/evershop/site"

exec >>"$LOG" 2>&1
echo "================ $(date '+%Y-%m-%d %H:%M:%S %Z') ================"

# PATH is minimal under launchd; node lives in a user-local install.
export PATH="$HOME/.local/node/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
command -v node >/dev/null || { echo "FATAL: node not on PATH"; exit 1; }

./refresh.sh
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo "refresh.sh exited $STATUS — not publishing a partial build"
  exit $STATUS
fi

# refresh.sh already copied the encrypted file into the serving clone.
cd "$SITE" || { echo "FATAL: $SITE missing"; exit 1; }

if git diff --quiet -- OKOT-Update && git diff --cached --quiet -- OKOT-Update; then
  echo "no change in OKOT-Update — nothing to publish"
  exit 0
fi

git add OKOT-Update || exit 1
git commit -q -m "OKOT-Update: daily refresh $(date '+%Y-%m-%d')" || exit 1

# Someone else pushes to this repo too (the Evershop jobs), so land on top of
# whatever arrived rather than failing on a non-fast-forward.
git fetch -q origin && git rebase -q origin/main || {
  echo "rebase failed — leaving the commit local for a human to sort out"
  git rebase --abort 2>/dev/null
  exit 1
}

if git push -q; then
  echo "published: $(git log --oneline -1)"
else
  echo "push failed — commit is local; run 'cd $SITE && git push' by hand"
  exit 1
fi
