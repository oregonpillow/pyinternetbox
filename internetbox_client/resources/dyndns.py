from internetbox_client.utils.APIClient import APIClient


class DynDNS(APIClient):
    """Dynamic DNS configuration and registered hosts."""

    def global_enable(self) -> str:
        """Get DynDNS global enable status"""
        data = {"parameters": {}}
        return self.post("/sysbus/DynDNS:getGlobalEnable", data)

    def hosts(self) -> str:
        """Get DynDNS hosts"""
        data = {"parameters": {}}
        return self.post("/sysbus/DynDNS:getHosts", data)

    def services(self) -> str:
        """Get DynDNS services"""
        data = {"parameters": {}}
        return self.post("/sysbus/DynDNS:getServices", data)
