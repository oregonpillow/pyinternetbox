from internetbox_client.utils.APIClient import APIClient


class History(APIClient):
    """Backup and upgrade history entries."""

    def backup_entries(self) -> str:
        """Get backup history entries"""
        data = {"parameters": {}}
        return self.post("/sysbus/History/Backup/Entry:get", data)

    def upgrade_entries(self) -> str:
        """Get upgrade history entries"""
        data = {"parameters": {}}
        return self.post("/sysbus/History/Upgrade/Entry:get", data)
