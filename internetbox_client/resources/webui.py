from internetbox_client.utils.APIClient import APIClient


class WebUI(APIClient):
    """WebUI upgrade service and release notes."""

    def status(self) -> str:
        """Get WebUI upgrade service status"""
        data = {"parameters": {}}
        return self.post("/sysbus/WebuiupgradeService:get", data)

    def release_notes(self) -> str:
        """Get WebUI release notes"""
        data = {"parameters": {}}
        return self.post("/sysbus/WebuiupgradeService:getReleaseNotes", data)
