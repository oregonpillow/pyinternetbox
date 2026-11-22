# Releasing

The version is defined **only by the git tag** — there is no version number to edit in any file.
[hatch-vcs](https://github.com/ofek/hatch-vcs) derives it at build time, and it flows into the PyPI package, `ibox --version`, the Docker image tags and the exporter's startup line.

First write the release notes: a section for the new version at the top of [`CHANGELOG.md`](https://github.com/oregonpillow/pyinternetbox/blob/master/CHANGELOG.md). Note changes under `## [Unreleased]` as you make them, if you like. In [OpenCode](https://opencode.ai/), `/release-notes v0.2.0` turns that section into the version's: it checks it against the changes since the last release, completes it (or writes it from the changes, if nothing was noted), and starts a new, empty `[Unreleased]`. Read and correct the draft, then commit it. `uv run scripts/release_notes.py v0.2.0` shows the notes as the release will have them.

Then tag the commit that has the notes:

```sh
git checkout master && git pull
git tag v0.2.0
git push origin v0.2.0
```

Pushing the tag runs [`release.yml`](https://github.com/oregonpillow/pyinternetbox/blob/master/.github/workflows/release.yml), which runs the tests and then:

- publishes `pyinternetbox==0.2.0` to PyPI
- pushes `oregonpillow/pyinternetbox:0.2.0`, `:0.2` and `:latest` to Docker Hub
- creates a GitHub Release with the version's section of `CHANGELOG.md` as its notes, and the built packages
- publishes this documentation site to GitHub Pages, so it describes the released version

The release stops before anything is published if `CHANGELOG.md` has no section for the version.

Every push to `master` also publishes `oregonpillow/pyinternetbox:edge`. Untagged builds get a development version such as `0.2.1.dev3+g1a2b3c4`.

To publish documentation fixes without a release, run the **Docs** workflow by hand: GitHub → Actions → Docs → Run workflow, on `master`.

**Choosing the version** ([semver](https://semver.org/)): bump `PATCH` for bug fixes, `MINOR` for new endpoints/metrics/options, `MAJOR` for breaking changes. Use plain `vMAJOR.MINOR.PATCH` tags (no `-rc1` style suffixes). To see the version the current commit would get: `uv run ibox --version`.

**If a release fails** before anything is published (e.g. tests fail), fix the problem on `master`, then move the tag:

```sh
git tag -d v0.2.0 && git push origin :refs/tags/v0.2.0
git tag v0.2.0 && git push origin v0.2.0
```

PyPI never accepts the same version twice, so if the package was already uploaded, release a new patch version (`v0.2.1`) instead.

**One-time setup** (kept here for reference):

- GitHub → Settings → Secrets and variables → Actions: `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (a Docker Hub personal access token with _Read & Write_ access).
- pypi.org → Account → Publishing: trusted publisher for owner `oregonpillow`, repository `pyinternetbox`, workflow `release.yml`, environment `pypi`.
- GitHub → Settings → Pages → Build and deployment: Source **GitHub Actions**.
- GitHub → Settings → Environments → `github-pages` → Deployment branches and tags: add a tag rule `v*`. Without it, GitHub only lets `master` publish the site, and the release's docs job fails.
