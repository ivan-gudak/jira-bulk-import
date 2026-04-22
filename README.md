# jira_bulk_importer

Imports Jira work items as timestamped markdown snapshots, including comments and attachments. Each run produces a new snapshot; exports can be throttled per work item.

## Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your config files (see examples)
cp .jira.config.example .jira.config   # then fill in your credentials
cp .jira.ids.example .jira.ids         # then add your Jira IDs
```

## Configuration

### `.jira.config`
Jira credentials. **Never commit this file.**

```
SERVER: https://your-org.atlassian.net
EMAIL: you@example.com
TOKEN: your_api_token_here
```

Generate an API token at: https://id.atlassian.com/manage-profile/security/api-tokens

Alternatively, set environment variables `JIRA_SERVER`, `JIRA_EMAIL`, `JIRA_TOKEN` — they take precedence over the config file.

### `.jira.ids`
One Jira ID per line. Lines starting with `#` and blank lines are ignored.

An optional `=N` suffix controls how often a work item is exported:

```
# Export every run (default: skip if exported less than 12 hours ago)
PROJ-123

# Export at most once every 3 days (skip if last export < 2.5 days ago)
PROJ-456=3

# Disabled — never export
TEAM-789=0
```

| Suffix | Behaviour |
|--------|-----------|
| _(none)_ or `=1` | Skip if last export < 12 hours ago |
| `=N` | Skip if last export < N × 0.5 days ago |
| `=0` | Always skip (disabled) |

## Usage

```bash
# Run with default .jira.ids
python src/main.py

# Run with a custom IDs file
python src/main.py path/to/my-ids.txt

# Force export of all work items, ignoring interval settings
python src/main.py --force
python src/main.py -f
```

## Output

Each run creates a timestamped snapshot under `.data/`:

```
.data/
├── jira-export-index.md              # table of contents (entry point)
└── PROJ-123/
    ├── PROJ-123-snapshot-index.md    # snapshot history for this work item
    ├── PROJ-123 - 2026-04-22 07-05-00.md   # snapshot
    ├── PROJ-123 - 2026-04-22 19-05-00.md   # next snapshot
    ├── Comments/
    │   ├── PROJ-123-comments-2026-04-22 07-05-00.md
    │   └── PROJ-123-comments-2026-04-22 19-05-00.md
    ├── Attachments/
    │   ├── 2026-04-22 07-05-00/      # attachments for that snapshot
    │   └── 2026-04-22 19-05-00/
    └── attachments_shared/           # deduplicated attachment pool (all runs)
```

Attachments are deduplicated by content hash — unchanged files are reused from `attachments_shared/` without re-downloading.

### Navigation

- **`jira-export-index.md`** — top-level table of contents. Lists all configured work items (with export interval and last export) and any orphaned items (present in `.data/` but removed from `.jira.ids`). Jira IDs link to the per-item snapshot index; the Last Export column links directly to the latest snapshot.
- **`<ID>-snapshot-index.md`** — per-item history table (date, timestamp, link to snapshot). Links back to the index.

If a ticket fails (e.g. permission denied, deleted), the error is logged and the remaining tickets continue.

## Scheduling

**macOS/Linux (cron):**
```cron
0 7 * * * cd /path/to/jira_bulk_importer && .venv/bin/python src/main.py >> .data/import.log 2>&1
```

**Windows (Task Scheduler):** point to `.venv\Scripts\python.exe src\main.py` with the project root as the working directory.
