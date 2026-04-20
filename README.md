# jira_bulk_importer

Imports a list of Jira work items as daily markdown snapshots, including comments and attachments.

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

```
# My work items
PROJ-123
PROJ-456
```

## Usage

```bash
# Run with default .jira.ids
python src/main.py

# Run with a custom IDs file
python src/main.py path/to/my-ids.txt
```

## Output

Each run creates a dated snapshot under `.data/`:

```
.data/
└── PROJ-123/
    ├── attachments_shared/       # deduplicated attachment pool (all runs)
    ├── 2026-04-20/
    │   ├── PROJ-123.md           # main work item
    │   ├── PROJ-123-comments-2026-04-20.md
    │   └── attachments/          # attachments for this snapshot
    └── 2026-04-21/
        └── ...
```

Attachments are deduplicated by content hash across runs — unchanged files are reused from `attachments_shared/` without re-downloading.

If a ticket fails (e.g. permission denied, deleted), the error is logged and the remaining tickets continue.

## Scheduling daily runs

**macOS/Linux (cron):**
```cron
0 7 * * * cd /path/to/jira_bulk_importer && .venv/bin/python src/main.py >> .data/import.log 2>&1
```

**Windows (Task Scheduler):** point to `.venv\Scripts\python.exe src\main.py` with the project root as the working directory.
