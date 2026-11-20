from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import write


class PowerManagement(APIClient):
    """Power management profiles and settings."""

    def profiles(self) -> str:
        """Get power management profiles"""
        data = {"parameters": {}}
        return self.post("/sysbus/PowerManagement:getProfiles", data)

    @write
    def set_wifi_6ghz_power_saving(self, enable: bool) -> str:
        """Turn 6 GHz power saving for WLAN-Box 3 extenders on or off, like the setting in the web UI's power settings.

        With it on, the 6 GHz Wi-Fi of a WLAN-Box 3 only runs while a 6 GHz device is in your network. When the first
        one connects, Wi-Fi is interrupted briefly. profiles() shows the setting as "Activate" of ECO_6G_SCS. The web
        UI's other power setting, the Wi-Fi schedule, is scheduler.set_wifi_schedule().

        Args:
            enable (bool): True to turn power saving on, False to turn it off.

        Returns:
            str: response content

        """
        data = {"parameters": {"profiles": [{"profile": "ECO_6G_SCS", "activate": enable}]}}
        return self.post("/sysbus/PowerManagement:setTriggeredProfiles", data)
