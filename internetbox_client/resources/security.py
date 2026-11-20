from internetbox_client.utils.APIClient import APIClient


class Security(APIClient):
    """Home Security and security package status."""

    def home_security_status(self) -> str:
        """Get the Home Security status, as on the web UI's Diagnostics > Security page.

        Home Security is on when MappingStatus is "Active" and PackageStatus is "Running".
        """
        data = {"parameters": {}}
        return self.post("/sysbus/RouterSecurityAgent:get", data)

    def user_exposure_status(self) -> str:
        """Get user exposure status. Not on the Internet Box 4 (HTTP 404)."""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Security:get", data)

    def package_management_status(self) -> str:
        """Get security package management status"""
        data = {"parameters": {}}
        return self.post("/sysbus/PackageManager/Package/security:_get", data)
