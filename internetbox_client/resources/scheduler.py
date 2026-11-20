import json
import re

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.helpers import normalize_mac
from internetbox_client.utils.labels import write

WEEK = 7 * 86400  # schedule times are seconds since Monday 00:00
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _week_seconds(value: int | str) -> int:
    """Seconds since Monday 00:00, from seconds or a "Tue 07:30" string ("Sun 24:00" is the end of the week)."""
    if isinstance(value, str) and not value.strip().isdigit():
        match = re.fullmatch(r"([a-z]{3})[a-z]*\s+(\d{1,2}):(\d{2})", value.strip().lower())
        day, hours, minutes = match.groups() if match else ("", "0", "0")
        if day not in _DAYS or int(minutes) > 59 or int(hours) * 60 + int(minutes) > 1440:
            raise ValueError(f'Expected seconds since Monday 00:00 or a time like "Tue 07:30", got {value!r}')
        return _DAYS.index(day) * 86400 + int(hours) * 3600 + int(minutes) * 60
    seconds = int(value)
    if not 0 <= seconds <= WEEK:
        raise ValueError(f"Schedule times must be between 0 and {WEEK} seconds (Monday 00:00 to Sunday 24:00), got {value}")
    return seconds


def _blocked_periods(periods: list) -> list[dict]:
    """Turn {"begin", "end"} periods into the router's format: sorted, merged, within one week.

    The router silently drops a period that wraps past Sunday midnight (begin > end), so it is split in two.
    """
    spans = []
    for period in periods:
        begin, end = _week_seconds(period["begin"]), _week_seconds(period["end"])
        spans += [(begin, WEEK), (0, end)] if begin > end else [(begin, end)]
    merged: list[list[int]] = []
    for begin, end in sorted(span for span in spans if span[0] < span[1]):
        if merged and begin <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([begin, end])
    return [{"begin": begin, "end": end, "state": "Disable"} for begin, end in merged]


class Scheduler(APIClient):
    """Scheduled tasks and timer configurations."""

    def complete_schedules(self, schedule_type: str = "WLAN") -> str:
        """Get complete schedules

        Args:
            schedule_type (str): type of schedule to retrieve. E.g. "WLAN", "MST". Default is "WLAN"
        """
        data = {"parameters": {"type": schedule_type}}
        return self.post("/sysbus/Scheduler:getCompleteSchedules", data)

    def device_schedule(self, mac: str) -> str:
        """Get a device's internet access schedule (parental controls).

        In the response, "value" is the current state: "Disable" while internet access is blocked. A device without a
        schedule returns {"status": false}.

        Args:
            mac (str): device MAC address.

        Returns:
            str: response content

        """
        data = {"parameters": {"type": "ToD", "ID": normalize_mac(mac)}}
        return self.post("/sysbus/Scheduler:getSchedule", data)

    @write
    def set_device_schedule(self, mac: str, blocked_periods: list, enable: bool = True) -> str:
        """Create or replace a device's internet access schedule (parental controls).

        Args:
            mac (str): device MAC address.
            blocked_periods (list): when internet access is blocked, as [{"begin": ..., "end": ...}]. Times are
                strings like "Mon 22:00" or seconds since Monday 00:00. A period may run past Sunday midnight.
                [] never blocks; [{"begin": "Mon 00:00", "end": "Sun 24:00"}] blocks all week.
            enable (bool): whether the schedule is active. Default is True.

        Example:
            Block Sunday to Thursday nights, 21:00 to 07:00:
            [{"begin": "Sun 21:00", "end": "Mon 07:00"}, {"begin": "Mon 21:00", "end": "Tue 07:00"}, ...]

        Returns:
            str: response content

        """
        info = {
            "ID": normalize_mac(mac),
            "enable": enable,
            "base": "Weekly",
            "def": "Enable",
            "override": "",
            "schedule": _blocked_periods(blocked_periods),
        }
        return self.post("/sysbus/Scheduler:addSchedule", {"parameters": {"type": "ToD", "info": info}})

    @write
    def enable_device_schedule(self, mac: str, enable: bool = True) -> str:
        """Turn a device's internet access schedule on or off, keeping its periods.

        Args:
            mac (str): device MAC address.
            enable (bool): True to turn the schedule on, False to turn it off. Default is True.

        Returns:
            str: response content

        """
        data = {"parameters": {"type": "ToD", "ID": normalize_mac(mac), "enable": enable}}
        return self.post("/sysbus/Scheduler:enableSchedule", data)

    @write
    def remove_device_schedule(self, mac: str) -> str:
        """Delete a device's internet access schedule.

        Args:
            mac (str): device MAC address.

        Returns:
            str: response content

        """
        mac = normalize_mac(mac)
        # The router ignores the removal of a schedule turned on with enableSchedule until it's turned off again.
        if json.loads(self.device_schedule(mac)).get("status"):
            self.enable_device_schedule(mac, False)
        data = {"parameters": {"type": "ToD", "ID": mac}}
        return self.post("/sysbus/Scheduler:removeSchedules", data)
