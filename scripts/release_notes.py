"""Print a release's section of CHANGELOG.md: the notes of its GitHub Release.

The release workflow runs it when a version tag is pushed, and stops the release before anything is published if the
section is missing or empty. To see what a release's notes will be::

    uv run scripts/release_notes.py v0.2.0
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"

# A link reference at the end of the changelog, e.g. "[0.2.0]: https://github.com/...". It belongs to the headings.
_LINK_REFERENCE = re.compile(r"^\[[^\]]+\]:\s")


class MissingNotes(ValueError):
    """CHANGELOG.md has no notes for the version."""


def release_notes(version: str, changelog: str) -> str:
    """The section of *changelog* for *version*, e.g. "v0.2.0" or "0.2.0", without its heading.

    Raises:
        MissingNotes: if there is no section for the version, or it's empty.
    """
    version = version.removeprefix("v")
    heading = re.compile(rf"^## \[?v?{re.escape(version)}\]?(\s|$)")
    lines = changelog.splitlines()
    start = next((n for n, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        raise MissingNotes(f'CHANGELOG.md has no section for {version}: add one headed "## [{version}] - YYYY-MM-DD".')
    section = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if not _LINK_REFERENCE.match(line):
            section.append(line)
    notes = "\n".join(section).strip()
    if not notes:
        raise MissingNotes(f"The CHANGELOG.md section for {version} is empty.")
    return notes + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("version", help='the release\'s version or tag, e.g. "v0.2.0"')
    parser.add_argument("--changelog", type=Path, default=CHANGELOG, help="the changelog file (default: CHANGELOG.md)")
    args = parser.parse_args(argv)
    try:
        notes = release_notes(args.version, args.changelog.read_text(encoding="utf-8"))
    except (MissingNotes, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
