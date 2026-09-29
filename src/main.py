"""
Jira Bulk Importer
Reads a list of Jira IDs and imports each as a daily markdown snapshot.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))

from jira_auth import JiraAuth
from markdown_generator import MarkdownGenerator
from comments_handler import CommentsHandler
from config import JIRA_BASE_URL
from report_generator import generate_report, generate_snapshot_index


DEFAULT_EXPORT_DIR = ".data"

_cwd = Path(os.getcwd())


class ExportPathError(ValueError):
    """Raised when --export-dir cannot be used as a destination."""


def resolve_export_dir(export_dir: str, cwd: Optional[Path] = None) -> Path:
    """Resolve --export-dir to an absolute directory. Creates nothing.

    runme.sh builds the destination as "$VAULT_PATH/_archive/jira-snapshots".
    With VAULT_PATH unset that collapses to "/_archive/jira-snapshots", and
    joining an absolute path onto the working directory discards the working
    directory -- so the export aims at the filesystem root. That is never what
    anyone asked for, so it is reported rather than attempted.
    """
    raw = (export_dir or "").strip()
    if not raw:
        raise ExportPathError(
            "--export-dir is empty. Pass a directory, or leave the flag off to "
            f"use the default ({DEFAULT_EXPORT_DIR})."
        )

    target = Path(raw).expanduser()
    if not target.is_absolute():
        target = (Path(cwd) if cwd else _cwd) / target
    target = Path(os.path.normpath(target))

    # An unset VAULT_PATH leaves the whole suffix hanging off the filesystem
    # root ("/_archive/jira-snapshots"). Counting path components cannot tell
    # that apart from a real destination -- the suffix is configurable -- but
    # the filesystem can: it would mean creating a new top-level directory,
    # which is never the intent.
    root = Path(target.anchor)
    nearest = target
    while not nearest.exists() and nearest != nearest.parent:
        nearest = nearest.parent
    if nearest == root:
        raise ExportPathError(
            f"--export-dir resolved to {target}, which would create a new "
            f"directory directly under {root}. That is what an unset "
            'VAULT_PATH looks like once the shell expands '
            '"$VAULT_PATH/_archive/jira-snapshots". Set VAULT_PATH, or pass '
            "--export-dir explicitly."
        )
    return target

def _display_path(p: Path) -> Path:
    """Return a CWD-relative path, or the absolute path if outside CWD."""
    try:
        return p.relative_to(_cwd)
    except ValueError:
        return p


def read_jira_ids(ids_file: str) -> list[tuple[str, int]]:
    """Read Jira IDs from file. Returns list of (id, interval_days).
    Format: PROJ-123 or PROJ-123=3 (export every 3 days) or PROJ-123=0 (disabled).
    Default interval is 1 (skip if exported less than 0.5 days ago).
    """
    path = Path(ids_file)
    if not path.exists():
        raise FileNotFoundError(f"IDs file not found: {ids_file}")
    ids = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                jira_id, _, val = line.partition("=")
                try:
                    interval = int(val)
                except ValueError:
                    interval = 1
            else:
                jira_id, interval = line, 1
            ids.append((jira_id.strip(), interval))
    return ids


def should_skip(work_item_id: str, interval_days: int, data_dir: Path) -> bool:
    """Return True if the ticket should be skipped based on last export time."""
    if interval_days == 0:
        return True
    item_dir = data_dir / work_item_id
    if not item_dir.exists():
        return False
    import re
    pattern = re.compile(rf"^{re.escape(work_item_id)} - (\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}-\d{{2}}-\d{{2}})\.md$")
    timestamps = sorted(
        (m.group(1) for f in item_dir.iterdir() if f.is_file() and (m := pattern.match(f.name))),
        reverse=True,
    )
    if not timestamps:
        return False
    try:
        last_dt = datetime.strptime(timestamps[0], "%Y-%m-%d %H-%M-%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    elapsed_days = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
    return elapsed_days < (interval_days * 0.5)


def import_ticket(jira_client, work_item_id: str, timestamp: str, data_dir: Path, field_names: dict) -> None:
    """Import a single Jira ticket into <data_dir>/<ID>/ with timestamp-based filenames."""
    item_dir = data_dir / work_item_id
    attachments_dir = item_dir / "Attachments" / timestamp
    comments_dir = item_dir / "Comments"
    shared_dir = item_dir / "attachments_shared"

    for d in (attachments_dir, comments_dir, shared_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Fetch issue with all fields (not just the mapped ones) so the RFE fallback
    # can render populated custom fields when the description is empty.
    issue = jira_client.issue(work_item_id)
    print(f"  Fetched: {issue.key} - {issue.fields.summary}")

    # Generate main markdown
    generator = MarkdownGenerator(
        issue,
        jira_client=jira_client,
        attachments_dir=str(attachments_dir),
        shared_dir=str(shared_dir),
        field_names=field_names,
    )
    markdown_content = generator.generate_markdown(timestamp)

    main_path = item_dir / f"{work_item_id} - {timestamp}.md"
    with open(main_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"  Written:  {_display_path(main_path)}")

    # Generate comments
    comments_handler = CommentsHandler(JIRA_BASE_URL, generator.attachment_handler)
    comments_content = comments_handler.fetch_and_format_comments(issue)

    comments_path = comments_dir / f"{work_item_id}-comments-{timestamp}.md"
    with open(comments_path, "w", encoding="utf-8") as f:
        f.write(comments_content)
    print(f"  Comments: {_display_path(comments_path)}")


def main():
    parser = argparse.ArgumentParser(
        description="Import Jira work items as daily markdown snapshots."
    )
    parser.add_argument(
        "ids_file",
        nargs="?",
        default=".jira.ids",
        help="Path to file with Jira IDs (default: .jira.ids)",
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force export of all work items, ignoring interval settings.",
    )
    parser.add_argument(
        "--export-dir",
        default=DEFAULT_EXPORT_DIR,
        help=f"Output directory for exported data (default: {DEFAULT_EXPORT_DIR})",
    )
    args = parser.parse_args()

    try:
        data_dir = resolve_export_dir(args.export_dir)
    except ExportPathError as e:
        print(f"Error: {e}")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")

    # Ensure export dir exists
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error: cannot create the export directory {data_dir}: {e}")
        sys.exit(1)

    print(f"Destination: {data_dir}")

    # Read IDs
    try:
        jira_ids = read_jira_ids(args.ids_file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if not jira_ids:
        print("No Jira IDs found in the file. Nothing to do.")
        sys.exit(0)

    print(f"Found {len(jira_ids)} ID(s) to import. Timestamp: {timestamp}")

    # Authenticate
    try:
        auth = JiraAuth()
        jira_client = auth.get_jira_client()
        print(f"Connected to: {auth.server}\n")
        # Map customfield ids to display names (one call) for the Details fallback
        field_names = {f["id"]: f["name"] for f in jira_client.fields()}
    except (FileNotFoundError, ValueError) as e:
        print(f"Auth error: {e}")
        sys.exit(1)

    # Process each ticket
    success, failed, skipped = 0, [], 0
    for work_item_id, interval_days in jira_ids:
        if not args.force and should_skip(work_item_id, interval_days, data_dir):
            reason = "disabled" if interval_days == 0 else f"interval={interval_days}d"
            print(f"[{work_item_id}] Skipped ({reason})\n")
            skipped += 1
            continue
        print(f"[{work_item_id}]")
        try:
            import_ticket(jira_client, work_item_id, timestamp, data_dir, field_names)
            generate_snapshot_index(data_dir / work_item_id)
            success += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed.append((work_item_id, str(e)))
        print()

    # Summary
    print("=" * 50)
    print(f"Done. {success}/{len(jira_ids)} imported, {skipped} skipped.")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for ticket_id, err in failed:
            print(f"  {ticket_id}: {err}")
    print("=" * 50)

    # Generate index
    report_path = data_dir / "jira-export-index.md"
    report_path.write_text(generate_report(data_dir, jira_ids), encoding="utf-8")
    print(f"\nIndex: {_display_path(report_path)}")


if __name__ == "__main__":
    main()
