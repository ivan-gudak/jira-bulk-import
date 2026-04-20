"""
Jira Bulk Importer
Reads a list of Jira IDs and imports each as a daily markdown snapshot.
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))

from jira_auth import JiraAuth
from markdown_generator import MarkdownGenerator
from comments_handler import CommentsHandler
from config import FIELD_MAPPING, JIRA_BASE_URL


DATA_DIR = Path(os.getcwd()) / ".data"


def read_jira_ids(ids_file: str) -> list[str]:
    """Read Jira IDs from file, one per line. Skips blank lines and comments."""
    path = Path(ids_file)
    if not path.exists():
        raise FileNotFoundError(f"IDs file not found: {ids_file}")
    ids = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                ids.append(line)
    return ids


def import_ticket(jira_client, work_item_id: str, today: str) -> None:
    """Import a single Jira ticket into .data/<ID>/<date>/."""
    ticket_dir = DATA_DIR / work_item_id / today
    attachments_dir = ticket_dir / "attachments"
    shared_dir = DATA_DIR / work_item_id / "attachments_shared"

    ticket_dir.mkdir(parents=True, exist_ok=True)
    shared_dir.mkdir(parents=True, exist_ok=True)

    # Fetch issue
    field_ids = ",".join(set(FIELD_MAPPING.values())) + ",attachment,comment"
    issue = jira_client.issue(work_item_id, fields=field_ids)
    print(f"  Fetched: {issue.key} - {issue.fields.summary}")

    # Generate main markdown
    generator = MarkdownGenerator(
        issue,
        jira_client=jira_client,
        attachments_dir=str(attachments_dir),
        shared_dir=str(shared_dir),
    )
    markdown_content = generator.generate_markdown(today)

    main_path = ticket_dir / f"{work_item_id}.md"
    with open(main_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"  Written:  {main_path.relative_to(Path(os.getcwd()))}")

    # Generate comments
    comments_handler = CommentsHandler(JIRA_BASE_URL, generator.attachment_handler)
    comments_content = comments_handler.fetch_and_format_comments(issue)

    comments_path = ticket_dir / f"{work_item_id}-comments-{today}.md"
    with open(comments_path, "w", encoding="utf-8") as f:
        f.write(comments_content)
    print(f"  Comments: {comments_path.relative_to(Path(os.getcwd()))}")


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
    args = parser.parse_args()

    today = date.today().isoformat()  # YYYY-MM-DD

    # Ensure .data exists
    DATA_DIR.mkdir(exist_ok=True)

    # Read IDs
    try:
        jira_ids = read_jira_ids(args.ids_file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if not jira_ids:
        print("No Jira IDs found in the file. Nothing to do.")
        sys.exit(0)

    print(f"Found {len(jira_ids)} ID(s) to import. Date: {today}")

    # Authenticate
    try:
        auth = JiraAuth()
        jira_client = auth.get_jira_client()
        print(f"Connected to: {auth.server}\n")
    except (FileNotFoundError, ValueError) as e:
        print(f"Auth error: {e}")
        sys.exit(1)

    # Process each ticket
    success, failed = 0, []
    for work_item_id in jira_ids:
        print(f"[{work_item_id}]")
        try:
            import_ticket(jira_client, work_item_id, today)
            success += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed.append((work_item_id, str(e)))
        print()

    # Summary
    print("=" * 50)
    print(f"Done. {success}/{len(jira_ids)} imported successfully.")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for ticket_id, err in failed:
            print(f"  {ticket_id}: {err}")
    print("=" * 50)


if __name__ == "__main__":
    main()
