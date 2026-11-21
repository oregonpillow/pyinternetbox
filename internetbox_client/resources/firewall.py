import ipaddress
import json
import re
import time
from typing import Literal

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.helpers import normalize_mac
from internetbox_client.utils.labels import disruptive, write

_PROTOCOLS = {"tcp": "6", "udp": "17", "both": "6,17"}
# IP protocols without ports, by name, for protocol forwarding.
_IP_PROTOCOLS = {"gre": "47", "esp": "50", "ah": "51"}
_ACTIONS = {"allow": "Accept", "block": "Drop"}
# The custom rule chains, by IP version and direction. IPv4 rules are outbound only.
_CHAINS = {(4, "outbound"): "Custom", (6, "outbound"): "Custom_V6Out", (6, "inbound"): "Custom_V6In"}


def _chain(ip_version: int, direction: str) -> str:
    if ip_version not in (4, 6):
        raise ValueError(f"ip_version must be 4 or 6, got {ip_version!r}")
    if direction not in ("outbound", "inbound"):
        raise ValueError(f'direction must be "outbound" or "inbound", got {direction!r}')
    if (ip_version, direction) not in _CHAINS:
        raise ValueError("IPv4 custom rules are outbound only (from your devices to the internet). Use port forwarding for inbound IPv4.")
    return _CHAINS[ip_version, direction]


def _port_range(port: int | str) -> tuple[int, int]:
    """A port, e.g. 443, or a range, e.g. "8000-8010", as (first, last)."""
    match = re.fullmatch(r"(\d{1,5})(?:\s*-\s*(\d{1,5}))?", str(port).strip())
    if not match:
        raise ValueError(f'port must be a port such as 443 or a range such as "8000-8010", got {port!r}')
    first, last = int(match[1]), int(match[2] or match[1])
    if not (1 <= first <= 65535 and 1 <= last <= 65535):
        raise ValueError(f"Ports must be between 1 and 65535, got {port!r}")
    if match[2] and last <= first:
        raise ValueError(f"A port range must go from a lower to a higher port, got {port!r}")
    return first, last


def _ip_protocols(protocol: str) -> str:
    """Protocols such as "gre" or "47,50" as the router stores them, e.g. "47,50"."""
    numbers = []
    for part in str(protocol).split(","):
        number = _IP_PROTOCOLS.get(part.strip().lower(), part.strip())
        if not number.isdigit() or int(number) > 255:
            raise ValueError(f'protocol must be numbers from 0 to 255 or "gre", "esp" or "ah", separated by commas, got {protocol!r}')
        numbers.append(str(int(number)))
    return ",".join(numbers)


def _rule_ports(rule: dict) -> tuple[int, int]:
    first, _, last = str(rule.get("DestinationPort") or "0").partition("-")
    return int(first or 0), int(last or first or 0)


def _rule_device(chain: str, rule: dict) -> str:
    """The device a rule applies to, or "" for all devices: the target of inbound rules, the source of outbound ones."""
    return (rule.get("DestinationMACAddress") if chain == "Custom_V6In" else rule.get("SourceMACAddress")) or ""


def _rule_summary(chain: str, rule_id: str, rule: dict) -> dict:
    ip_version, direction = next(key for key, name in _CHAINS.items() if name == chain)
    actions, protocols = {v: k for k, v in _ACTIONS.items()}, {v: k for k, v in _PROTOCOLS.items()}
    return {
        "name": rule.get("Description") or rule_id,
        "port": rule.get("DestinationPort"),
        "action": actions.get(rule.get("Target"), rule.get("Target")),
        "ip_version": ip_version,
        "direction": direction,
        "protocol": protocols.get(rule.get("Protocol"), rule.get("Protocol")),
        "device": _rule_device(chain, rule) or None,
        "enabled": rule.get("Enable"),
        "id": rule_id,
        "chain": chain,
    }


