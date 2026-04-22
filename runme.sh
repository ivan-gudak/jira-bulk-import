#!/bin/bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Run with default .jira.ids
# python src/main.py

# Run with a custom IDs file
# python src/main.py path/to/my-ids.txt

# Force export of all work items, ignoring interval settings
# python src/main.py --force
# python src/main.py -f

# Export to a custom directory (default: .data)
# python src/main.py --export-dir=my-exports
python src/main.py .jira.ids --export-dir=/mnt/c/workspaces/obsidian_vault/_archive/jira-snapshots

