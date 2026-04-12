from typing import Literal

from internetbox_client.utils.APIClient import APIClient


class Wifi(APIClient):
    """Query and configure Wi-Fi radios, SSIDs, guest networks, and band steering."""

    def status(self) -> str:
        """Get Wi-Fi status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Wifi:get", data, auth_required=False)

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

    def radio(self, id: int) -> str:
        """Get Wi-Fi radio settings

        Args:
            id (int): radio ID. E.g 0 for 2.4GHz, 1 for 5GHz, 2 for 6GHz.

        Returns:
            str: response content


        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wifi{id}_bcm:get", data)

    def spectrum_info(self, id: int) -> str:
        """Get spectrum information for a radio

        Args:
            id (int): radio ID. E.g 0 for 2.4GHz, 1 for 5GHz.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wifi{id}_bcm:getSpectrumInfo", data)

    def scan(self, id: int) -> str:
        """Scan for nearby networks for a radio

        Args:
            id (int): radio ID. E.g 0 for 2.4GHz, 1 for 5GHz.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wifi{id}_bcm:scan", data)

    def power(self, id: int, power: Literal[0, 25, 50, 75, 100]) -> str:
        """Set Wi-Fi power level
            For Duel band/tri band models, setting 1 radio may set the others to the same level as well.
            Use the radio method to check the supported power levels for each radio.

        Args:
            id (int): radio ID. E.g 0 for 2.4GHz, 1 for 5GHz, 2 for 6GHz.
            power (int): Wi-Fi power level (0-100)

        Returns:
            str: response content

        """
        data = {"parameters": {"mibs": {"wlanradio": {f"wifi{id}_bcm": {"PersistentEnable": True, "TransmitPower": power}}}}}
        return self.post("/sysbus/NeMo/Intf/lan:setWLANConfig", data)

    def latest_power(self, id: int) -> str:
        """Get latest Wi-Fi power for a radio

        Args:
            id (int): radio ID. E.g 0 for 2.4GHz, 1 for 5GHz.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wifi{id}_bcm:getLatestPower", data)

    def per_antenna_rssi(self, id: int) -> str:
        """Get per-antenna RSSI for a radio

        Args:
            id (int): radio ID. E.g 0 for 2.4GHz, 1 for 5GHz.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NeMo/Intf/wifi{id}_bcm:getPerAntennaRssi", data)

    def station_stats(self, id: int) -> str:
        """Get station statistics for a radio

        Args:
            id (int): radio ID. E.g 0 for 2.4GHz, 1 for 5GHz.

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
