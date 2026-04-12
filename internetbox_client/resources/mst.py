from internetbox_client.utils.APIClient import APIClient


class MST(APIClient):
    """Query and manage Parental Control: Max Surf Time (MST)."""

    def status(self) -> str:
        """Get Max Surf Time (MST) status"""
        data = {"parameters": {}}
        return self.post("/sysbus/ToD/MaxSurfTime:get", data)

    def config(self, id: str) -> str:
        """Get Max Surf Time (MST) settings

        Args:
            id (str): MST entry ID.
        """
        data = {"parameters": {"id": id}}
        return self.post("/sysbus/ToD:getMST", data)

    def get(self) -> str:
        """Get all Max Surf Time (MST) entries"""
        data = {"parameters": {}}
        return self.post("/sysbus/ToD:listMST", data)

    def set(self) -> str:
        """Set Max Surf Time (MST) settings"""
        data = {"parameters": {}}
        return self.post("/sysbus/ToD:setMST", data)

    def stats(self, id: str) -> str:
        """Get Max Surf Time (MST) statistics

        Args:
            id (str): MST entry ID.
        """
        data = {"parameters": {"id": id}}
        return self.post("/sysbus/ToD:statsMST", data)
