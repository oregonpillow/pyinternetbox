"""Labels for what resource methods do to the router, for tools that decide which ones to offer, e.g. an MCP server.

Methods without a label only read. The labels don't change what the methods do: the library and the CLI work as before.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, TypeVar

Action = Literal["read", "write", "disruptive"]

_Method = TypeVar("_Method", bound=Callable[..., object])


def write(method: _Method) -> _Method:
    """Label a method that changes settings or data on the router, or makes it do something, e.g. a speed test."""
    method._action = "write"  # type: ignore[attr-defined]
    return method


def disruptive(method: _Method) -> _Method:
    """Label a method that also cuts the internet, Wi-Fi or phone for others, e.g. a restart or a new Wi-Fi password."""
    method._action = "disruptive"  # type: ignore[attr-defined]
    return method


def secret_result(method: _Method) -> _Method:
    """Label a method whose whole result is a secret, e.g. a PIN, which hide_secrets() can't recognise by its key."""
    method._secret_result = True  # type: ignore[attr-defined]
    return method


def action(method: Callable[..., object]) -> Action:
    """What a method does to the router: "read", "write" or "disruptive". Works on bound methods too."""
    return getattr(method, "_action", "read")


def has_secret_result(method: Callable[..., object]) -> bool:
    """Whether a method's whole result is a secret, e.g. dect.pin()."""
    return getattr(method, "_secret_result", False)
