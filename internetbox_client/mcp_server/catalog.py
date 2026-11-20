"""The library functions the MCP server's general tools offer, e.g. "wifi.summary", with what they do to the router."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter, ValidationError

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import Action, action, has_secret_result

# Telephony is left out on purpose: hardly anyone uses the landline anymore.
EXCLUDED_GROUPS = frozenset({"voice", "dect", "phonebook", "carddav"})

EXCLUDED_FUNCTIONS = frozenset(
    {
        "nmc.restore",  # replaces every setting: never through MCP
        "nmc.backup",  # the whole configuration, passwords included, as one file
        "nmc.phonebook_backup",  # telephony
        "static.translations",  # the web UI's texts: 350 KB
        "webui.release_notes",  # refused on the Internet Box 4
        "led.party_time",  # toys that keep the call busy while they blink
        "led.morse_code",
        # The event channels' plumbing. poll() waits for events, the others open or change channels.
        "events.service",
        "events.handler",
        "events.open_channel",
        "events.subscribe",
        "events.unsubscribe",
        "events.poll",
        "events.device_network",
        "events.ethernet_ports",
    }
)


@dataclass(frozen=True)
class Function:
    """A library function, e.g. wifi.set_channel."""

    group: str
    method: str
    action: Action
    secret_result: bool
    signature: inspect.Signature
    doc: str

    @property
    def name(self) -> str:
        return f"{self.group}.{self.method}"

    @property
    def summary(self) -> str:
        """The first line of the docstring."""
        return self.doc.split("\n", 1)[0]

    @property
    def usage(self) -> str:
        """The name and arguments, e.g. "wifi.set_channel(band: Literal['2.4GHz', '5GHz'], ...)"."""
        return f"{self.name}{self.signature}"

    def arguments(self, given: dict[str, Any] | None) -> dict[str, Any]:
        """Check the arguments for a call and convert them, e.g. "5" to 5 for an int.

        Returns:
            dict: every argument, defaults included.

        Raises:
            ValueError: for unknown, missing or invalid arguments.
        """
        given = dict(given or {})
        accepted = list(self.signature.parameters)
        unknown = [name for name in given if name not in accepted]
        if unknown:
            raise ValueError(f"{self.name} has no argument {', '.join(unknown)}. Its arguments: {_or_none(accepted)}.")
        missing = [name for name, p in self.signature.parameters.items() if p.default is inspect.Parameter.empty and name not in given]
        if missing:
            raise ValueError(f"{self.name} needs {', '.join(missing)}. Usage: {self.usage}")
        checked = {}
        for name, parameter in self.signature.parameters.items():
            if name not in given:
                checked[name] = parameter.default
            elif parameter.annotation is inspect.Parameter.empty:
                checked[name] = given[name]
            else:
                try:
                    checked[name] = TypeAdapter(parameter.annotation).validate_python(given[name])
                except ValidationError as exc:
                    problems = "; ".join(error["msg"] for error in exc.errors())
                    raise ValueError(f"Invalid {name} for {self.name}: {problems}. Usage: {self.usage}") from None
        return checked


def _or_none(names: list[str]) -> str:
    return ", ".join(names) or "none"


def groups(client: object) -> dict[str, APIClient]:
    """The client's resources the general tools offer, by name, e.g. {"wifi": client.wifi}."""
    return {
        name: resource
        for name, resource in vars(client).items()
        if not name.startswith("_") and isinstance(resource, APIClient) and name not in EXCLUDED_GROUPS
    }


def functions(client: object) -> dict[str, Function]:
    """Every function the general tools offer, by name, e.g. "wifi.summary"."""
    found = {}
    for group, resource in groups(client).items():
        cls = type(resource)
        for method, fn in inspect.getmembers(cls, inspect.isfunction):
            # The HTTP helpers come from APIClient, unless a resource replaces one with its own, e.g. Devices.get.
            if method.startswith("_") or (method in APIClient.__dict__ and method not in cls.__dict__):
                continue
            if f"{group}.{method}" in EXCLUDED_FUNCTIONS:
                continue
            signature = inspect.signature(fn, eval_str=True)
            signature = signature.replace(
                parameters=[p for name, p in signature.parameters.items() if name != "self"], return_annotation=inspect.Signature.empty
            )
            doc = inspect.cleandoc(fn.__doc__ or "") or method.replace("_", " ")
            found[f"{group}.{method}"] = Function(group, method, action(fn), has_secret_result(fn), signature, doc)
    return found
