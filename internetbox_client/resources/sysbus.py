from internetbox_client.utils.APIClient import APIClient


class Sysbus(APIClient):
    """Low-level sysbus services (GPIO, time, MIBs, NeMo)."""

    def gpio(self) -> str:
        """Get all GPIOs."""
        data = {"parameters": {}}
        return self.post("/sysbus/GPIOs/GPIO:get", data, auth_required=False)

    def time(self) -> str:
        """Get system time."""
        data = {"parameters": {}}
        return self.post("/sysbus/Time:getTime", data)

    def mibs(self, flag: str = "(dslline || sfp || eth || gpon) && wan") -> str:
        """Get all MIBs

        Args:
            flag (str): expression to filter MIBs, separated by "||" for multiple tags and "&&" for AND operator.

        Example:
            (dslline || sfp || eth || gpon) && wan

        Returns:
            str: response content

        """
        data = {"parameters": {"mibs": "", "flag": flag, "traverse": "all"}}
        return self.post("/sysbus/NeMo/Intf/data:getMIBs", data, auth_required=False)

    def veip(self) -> str:
        """Get VEIP information."""
        data = {"parameters": {}}
        return self.post("/sysbus/NeMo/Intf/veip0:get", data, auth_required=False)

    def veip_mibs(self) -> str:
        """Get VEIP MIBs."""
        data = {"parameters": {}}
        return self.post("/sysbus/NeMo/Intf/veip0:getMIBs", data, auth_required=False)

    def netmaster(self) -> str:
        """Get NetMaster status."""
        data = {"parameters": {}}
        return self.post("/sysbus/NetMaster:get", data)

    def multipath_tcp(self) -> str:
        """Get MultipathTCP status."""
        data = {"parameters": {}}
        return self.post("/sysbus/MultipathTCP:get", data)

    def nemo_has_flag(self) -> str:
        """Check NeMo data interface flags."""
        data = {"parameters": {}}
        return self.post("/sysbus/NeMo/Intf/data:hasFlag", data)
