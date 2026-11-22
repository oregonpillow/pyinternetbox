"""Tests for the documentation site: every group of InternetBoxClient has a library reference page in the navigation."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from internetbox_client import InternetBoxClient
from internetbox_client.utils.APIClient import APIClient

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "docs" / "reference" / "library"


def _groups() -> dict[str, type[APIClient]]:
    client = InternetBoxClient(hostname="internetbox.example")
    return {group: type(resource) for group, resource in vars(client).items() if isinstance(resource, APIClient)}


def _nav_pages(nav: list[Any]) -> Iterator[str]:
    for item in nav:
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            for value in item.values():
                yield from _nav_pages(value) if isinstance(value, list) else [value]


def test_every_group_has_a_reference_page() -> None:
    for group, cls in _groups().items():
        page = LIBRARY / f"{group}.md"
        assert page.is_file(), f"{page.relative_to(ROOT)} is missing"
        assert f"::: {cls.__module__}.{cls.__qualname__}\n" in page.read_text(), f"{page.name} doesn't render {cls.__qualname__}"


def test_no_reference_page_without_a_group() -> None:
    pages = {page.stem for page in LIBRARY.glob("*.md")} - {"index"}
    assert pages == set(_groups())


def test_every_page_is_in_the_navigation() -> None:
    config = tomllib.loads((ROOT / "zensical.toml").read_text())
    nav = set(_nav_pages(config["project"]["nav"]))
    pages = {page.relative_to(ROOT / "docs").as_posix() for page in (ROOT / "docs").rglob("*.md")}
    assert pages - nav == set(), "pages missing from the nav in zensical.toml"
    assert nav - pages == set(), "nav entries in zensical.toml without a page"
