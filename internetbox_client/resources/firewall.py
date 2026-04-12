from internetbox_client.utils.APIClient import APIClient


class Firewall(APIClient):
    """Firewall rules, DMZ, and port-forwarding settings."""

    def dmz(self) -> str:
        """Get DMZ status"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getDMZ", data)

    def ipv6_level(self) -> str:
        """Get IPv6 firewall level"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getFirewallIPv6Level", data)

    def port_forwarding(self) -> str:
        """Get port forwarding rules"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getPortForwarding", data)

    def custom_rule(self) -> str:
        """Get custom firewall rules"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getCustomRule", data)
