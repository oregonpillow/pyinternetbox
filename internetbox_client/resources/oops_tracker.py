from internetbox_client.utils.APIClient import APIClient


class OopsTracker(APIClient):
    """Kernel oops crash reports."""

    def status(self) -> str:
        """Get OopsTracker status"""
        data = {"parameters": {}}
        return self.post("/sysbus/OopsTracker:get", data)

    def oopses(self) -> str:
        """Get OopsTracker oopses"""
        data = {"parameters": {}}
        return self.post("/sysbus/OopsTracker:getOopses", data)
