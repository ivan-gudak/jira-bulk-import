"""--export-dir resolution.

runme.sh builds the destination as "$VAULT_PATH/_archive/jira-snapshots". When
VAULT_PATH is unset that becomes "/_archive/jira-snapshots", and joining an
absolute path onto the working directory discards the working directory --
so the export silently aims at the filesystem root instead of the vault.
"""

import pytest

from main import ExportPathError, resolve_export_dir


def test_relative_dir_resolves_against_the_working_directory(tmp_path):
    assert resolve_export_dir(".data", cwd=tmp_path) == tmp_path / ".data"


def test_absolute_dir_is_honoured(tmp_path):
    target = tmp_path / "out"
    assert resolve_export_dir(str(target), cwd=tmp_path) == target


def test_tilde_expands_instead_of_making_a_literal_directory(tmp_path, monkeypatch):
    """Path(cwd) / '~/out' yields '<cwd>/~/out' -- a directory named '~'."""
    monkeypatch.setenv("HOME", str(tmp_path))
    assert resolve_export_dir("~/out", cwd=tmp_path) == tmp_path / "out"


def test_trailing_slash_normalizes(tmp_path):
    assert resolve_export_dir(f"{tmp_path}/out/", cwd=tmp_path) == tmp_path / "out"


# --- The reported failure ----------------------------------------------------

def test_unset_vault_path_is_rejected(tmp_path):
    """VAULT_PATH='' turns the destination into '/_archive/jira-snapshots'."""
    with pytest.raises(ExportPathError) as exc:
        resolve_export_dir("/_archive/jira-snapshots", cwd=tmp_path)
    message = str(exc.value)
    assert "VAULT_PATH" in message
    assert "/_archive/jira-snapshots" in message


def test_a_real_absolute_destination_is_allowed(tmp_path):
    """Its parent exists, so no new top-level directory is implied."""
    target = tmp_path / "vault" / "_archive" / "jira-snapshots"
    assert resolve_export_dir(str(target), cwd=tmp_path) == target


def test_a_missing_leaf_under_an_existing_root_is_allowed(tmp_path):
    """Only the top level matters; mkdir(parents=True) handles the rest."""
    assert resolve_export_dir("deep/nested/out", cwd=tmp_path) == (
        tmp_path / "deep" / "nested" / "out"
    )


def test_filesystem_root_itself_is_rejected(tmp_path):
    with pytest.raises(ExportPathError):
        resolve_export_dir("/", cwd=tmp_path)


# --- Degenerate values -------------------------------------------------------

def test_empty_dir_is_rejected_rather_than_exporting_into_the_project(tmp_path):
    """Path(cwd) / '' is cwd, which scatters ticket directories into the repo."""
    with pytest.raises(ExportPathError, match="empty"):
        resolve_export_dir("", cwd=tmp_path)


def test_whitespace_only_dir_is_rejected(tmp_path):
    with pytest.raises(ExportPathError, match="empty"):
        resolve_export_dir("   ", cwd=tmp_path)


def test_resolver_creates_nothing(tmp_path):
    target = resolve_export_dir("out", cwd=tmp_path)
    assert not target.exists()
