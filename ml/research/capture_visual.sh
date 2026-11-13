#!/usr/bin/env bash
# Capture the visual-regression screenshots from one working tree.
#
# Usage: capture_visual.sh <tree-root> <destination-dir>
#
# The suite is the same one that runs in CI; this only selects the four specs that write
# screenshots and copies their output into a named directory, so the parent and the candidate can be
# compared without either run overwriting the other.
set -uo pipefail
TREE="$1"
DEST="$2"
export PATH=/home/user/.cache/p35work/venv/bin:$PATH
export PYTHON=/home/user/.cache/p35work/venv/bin/python
export LD_LIBRARY_PATH=/tmp/libs35/usr/lib/x86_64-linux-gnu
# Never reuse a server that may belong to the other tree: a capture that silently talks to the
# candidate's API while rendering the parent's bundle compares two different applications. CI=1
# turns reuseExistingServer off, so each run starts both servers from the tree being captured.
export CI=1
cd "$TREE/frontend"
rm -rf test-results/screenshots
# The capture tests write files; the same suite also holds assertions, and one of them
# (screens.spec.js: the evidence-verdict badge) is expected to fail on the parent commit, which
# predates the feature. A non-zero exit is therefore recorded, not fatal: the captures are the
# artefact this script exists to produce.
set +e
# Called through node: the repository has no package.json, so `npx` has no local bin to resolve.
node node_modules/@playwright/test/cli.js test e2e/mission.spec.js e2e/radiation.spec.js e2e/water-evidence.spec.js e2e/screens.spec.js \
  --reporter=line 2>&1 | tail -4
echo "playwright exit: $?"
set -e
mkdir -p "$DEST"
rm -f "$DEST"/*.png
cp test-results/screenshots/*.png "$DEST"/
ls "$DEST" | wc -l
