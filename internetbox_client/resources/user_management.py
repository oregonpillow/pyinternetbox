from internetbox_client.utils.APIClient import APIClient


class UserManagement(APIClient):
    """User management logs."""

    def user_log(self) -> str:
        """Get user management log"""
        data = {"parameters": {}}
        return self.post("/sysbus/UserManagement:getUserLog", data)
