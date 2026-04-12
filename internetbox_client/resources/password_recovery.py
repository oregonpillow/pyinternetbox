from internetbox_client.utils.APIClient import APIClient


class PasswordRecovery(APIClient):
    """Password recovery status."""

    def status(self) -> str:
        """Get password recovery status"""
        data = {"parameters": {}}
        return self.post("/sysbus/PasswordRecovery:getStatus", data, auth_required=False)
