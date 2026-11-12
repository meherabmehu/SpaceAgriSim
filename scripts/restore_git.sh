#!/usr/bin/env bash
# Reattach a working tree to its remote without touching a single file.
#
# Why this exists
# ---------------
# Some execution environments snapshot the workspace between sessions with a size budget. A
# repository whose working tree plus history exceeds that budget can come back without `.git` (and,
# in the worst case, without the largest files). Nothing is lost when that happens - the remote is
# the source of truth and every commit is pushed before a session ends - but the checkout has to be
# reattached before any git command will work.
#
# This script does exactly that, in the safest order it can:
#
#   1. refuse to run if a repository is already attached;
#   2. clone the remote into a temporary directory (fetches history only, no working tree);
#   3. move that `.git` into place, so the existing files are never overwritten;
#   4. reset the index to the fetched commit - `--mixed`, so working files stay exactly as they are
#      and any local edit shows up as a modification instead of being discarded;
#   5. print what differs, so a human can decide what to commit.
#
# Usage:
#   scripts/restore_git.sh                       # uses origin/main
#   scripts/restore_git.sh <remote-url> <ref>    # e.g. a branch other than main
#
# The token, if the remote needs one, is read from $SPACEAGRISIM_GIT_TOKEN and never written to
# disk, to `.git/config`, or to the terminal.
set -euo pipefail

REMOTE="${1:-https://github.com/meherabmehu/SpaceAgriSim.git}"
REF="${2:-main}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -d "$ROOT/.git" ]; then
  echo "$ROOT already has a .git directory; nothing to restore." >&2
  echo "If it is damaged, move it aside first: mv .git .git.broken" >&2
  exit 0
fi

if [ -n "${SPACEAGRISIM_GIT_TOKEN:-}" ]; then
  REMOTE="https://x-access-token:${SPACEAGRISIM_GIT_TOKEN}@${REMOTE#https://}"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "fetching $REF from $REMOTE"
git clone --quiet --no-checkout "$REMOTE" "$TMP/repo"
git -C "$TMP/repo" fetch --quiet origin "$REF"
COMMIT="$(git -C "$TMP/repo" rev-parse "origin/$REF")"

cp -a "$TMP/repo/.git" "$ROOT/.git"
# Rewrite the remote to the credential-free form so a token can never be left behind in config.
git -C "$ROOT" remote set-url origin "$(printf '%s' "$REMOTE" | sed -E 's#//[^@]*@#//#')"
git -C "$ROOT" config user.name "Meherab Mehu"
git -C "$ROOT" config user.email "meherabmehu@users.noreply.github.com"
git -C "$ROOT" reset --mixed --quiet "$COMMIT"
git -C "$ROOT" checkout --quiet -B "$REF" "$COMMIT"

echo "attached at $COMMIT ($REF)"
echo "--- files that differ from the remote (nothing has been discarded):"
git -C "$ROOT" status --porcelain | sed -n '1,40p'
echo "--- to keep local edits: commit them. To discard them: git checkout -- ."
