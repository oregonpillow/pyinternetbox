from internetbox_client.utils.APIClient import APIClient


class Voice(APIClient):
    """VoIP telephony status, trunks, handsets, and call lists."""

    def status(self) -> str:
        """Get voice status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/VoiceActivation:get", data, auth_required=False)

    def trunks(self) -> str:
        """List of trunks"""
        data = {"parameters": {}}
        return self.post("/sysbus/VoiceService/VoiceApplication:listTrunks", data, auth_required=False)

    def sip_extensions_status(self) -> str:
        """Get SIP extensions status"""
        data = {"parameters": {}}
        return self.post("/sysbus/VoiceService/VoiceApplication:getSipExtensionsStatus", data)

    def groups(self) -> str:
        """List voice groups"""
        data = {"parameters": {}}
        return self.post("/sysbus/VoiceService/VoiceApplication:listGroups", data)

    def handsets(self) -> str:
        """List connected handsets"""
        data = {"parameters": {}}
        return self.post("/sysbus/VoiceService/VoiceApplication:listHandsets", data)

    def call_list(self) -> str:
        """Get call list"""
        data = {"parameters": {}}
        return self.post("/sysbus/VoiceService/VoiceApplication:getCallList", data)
