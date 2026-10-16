"""src/main.py runs `jiramd snapshot` with this repository's Dynatrace configuration.

The command line, the IDs file, the credentials file and the default output
directory are the ones this tool always had; jiramd does the work.
"""

import main
from jiramd.config import load_settings


def test_defaults_are_the_ids_file_and_data_dir():
    assert main.jiramd_argv([]) == ["--config", str(main.CONFIG), "snapshot", ".jira.ids", "--export-dir", ".data"]


def test_ids_file_export_dir_and_force_pass_through():
    argv = main.jiramd_argv(["my.ids", "--export-dir=/vault/_archive/jira-snapshots", "--force"])
    assert argv[3:] == ["my.ids", "--export-dir", "/vault/_archive/jira-snapshots", "--force"]


def test_short_force_flag():
    assert main.jiramd_argv(["-f"])[-1] == "--force"


def test_credentials_come_from_jira_config(tmp_path):
    (tmp_path / ".jira.config").write_text("SERVER: https://s\nEMAIL: e@x\nTOKEN: t\n", encoding="utf-8")
    env = main.credentials({}, tmp_path)
    assert (env["JIRA_URL"], env["JIRA_USER"], env["JIRA_TOKEN"]) == ("https://s", "e@x", "t")


def test_credentials_come_from_the_environment_when_all_three_are_set(tmp_path):
    env = main.credentials({"JIRA_SERVER": "https://s", "JIRA_EMAIL": "e@x", "JIRA_TOKEN": "t"}, tmp_path)
    assert env == {"JIRA_URL": "https://s", "JIRA_USER": "e@x", "JIRA_TOKEN": "t"}


def test_snapshots_stay_as_they_were():
    """Real names, no Team in Metadata, no pull requests -- as before."""
    settings = load_settings(main.CONFIG, {})
    assert settings.snapshot.anonymize is False
    assert "customfield_17800" not in settings.page.metadata
    assert "pull-requests" not in settings.page.order
    assert [s.title for s in settings.page.sections] == ["Status Details", "Release Notes"]
