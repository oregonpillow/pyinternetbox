from internetbox_client.utils.APIClient import APIClient


class Wireguard(APIClient):
    """WireGuard VPN tunnel status."""

    def app_status(self) -> str:
        """Get Wireguard application status"""
        data = {"parameters": {}}
        return self.post("/sysbus/WireGuard:_get", data)

    def server_status(self) -> str:
        """Get Wireguard server status"""
        data = {"parameters": {}}
        return self.post("/sysbus/WireGuard/Server:_get", data)

    def clients(self) -> str:
        """Get configured Wireguard clients"""
        data = {"parameters": {}}
        return self.post("/sysbus/WireGuard/Server/default/Client:_get", data)

    def client_status(self, alias: str) -> str:
        """Get specific Wireguard client stats
        Such as connection status, data transferred, etc.
        Args:
            alias (str): client alias name
        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/WireGuard/Server/default/Client/{alias}/InfoStats:_get", data)
