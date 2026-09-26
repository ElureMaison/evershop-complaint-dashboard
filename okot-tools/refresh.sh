#!/bin/bash
# refresh.sh — pull all three OKOT sources and rebuild the published digest.
#
#   ./refresh.sh          masked email addresses (what gets published)
#   ./refresh.sh --full   unmasked, for local reading only
set -uo pipefail
cd "$(dirname "$0")"

FULL=""
[ "${1:-}" = "--full" ] && FULL="--full"

echo "=== OKOT refresh $(date '+%Y-%m-%d %H:%M') ==="
for src in gmail monday trello; do
  echo "--- $src ---"
  python3 -u "collect_$src.py" || echo "  ($src did not finish; digest will show its last good data)"
done

echo "--- build ---"
python3 -u build_updates.py $FULL || exit 1

# The page is served from a public repo, so what ships is ciphertext: the
# password is the decryption key, not a gate. It lives in okot_config.json
# (chmod 600) rather than in this file — passwords with shell metacharacters
# do not belong on a command line. OKOT_PW still overrides.
PW="${OKOT_PW:-$(python3 -c 'import json;print(json.load(open("okot_config.json")).get("page_password",""))')}"
if [ -z "$PW" ]; then
  echo "No page password: set page_password in okot_config.json or export OKOT_PW" >&2
  exit 1
fi
echo "--- encrypt ---"
node encrypt_data.js "$PW" || exit 1

# Two destinations: the project's own copy, and the clone that actually
# serves yourbadassvaronceph.com. Forgetting the second is why a refresh can
# look done while the live page still shows the previous build.
cp data/updates.enc.json "../site/OKOT-Update/data.json"
echo "staged   -> ../site/OKOT-Update/data.json"

SERVE="$HOME/Documents/evershop/site/OKOT-Update"
if [ -d "$SERVE" ]; then
  cp data/updates.enc.json "$SERVE/data.json"
  cp ../site/OKOT-Update/index.html "$SERVE/index.html"
  echo "published-> $SERVE (encrypted)"
  echo
  echo "Now publish it:"
  echo "  cd ~/Documents/evershop/site && git add OKOT-Update && \\"
  echo "     git commit -m 'OKOT-Update: refresh digest' && git push"
else
  echo "NOTE: $SERVE not found — the live page will keep showing the old build."
fi
