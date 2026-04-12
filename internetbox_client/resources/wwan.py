from internetbox_client.utils.APIClient import APIClient


class WWAN(APIClient):
    """Mobile broadband (WWAN/LTE) status and device information."""

    def status(self) -> str:
        """Get WWAN status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/WWAN:get", data, auth_required=False)

    def mibs(self) -> str:
        """Get WWAN MIBs"""
        data = {"parameters": {}}
        return self.post("/sysbus/NeMo/Intf/wwan:getMIBs", data, auth_required=False)

    def device(self) -> str:
        """Get WWAN device status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NetWWAN/Device:get", data)

    def device_results(self) -> str:
        """Get WWAN device results"""
        data = {"parameters": {}}
        return self.post("/sysbus/NetWWAN/Device/wwan_xt:getResults", data)
