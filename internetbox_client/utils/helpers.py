import re
from typing import Any

HIDDEN = "<hidden>"

# Keys of secrets, e.g. KeyPassPhrase, RadiusSecret, IPsecPreSharedKey, authPassword or SelfPIN. Keys with spaces or
# dashes aren't matched: they are text, e.g. in the web UI's translations.
_SECRET_KEY = re.compile(r"\w*(password|passphrase|secret|presharedkey|psk|privatekey|wepkey|r0khkey|pin|puk|token)", re.IGNORECASE)


def hide_secrets(data: Any) -> Any:
    """Return a copy of a decoded response with passwords, keys and other secrets replaced by `"<hidden>"`.

    Secrets are recognised by their key, e.g. KeyPassPhrase (Wi-Fi), password (DynDNS) or PreSharedKey (WireGuard).
    Empty values stay, so it's still visible that none is set, and so do booleans such as UseSyncToken. A method whose
    whole result is a secret, e.g. dect.pin(), is labelled instead: see labels.has_secret_result().

    The library and the CLI show secrets. This is for output that shouldn't, e.g. an MCP server's.
    """
    if isinstance(data, dict):
        return {key: HIDDEN if _is_secret(key, value) else hide_secrets(value) for key, value in data.items()}
    if isinstance(data, list):
        return [hide_secrets(value) for value in data]
    return data


def _is_secret(key: object, value: object) -> bool:
    if not isinstance(key, str) or not _SECRET_KEY.fullmatch(key) or isinstance(value, bool):
        return False
    return value not in (None, "", [], {})


def camel(s: str) -> str:
    """Convert a string to camel case.
        Several client payloads need case sensitive keys

    Args:
        s (str): The string to convert.

    Returns:
        str: The converted string in camel case.

    """
    return "".join(w.capitalize() for w in __import__("re").split(r"[_\-\s]+", s.lower()) if w)


def decode_nested_json(obj):
    """Recursively decode stringified JSON values in a parsed object.

    Some router API responses embed JSON-encoded strings as field values.
    This function walks the structure and replaces any string that is valid
    JSON (dict or list) with its decoded form.

    Args:
        obj: A parsed JSON value (dict, list, str, or scalar).

    Returns:
        The same structure with nested JSON strings decoded in place.
    """
    import json

    if isinstance(obj, dict):
        return {k: decode_nested_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decode_nested_json(v) for v in obj]
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
            if isinstance(parsed, (dict, list)):
                return decode_nested_json(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
    return obj


def normalize_mac(mac: str) -> str:
    """Return a MAC address in the router's format: upper case, colon-separated.

    Accepts the common notations: "aa:bb:cc:dd:ee:ff", "AA-BB-CC-DD-EE-FF", "aabb.ccdd.eeff" and "aabbccddeeff".

    Raises:
        ValueError: if *mac* is not a MAC address.
    """
    digits = re.sub(r"[:.\-]", "", mac.strip())
    if not re.fullmatch(r"[0-9A-Fa-f]{12}", digits):
        raise ValueError(f"Not a MAC address: {mac!r}")
    return ":".join(digits[i : i + 2] for i in range(0, 12, 2)).upper()
