from internetbox_client.utils.APIClient import APIClient


class NMC(APIClient):
    """Query the Network Management Controller for WAN, LAN, and system status."""

    def status(self) -> str:
        """Get NMC status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:get", data, auth_required=False)

    def ip_conflicts(self) -> str:
        """Get IP conflicts"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:getIPConflicts", data, auth_required=False)

    def wan_status(self) -> str:
        """Get WAN status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:getWANStatus", data, auth_required=False)

    def orientation(self) -> str:
        """Get device orientation"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Orientation:get", data, auth_required=False)

    def lan_ip(self) -> str:
        """Get LAN IP address"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:getLANIP", data)

    def phonebook_backup(self) -> str:
        """Get phonebook backup status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/PhonebookBackup:get", data)

    def static_routes(self) -> str:
        """Get LAN static routes"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/LAN:getStaticRoutes", data)

    def network_config(self) -> str:
        """Get network configuration"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/NetworkConfig:get", data)

    def bdd(self) -> str:
        """Get NMC BDD (Broadband Device Database) information"""
        data = {"service": "NMC.BDD", "method": "get", "parameters": {}}
        return self.post("/ws", data)
