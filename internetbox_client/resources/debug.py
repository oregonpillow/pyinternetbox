from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import write


class Debug(APIClient):
    """Access debug and diagnostic information."""

    def status(self) -> str:
        """Get the log file's status: "FileStatus" is "Ready" once save_log_file() has saved one, "Idle" before."""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Debug/DebugFile:get", data)

    def wifi_driver_stats(self) -> str:
        """Get Wi-Fi driver statistics"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Debug:getWifiDriverStats", data)

    @write
    def save_log_file(self) -> str:
        """Save a log file on the router for technical support, like "Save the log data on the Internet-Box" in the
        web UI's troubleshooting page. Once it's saved, status() shows "FileStatus": "Ready".

        The file stays on the router: on regular firmware it can't be downloaded (the web UI's download link, /debug,
        only works on developer firmware; otherwise the router answers 503).

        Returns:
            str: response content

        """
        data = {"parameters": {"GenerateFile": True}}
        return self.post("/sysbus/NMC/Debug/DebugFile:set", data)

    @write
    def save_wifi_logs(self) -> str:
        """Save the current Wi-Fi debug information on the router, like the web UI's WLAN debugging option. Run it
        before save_log_file() to add it to the log file.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Debug:generateWiFiLogs", data)
