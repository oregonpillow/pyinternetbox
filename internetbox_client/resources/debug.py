from internetbox_client.utils.APIClient import APIClient


class Debug(APIClient):
    """Access debug and diagnostic information."""

    def status(self) -> str:
        """Get debug status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Debug/DebugFile:get", data)

    def wifi_driver_stats(self) -> str:
        """Get Wi-Fi driver statistics"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Debug:getWifiDriverStats", data)
