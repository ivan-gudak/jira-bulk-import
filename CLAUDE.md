# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

The Dynatrace wrapper around [jiramd](https://github.com/ihudak/jiramd)'s `snapshot` command, which does the work. This repository keeps:

| File | Role |
|---|---|
| `jiramd.toml` | dt-rnd settings: frontmatter and metadata fields (custom fields by ID where names are shared), the Status Details and Release Notes sections, `[snapshot] anonymize = false` |
| `src/main.py` | Keeps this tool's command line (`[IDS_FILE] [--force] [--export-dir]`, defaults `.jira.ids` and `.data`) and credentials (`JIRA_SERVER`/`JIRA_EMAIL`/`JIRA_TOKEN`, else `.jira.config` in the working directory), and runs `jiramd snapshot` with `jiramd.toml` |
| `runme.sh` | Requires `VAULT_PATH`; builds or repairs `.venv`, installs the jiramd version pinned in `requirements.txt` when it differs, runs `src/main.py .jira.ids --export-dir="$VAULT_PATH/_archive/jira-snapshots"` plus your flags |
| `requirements.txt` | `jiramd @ git+https://github.com/ihudak/jiramd@vX.Y.Z` |

Fix snapshot behaviour in jiramd, not here; then bump the tag in `requirements.txt`.

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest                       # runner and config tests; no network
./runme.sh [--force]                   # needs VAULT_PATH
python src/main.py [IDS_FILE] [--force] [--export-dir=DIR]
```

`.jira.config` and `.jira.ids` are gitignored and must never be committed. The Obsidian vault holds a hand-synced copy of this repository whose `runme.sh` adds `unset SPECS_PATH`.
