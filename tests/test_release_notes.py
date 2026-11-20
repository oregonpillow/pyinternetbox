"""Tests for scripts/release_notes.py, which gives each GitHub Release its notes from CHANGELOG.md."""

from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "release_notes.py"
_spec = importlib.util.spec_from_file_location("release_notes", _SCRIPT)
release_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_notes)

CHANGELOG = """# Changelog

Intro.

## [0.2.10] - 2026-12-01

### Fixed

- Something else.

## [0.2.1] - 2026-11-21

### Fixed

- Something.

## [0.2.0] - 2026-11-20

### Added

- Everything.

## [0.1.0] - 2026-11-19

[0.2.1]: https://github.com/oregonpillow/pyinternetbox/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/oregonpillow/pyinternetbox/compare/v0.1.0...v0.2.0
"""


@pytest.mark.parametrize("version", ["v0.2.1", "0.2.1"])
def test_a_section(version: str) -> None:
    assert release_notes.release_notes(version, CHANGELOG) == "### Fixed\n\n- Something.\n"


def test_the_last_section_leaves_out_the_links() -> None:
    changelog = CHANGELOG.replace("## [0.1.0] - 2026-11-19\n", "## [0.1.0] - 2026-11-19\n\nFirst release.\n")
    assert release_notes.release_notes("v0.1.0", changelog) == "First release.\n"


@pytest.mark.parametrize(
    "version,message",
    [("v0.3.0", 'no section for 0.3.0: add one headed "## [0.3.0] - YYYY-MM-DD"'), ("v0.1.0", "section for 0.1.0 is empty")],
)
def test_missing_notes(version: str, message: str) -> None:
    with pytest.raises(release_notes.MissingNotes, match=re.escape(message)):
        release_notes.release_notes(version, CHANGELOG)


def test_main(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG)
    assert release_notes.main(["v0.2.0", "--changelog", str(changelog)]) == 0
    assert capsys.readouterr().out == "### Added\n\n- Everything.\n"
    assert release_notes.main(["v9.9.9", "--changelog", str(changelog)]) == 1
    assert "error: CHANGELOG.md has no section for 9.9.9" in capsys.readouterr().err
    assert release_notes.main(["v0.2.0", "--changelog", str(tmp_path / "missing.md")]) == 1


def test_every_release_in_the_changelog_has_notes() -> None:
    changelog = (_SCRIPT.parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
    versions = [line.split("]")[0].removeprefix("## [") for line in changelog.splitlines() if line.startswith("## [")]
    assert versions
    for version in versions:
        assert release_notes.release_notes(version, changelog).strip(), version
