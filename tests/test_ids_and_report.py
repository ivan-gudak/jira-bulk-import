"""The IDs file and the table of contents."""

import pytest

from jira_auth import describe
from main import read_jira_ids
from report_generator import generate_report


def test_ids_file_with_a_byte_order_mark(tmp_path):
    p = tmp_path / ".jira.ids"
    p.write_bytes("﻿PROJ-1\r\nPROJ-2=3\r\n".encode("utf-8"))
    assert read_jira_ids(str(p)) == [("PROJ-1", 1), ("PROJ-2", 3)]


def test_a_line_that_is_not_a_key_stops_with_its_line_number(tmp_path):
    p = tmp_path / ".jira.ids"
    p.write_text("PROJ-1\nPROJ 2\n../x\n", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        read_jira_ids(str(p))
    assert "line 2" in str(e.value) and "line 3" in str(e.value)


def test_table_cells_escape_pipes(tmp_path):
    item = tmp_path / "PROJ-1"
    item.mkdir()
    (item / "PROJ-1 - 2026-10-02 08-00-00.md").write_text('---\nsummary: "A | B"\n---\n', encoding="utf-8")
    assert "A \\| B" in generate_report(tmp_path, [("PROJ-1", 1)])


def test_describe_keeps_status_and_text_but_not_headers():
    from jira.exceptions import JIRAError

    class Response:
        headers = {"Set-Cookie": "JSESSIONID=SECRET-SESSION"}
        text = "x"

    error = JIRAError(status_code=403, text="Forbidden", url="https://example.atlassian.net/x", response=Response())
    assert "SECRET-SESSION" in str(error)
    assert describe(error) == "HTTP 403: Forbidden"
