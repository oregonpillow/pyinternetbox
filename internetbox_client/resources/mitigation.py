from internetbox_client.utils.APIClient import APIClient


class Mitigation(APIClient):
    """Thermal mitigation status."""

    def status(self) -> str:
        """Get mitigation status"""
        data = {"parameters": {}}
        return self.post("/sysbus/Temperature/X_SWISSCOM-COM_Mitigation:get", data, auth_required=False)
