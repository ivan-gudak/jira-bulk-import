#!/bin/bash
cd "$(dirname "$0")" || exit 1
# 1. Create and activate a virtual environment
# A venv is machine-specific, and this one lives inside the Obsidian vault, so a
# venv built on another machine can arrive here by vault sync. Re-running
# `python3 -m venv .venv` over it exits 0 and repairs NOTHING -- the stale
# symlinks survive, `set -e` never fires, and the run dies later at pip or at
# the interpreter itself (on macOS, as "Killed: 9"). Validate before reuse and
# rebuild with --clear when the interpreter is not executable here.
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c '' 2>/dev/null; then
  python3 -m venv --clear .venv
fi
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -q

# Run with default .jira.ids
# python src/main.py

# Run with a custom IDs file
# python src/main.py path/to/my-ids.txt

# Force export of all work items, ignoring interval settings
# python src/main.py --force
# python src/main.py -f

# Export to a custom directory (default: .data)
# python src/main.py --export-dir=my-exports
python src/main.py .jira.ids --export-dir="$VAULT_PATH/_archive/jira-snapshots"

