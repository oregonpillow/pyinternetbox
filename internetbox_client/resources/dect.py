from internetbox_client.utils.APIClient import APIClient


class DECT(APIClient):
    """DECT cordless telephony status and configuration."""

    def base_state(self) -> str:
        """Get DECT base state"""
        data = {"parameters": {}}
        return self.post("/sysbus/DECT:getBaseState", data)

    def nemo_state(self) -> str:
        """Get DECT NEMo state"""
        data = {"parameters": {}}
        return self.post("/sysbus/DECT:getNEMoState", data)

    def rfpi(self) -> str:
        """Get DECT RFPI"""
        data = {"parameters": {}}
        return self.post("/sysbus/DECT:getRFPI", data)

    def pin(self) -> str:
        """Get DECT PIN"""
        data = {"parameters": {}}
        return self.post("/sysbus/DECT:getPIN", data)

    def version(self) -> str:
        """Get DECT version"""
        data = {"parameters": {}}
        return self.post("/sysbus/DECT:getVersion", data)

    def dspg(self) -> str:
        """Get DSPG DECT status"""
        data = {"parameters": {}}
        return self.post("/sysbus/DSPGDECT:get", data)

    def radio_state(self) -> str:
        """Get DECT radio state"""
        data = {"parameters": {}}
        return self.post("/sysbus/DECT:getRadioState", data)

    def pairing_status(self) -> str:
        """Get DECT pairing status"""
        data = {"parameters": {}}
        return self.post("/sysbus/DECT:getPairingStatus", data)

    def standard_version(self) -> str:
        """Get DECT standard version"""
        data = {"parameters": {}}
        return self.post("/sysbus/DECT:getStandardVersion", data)

    def name(self) -> str:
        """Get DECT name"""
        data = {"parameters": {}}
        return self.post("/sysbus/DECT:getName", data)

    def ringtone(self) -> str:
        """Get DECT ringtone"""
        data = {"parameters": {}}
        return self.post("/sysbus/VoiceService.VoiceApplication:getRingtone", data)
