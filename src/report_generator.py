"""
Generates the export index (table of contents) and per-item snapshot index files.
"""

import re
from pathlib import Path

# Matches flat snapshot filenames: <ID> - <YYYY-MM-DD HH-MM-SS>.md
_SNAPSHOT_RE = re.compile(r"^(.+) - (\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2})\.md$")


def _read_frontmatter(md_file: Path) -> dict:
    """Extract key: value pairs from YAML frontmatter."""
    result = {}
    try:
        text = md_file.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return result
        end = text.index("---", 3)
        for line in text[3:end].splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                result[key.strip()] = val.strip().strip('"')
    except (ValueError, OSError):
        pass
    return result


def _list_snapshots(item_dir: Path) -> list[tuple[str, str]]:
    """Return list of (timestamp, filename_stem) sorted newest-first."""
    snapshots = []
    for f in item_dir.iterdir():
        if not f.is_file():
            continue
        m = _SNAPSHOT_RE.match(f.name)
        if m:
            snapshots.append((m.group(2), f.stem))  # (timestamp, stem)
    snapshots.sort(key=lambda x: x[0], reverse=True)
    return snapshots


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(h), max((len(r[i]) for r in rows), default=0))
              for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    header = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    lines = [header, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(row[i]).ljust(widths[i]) for i in range(len(headers))) + " |")
    return "\n".join(lines)


def generate_snapshot_index(item_dir: Path) -> None:
    """Write <ID>/<ID>-snapshot-index.md with header info and snapshot history table."""
    jira_id = item_dir.name
    snapshots = _list_snapshots(item_dir)

    # Read meta from most recent snapshot
    meta = {}
    if snapshots:
        meta = _read_frontmatter(item_dir / f"{snapshots[0][1]}.md")

    summary = meta.get("summary", "")
    issue_type = meta.get("issue_type", "")

    lines = [
        f"# {jira_id} — Snapshot History",
        "",
        f"**Jira ID:** {jira_id}",
    ]
    if summary:
        lines.append(f"**Summary:** {summary}")
    if issue_type:
        lines.append(f"**Type:** {issue_type}")
    lines += [
        "**Index:** [[jira-export-index]]",
        "",
    ]

    if snapshots:
        date_col_width = 10  # YYYY-MM-DD
        rows = []
        for ts, stem in snapshots:
            date = ts[:10]
            rows.append([date, ts, f"[[{stem}]]"])
        lines.append(_md_table(["Date", "Timestamp", "Snapshot"], rows))
    else:
        lines.append("_No snapshots yet._")

    lines.append("")
    index_path = item_dir / f"{jira_id}-snapshot-index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")


def generate_report(data_dir: Path, configured: list[tuple[str, int]]) -> str:
    """Generate the top-level jira-export-index.md content."""
    configured_ids = {jid for jid, _ in configured}

    def _item_meta(jira_id: str) -> tuple[str, str, str]:
        """Returns (summary, issue_type, last_timestamp) for a given ID."""
        item_dir = data_dir / jira_id
        if not item_dir.exists():
            return "", "", ""
        snapshots = _list_snapshots(item_dir)
        if not snapshots:
            return "", "", ""
        ts, stem = snapshots[0]
        fm = _read_frontmatter(item_dir / f"{stem}.md")
        return fm.get("summary", ""), fm.get("issue_type", ""), ts

    # Table 1: configured items
    rows1 = []
    for jira_id, interval in configured:
        summary, issue_type, last_ts = _item_meta(jira_id)
        id_link = f"[[{jira_id}-snapshot-index\\|{jira_id}]]"
        last_cell = f"[[{jira_id} - {last_ts}\\|{last_ts}]]" if last_ts else "never"
        rows1.append([id_link, summary, issue_type, str(interval), last_cell])

    rows1.sort(key=lambda r: ("0" if r[4] == "never" else "1" + r[4]), reverse=True)

    # Table 2: orphaned items
    rows2 = []
    if data_dir.exists():
        for item_dir in data_dir.iterdir():
            if not item_dir.is_dir() or item_dir.name in configured_ids:
                continue
            jira_id = item_dir.name
            summary, issue_type, last_ts = _item_meta(jira_id)
            if not last_ts:
                continue
            id_link = f"[[{jira_id}-snapshot-index\\|{jira_id}]]"
            last_cell = f"[[{jira_id} - {last_ts}\\|{last_ts}]]"
            rows2.append([id_link, summary, issue_type, last_cell])

    rows2.sort(key=lambda r: r[3], reverse=True)

    lines = ["# Jira Export Index", ""]

    lines.append("## Configured Work Items")
    lines.append("")
    if rows1:
        lines.append(_md_table(["Jira ID", "Summary", "Type", "N", "Last Export"], rows1))
    else:
        lines.append("_No items configured._")
    lines.append("")

    lines.append("## Orphaned Work Items")
    lines.append("")
    if rows2:
        lines.append(_md_table(["Jira ID", "Summary", "Type", "Last Export"], rows2))
    else:
        lines.append("_No orphaned items._")
    lines.append("")

    return "\n".join(lines)
