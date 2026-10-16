"""should_skip reads the last export time from the newest snapshot's file name.

main.py stamps snapshots with datetime.now() -- the machine's local time --
but should_skip read that stamp as UTC, so the throttle window was off by the
machine's UTC offset: longer east of UTC, shorter west of it.
"""

import time
from datetime import datetime, timedelta

import pytest

from main import should_skip


@pytest.fixture
def local_zone(monkeypatch):
    """Switch the process's local time zone (POSIX TZ: 'EST+5' is UTC-5)."""
    def use(tz):
        monkeypatch.setenv("TZ", tz)
        time.tzset()
    yield use
    monkeypatch.undo()
    time.tzset()


def _snapshot(data_dir, hours_ago):
    """Write a snapshot named the way main.py names it, hours_ago in the past."""
    item = data_dir / "PROJ-1"
    item.mkdir(parents=True, exist_ok=True)
    stamp = (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H-%M-%S")
    (item / f"PROJ-1 - {stamp}.md").write_text("", encoding="utf-8")


def test_east_of_utc_a_snapshot_older_than_the_window_is_exported_again(tmp_path, local_zone):
    local_zone("EET-2")  # UTC+2
    _snapshot(tmp_path, hours_ago=13)
    assert should_skip("PROJ-1", 1, tmp_path) is False


def test_west_of_utc_a_snapshot_inside_the_window_is_skipped(tmp_path, local_zone):
    local_zone("EST+5")  # UTC-5
    _snapshot(tmp_path, hours_ago=10)
    assert should_skip("PROJ-1", 1, tmp_path) is True
