from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.helpers import normalize_mac
from internetbox_client.utils.labels import write

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _mst_id(mac: str) -> str:
    """Max Surf Time entries are keyed by the device's MAC address in lower case, without separators."""
    return normalize_mac(mac).replace(":", "").lower()


class MST(APIClient):
    """Query and manage Parental Control: Max Surf Time (MST)."""

    def status(self) -> str:
        """Get Max Surf Time (MST) status"""
        data = {"parameters": {}}
        return self.post("/sysbus/ToD/MaxSurfTime:get", data)

    def config(self, id: str) -> str:
        """Get Max Surf Time (MST) settings

        Args:
            id (str): MST entry ID.
        """
        data = {"parameters": {"id": id}}
        return self.post("/sysbus/ToD:getMST", data)

    def get(self) -> str:
        """Get all Max Surf Time (MST) entries"""
        data = {"parameters": {}}
        return self.post("/sysbus/ToD:listMST", data)

    @write
    def set(self, mac: str, enable: bool = True, minutes_per_day: int | None = None, allowed_time: dict | None = None) -> str:
        """Create or update a device's daily internet time limit (Max Surf Time).

        Days you don't give keep their current limit. A new entry starts at 1440 minutes (unlimited) every day.

        Args:
            mac (str): device MAC address, or its MST entry ID (see get()).
            enable (bool): whether the limit is enforced. Default is True.
            minutes_per_day (int | None): limit for every day of the week, 0-1440 minutes.
            allowed_time (dict | None): limit per day in minutes, e.g. {"Sat": 240, "Sun": 240}. Overrides
                minutes_per_day for the days given.

        Returns:
            str: response content

        """
        mac = normalize_mac(mac)
        allowed = dict.fromkeys(_DAYS, minutes_per_day) if minutes_per_day is not None else {}
        for day, minutes in (allowed_time or {}).items():
            allowed[day[:3].capitalize()] = minutes
        for day, minutes in allowed.items():
            if day not in _DAYS:
                raise ValueError(f"Unknown day {day!r} in allowed_time; use {list(_DAYS)}")
            if not 0 <= minutes <= 1440:
                raise ValueError(f"Daily limits must be between 0 and 1440 minutes, got {minutes} for {day}")
        parameters: dict = {"id": _mst_id(mac), "subject": f"MAC:{mac}", "enable": enable}
        if allowed:
            parameters["allowedTime"] = allowed
        return self.post("/sysbus/ToD:setMST", {"parameters": parameters})

    @write
    def delete(self, mac: str) -> str:
        """Delete a device's daily internet time limit (Max Surf Time) entry.

        Args:
            mac (str): device MAC address, or its MST entry ID (see get()).

        Returns:
            str: response content

        """
        data = {"parameters": {"id": _mst_id(mac)}}
        return self.post("/sysbus/ToD:deleteMST", data)

    def stats(self, id: str) -> str:
        """Get Max Surf Time (MST) statistics

        Args:
            id (str): MST entry ID.
        """
        data = {"parameters": {"id": id}}
        return self.post("/sysbus/ToD:statsMST", data)
