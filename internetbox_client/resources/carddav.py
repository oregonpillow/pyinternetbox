from internetbox_client.utils.APIClient import APIClient


class CardDav(APIClient):
    """CardDAV contact synchronisation settings."""

    def status(self) -> str:
        """Get CardDav status"""
        data = {"parameters": {}}
        return self.post("/sysbus/CardDav:get", data)
