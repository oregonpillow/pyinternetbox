from internetbox_client.utils.APIClient import APIClient


class LAN(APIClient):
    """LAN network settings, interfaces, and connected devices."""

    def mac(self) -> str:
        """Get MAC address"""
        data = {"parameters": {"name": "LLAddress", "flag": "", "traverse": "down"}}
        return self.post("/sysbus/NeMo/Intf/lan:getFirstParameter", data)

    def ipv4_network(self) -> str:
        """Get IPv4 network settings"""
        data = {"parameters": {}}
        return self.post("/sysbus/NetMaster/LAN/default/Bridge/lan:getIPv4", data)

    def ipv6_configuration(self) -> str:
        """Get IPv6 network settings"""
        data = {"parameters": {"Name": "lan"}}
        return self.post("/sysbus/NetMaster/LAN/default/Bridge/lan:getIPv6Configuration", data)

    def mibs(self) -> str:
        """Get LAN MIBs"""
        data = {"parameters": {}}
        return self.post("/sysbus/NeMo/Intf/lan:getMIBs", data)

    def parameters(self, flag: str = "bridge enabled && !wan") -> str:
        """Get LAN parameters

        Args:
            flag (str): filter expression for parameters. Default is "bridge enabled && !wan"
            to get parameters of the LAN bridge interface only.
        """
        data = {"parameters": {"flag": flag, "traverse": "all", "name": "STPEnable"}}
        return self.post("/sysbus/NeMo/Intf/lan:getParameters", data)

    def ethernet_port(self, port: int = 4) -> str:
        """Get Ethernet port information

        Args:
            port (int): Ethernet port number (0-4)

        Returns:
            str: response content

        """
        data = {"service": f"Devices.Device.ETH{port}", "method": "get", "parameters": {"flags": "full_links"}}
        return self.post("/ws", data)

    def mac_lookup(self, mac: str) -> str:
        """Lookup whether a MAC address is known in the LAN.

        Returns Wi-Fi or Ethernet port information if found.

        Args:
            mac (str): MAC address to look up

        Returns:
            str: response content

        """
        data = {"service": f"Devices.Device.{mac.upper()}.UDevice", "method": "get", "parameters": {}}
        return self.post("/ws", data)
