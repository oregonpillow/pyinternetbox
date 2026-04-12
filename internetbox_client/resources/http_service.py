from internetbox_client.utils.APIClient import APIClient


class HTTPService(APIClient):
    """HTTP management service."""

    def current_user(self) -> str:
        """Get current HTTP service user"""
        data = {"parameters": {}}
        return self.post("/sysbus/HTTPService:getCurrentUser", data)
