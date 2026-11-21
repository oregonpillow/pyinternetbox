import json
import re
from typing import Literal

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.helpers import normalize_mac
from internetbox_client.utils.labels import disruptive, write

WEEK = 7 * 86400  # schedule times are seconds since Monday 00:00
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# The Wi-Fi schedule in the web UI's power settings: one schedule, with the ID "wl0", for all Wi-Fi networks.
_WIFI = {"type": "WLAN", "ID": "wl0"}
# override_device_schedule()'s choices, and the router's override for each.
_OVERRIDES = {"allow": "Enable", "block": "Disable", "schedule": ""}


def _schedule_info(schedule: dict) -> dict:
    """The "scheduleInfo" of a getSchedule response, or {} without a schedule."""
    return (schedule.get("data") or {}).get("scheduleInfo") or {}


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

        In the response, "value" is the current state: "Disable" while internet access is blocked. "override" is a
        lasting override and "temporaryOverride" whether one lasts until the schedule next changes (see
        override_device_schedule()). A device without a schedule returns {"status": false}.

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
    def override_device_schedule(self, mac: str, access: Literal["allow", "block", "schedule"], until_next_change: bool = False) -> str:
        """Allow or block a device's internet access now, whatever its schedule says, e.g. for one more evening.

        A lasting override stays until it's set back to "schedule", also when the schedule is turned off and on.
        set_device_schedule() ends it, and so does devices.block() if it allows access. The web UI doesn't show
        overrides.

        Args:
            mac (str): device MAC address. The device needs a schedule that's on (see set_device_schedule()).
            access (str): "allow" or "block" internet access, or "schedule" to follow the schedule again.
            until_next_change (bool): True to override only until the schedule next switches the other way, e.g.
                "allow" until the schedule next blocks the device. Default is False: until set back to "schedule".

        Returns:
            str: the device's schedule, as from device_schedule(). "value" is "Disable" while it is blocked.

        Raises:
            ValueError: if the device has no schedule, or it's off, or until_next_change is given with "schedule".

        """
        if access not in _OVERRIDES:
            raise ValueError(f"access must be one of {list(_OVERRIDES)}, got {access!r}")
        if until_next_change and access == "schedule":
            raise ValueError('until_next_change needs access "allow" or "block".')
        mac = normalize_mac(mac)
        schedule = json.loads(self.device_schedule(mac))
        if not schedule.get("status"):
            raise ValueError(f"{mac} has no internet access schedule. Create one with set_device_schedule().")
        if access != "schedule" and not _schedule_info(schedule).get("enable"):
            raise ValueError(f"The internet access schedule of {mac} is off, so overriding it does nothing. Turn it on first.")
        self._override(mac, access, until_next_change)
        return self.device_schedule(mac)

    def _override(self, mac: str, access: str, until_next_change: bool = False) -> None:
        if until_next_change:
            self.post("/sysbus/Scheduler:overrideState", {"parameters": {"type": "ToD", "ID": mac, "state": _OVERRIDES[access]}})
        else:
            self.post("/sysbus/Scheduler:overrideSchedule", {"parameters": {"type": "ToD", "ID": mac, "override": _OVERRIDES[access]}})

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

    def wifi_schedule(self) -> str:
        """Get the Wi-Fi schedule, which turns Wi-Fi off at set times to save power (the web UI's power settings).

        In the response, "schedule" lists the periods when Wi-Fi is off, "enable" whether the schedule is on, and
        "value" the current state: "Disable" while Wi-Fi is off. Without a schedule, the response is {"status": false}.

        Returns:
            str: response content

        """
        data = {"parameters": _WIFI}
        return self.post("/sysbus/Scheduler:getSchedule", data)

    @disruptive
    def set_wifi_schedule(self, off_periods: list, enable: bool = True) -> str:
        """Turn Wi-Fi off at set times every week, like the Wi-Fi schedule in the web UI's power settings.

        The schedule covers all Wi-Fi networks, including the guest network. While it's on, wireless devices lose
        their connection during the off periods, including this computer if it's on Wi-Fi.

        Args:
            off_periods (list): when Wi-Fi is off, as [{"begin": ..., "end": ...}], like the blocked periods of
                set_device_schedule(): times such as "Mon 00:30" or seconds since Monday 00:00. A period may run past
                Sunday midnight. With [], Wi-Fi stays on, and the schedule is saved turned off, like in the web UI.
            enable (bool): whether the schedule is on. Default is True.

        Example:
            Wi-Fi off every night from 01:00 to 06:00:
            [{"begin": "Mon 01:00", "end": "Mon 06:00"}, {"begin": "Tue 01:00", "end": "Tue 06:00"}, ...]

        Returns:
            str: response content

        Raises:
            ValueError: if Wi-Fi would be off all week. Use wifi.set_enabled(False) to turn it off.

        """
        schedule = _blocked_periods(off_periods)
        if schedule == [{"begin": 0, "end": WEEK, "state": "Disable"}]:
            raise ValueError(
                "The schedule would turn Wi-Fi off all week. To turn Wi-Fi off, use wifi.set_enabled(False) (ibox wifi set-enabled false)."
            )
        return self._save_wifi_schedule(schedule, enable and bool(schedule))

    @disruptive
    def enable_wifi_schedule(self, enable: bool = True) -> str:
        """Turn the Wi-Fi schedule on or off, keeping its periods, like its switch in the web UI's power settings.

        While the schedule is on, wireless devices lose their connection during its off periods.

        Args:
            enable (bool): True to turn the schedule on, False to turn it off. Default is True.

        Returns:
            str: response content

        Raises:
            ValueError: if there's no Wi-Fi schedule. Create one with set_wifi_schedule().

        """
        answer = json.loads(self.wifi_schedule())
        info = (answer.get("data") or {}).get("scheduleInfo") if answer.get("status") else None
        if not info:
            raise ValueError("There's no Wi-Fi schedule. Create one with set_wifi_schedule().")
        schedule = info.get("schedule") or []
        if enable and not schedule:
            raise ValueError("The Wi-Fi schedule has no off periods, so it can't be turned on. Set some with set_wifi_schedule().")
        return self._save_wifi_schedule(schedule, enable)

    @write
    def remove_wifi_schedule(self) -> str:
        """Delete the Wi-Fi schedule. Wi-Fi then stays on.

        Returns:
            str: response content

        """
        # As for device schedules: the router may ignore the removal of a schedule that's on.
        if json.loads(self.wifi_schedule()).get("status"):
            self.post("/sysbus/Scheduler:enableSchedule", {"parameters": {**_WIFI, "enable": False}})
        data = {"parameters": _WIFI}
        return self.post("/sysbus/Scheduler:removeSchedules", data)

    def _save_wifi_schedule(self, schedule: list[dict], enable: bool) -> str:
        """Save the Wi-Fi schedule, as the web UI does for every change, including turning it on or off."""
        info = {"ID": _WIFI["ID"], "enable": enable, "base": "Weekly", "def": "Enable", "override": "", "schedule": schedule}
        return self.post("/sysbus/Scheduler:addSchedule", {"parameters": {"type": _WIFI["type"], "info": info}})
