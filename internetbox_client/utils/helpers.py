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
