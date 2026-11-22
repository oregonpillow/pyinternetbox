---
description: Turn CHANGELOG.md's Unreleased section into the next release's notes, e.g. /release-notes v0.3.0
---

Prepare the release notes for pyinternetbox $ARGUMENTS in CHANGELOG.md. The release workflow publishes the version's section as the GitHub Release's notes, so they're the first thing users read about the release.

Changes are noted under `## [Unreleased]` at the top of CHANGELOG.md while they're made. That section becomes the release's: check it against the changes, complete it and give it the version.

## The changes

The last release: !`git describe --tags --abbrev=0 --match 'v*.*.*'`

Commits since then:

!`git log --format='%h %ad %s' --date=short "$(git describe --tags --abbrev=0 --match 'v*.*.*')"..HEAD`

Files changed since then, including changes not committed yet:

!`git diff --stat=120 "$(git describe --tags --abbrev=0 --match 'v*.*.*')"`

New files and changes not committed yet:

!`git status --short --untracked-files=all`

The commit messages are short, so read the changes themselves: `git diff <last release> -- <path>` for the library (`internetbox_client/`), the CLI (`internetbox_client/cli.py`), the exporter, the MCP server, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `README.md` and the documentation in `docs/`, and the new files. Leave out tests, CI and refactoring unless users notice them.

Look for changes that could break someone's code, scripts, dashboards or setup: public methods, arguments, CLI commands or options that were removed or renamed, changed defaults or output, renamed metrics or labels, environment variables, the minimum Python version and dependencies. To compare the public methods, list each resource class's methods at the last release (`git show <tag>:<path>`) and now.

## The version

The version is $ARGUMENTS. If it's empty, propose one following the rules in `docs/contributing/releasing.md` ("Choosing the version") and ask before writing anything. If there are breaking changes but only the patch or minor number goes up, say so.

## The section

Start from the `## [Unreleased]` section. If it's empty or missing, because changes weren't noted as they were made, write the section from the changes alone: the steps below are the same.

- Check every line against the changes: correct what's wrong, remove what was undone or isn't in the release, and add what's missing. Merge lines that describe the same area.
- The section goes below the introduction, above the previous release. Head it `## [X.Y.Z] - YYYY-MM-DD`, with today's date, and put a new, empty `## [Unreleased]` above it.
- At the end of the file, make the `[Unreleased]` link compare from the new version, and add the version's link below it: `[Unreleased]: https://github.com/oregonpillow/pyinternetbox/compare/vX.Y.Z...HEAD` and `[X.Y.Z]: https://github.com/oregonpillow/pyinternetbox/compare/v<last release>...vX.Y.Z`.

The version's section looks like the previous releases':

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

- Leave out empty headings, and "Upgrade notes" when nothing breaks.
- Write for the library's, CLI's, exporter's and Docker image's users: what they can do now, not how it's implemented. Group related changes, e.g. "Wi-Fi: turn Wi-Fi on or off, change network names and passwords", instead of listing every method. Name commands and methods in backticks, e.g. `ibox wifi set-channel` or `wifi.set_channel()`.
- Every line must be backed by the changes. Don't guess what a change is for: read the code, its docstrings and tests, or ask.
- Short, plain sentences. Bold a leading label only where a list mixes areas, e.g. **CLI**: or **Exporter**:.

## Then

1. Run `uv run scripts/release_notes.py $ARGUMENTS` to show the notes as the release will have them, and `npx --yes prettier --write CHANGELOG.md`.
2. Show the draft, and list what you changed in the Unreleased section and anything you weren't sure about.
3. Don't commit, tag or push: the user reviews the notes first.
