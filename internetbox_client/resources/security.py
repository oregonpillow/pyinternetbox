from internetbox_client.utils.APIClient import APIClient


class Security(APIClient):
    """Security gateway and package status."""

    def gateway_status(self) -> str:
        """Get security gateway status"""
        data = {"parameters": {}}
        return self.post("/sysbus/SecurityGateway:get", data)

    def user_exposure_status(self) -> str:
        """Get user exposure status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Security:get", data)

    def package_management_status(self) -> str:
        """Get security package management status"""
        data = {"parameters": {}}
        return self.post("/sysbus/PackageManager/Package/security:_get", data)
