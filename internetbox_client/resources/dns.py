import ipaddress

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import write


def _join_servers(servers: list[str], version: int) -> str:
    """The servers as the router stores them, e.g. "1.1.1.1,9.9.9.9", after checking them like the web UI's two fields."""
    if len(servers) > 2:
        raise ValueError(f"Give at most 2 DNS servers, got {len(servers)}")
    addresses = []
    for server in servers:
        try:
            address = ipaddress.ip_address(server.strip())
        except ValueError:
            address = None
        if address is None or address.version != version:
            raise ValueError(f"{server!r} isn't an IPv{version} address")
        addresses.append(str(address))
    return ",".join(addresses)


class DNS(APIClient):
    """DNS resolver status, settings, and cache."""

    def status(self) -> str:
        """Get DNS status"""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/DNS:get", data, auth_required=False)

    def mode(self) -> str:
        """Get DNS mode"""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS:get", data)

    def settings(self) -> str:
        """Get DNS settings"""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS/Server/Route:get", data)

    def user(self) -> str:
        """Get the DNS servers the router gives devices on the local network (IPv4). Empty: the router itself."""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/DHCPv4/DNSServers/User:get", data)

    @write
    def set_device_servers(self, servers: list[str]) -> str:
        """Set the DNS servers the router gives devices on the local network, like the DNS fields in the web UI's DHCP settings.

        Devices ask these servers instead of the router once they renew their address, e.g. when they reconnect.

        Args:
            servers (list[str]): up to 2 IPv4 addresses, e.g. ["1.1.1.1", "9.9.9.9"]. An empty list gives devices the
                router again (the default).

        Returns:
            str: response content

        """
        data = {"parameters": {"DNSServers": _join_servers(servers, 4)}}
        return self.post("/sysbus/NMC/DHCPv4/DNSServers/User:set", data)

    def user_ipv6(self) -> str:
        """Get the IPv6 DNS servers the router gives devices on the local network. Empty: the router itself."""
        data = {"parameters": {}}
        return self.post("/sysbus/NMC/DHCPv6/DNSServers/User:get", data)

    @write
    def set_device_servers_ipv6(self, servers: list[str]) -> str:
        """Set the IPv6 DNS servers the router gives devices on the local network, like the DNS fields in the web UI's IPv6 settings.

        Args:
            servers (list[str]): up to 2 IPv6 addresses, e.g. ["2606:4700:4700::1111"]. An empty list gives devices
                the router again (the default).

        Returns:
            str: response content

        """
        data = {"parameters": {"DNSServers": _join_servers(servers, 6)}}
        return self.post("/sysbus/NMC/DHCPv6/DNSServers/User:set", data)

    def cache(self) -> str:
        """Get DNS server cache"""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS/Server/Cache:get", data)

    @write
    def flush_cache(self) -> str:
        """Empty the router's DNS cache, so names are looked up again. Only matters while the cache is on (see cache())."""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS/Server/Cache:flush", data)
