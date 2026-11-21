import ipaddress
import json

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.labels import disruptive, write

# The routes the web UI keeps the router's own DNS servers in, as listed by settings().
_UPSTREAM_ROUTES = ("webuidns1", "webuidns2")
_PRIVATE_NETWORKS = tuple(ipaddress.IPv4Network(network) for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def _check_upstream_server(server: str, lan: ipaddress.IPv4Interface) -> str:
    """The server as the router stores it, after checking it like the web UI against the router's network, lan."""
    try:
        address = ipaddress.IPv4Address(server.strip())
    except ValueError:
        raise ValueError(f"{server!r} isn't an IPv4 address") from None
    if address == ipaddress.IPv4Address(0) or address >= ipaddress.IPv4Address("224.0.0.0"):
        raise ValueError(f"{server!r} can't be a DNS server: it's a reserved or multicast address")
    if any(address in network for network in _PRIVATE_NETWORKS) and (
        address not in lan.network or address in (lan.network.network_address, lan.network.broadcast_address)
    ):
        raise ValueError(
            f"{server!r} isn't a device in your network ({lan.network}). Like the web UI, a DNS server with a private address must be one."
        )
    return str(address)


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
        """Get the DNS mode: "Custom" when the router asks the servers set in the web UI or with set_upstream_servers(),
        "All" when it asks the internet provider's."""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS:get", data)

    def settings(self) -> str:
        """Get the DNS servers the router itself asks: the provider's ("dataV4_1", ...) and those set in the web UI or
        with set_upstream_servers() ("webuidns1" and "webuidns2"). mode() says which ones it uses."""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS/Server/Route:get", data)

    @disruptive
    def set_upstream_servers(self, servers: list[str]) -> str:
        """Set the DNS servers the router itself asks, like the DNS server settings in the web UI's network settings.

        Devices ask the router, which asks these servers (unless set_device_servers() gives devices other servers). If
        they don't answer, devices on the home network can't look up names, so the internet seems down.

        Args:
            servers (list[str]): up to 2 IPv4 addresses, e.g. ["1.1.1.1", "9.9.9.9"]. A private address must be in your
                network, e.g. a Pi-hole. An empty list goes back to the internet provider's servers (the default).

        Returns:
            str: response content

        Raises:
            ValueError: if the web UI would refuse a server.

        """
        if len(servers) > 2:
            raise ValueError(f"Give at most 2 DNS servers, got {len(servers)}")
        checked = []
        if servers:
            lan = json.loads(self.post("/sysbus/NMC:getLANIP", {"parameters": {}})).get("data") or {}
            network = ipaddress.IPv4Interface(f"{lan.get('Address')}/{lan.get('Netmask')}")
            checked = [_check_upstream_server(server, network) for server in servers]
        # Like the web UI: delete the old servers, save the new ones, then use only them ("Custom") or the provider's ("All").
        routes = json.loads(self.settings()).get("status") or {}
        for route_id in _UPSTREAM_ROUTES:
            if route_id in routes:
                data = {"parameters": {"id": route_id, "dns": routes[route_id].get("DNS"), "commit": True}}
                self.post("/sysbus/DNS/Server:deleteRoute", data)
        for route_id, server in zip(_UPSTREAM_ROUTES, checked):
            self.post("/sysbus/DNS/Server:setRoute", {"parameters": {"id": route_id, "dns": server, "commit": True}})
        return self.post("/sysbus/DNS:setMode", {"parameters": {"mode": "Custom" if checked else "All"}})

    def metrics(self) -> str:
        """Count the DNS queries the router answered: from its cache or itself ("dns_local_answered"), or by passing
        them on ("dns_queries_forwarded"), with the queries sent to each DNS server and how many failed."""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS/Server:getMetrics", data)

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
        """Get whether the router's DNS cache is on ("Enable") and how many answers it keeps ("MaxEntries")."""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS/Server/Cache:get", data)

    @write
    def set_cache_enabled(self, enable: bool) -> str:
        """Turn the router's DNS cache on or off, like the DNS cache switch in the web UI.

        With the cache on, the router keeps answers for a while and gives them to devices straight away. Like the web
        UI, this also empties the cache.

        Args:
            enable (bool): True to turn the cache on, False to turn it off.

        Returns:
            str: response content

        """
        result = self.post("/sysbus/DNS/Server:configureCache", {"parameters": {"enable": enable, "commit": True}})
        self.flush_cache()
        return result

    @write
    def flush_cache(self) -> str:
        """Empty the router's DNS cache, so names are looked up again. Only matters while the cache is on (see cache())."""
        data = {"parameters": {}}
        return self.post("/sysbus/DNS/Server/Cache:flush", data)
