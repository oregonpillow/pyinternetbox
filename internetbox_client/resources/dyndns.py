import contextlib
import json
import re

import requests

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import write

# The web UI's check: labels that start with a letter, separated by dots, e.g. "myhome.ddns.net".
_HOSTNAME = re.compile(r"[A-Za-z]([A-Za-z0-9]|[A-Za-z0-9-]+[A-Za-z0-9])?(\.[A-Za-z]([A-Za-z0-9]|[A-Za-z0-9-]+[A-Za-z0-9]))*\.[A-Za-z]+")


def _is_swisscom(host_or_service: dict | str) -> bool:
    """Whether this is Swisscom's own DynDNS service, or a host registered with it. The web UI never changes those."""
    service = host_or_service.get("service") if isinstance(host_or_service, dict) else host_or_service
    return str(service).lower() == "swisscom"


class DynDNS(APIClient):
    """Dynamic DNS configuration and registered hosts."""

    def global_enable(self) -> str:
        """Get DynDNS global enable status"""
        data = {"parameters": {}}
        return self.post("/sysbus/DynDNS:getGlobalEnable", data)

    def hosts(self) -> str:
        """Get DynDNS hosts"""
        data = {"parameters": {}}
        return self.post("/sysbus/DynDNS:getHosts", data)

    def services(self) -> str:
        """Get DynDNS services"""
        data = {"parameters": {}}
        return self.post("/sysbus/DynDNS:getServices", data)

    @write
    def set_host(self, service: str, hostname: str, username: str, password: str, enable: bool = True) -> str:
        """Register a host name with a dynamic DNS service, or change it, like the web UI's DynDNS settings.

        The router then keeps the host name pointing to its public IP address. A host with the same service or the
        same host name is replaced: the router has one host per service. Other hosts stay, including Swisscom's. The
        web UI only shows one host besides Swisscom's.

        Args:
            service (str): one of services() except "Swisscom", e.g. "No-IP".
            hostname (str): host name registered with the service, e.g. "myhome.ddns.net".
            username (str): account name at the service, up to 63 characters.
            password (str): account password, 12 to 63 characters.
            enable (bool): whether the router keeps the host name up to date. Default is True.

        Returns:
            str: response content

        Raises:
            ValueError: if a value would be refused by the web UI, or the router doesn't add the host. A host that was
                to be replaced is then put back.

        """
        if _is_swisscom(service):
            raise ValueError("Swisscom's DynDNS host is set up by Swisscom; the web UI doesn't change it either.")
        if not (3 <= len(hostname) <= 63 and _HOSTNAME.fullmatch(hostname)):
            raise ValueError(f'hostname must be a host name of 3 to 63 characters, such as "myhome.ddns.net", got {hostname!r}')
        if not re.fullmatch(r"[ -~]{1,63}", username) or not username.strip():
            raise ValueError(f"The username must be 1 to 63 letters, digits, spaces or symbols (no accents or emoji), got {username!r}")
        if not re.fullmatch(r"[ -~]{12,63}", password) or not password.strip():
            raise ValueError("The password must be 12 to 63 letters, digits, spaces or symbols (no accents or emoji).")
        services = [name for name in json.loads(self.services()).get("status") or [] if not _is_swisscom(name)]
        if service not in services:
            raise ValueError(f"service must be one of {services}, got {service!r}")
        hosts = json.loads(self.hosts()).get("status") or []
        if any(_is_swisscom(host) and str(host.get("hostname")).lower() == hostname.lower() for host in hosts):
            raise ValueError(f"{hostname} is Swisscom's DynDNS host, which only Swisscom changes.")
        replaced = [
            host
            for host in hosts
            if not _is_swisscom(host) and (host.get("service") == service or str(host.get("hostname")).lower() == hostname.lower())
        ]
        for host in replaced:
            self.post("/sysbus/DynDNS:delHost", {"parameters": {"hostname": host["hostname"]}})
        data = {"parameters": {"service": service, "hostname": hostname, "username": username, "password": password, "enable": enable}}
        try:
            response = self.post("/sysbus/DynDNS:addHost", data)
            if json.loads(response).get("status") is not True:
                raise ValueError(f"The router didn't add the host. It answered: {response}")
        except (requests.HTTPError, ValueError):
            for host in replaced:
                old = {key: host.get(key) for key in ("service", "hostname", "username", "password", "enable")}
                with contextlib.suppress(requests.HTTPError):
                    self.post("/sysbus/DynDNS:addHost", {"parameters": old})
            raise
        return response

    @write
    def delete_host(self, hostname: str) -> str:
        """Delete a DynDNS host added in the web UI or with set_host(). Swisscom's host stays.

        Args:
            hostname (str): host name, as listed by hosts().

        Returns:
            str: response content

        """
        hosts = json.loads(self.hosts()).get("status") or []
        host = next((host for host in hosts if str(host.get("hostname")).lower() == hostname.lower()), None)
        if host is None:
            names = ", ".join(repr(host.get("hostname")) for host in hosts) or "none"
            raise ValueError(f"There's no DynDNS host {hostname!r}. The hosts are: {names}.")
        if _is_swisscom(host):
            raise ValueError(f"{hostname} is Swisscom's DynDNS host, which only Swisscom changes.")
        data = {"parameters": {"hostname": host["hostname"]}}
        return self.post("/sysbus/DynDNS:delHost", data)
