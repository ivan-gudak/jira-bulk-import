"""import_ticket and the shared attachment pool.

Every run used to create an Attachments/<timestamp>/ folder that nothing was
ever written to, and to download every attachment again only to find its hash
already in the pool. A Jira attachment ID always names the same content, so a
file already pooled under that ID needs no download.
"""

import hashlib

from main import import_ticket


class FakeAttachment:
    def __init__(self, att_id, filename, content):
        self.id = att_id
        self.filename = filename
        self.content = content
        self.downloads = 0

    def get(self):
        self.downloads += 1
        return self.content


class FakeFields:
    """Any field the generator asks for and the test did not set is empty."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        return None


class FakeIssue:
    def __init__(self, key, attachments):
        self.key = key
        self.id = "1"
        self.fields = FakeFields(summary="S", description="D", attachment=attachments)


class FakeJira:
    def __init__(self, issue):
        self._issue = issue

    def issue(self, key):
        return self._issue


def _pooled(att):
    return f"{hashlib.sha256(att.content).hexdigest()[:8]}_{att.filename}"


def _run(tmp_path, att, stamp):
    import_ticket(FakeJira(FakeIssue("PROJ-1", [att])), "PROJ-1", stamp, tmp_path, {})
    return (tmp_path / "PROJ-1" / f"PROJ-1 - {stamp}.md").read_text(encoding="utf-8")


def test_a_run_creates_no_per_run_attachment_folder(tmp_path):
    _run(tmp_path, FakeAttachment("10", "a.png", b"png"), "2026-10-16 08-00-00")
    item = tmp_path / "PROJ-1"
    assert (item / "attachments_shared").is_dir()
    assert not (item / "Attachments").exists()


def test_an_unchanged_attachment_is_not_downloaded_again(tmp_path):
    att = FakeAttachment("10", "a.png", b"png")
    _run(tmp_path, att, "2026-10-16 08-00-00")
    second = _run(tmp_path, att, "2026-10-17 08-00-00")
    assert att.downloads == 1
    assert _pooled(att) in second


def test_an_attachment_missing_from_the_pool_is_downloaded_again(tmp_path):
    att = FakeAttachment("10", "a.png", b"png")
    _run(tmp_path, att, "2026-10-16 08-00-00")
    pooled = tmp_path / "PROJ-1" / "attachments_shared" / _pooled(att)
    pooled.unlink()
    _run(tmp_path, att, "2026-10-17 08-00-00")
    assert att.downloads == 2
    assert pooled.is_file()


def test_an_unreadable_attachment_record_means_downloading_again(tmp_path):
    att = FakeAttachment("10", "a.png", b"png")
    _run(tmp_path, att, "2026-10-16 08-00-00")
    for record in (tmp_path / "PROJ-1" / "attachments_shared").glob(".*"):
        record.write_text("{not json", encoding="utf-8")
    second = _run(tmp_path, att, "2026-10-17 08-00-00")
    assert att.downloads == 2
    assert _pooled(att) in second


def test_an_attachment_name_cannot_leave_the_pool(tmp_path):
    """The name comes from whoever attached the file."""
    att = FakeAttachment("10", "../../escaped.png", b"png")
    second = _run(tmp_path, att, "2026-10-16 08-00-00")
    pooled = f"{hashlib.sha256(b'png').hexdigest()[:8]}_escaped.png"
    assert pooled in second
    assert [p.parent for p in tmp_path.rglob("*.png")] == [tmp_path / "PROJ-1" / "attachments_shared"]
