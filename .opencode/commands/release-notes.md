---
description: Draft the CHANGELOG.md section for the next release, e.g. /release-notes v0.3.0
---

Draft the release notes for pyinternetbox $ARGUMENTS: a new section at the top of CHANGELOG.md. The release workflow publishes that section as the GitHub Release's notes, so they're the first thing users read about the release.

## The changes

The last release: !`git describe --tags --abbrev=0 --match 'v*.*.*'`

Commits since then:

!`git log --format='%h %ad %s' --date=short "$(git describe --tags --abbrev=0 --match 'v*.*.*')"..HEAD`

Files changed since then, including changes not committed yet:

!`git diff --stat=120 "$(git describe --tags --abbrev=0 --match 'v*.*.*')"`

New files and changes not committed yet:

!`git status --short --untracked-files=all`

The commit messages are short, so read the changes themselves: `git diff <last release> -- <path>` for the library (`internetbox_client/`), the CLI (`internetbox_client/cli.py`), the exporter, the MCP server, `pyproject.toml`, `Dockerfile`, `docker-compose.yml` and `README.md`, and the new files. Leave out tests, CI and refactoring unless users notice them.

Look for changes that could break someone's code, scripts, dashboards or setup: public methods, arguments, CLI commands or options that were removed or renamed, changed defaults or output, renamed metrics or labels, environment variables, the minimum Python version and dependencies. To compare the public methods, list each resource class's methods at the last release (`git show <tag>:<path>`) and now.

## The version

The version is $ARGUMENTS. If it's empty, propose one following the README's rules (Releasing > Choosing the version) and ask before writing anything. If there are breaking changes but only the patch or minor number goes up, say so.

## The section

Write it below the introduction of CHANGELOG.md, above the previous release, like the sections already there:

```md
## [X.Y.Z] - YYYY-MM-DD

One to three sentences: what the release is about, for someone deciding whether to upgrade.

### Upgrade notes

- What breaks, and what to do instead.

### Added

### Changed

### Fixed

### Removed

### Security
```

- Use today's date. Leave out empty headings, and "Upgrade notes" when nothing breaks.
- Add a link reference at the end of the file, above the others: `[X.Y.Z]: https://github.com/oregonpillow/pyinternetbox/compare/v<last release>...vX.Y.Z`.
- Write for the library's, CLI's, exporter's and Docker image's users: what they can do now, not how it's implemented. Group related changes, e.g. "Wi-Fi: turn Wi-Fi on or off, change network names and passwords", instead of listing every method. Name commands and methods in backticks, e.g. `ibox wifi set-channel` or `wifi.set_channel()`.
- Every line must be backed by the changes. Don't guess what a change is for: read the code, its docstrings and tests, or ask.
- Short, plain sentences. Bold a leading label only where a list mixes areas, e.g. **CLI**: or **Exporter**:.

## Then

1. Run `uv run scripts/release_notes.py $ARGUMENTS` to show the notes as the release will have them, and `npx --yes prettier --write CHANGELOG.md`.
2. Show the draft, and list anything you weren't sure about.
3. Don't commit, tag or push: the user reviews the notes first.
