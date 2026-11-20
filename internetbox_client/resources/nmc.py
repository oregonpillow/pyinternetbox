import base64
import binascii
import json
from pathlib import Path

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import disruptive, secret_result, write


def _read_backup(path: str) -> bytes:
    """The content of a configuration backup file, with the router's line endings (files saved on Windows have \\r\\n)."""
    content = Path(path).read_bytes().replace(b"\r\n", b"\n")
    try:
        is_backup = bool(base64.b64decode(b"".join(content.split()), validate=True))
    except binascii.Error:
        is_backup = False
    if not is_backup:
        raise ValueError(f"{path} isn't a configuration backup. Use a file saved with nmc backup or the web interface.")
    return content


class NMC(APIClient):
    """Query the Network Management Controller for WAN, LAN, and system status."""

    def status(self) -> str:
        """Get NMC status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:get", data, auth_required=False)

    def ip_conflicts(self) -> str:
        """Get IP conflicts"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:getIPConflicts", data, auth_required=False)

    def wan_status(self) -> str:
        """Get WAN status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:getWANStatus", data, auth_required=False)

    def orientation(self) -> str:
        """Get device orientation"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/Orientation:get", data, auth_required=False)

    def lan_ip(self) -> str:
        """Get LAN IP address"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC:getLANIP", data)

    @disruptive
    def reboot(self, reason: str = "pyinternetbox") -> str:
        """Restart the router. Internet, Wi-Fi and phone are down for a few minutes.

        Args:
            reason (str): reason sent to the router (the web UI sends "WebUI"). Default is "pyinternetbox".

        Returns:
            str: response content

        """
        data = {"parameters": {"reason": reason}}
        return self.post("/sysbus/NMC:reboot", data)

    @secret_result
    def backup(self) -> str:
        """Download a backup of all settings, e.g. ibox nmc backup > internetbox.cfg

        This is the file the web UI's "Save Current Configuration" button saves; restore() loads it back. The phone book
        isn't included. The router keeps the dates of the last two backups (History.backup_entries()).

        Returns:
            str: content of the backup file

        """
        return self.download("/backup")

    @disruptive
    def restore(self, path: str) -> str:
        """Replace all settings with a backup file. The router restarts: internet, Wi-Fi and phone are down for a few minutes.

        The phone book isn't in the file and stays as it is.

        Args:
            path (str): backup file saved with backup() or the web UI.

        Returns:
            str: response content

        Raises:
            ValueError: if the file isn't a configuration backup or the router doesn't confirm the restore.

        """
        content = _read_backup(path)
        # Sent under the name the router gives its backups: the web UI only uploads .cfg files.
        response = self.upload("/restore", "restore", "internetbox.cfg", content)
        # The answer is a page that passes the result to the web UI: ...fire('sah:models:System:state', 'restore-success')
        if "restore-success" not in response:
            raise ValueError(f"The router didn't confirm the restore. It answered: {response[:300]}")
        return response

    @write
    def backup_to_swisscom(self) -> str:
        """Upload a backup of the settings to Swisscom, as the web UI does when settings are saved.

        Only if backup to Swisscom is turned on for this router; the web UI has no setting for it. The router answers
        straight away and uploads in the background, which takes about a minute: network_config() shows Saving,
        Uploading, then Uploaded, and History.backup_entries() lists the upload.

        Returns:
            str: response content

        Raises:
            ValueError: if backup to Swisscom isn't turned on. Nothing is uploaded.

        """
        status = (json.loads(self.network_config()).get("status") or {}).get("Status")
        # Like the web UI, which uploads unless the status is "Disabled".
        if status in (None, "Disabled"):
            raise ValueError(
                f"Backup to Swisscom isn't turned on for this router (status: {status}), so nothing was uploaded. "
                "The web interface has no setting for it."
            )
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/NetworkConfig:launchNetworkBackup", data)

    def phonebook_backup(self) -> str:
        """Get phonebook backup status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/PhonebookBackup:get", data)

    def static_routes(self) -> str:
        """Get LAN static routes"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/LAN:getStaticRoutes", data)

    def network_config(self) -> str:
        """Get the status of backup to Swisscom: Enabled, or Saving, Uploading and Uploaded during an upload. Disabled means it's off."""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/NetworkConfig:get", data)

    def bdd(self) -> str:
        """Get NMC BDD (Broadband Device Database) information"""
        data = {"service": "NMC.BDD", "method": "get", "parameters": {}}
        return self.post("/ws", data)
