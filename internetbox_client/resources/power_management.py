from internetbox_client.utils.APIClient import APIClient


class PowerManagement(APIClient):
    """Power management profiles and settings."""

    def profiles(self) -> str:
        """Get power management profiles"""
        data = {"parameters": {}}
        return self.post("/sysbus/PowerManagement:getProfiles", data)
