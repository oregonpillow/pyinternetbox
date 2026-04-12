import json

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.helpers import decode_nested_json


class APServices(APIClient):
    """Interact with the Swisscom AP Services Manager (APSM)."""

    _SERVICE = "com.swisscom.apsm/apservicesinfo.com.swisscom.apsm.apservicesinfo"

    def _clean(self, raw: str) -> str:
        try:
            return json.dumps(decode_nested_json(json.loads(raw)), indent=2)
        except (json.JSONDecodeError, ValueError):
            return raw

    def info(self) -> str:
        """Get AP services information.

        Returns:
            str: response content

        """
        data = {"service": self._SERVICE, "method": "Get", "parameters": {}}
        return self._clean(self.post("/ws", data))
