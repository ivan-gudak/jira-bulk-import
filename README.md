# jira-bulk-import

Imports Jira work items as timestamped markdown snapshots, including comments and attachments. Each run produces a new snapshot; exports can be throttled per work item.

The output is meant to be read in [Obsidian](https://obsidian.md): images are embedded with `![[...]]`, comments are transcluded, and the indexes link with wikilinks.

## Requirements

- Python 3.10 or later
- A Jira Cloud account with read access to the tickets, and an API token for it
- The Jira site this copy is configured for — see [Settings tied to one Jira site](#settings-tied-to-one-jira-site)

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

Alternatively, set environment variables `JIRA_SERVER`, `JIRA_EMAIL`, `JIRA_TOKEN`. They take precedence only when all three are set; if any is missing, `.jira.config` is read and its values are used.

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

### With `runme.sh`

```bash
export VAULT_PATH=/path/to/obsidian-vault
./runme.sh            # exports .jira.ids to $VAULT_PATH/_archive/jira-snapshots
./runme.sh --force    # flags are forwarded to src/main.py
```

The script creates or repairs `.venv`, installs the requirements, and runs the
importer on `.jira.ids`. It stops with an error when `VAULT_PATH` is not set.
It forwards flags only: to use another IDs file or destination, call
`src/main.py` directly.

### With Python

Run from the project root, where `.jira.config` and `.jira.ids` are read:

```bash
# Run with default .jira.ids
python src/main.py

# Run with a custom IDs file
python src/main.py path/to/my-ids.txt

# Force export of all work items, ignoring interval settings
python src/main.py --force
python src/main.py -f

# Export to a custom directory (default: .data)
python src/main.py --export-dir=my-exports
python src/main.py path/to/my-ids.txt --export-dir=/absolute/path/to/output
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
    └── attachments_shared/           # every attachment file, all runs
        └── .attachment-ids.json      # which Jira attachment is which file
```

Timestamps are the local time of the machine that ran the import.

Attachments are deduplicated by content hash: each file is stored once in
`attachments_shared/` as `<hash>_<filename>`, and every snapshot links to it
there. `.attachment-ids.json` records which Jira attachment each file came
from, so an attachment already in the pool is not downloaded again. If the
record or a pooled file is missing, that attachment is simply downloaded again.

Older versions also created an empty `Attachments/<timestamp>/` folder on every
run. Nothing uses them; they can be deleted.

### What a snapshot contains

- YAML frontmatter with the fields listed in `EXPORT_FIELDS` (`src/config.py`)
- Metadata, status details and description, converted from Jira markup
- **Details**, in place of an empty description — every populated custom field
  not already shown elsewhere, one subsection each. Tickets such as RFEs keep
  their content in custom fields and leave the description blank.
- Attachments (embedded images, plus a file list)
- Release notes — relevance, release versions, change type, category, title and
  summary — when the ticket has any of them
- Linked issues, grouped by link type
- Comments, transcluded from that run's comments file

### Personal data

Snapshots are not anonymized: assignee, reporter, comment authors, mentions and
email addresses appear as Jira returns them. Keep that in mind before sharing or
committing an export. (The sibling `jira-workitem-import` does anonymize.)

### Navigation

- **`jira-export-index.md`** — top-level table of contents. Lists all configured work items (with export interval and last export) and any orphaned items (present in `.data/` but removed from `.jira.ids`). Jira IDs link to the per-item snapshot index; the Last Export column links directly to the latest snapshot.
- **`<ID>-snapshot-index.md`** — per-item history table (date, timestamp, link to snapshot). Links back to the index.

If a ticket fails (e.g. permission denied, deleted), the error is logged and the remaining tickets continue.

## Scheduling

**macOS/Linux (cron):**
```cron
0 7 * * * cd /path/to/jira-bulk-import && .venv/bin/python src/main.py >> .data/import.log 2>&1
```

To export to a custom directory, add `--export-dir`:
```cron
0 7 * * * cd /path/to/jira-bulk-import && .venv/bin/python src/main.py --export-dir=/path/to/vault/jira >> /path/to/vault/jira/import.log 2>&1
```

**Windows (Task Scheduler):** point to `.venv\Scripts\python.exe src\main.py` with the project root as the working directory.

## Settings tied to one Jira site

This copy is set up for one Jira site, and pointing `SERVER` at another site is
not enough:

- **Links in the export** use `JIRA_BASE_URL` in `src/config.py`, not `SERVER`.
  Change both.
- **Custom field IDs** differ between sites. `FIELD_MAPPING` in `src/config.py`
  lists them, and a few (Status details, the assignee and release-notes fields)
  are also used directly in `src/markdown_generator.py`. `CLAUDE.md` lists them.

On another site, a field ID that does not exist there is simply left empty, but
one that exists with a different meaning is exported under the wrong name.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest
```

`src/jira_markup_converter.py` is shared with the sibling `jira-workitem-import`
project; the test that keeps the two copies in step lives there. `CLAUDE.md`
describes the architecture and how to add a Jira field.