class Firewall(APIClient):
    """Firewall rules, DMZ, and port-forwarding settings."""

    def status(self) -> str:
        """Get firewall status, including whether UPnP port forwarding is on (UpnpPortForwardingEnable)"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:get", data)

    @write
    def set_upnp_enabled(self, enable: bool) -> str:
        """Turn UPnP port forwarding on or off, like the UPnP switch in the web UI's port forwarding settings.

        With UPnP on, devices such as game consoles open ports to the internet themselves.

        Args:
            enable (bool): True to turn UPnP on, False to turn it off.

        Returns:
            str: response content

        """
        data = {"parameters": {"UpnpPortForwardingEnable": enable}}
        return self.post("/sysbus/Firewall:set", data)

    def upnp_description(self) -> str:
        """Get how the router presents itself to devices over UPnP: its name ("FriendlyName"), model and provider, and
        whether its UPnP service runs ("Enable"). Whether devices may open ports with UPnP is separate (see status())."""
        data = {"parameters": {}}
        return self.post("/sysbus/UPnP-IGD:get", data)

    def dmz(self) -> str:
        """Get DMZ status"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getDMZ", data)

    @write
    def set_dmz(self, destination_ip: str) -> str:
        """Expose a device to the internet (DMZ host).

        Incoming connections that no port forwarding rule matches go to this device instead of being blocked.
        Only use it for a device that is safe to expose directly to the internet.

        Args:
            destination_ip (str): LAN IP address of the device, e.g. "192.168.1.20".

        Returns:
            str: response content

        """
        data = {"parameters": {"id": "webui", "sourceInterface": "data", "destinationIPAddress": destination_ip, "enable": True}}
        return self.post("/sysbus/Firewall:setDMZ", data)

    @write
    def delete_dmz(self) -> str:
        """Remove the DMZ host set in the web UI or with set_dmz."""
        data = {"parameters": {"id": "webui"}}
        return self.post("/sysbus/Firewall:deleteDMZ", data)

    def level(self) -> str:
        """Get IPv4 firewall level"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getFirewallLevel", data)

    @write
    def set_level(self, level: Literal["Low", "Medium", "High", "Custom"]) -> str:
        """Set the IPv4 firewall level.

        Args:
            level (str): "Low" (Off in the web UI), "Medium" (Balanced), "High" (Strict) or "Custom" (custom rules).

        Returns:
            str: response content

        """
        data = {"parameters": {"level": level}}
        return self.post("/sysbus/Firewall:setFirewallLevel", data)

    def ipv6_level(self) -> str:
        """Get IPv6 firewall level"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getFirewallIPv6Level", data)

    @write
    def set_ipv6_level(self, level: Literal["Off", "Medium", "High", "Custom"]) -> str:
        """Set the IPv6 firewall level.

        Args:
            level (str): "Off", "Medium" (Balanced in the web UI), "High" (Strict) or "Custom" (custom rules).

        Returns:
            str: response content

        """
        data = {"parameters": {"level": level}}
        return self.post("/sysbus/Firewall:setFirewallIPv6Level", data)

    def port_forwarding(self) -> str:
        """Get port forwarding rules"""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getPortForwarding", data)

    @write
    def set_port_forwarding(
        self,
        name: str,
        destination_ip: str,
        external_port: str,
        internal_port: str | None = None,
        protocol: Literal["tcp", "udp", "both"] = "both",
        enabled: bool = True,
    ) -> str:
        """Add a port forwarding rule, or update the rule with this name.

        The rule shows up in the web UI like rules created there, with the ID "webui_<name>".

        Args:
            name (str): rule name, e.g. "minecraft".
            destination_ip (str): LAN IP address of the device to forward to, e.g. "192.168.1.20".
            external_port (str): port on the internet side, e.g. "25565", or a range such as "8000-8010".
            internal_port (str | None): port on the device. Default is the same as external_port. For a range of
                external ports, give the same range, or a single port to send the whole range to it.
            protocol (str): "tcp", "udp" or "both". Default is "both".
            enabled (bool): whether the rule is active. Default is True.

        Returns:
            str: response content, including the stored rule

        """
        if protocol not in _PROTOCOLS:
            raise ValueError(f"protocol must be one of {list(_PROTOCOLS)}, got {protocol!r}")
        external_port, internal_port = str(external_port), str(internal_port or external_port)
        if "-" in internal_port and internal_port != external_port:
            raise ValueError(f"internal_port must be a single port or the same range as external_port, got {internal_port!r}")
        data = {
            "parameters": {
                "id": name,
                "description": name,
                "persistent": True,
                "origin": "webui",
                "sourceInterface": "data",
                "sourcePrefix": "",
                "enable": enabled,
                "protocol": _PROTOCOLS[protocol],
                "destinationIPAddress": destination_ip,
                "externalPort": external_port,
                "internalPort": internal_port,
            }
        }
        result = self.post("/sysbus/Firewall:setPortForwarding", data)
        self._commit()
        return result

    @write
    def delete_port_forwarding(self, name: str) -> str:
        """Delete a port forwarding rule created in the web UI or with set_port_forwarding.

        Args:
            name (str): rule name, or its ID as listed by port_forwarding() (e.g. "webui_minecraft").

        Returns:
            str: response content

        """
        data = {"parameters": {"id": name, "origin": "webui"}}
        result = self.post("/sysbus/Firewall:deletePortForwarding", data)
        self._commit()
        return result

    @write
    def delete_all_port_forwarding(self) -> str:
        """Delete all port forwarding rules created in the web UI or with set_port_forwarding(). They can't be brought
        back. Ports that devices opened themselves with UPnP stay open.

        Returns:
            str: response content

        """
        result = self.post("/sysbus/Firewall:deletePortForwarding", {"parameters": {"origin": "webui"}})
        self._commit()
        return result

    def respond_to_ping(self) -> str:
        """Get whether the router answers pings from the internet, over IPv4 ("enableIPv4") and IPv6 ("enableIPv6")."""
        data = {"parameters": {"sourceInterface": "data"}}
        return self.post("/sysbus/Firewall:getRespondToPing", data)

    @write
    def set_respond_to_ping(self, enable: bool, ip_version: Literal[4, 6] | None = None) -> str:
        """Choose whether the router answers pings from the internet.

        Args:
            enable (bool): True to answer pings, False to ignore them.
            ip_version (int | None): 4 or 6 to change only IPv4 or IPv6. Default: both.

        Returns:
            str: response content

        """
        if ip_version not in (None, 4, 6):
            raise ValueError(f"ip_version must be 4 or 6, got {ip_version!r}")
        service = {"enableIPv4": enable, "enableIPv6": enable}
        if ip_version is not None:
            other = f"enableIPv{10 - ip_version}"  # the IP version that stays as it is
            service[other] = bool((json.loads(self.respond_to_ping()).get("status") or {}).get(other))
        data = {"parameters": {"sourceInterface": "data", "service_enable": service}}
        return self.post("/sysbus/Firewall:setRespondToPing", data)

    def protocol_forwarding(self) -> str:
        """Get the protocol forwarding rules: whole IP protocols, e.g. GRE, forwarded from the internet to a device."""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getProtocolForwarding", data)

    @write
    def set_protocol_forwarding(self, name: str, destination_ip: str, protocol: str, enabled: bool = True) -> str:
        """Forward a whole IP protocol from the internet to a device, or update the rule with this name.

        Port forwarding forwards TCP and UDP ports; this forwards protocols without ports, e.g. GRE for a PPTP VPN
        server or ESP for an IPsec one.

        Args:
            name (str): rule name, e.g. "vpn".
            destination_ip (str): LAN IP address of the device to forward to, e.g. "192.168.1.20".
            protocol (str): a protocol number from 0 to 255 or "gre", "esp" or "ah", or several separated by commas,
                e.g. "esp,ah".
            enabled (bool): whether the rule is active. Default is True.

        Returns:
            str: response content

        """
        parameters = {
            "id": name,
            "description": name,
            "persistent": True,
            "sourceInterface": "data",
            "enable": enabled,
            "protocol": _ip_protocols(protocol),
            "destinationIPAddress": destination_ip,
        }
        result = self.post("/sysbus/Firewall:setProtocolForwarding", {"parameters": parameters})
        self._commit()
        return result

    @write
    def delete_protocol_forwarding(self, name: str) -> str:
        """Delete a protocol forwarding rule.

        Args:
            name (str): rule name, as given to set_protocol_forwarding().

        Returns:
            str: response content

        """
        result = self.post("/sysbus/Firewall:deleteProtocolForwarding", {"parameters": {"id": name}})
        self._commit()
        return result

    def ipv6_pinholes(self) -> str:
        """Get the IPv6 pinholes: ports open from the internet to a device's IPv6 address."""
        data = {"parameters": {}}
        return self.post("/sysbus/Firewall:getPinhole", data)

    @write
    def set_ipv6_pinhole(
        self, name: str, destination_ip: str, port: str, protocol: Literal["tcp", "udp", "both"] = "both", enabled: bool = True
    ) -> str:
        """Open a port from the internet to a device's IPv6 address (a pinhole), or update the pinhole with this name.

        IPv6 needs no port forwarding: devices have their own public IPv6 addresses, which the firewall protects. A
        pinhole lets connections to one port of one address through.

        Args:
            name (str): pinhole name, e.g. "minecraft".
            destination_ip (str): the device's public IPv6 address, e.g. "2001:db8::20". devices.summary() and get()
                list devices' addresses.
            port (str): port, e.g. "25565", or a range such as "8000-8010".
            protocol (str): "tcp", "udp" or "both". Default is "both".
            enabled (bool): whether the pinhole is open. Default is True.

        Returns:
            str: response content

        """
        if protocol not in _PROTOCOLS:
            raise ValueError(f"protocol must be one of {list(_PROTOCOLS)}, got {protocol!r}")
        try:
            address = ipaddress.IPv6Address(destination_ip.strip())
        except ValueError:
            raise ValueError(f"destination_ip must be an IPv6 address, got {destination_ip!r}") from None
        first, last = _port_range(port)
        parameters = {
            "id": name,
            "description": name,
            "origin": "webui",
            "sourceInterface": "data",
            "sourcePort": "",
            "sourcePrefix": "",
            "destinationPort": f"{first}-{last}" if last != first else str(first),
            "destinationIPAddress": str(address),
            "destinationMACAddress": "",
            "protocol": _PROTOCOLS[protocol],
            "ipversion": 6,
            "enable": enabled,
            "persistent": True,
        }
        result = self.post("/sysbus/Firewall:setPinhole", {"parameters": parameters})
        self._commit()
        return result

    @write
    def delete_ipv6_pinhole(self, name: str) -> str:
        """Delete an IPv6 pinhole.

        Args:
            name (str): pinhole name, as given to set_ipv6_pinhole().

        Returns:
            str: response content

        """
        result = self.post("/sysbus/Firewall:deletePinhole", {"parameters": {"id": name, "origin": "webui"}})
        self._commit()
        return result

    def custom_rule(self, chain: Literal["Custom", "Custom_V6Out", "Custom_V6In"] | None = None) -> str:
        """Get the custom firewall rules of a chain: "Custom" (IPv4, the default), "Custom_V6Out" or "Custom_V6In" (IPv6).

        custom_rules() lists the rules of all three chains in short form.
        """
        data = {"parameters": {"chain": chain} if chain else {}}
        return self.post("/sysbus/Firewall:getCustomRule", data)

    def custom_rules(self) -> str:
        """A short list of the custom firewall rules, IPv4 and IPv6, like the web UI's list.

        Custom rules only apply while the firewall level is "Custom" (see level() and ipv6_level()). Traffic that no
        rule matches gets the basic action in custom_policy().

        Returns:
            str: a JSON array, e.g. [{"name": "Telnet", "port": "23", "action": "block", "ip_version": 4, "direction":
                "outbound", "protocol": "tcp", "device": null, "enabled": true, "id": "1732101234567_1", "chain": "Custom"}]

        """
        rules = [_rule_summary(chain, rule_id, rule) for chain, rule_id, rule in self._custom_rules()]
        return json.dumps(rules, ensure_ascii=False)

    @write
    def set_custom_rule(
        self,
        name: str,
        port: str,
        action: Literal["allow", "block"],
        ip_version: Literal[4, 6] = 4,
        direction: Literal["outbound", "inbound"] = "outbound",
        protocol: Literal["tcp", "udp", "both"] = "both",
        device: str | None = None,
        enabled: bool = True,
    ) -> str:
        """Add a custom firewall rule, or change the rule with this name, like the web UI's custom firewall.

        The rule only applies while the firewall level of its IP version is "Custom" (see set_level() and
        set_ipv6_level()). Outbound rules allow or block traffic from your devices to these ports on the internet;
        inbound rules (IPv6 only) traffic from the internet to these ports on your devices.

        Args:
            name (str): rule name, 1 to 40 letters, digits, spaces or symbols, e.g. "Telnet".
            port (str): destination port, e.g. "23", or a range such as "8000-8010".
            action (str): "allow" or "block".
            ip_version (int): 4 or 6. Default is 4.
            direction (str): "outbound" or "inbound". IPv4 rules are outbound only. Default is "outbound".
            protocol (str): "tcp", "udp" or "both". Default is "both".
            device (str | None): MAC address of the only device the rule applies to. Default: all devices.
            enabled (bool): whether the rule is on. Default is True.

        Returns:
            str: response content, with the rule's ID. A changed rule gets a new ID, as in the web UI.

        Raises:
            ValueError: if the web UI would refuse the rule: for instance because it overlaps another rule of the same
                IP version and direction, or covers all ports (1-65535) with the opposite of the basic action in
                custom_policy().

        """
        chain = _chain(ip_version, direction)
        if action not in _ACTIONS:
            raise ValueError(f'action must be "allow" or "block", got {action!r}')
        if protocol not in _PROTOCOLS:
            raise ValueError(f"protocol must be one of {list(_PROTOCOLS)}, got {protocol!r}")
        if not re.fullmatch(r"[ -~]{1,40}", name) or not name.strip():
            raise ValueError(f"The rule name must be 1 to 40 letters, digits, spaces or symbols (no accents or emoji), got {name!r}")
        first, last = _port_range(port)
        mac = normalize_mac(device) if device else ""
        rules = self._custom_rules()
        current = _named(rules, name)
        current_key = current[:2] if current else None  # the rule doesn't overlap the one it replaces
        for other_chain, other_id, other in rules:
            if other_chain != chain or (other_chain, other_id) == current_key:
                continue
            other_first, other_last = _rule_ports(other)
            other_device = _rule_device(other_chain, other).upper()
            if (
                set(_PROTOCOLS[protocol].split(",")) & set(str(other.get("Protocol")).split(","))
                and (not mac or not other_device or mac == other_device)
                and first <= other_last
                and other_first <= last
            ):
                conflict = "contradicts" if other.get("Target") != _ACTIONS[action] else "overlaps"
                raise ValueError(
                    f"The rule {conflict} the custom rule {other.get('Description') or other_id!r} (port "
                    f"{other.get('DestinationPort')}). Like the web UI, rules for the same ports, protocol and device "
                    "aren't allowed: change or delete that rule first."
                )
        if (first, last) == (1, 65535) and _ACTIONS[action] != self._policy(chain):
            raise ValueError(
                "A rule for all ports (1-65535) must have the same action as the basic action in custom_policy(). "
                "To change what happens to all traffic, use set_custom_policy()."
            )
        stamp, ids = int(time.time() * 1000), {rule_id for _, rule_id, _ in rules}
        rule_id = next(f"{stamp}_{n}" for n in range(1, len(ids) + 2) if f"{stamp}_{n}" not in ids)
        parameters = {
            "id": rule_id,
            "chain": chain,
            "description": name,
            "action": _ACTIONS[action],
            "ipversion": ip_version,
            "protocol": _PROTOCOLS[protocol],
            "destinationPort": f"{first}-{last}" if last != first else str(first),
            "destinationMAC" if chain == "Custom_V6In" else "sourceMAC": mac,
            "enable": enabled,
            "persistent": True,
        }
        result = self.post("/sysbus/Firewall:setCustomRule", {"parameters": parameters})
        # Like the web UI, a changed rule replaces the old one. The router keeps a rule's device when it's changed to
        # all devices. The new rule is added first, so the old one stays if that fails.
        if current:
            self.post("/sysbus/Firewall:deleteCustomRule", {"parameters": {"id": current[1], "chain": current[0]}})
        self._commit()
        return result

    @write
    def enable_custom_rule(self, name: str, enable: bool = True) -> str:
        """Turn a custom firewall rule on or off, like its switch in the web UI.

        Args:
            name (str): rule name, as listed by custom_rules().
            enable (bool): True to turn the rule on, False to turn it off. Default is True.

        Returns:
            str: response content

        """
        chain, rule_id, rule = self._custom_rule_named(name)
        parameters = {
            "id": rule_id,
            "chain": chain,
            "description": rule.get("Description") or "",
            "action": rule.get("Target"),
            "ipversion": rule.get("IPVersion"),
            "protocol": rule.get("Protocol"),
            "destinationPort": rule.get("DestinationPort"),
            "destinationMAC" if chain == "Custom_V6In" else "sourceMAC": _rule_device(chain, rule),
            "enable": enable,
            "persistent": True,
        }
        # Settings the web UI can't make, kept for rules made elsewhere.
        for key in ("SourcePort", "DestinationPrefix", "SourcePrefix"):
            if rule.get(key):
                parameters[key[0].lower() + key[1:]] = rule[key]
        result = self.post("/sysbus/Firewall:setCustomRule", {"parameters": parameters})
        self._commit()
        return result

    @write
    def delete_custom_rule(self, name: str) -> str:
        """Delete a custom firewall rule.

        Args:
            name (str): rule name, as listed by custom_rules().

        Returns:
            str: response content

        """
        chain, rule_id, _ = self._custom_rule_named(name)
        result = self.post("/sysbus/Firewall:deleteCustomRule", {"parameters": {"id": rule_id, "chain": chain}})
        self._commit()
        return result

    def custom_policy(self) -> str:
        """What the custom firewall does with traffic that no custom rule matches: "allow" or "block".

        This is the basic setting of the web UI's custom firewall, for IPv4 and for each IPv6 direction. It only
        applies while the firewall level is "Custom".

        Returns:
            str: a JSON object, e.g. {"ipv4": "allow", "ipv6_outbound": "allow", "ipv6_inbound": "block"}

        """
        actions = {v: k for k, v in _ACTIONS.items()}
        chains = {"ipv4": "Custom", "ipv6_outbound": "Custom_V6Out", "ipv6_inbound": "Custom_V6In"}
        policies = {key: self._policy(chain) for key, chain in chains.items()}
        return json.dumps({key: actions.get(policy, policy) for key, policy in policies.items()})

    @disruptive
    def set_custom_policy(
        self, action: Literal["allow", "block"], ip_version: Literal[4, 6] = 4, direction: Literal["outbound", "inbound"] = "outbound"
    ) -> str:
        """Set what the custom firewall does with traffic that no custom rule matches, like its basic setting in the web UI.

        It only applies while the firewall level of this IP version is "Custom". Blocking outbound traffic then cuts
        devices off the internet, except for the ports that custom rules allow.

        Args:
            action (str): "allow" or "block".
            ip_version (int): 4 or 6. Default is 4.
            direction (str): "outbound" or "inbound" (IPv6 only). Default is "outbound".

        Returns:
            str: response content

        """
        chain = _chain(ip_version, direction)
        if action not in _ACTIONS:
            raise ValueError(f'action must be "allow" or "block", got {action!r}')
        data = {"parameters": {"chain": chain, "policy": _ACTIONS[action]}}
        return self.post("/sysbus/Firewall:setChainPolicy", data)

    def _custom_rules(self) -> list[tuple[str, str, dict]]:
        """Every custom rule, as (chain, ID, rule)."""
        found = []
        for chain in _CHAINS.values():
            rules = json.loads(self.custom_rule(chain)).get("status") or {}
            found += [(chain, rule_id, rule) for rule_id, rule in rules.items()]
        return found

    def _custom_rule_named(self, name: str) -> tuple[str, str, dict]:
        rules = self._custom_rules()
        found = _named(rules, name)
        if found is None:
            names = ", ".join(repr(rule.get("Description") or rule_id) for _, rule_id, rule in rules) or "none"
            raise ValueError(f"There's no custom firewall rule named {name!r}. The rules are: {names}.")
        return found

    def _policy(self, chain: str) -> str:
        """A chain's basic action: "Accept" or "Drop". Like the web UI, "Accept" if it has none."""
        policy = json.loads(self.post("/sysbus/Firewall:getChainPolicy", {"parameters": {"chain": chain}})).get("status")
        return policy if isinstance(policy, str) and policy not in ("", "None") else "Accept"

    def _commit(self) -> None:
        """Apply saved rule changes, as the web UI does after changing a rule."""
        self.post("/sysbus/Firewall:commit", {"parameters": {}})


def _named(rules: list[tuple[str, str, dict]], name: str) -> tuple[str, str, dict] | None:
    """The custom rule with this name. The web UI shows the ID of IPv4 rules without a name."""
    return next((found for found in rules if (found[2].get("Description") or found[1]) == name), None)
