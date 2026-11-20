import contextlib
import itertools
import json
import re
from typing import Literal

import requests

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import disruptive, write

# The web UI offers these 5 GHz channels, though the radio supports more. 52 to 112 are DFS channels.
_5GHZ_CHANNELS = (36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112)
# The web UI's channel widths. 5 GHz "Auto" is 80 or 160 MHz.
_BANDWIDTHS = {"2.4GHz": ("20MHz", "40MHz"), "5GHz": ("80MHz", "Auto")}


def _check_ssid(ssid: str, network: str) -> None:
    """Raise unless the web UI would accept ssid as a network name."""
    if not re.fullmatch(r"[ -~]{2,32}", ssid):
        raise ValueError(f"The {network} name must be 2 to 32 letters, digits, spaces or symbols (no accents or emoji), got {ssid!r}")
    if ssid != ssid.strip(" "):
        raise ValueError(f"The {network} name must not start or end with a space, got {ssid!r}")


def _check_password(password: str, network: str) -> None:
    """Raise unless the web UI would accept password. The message never contains it."""
    if not re.fullmatch(r"[ -~]{12,63}", password):
        raise ValueError(f"The {network} password must be 12 to 63 letters, digits, spaces or symbols (no accents or emoji).")
    if not all(re.search(kind, password) for kind in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^a-zA-Z0-9]")):
        raise ValueError(
            f"The {network} password must contain a lower-case letter, an upper-case letter, a digit and a symbol such as - or !."
        )


def _password(access_point: dict) -> str | None:
    return (access_point.get("Security") or {}).get("KeyPassPhrase")


def _radio_name(mibs: dict, access_point: str) -> str | None:
    """The radio an access point runs on, e.g. "wifi0_bcm". RadioReference is empty, so it comes from "base"."""
    return next(iter(((mibs.get("base") or {}).get(access_point) or {}).get("LLIntf") or {}), None)


def _network_summary(network: str, access_point: dict) -> dict:
    security = access_point.get("Security") or {}
    return {
        "network": network,
        "band": access_point.get("Band"),
        "ssid": access_point.get("SSID"),
        "password": security.get("KeyPassPhrase"),
        "encryption": security.get("ModeEnabled"),
        "up": access_point.get("VAPStatus") == "Up",
        "visible": access_point.get("SSIDAdvertisementEnabled"),
        "channel": access_point.get("Channel"),
        "connected_devices": access_point.get("ActiveAssociatedDeviceNumberOfEntries"),
    }


def _check_changes(changed: dict, others: dict, ssid: str | None, password: str | None, network: str, other_network: str) -> None:
    """Raise if the web UI would refuse the new name or password for the changed access points. A value they all have
    already isn't checked, so current settings can always be written back."""
    if ssid is not None and any(access_point.get("SSID") != ssid for access_point in changed.values()):
        _check_ssid(ssid, network)
        if ssid in {access_point.get("SSID") for access_point in others.values()}:
            raise ValueError(f"The {network} name must be different from the {other_network} name.")
    if password is None:
        return
    if any((access_point.get("Security") or {}).get("ModeEnabled") == "None" for access_point in changed.values()):
        raise ValueError(f"The {network} has no encryption, so it has no password. Choose an encryption in the web UI first.")
    if any(_password(access_point) != password for access_point in changed.values()):
        _check_password(password, network)
        if password in {_password(access_point) for access_point in others.values()}:
            raise ValueError(f"The {network} password must be different from the {other_network} password.")


