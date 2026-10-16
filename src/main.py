"""
Import Jira work items as timestamped markdown snapshots, with jiramd.

Keeps this tool's command line, IDs file, credentials file and default output
directory, and runs `jiramd snapshot` with the Dynatrace settings in
jiramd.toml:

    python src/main.py [IDS_FILE] [--force] [--export-dir=DIR]

Credentials: JIRA_SERVER, JIRA_EMAIL and JIRA_TOKEN when all three are set,
otherwise .jira.config in the working directory.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Mapping, Optional

CONFIG = Path(__file__).resolve().parent.parent / "jiramd.toml"
DEFAULT_EXPORT_DIR = ".data"


def jiramd_argv(argv: list) -> list:
    """This tool's arguments as a jiramd command line."""
    parser = argparse.ArgumentParser(description="Import Jira work items as daily markdown snapshots.")
    parser.add_argument("ids_file", nargs="?", default=".jira.ids",
                        help="Path to file with Jira IDs (default: .jira.ids)")
    parser.add_argument("-f", "--force", action="store_true",
                        help="Force export of all work items, ignoring interval settings.")
    parser.add_argument("--export-dir", default=DEFAULT_EXPORT_DIR,
                        help=f"Output directory for exported data (default: {DEFAULT_EXPORT_DIR})")
    args = parser.parse_args(argv)
    out = ["--config", str(CONFIG), "snapshot", args.ids_file, "--export-dir", args.export_dir]
    return out + (["--force"] if args.force else [])


def credentials(env: Mapping[str, str], cwd: Path) -> dict:
    """JIRA_URL / JIRA_USER / JIRA_TOKEN for jiramd, from this tool's sources."""
    if all(env.get(k) for k in ("JIRA_SERVER", "JIRA_EMAIL", "JIRA_TOKEN")):
        return {"JIRA_URL": env["JIRA_SERVER"], "JIRA_USER": env["JIRA_EMAIL"], "JIRA_TOKEN": env["JIRA_TOKEN"]}
    path = Path(cwd) / ".jira.config"
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() in ("SERVER", "EMAIL", "TOKEN"):
            values[key.strip()] = value.strip()
    names = {"SERVER": "JIRA_URL", "EMAIL": "JIRA_USER", "TOKEN": "JIRA_TOKEN"}
    return {names[k]: v for k, v in values.items() if v}


def run(argv: Optional[list] = None, env: Optional[Mapping[str, str]] = None) -> int:
    try:
        from jiramd.cli import main as jiramd_main
    except ImportError:
        print("Error: jiramd is not installed in this environment. Run ./runme.sh once, "
              "or `pip install -r requirements.txt`.", file=sys.stderr)
        return 1
    env = dict(os.environ if env is None else env)
    cwd = Path.cwd()
    found = credentials(env, cwd)
    if not found:
        print(f"Note: no .jira.config in {cwd}, and JIRA_SERVER, JIRA_EMAIL, JIRA_TOKEN are not all set.",
              file=sys.stderr)
    return jiramd_main(jiramd_argv(sys.argv[1:] if argv is None else argv), env={**env, **found}, cwd=cwd)


if __name__ == "__main__":
    sys.exit(run())
