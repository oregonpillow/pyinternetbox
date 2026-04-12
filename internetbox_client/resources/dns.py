from internetbox_client.utils.APIClient import APIClient


class DNS(APIClient):
    """DNS resolver status, settings, and cache."""

    def status(self) -> str:
        """Get DNS status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/DNS:get", data, auth_required=False)

    def mode(self) -> str:
        """Get DNS mode"""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS:get", data)

    def settings(self) -> str:
        """Get DNS settings"""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS/Server/Route:get", data)

    def user(self) -> str:
        """Get DNS user settings"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/DHCPv4/DNSServers/User:get", data)

    def user_ipv6(self) -> str:
        """Get DHCPv6 DNS user settings"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/DHCPv6/DNSServers/User:get", data)

    def cache(self) -> str:
        """Get DNS server cache"""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS/Server/Cache:get", data)