class Wifi(APIClient):
    """Query and configure Wi-Fi radios, SSIDs, guest networks, and band steering."""

    def status(self) -> str:
        """Get Wi-Fi status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Wifi:get", data, auth_required=False)

    def summary(self) -> str:
        """A short overview of the Wi-Fi and guest Wi-Fi networks: name, password, channel and devices of each band.

        Each band's entry also has its encryption and whether it's up and visible. The overview also says whether Wi-Fi
        and WPS are on and whether the bands share their settings. The access points' full settings take about 60 KB in
        lan.mibs() and in guest_mibs().

        Returns:
            str: a JSON object, e.g. {"enabled": true, "bands_share_settings": false, "wps": true, "networks": [{"network":
                "Wi-Fi", "band": "5GHz", "ssid": "MyHome", ...}]}

        """
        settings = self._settings()
        main, guest = self._access_points()
        networks = [_network_summary("Wi-Fi", access_point) for access_point in main.values()]
        networks += [_network_summary("guest Wi-Fi", access_point) for access_point in guest.values()]
        summary = {
            "enabled": settings.get("Enable"),
            "bands_share_settings": settings.get("ConfigurationMode"),
            "wps": settings.get("WPSEnable"),
            "networks": networks,
        }
        return json.dumps(summary, ensure_ascii=False)

    @disruptive
    def set_enabled(self, enable: bool) -> str:
        """Turn all Wi-Fi networks on or off, like the Wi-Fi switch in the web UI.

        Turning Wi-Fi off disconnects every wireless device, including this computer if it uses Wi-Fi. Turn it back on
        from a wired connection or with the button on the router. The guest network stays off when Wi-Fi comes back on
        (the web UI's switch doesn't turn it on again either): use set_guest_enabled() for that.

        Args:
            enable (bool): True to turn Wi-Fi on, False to turn it off.

        Returns:
            str: response content

        """
        current = self._settings()
        # Internet Box 5 models: the web UI sends TempEnable instead of Status (untested).
        parameters = {"Enable": enable, "Status": enable}
        if "ConfigurationMode" in current:
            parameters["ConfigurationMode"] = current["ConfigurationMode"]
        return self.post("/sysbus/NMC/Wifi:set", {"parameters": parameters})

    @disruptive
    def set_network(
        self,
        ssid: str | None = None,
        password: str | None = None,
        visible: bool | None = None,
        band: Literal["2.4GHz", "5GHz"] | None = None,
    ) -> str:
        """Change the Wi-Fi network's name, password or visibility, like the Wi-Fi settings in the web UI.

        Settings you leave out stay as they are, and so does the encryption. Wireless devices lose their connection
        while the router applies the change, and must then reconnect with the new name and password. The guest network
        has its own settings: see set_guest_network().

        Args:
            ssid (str | None): network name, 2 to 32 letters, digits, spaces or symbols, e.g. "MyHome".
            password (str | None): 12 to 63 characters, with a lower-case letter, an upper-case letter, a digit and a
                symbol such as - or !.
            visible (bool | None): False hides the network name: devices then have to enter it to join.
            band (str | None): "2.4GHz" or "5GHz" to change one band only. Only when the bands have separate
                settings (see ConfigurationMode in status()). Default: all bands.

        Returns:
            str: response content

        Raises:
            ValueError: if a value would be refused by the web UI, or the router doesn't accept the change. Bands
                changed before the router refused keep their new settings.

        """
        if ssid is None and password is None and visible is None:
            raise ValueError("Nothing to change: give ssid, password or visible.")
        main, guest = self._access_points()
        changed = main
        if band is not None:
            if band not in ("2.4GHz", "5GHz"):
                raise ValueError(f'band must be "2.4GHz" or "5GHz", got {band!r}')
            if self._settings().get("ConfigurationMode"):
                raise ValueError("The Wi-Fi bands share their settings (combined mode), so a single band can't be changed.")
            changed = {name: access_point for name, access_point in main.items() if access_point["Band"] == band}
            if not changed:
                raise ValueError(f"This router has no {band} Wi-Fi network.")
        _check_changes(changed, guest, ssid, password, "Wi-Fi", "guest Wi-Fi")
        new_settings = {}
        for name, access_point in changed.items():
            security = access_point.get("Security") or {}
            new_settings[name] = {
                "SSID": access_point.get("SSID") if ssid is None else ssid,
                "SSIDAdvertisementEnabled": access_point.get("SSIDAdvertisementEnabled") if visible is None else visible,
                "Security": {
                    "KeyPassPhrase": security.get("KeyPassPhrase") if password is None else password,
                    "WEPKey": security.get("WEPKey"),
                    "ModeEnabled": security.get("ModeEnabled"),
                },
            }
        if ssid is not None or password is not None:
            # Devices treat bands with the same name as one network, so they need the same password.
            after = {
                name: (new_settings[name]["SSID"], new_settings[name]["Security"]["KeyPassPhrase"])
                if name in new_settings
                else (access_point.get("SSID"), _password(access_point))
                for name, access_point in main.items()
            }
            for first, second in itertools.combinations(after, 2):
                if after[first][0] == after[second][0] and after[first][1] != after[second][1]:
                    raise ValueError(
                        f"The {main[first]['Band']} and {main[second]['Band']} networks would have the same name but different "
                        "passwords. Give them the same password, or different names."
                    )
        response = ""
        for name, settings in new_settings.items():
            response = self._set_wlan_config(name, settings)
            if main[name]["Band"] == "5GHz":
                self._copy_to_6ghz(settings)
        return response

    @disruptive
    def set_guest_network(self, ssid: str | None = None, password: str | None = None) -> str:
        """Change the guest Wi-Fi network's name or password, like the guest Wi-Fi settings in the web UI.

        Settings you leave out stay as they are, and so do the encryption and whether the guest network is on (see
        set_guest_enabled()). Devices on the guest network must reconnect with the new name and password.

        Args:
            ssid (str | None): network name, 2 to 32 letters, digits, spaces or symbols, different from the Wi-Fi's.
            password (str | None): 12 to 63 characters, with a lower-case letter, an upper-case letter, a digit and a
                symbol such as - or !, different from the Wi-Fi's.

        Returns:
            str: response content

        Raises:
            ValueError: if a value would be refused by the web UI, or the router doesn't accept the change.

        """
        if ssid is None and password is None:
            raise ValueError("Nothing to change: give ssid or password.")
        main, guest = self._access_points()
        if not guest:
            raise ValueError("This router has no guest Wi-Fi network.")
        _check_changes(guest, main, ssid, password, "guest Wi-Fi", "Wi-Fi")
        response = ""
        for name, access_point in guest.items():
            security = access_point.get("Security") or {}
            settings = {
                "SSID": access_point.get("SSID") if ssid is None else ssid,
                "Security": {
                    "KeyPassPhrase": security.get("KeyPassPhrase") if password is None else password,
                    "WEPKey": security.get("WEPKey"),
                    "ModeEnabled": security.get("ModeEnabled"),
                },
            }
            response = self._set_wlan_config(name, settings)
        return response

    @write
    def set_wps_enabled(self, enable: bool) -> str:
        """Turn WPS on or off, like the WPS switch in the web UI's Wi-Fi settings.

        With WPS on, the WPS button on the router or start_wps_pairing() lets a device join without the password.

        Args:
            enable (bool): True to turn WPS on, False to turn it off.

        Returns:
            str: response content

        """
        data = {"parameters": {"enable": enable}}
        return self.post("/sysbus/NMC/Wifi:setWPSEnable", data)

    @write
    def start_wps_pairing(self) -> str:
        """Start WPS pairing, like pressing the WPS button on the router.

        For the next 2 minutes, a device that starts WPS (push button) joins the Wi-Fi without the password. The
        response doesn't say whether one did: the router reports that as an event. stop_wps_pairing() ends it early.

        Returns:
            str: response content

        Raises:
            ValueError: if WPS is off. Turn it on with set_wps_enabled(True).

        """
        if not self._settings().get("WPSEnable"):
            raise ValueError("WPS is turned off. Turn it on first with set_wps_enabled(True) (ibox wifi set-wps-enabled true).")
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Wifi:startPairing", data)

    @write
    def stop_wps_pairing(self) -> str:
        """Stop WPS pairing started with the WPS button or start_wps_pairing()."""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Wifi:stopPairing", data)

    @disruptive
    def set_channel(self, band: Literal["2.4GHz", "5GHz"], channel: int | Literal["auto"], bandwidth: str | None = None) -> str:
        """Set a band's Wi-Fi channel, or let the router choose it, like the channel settings in the web UI.

        Devices on the band lose their connection for a moment while the radio changes channel. On 5 GHz channels 52 to
        112 (DFS), the router first listens for radar for about a minute, and moves to another channel by itself when
        it hears one. The guest network uses the same radios, so it changes too.

        Args:
            band (str): "2.4GHz" or "5GHz".
            channel (int | str): a channel, or "auto" to let the router choose. 2.4 GHz: one of the radio's
                PossibleChannels in lan.mibs(), usually 1 to 13. 5 GHz: 36 to 64 or 100 to 112, like the web UI.
            bandwidth (str | None): channel width. 2.4 GHz: "20MHz" or "40MHz". 5 GHz: "80MHz", or "Auto" for 80 or
                160 MHz. Default: keep the current width.

        Returns:
            str: response content

        Raises:
            ValueError: if the router has no such band, the channel or width isn't one the web UI offers, or the
                router doesn't accept the change.

        """
        if band in _BANDWIDTHS and bandwidth is not None and bandwidth not in _BANDWIDTHS[band]:
            raise ValueError(f"The {band} bandwidth must be one of {list(_BANDWIDTHS[band])}, got {bandwidth!r}")
        access_point, radio_name, radio = self._radio(band)
        if channel == "auto":
            settings: dict = {"AutoChannelEnable": True}
        else:
            if band == "5GHz":
                allowed = _5GHZ_CHANNELS
            else:
                possible = str(radio.get("PossibleChannels") or "").split(",")
                allowed = tuple(int(c) for c in possible if c.strip().isdigit()) or tuple(range(1, 14))
            if isinstance(channel, bool) or channel not in allowed:
                raise ValueError(f'The {band} channel must be "auto" or one of {", ".join(map(str, allowed))}, got {channel!r}')
            settings = {"Channel": channel, "AutoChannelEnable": False}
        if bandwidth is not None:
            settings["OperatingChannelBandwidth"] = bandwidth
        return self._set_wlan_mibs(access_point, {"wlanradio": {radio_name: settings}})

    @disruptive
    def search_channel(self, band: Literal["2.4GHz", "5GHz"]) -> str:
        """Let the router choose a band's channel again now, like "Search again" in the web UI's Wi-Fi settings.

        Only when the band's channel is set to "auto" (see set_channel()). Finding a channel may take a minute; if the
        router moves to another one, devices on the band lose their connection for a moment.

        Args:
            band (str): "2.4GHz" or "5GHz".

        Returns:
            str: response content

        Raises:
            ValueError: if the router has no such band, or its channel is set by hand.

        """
        _, radio_name, radio = self._radio(band)
        if not radio.get("AutoChannelEnable"):
            raise ValueError(
                f"The {band} channel is set by hand (channel {radio.get('Channel')}). Let the router choose it with "
                f'set_channel("{band}", "auto") (ibox wifi set-channel {band} auto).'
            )
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/{radio_name}:startAutoChannelSelection", data)

    def _settings(self) -> dict:
        """The settings in status(), e.g. ConfigurationMode and WPSEnable."""
        response = json.loads(self.status())
        return response.get("status") or response.get("data") or {}

    def _mibs(self, interface: str) -> dict:
        """The access points, radios and base settings below interface, e.g. "lan"."""
        data = {"parameters": {"mibs": "wlanvap || wlanradio || base", "flag": "", "traverse": "down"}}
        return json.loads(self.post(f"/sysbus/NeMo/Intf/{interface}:getMIBs", data))["status"]

    def _access_points(self) -> tuple[dict[str, dict], dict[str, dict]]:
        """The Wi-Fi and the guest Wi-Fi access points by name, e.g. "wl0": their settings, with their radio's band and
        channel added as "Band" and "Channel"."""
        found = []
        for interface in ("lan", "guest"):
            mibs = self._mibs(interface)
            radios = mibs.get("wlanradio") or {}
            access_points = {}
            for name, settings in (mibs.get("wlanvap") or {}).items():
                radio = radios.get(_radio_name(mibs, name)) or {}
                access_points[name] = {**settings, "Band": radio.get("OperatingFrequencyBand"), "Channel": radio.get("Channel")}
            found.append(access_points)
        main, guest = found
        # The guest interface also lists the Wi-Fi's access points.
        return main, {name: settings for name, settings in guest.items() if name not in main}

    def _radio(self, band: str) -> tuple[str, str, dict]:
        """The Wi-Fi access point on band, e.g. "wl0", its radio, e.g. "wifi0_bcm", and the radio's settings."""
        if band not in _BANDWIDTHS:
            raise ValueError(f'band must be "2.4GHz" or "5GHz", got {band!r}')
        mibs = self._mibs("lan")
        radios = mibs.get("wlanradio") or {}
        for access_point in mibs.get("wlanvap") or {}:
            radio = _radio_name(mibs, access_point)
            if radio in radios and radios[radio].get("OperatingFrequencyBand") == band:
                return access_point, radio, radios[radio]
        raise ValueError(f"This router has no {band} Wi-Fi network.")

    def _set_wlan_config(self, access_point: str, settings: dict) -> str:
        """Save an access point's settings. Raises unless the router answers with a null status, like the web UI."""
        return self._set_wlan_mibs(access_point, {"wlanvap": {access_point: settings}})

    def _set_wlan_mibs(self, access_point: str, mibs: dict) -> str:
        """Save access point or radio settings through an access point, e.g. {"wlanradio": {"wifi0_bcm": {...}}}.
        Raises unless the router answers with a null status, like the web UI."""
        response = self.post(f"/sysbus/NeMo/Intf/{access_point}:setWLANConfig", {"parameters": {"mibs": mibs}})
        answer = json.loads(response)
        if answer.get("status") is not None or answer.get("errors"):
            reasons = "; ".join(str(error.get("description")) for error in answer.get("errors") or [])
            raise ValueError(f"The router didn't accept the settings for {access_point}" + (f": {reasons}" if reasons else "."))
        return response

    def _copy_to_6ghz(self, settings: dict) -> None:
        """Give the 6 GHz network the 5 GHz name, password and visibility, as the web UI does. Wi-Fi extenders use it."""
        entries = json.loads(self.ssid()).get("status") or {}
        name = next((name for name, entry in entries.items() if str(entry.get("Band")) == "6" and "guest" not in name.lower()), None)
        if name is None:
            return
        enable = entries[name].get("PersistentEnable")
        data = {
            "parameters": {
                "Enable": enable,
                "PersistentEnable": enable,
                "SSID": settings["SSID"],
                "SSIDAdvertisementEnabled": settings["SSIDAdvertisementEnabled"],
                "PassPhrase": settings["Security"]["KeyPassPhrase"],
            }
        }
        # The web UI ignores errors here too.
        with contextlib.suppress(requests.HTTPError):
            self.post(f"/sysbus/SSW/DataElements/Network/SSID/{name}:set", data)

    def steering(self) -> str:
        """Get Wi-Fi steering status"""
        data = {"parameters": {}}
        return self.post("/sysbus/SSW/Steering:get", data)

    def ssid(self) -> str:
        """Get Wi-Fi SSID"""
        data = {"parameters": {}}
        return self.post("/sysbus/SSW/DataElements/Network/SSID:get", data)

    def guest(self) -> str:
        """Get Wi-Fi guest network settings"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Guest:get", data)

    @disruptive
    def set_guest_enabled(self, enable: bool, hours: int = 0) -> str:
        """Turn the guest Wi-Fi on or off.

        Args:
            enable (bool): True to turn the guest network on, False to turn it off.
            hours (int): when turning it on, turn it off again automatically after this many hours.
                Default is 0: stay on until turned off.

        Returns:
            str: response content

        """
        result = self.post("/sysbus/NMC/Guest:set", {"parameters": {"Enable": enable}})
        if enable:
            self.post("/sysbus/NMC/WlanTimer:setActivationTimer", {"parameters": {"InterfaceName": "guest", "Timeout": hours}})
        return result

    def radio(self, id: int) -> str:
        """Get Wi-Fi radio settings

        Args:
            id (int): radio number, as in the radio's name "wifi{id}_bcm". Which band a radio serves differs between
                routers: OperatingFrequencyBand in the response shows it.

        Returns:
            str: response content


        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wifi{id}_bcm:get", data)

    def spectrum_info(self, id: int) -> str:
        """Get spectrum information for a radio

        Args:
            id (int): radio number, as in the radio's name "wifi{id}_bcm". Which band a radio serves differs between
                routers: OperatingFrequencyBand in radio(id) shows it.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wifi{id}_bcm:getSpectrumInfo", data)

    @write
    def scan(self, id: int) -> str:
        """Scan for nearby networks for a radio

        Args:
            id (int): radio number, as in the radio's name "wifi{id}_bcm". Which band a radio serves differs between
                routers: OperatingFrequencyBand in radio(id) shows it.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wifi{id}_bcm:scan", data)

    @write
    def power(self, id: int, power: Literal[0, 25, 50, 75, 100]) -> str:
        """Set Wi-Fi power level
            For Duel band/tri band models, setting 1 radio may set the others to the same level as well.
            Use the radio method to check the supported power levels for each radio.

        Args:
            id (int): radio number, as in the radio's name "wifi{id}_bcm". Which band a radio serves differs between
                routers: OperatingFrequencyBand in radio(id) shows it.
            power (int): Wi-Fi power level (0-100)

        Returns:
            str: response content

        """
        data = {"parameters": {"mibs": {"wlanradio": {f"wifi{id}_bcm": {"PersistentEnable": True, "TransmitPower": power}}}}}
        return self.post("/sysbus/NeMo/Intf/lan:setWLANConfig", data)

    def latest_power(self, id: int) -> str:
        """Get latest Wi-Fi power for a radio

        Args:
            id (int): radio number, as in the radio's name "wifi{id}_bcm". Which band a radio serves differs between
                routers: OperatingFrequencyBand in radio(id) shows it.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wifi{id}_bcm:getLatestPower", data)

    def per_antenna_rssi(self, id: int) -> str:
        """Get per-antenna RSSI for a radio

        Args:
            id (int): radio number, as in the radio's name "wifi{id}_bcm". Which band a radio serves differs between
                routers: OperatingFrequencyBand in radio(id) shows it.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wifi{id}_bcm:getPerAntennaRssi", data)

    def station_stats(self, id: int) -> str:
        """Get station statistics for a radio

        Args:
            id (int): access point number, as in its name "wl{id}". Which band an access point serves differs between
                routers: in lan.mibs(), "base" lists its radio (LLIntf) and "wlanradio" the radio's OperatingFrequencyBand.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wl{id}:getStationStats", data)

    def guest_mibs(self) -> str:
        """Get guest network MIBs"""
        data = {"parameters": {}}
        return self.post("/sysbus/NeMo/Intf/guest:getMIBs", data)

    def steering_master_config(self) -> str:
        """Get Wi-Fi steering master configuration"""
        data = {"parameters": {}}
        return self.post("/sysbus/SSW/Steering/MasterConfig:get", data)

    def steering_operating_standards(self) -> str:
        """Get Wi-Fi steering operating standards"""
        data = {"parameters": {}}
        return self.post("/sysbus/SSW/Steering/MasterConfig/OperatingStandards:get", data)

    def steering_log(self) -> str:
        """Get Wi-Fi steering log attempts"""
        data = {"parameters": {}}
        return self.post("/sysbus/SSW/Steering/SteerLog/Attempt:get", data)

    def steering_radio(self) -> str:
        """Get Wi-Fi steering radio configuration"""
        data = {"parameters": {}}
        return self.post("/sysbus/SSW/Steering/Radio:get", data)

    def steering_exception_list(self) -> str:
        """Get Wi-Fi steering exception list"""
        data = {"parameters": {}}
        return self.post("/sysbus/SSW/Steering/ExceptionList/Station:get", data)

    def activation_timer(self) -> str:
        """Get Wi-Fi activation timer"""
        data = {"parameters": {"InterfaceName": "guest"}}
        return self.post("/sysbus/NMC/WlanTimer:getActivationTimer", data)
