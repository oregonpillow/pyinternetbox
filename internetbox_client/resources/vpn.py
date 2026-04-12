from internetbox_client.utils.APIClient import APIClient


class VPN(APIClient):
    """VPN server status and configuration."""

    def status(self) -> str:
        """Get VPN status"""
        data = {"parameters": {}}
        return self.post("/sysbus/VPN:get", data)

    def servers_config(self) -> str:
        """Get VPN servers configuration"""
        data = {"parameters": {}}
        return self.post("/sysbus/VPN:getServersConfig", data)
