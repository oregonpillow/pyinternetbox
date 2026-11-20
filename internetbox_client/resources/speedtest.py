from __future__ import annotations

import json

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.helpers import decode_nested_json
from internetbox_client.utils.labels import write


class SpeedTest(APIClient):
    """Interact with the Vestiacom speed test service on the router."""

    _SERVICE = "com.vestiacom.speedtest/com/vestiacom/speedtest.com.vestiacom.speedtest"

    def _clean(self, raw: str) -> str:
        """Parse response and decode any nested JSON strings.
        The speedtest service seems to call a third-party service (Vestiacom) that also returns JSON
        therefore producing netsted JSON strings in the response.
        before: "{\n\t\"event\":\t\"IDLE\"\n}"
        after:    {"status": {"event": "IDLE"}}
        """
        try:
            return json.dumps(decode_nested_json(json.loads(raw)), indent=2)
        except (json.JSONDecodeError, ValueError):
            return raw

    @write
    def start(self, origin: str = "webui", wait_for_lan_result: bool = False) -> str:
        """Start a speed test.

        Args:
            origin (str): origin identifier for the test. Default is "webui".
            wait_for_lan_result (bool): whether to wait for LAN result. Default is False.

        Returns:
            str: response content

        """
        data = {
            "service": self._SERVICE,
            "method": "TestStart",
            "parameters": {"origin": origin, "waitforlanresult": str(wait_for_lan_result).lower()},
        }
        return self._clean(self.post("/ws", data))

    def status(self) -> str:
        """Get current speed test status and results.

        Returns:
            str: response content with test progress and results

        """
        data = {"service": self._SERVICE, "method": "TestStatus", "parameters": {}}
        return self._clean(self.post("/ws", data))
