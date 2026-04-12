from __future__ import annotations

from typing import Any, Mapping, Sequence

from internetbox_client.utils.APIClient import APIClient


class Events(APIClient):
    """Subscribe to and poll real-time event channels on the Internet Box."""

    def service(self, id: int | None = None) -> str:
        """Get service event channel information.

        Args:
            id (int): event channel ID. Default is None, which returns all channels.

        Returns:
            str: response content

        """
        data = {
            "service": "eventmanager",
            "method": "get_events",
            "parameters": {
                "channelid": f"{id}",
                "events": [
                    {"service": "Devices.Device.HGW", "event": "cpu"},
                    {"service": "Devices.Device.HGW", "event": "sysinfo", "data": {"types": "sysinfo"}},
                ],
            },
        }
        return self.post("/ws", data)

    def handler(self, handler: Sequence[str], id: int | None = None, method: str = "get_events") -> str:
        """Get service event channel information.

        Args:
            handler (Sequence[str]): event handlers to filter for.
            id (int): event channel ID. Default is None, which returns all channels.
            method (str): event manager method to call. Default is "get_events". "open_channel" can also be used to open a new channel for events.

        handler examples (case sensitive):
            NeMo.Intf.wifi1_bcm.ChannelMgt
            NeMo.Intf.wifi0_bcm.ChannelMgt
            NMC.Wifi
            NMC.Guest
            NeMo.Intf.wwan
            NMC.VoiceActivation
            VPN.Server.default.Client.account{1,2,3...}
            WebuiupgradeService

        Returns:
            str: response content

        """
        events = [{"handler": h} for h in handler]

        data = {"service": "eventmanager", "method": method, "parameters": {"channelid": f"{id}", "events": events}}
        return self.post("/ws", data)

    def log(self, mac: str) -> str:
        """Get event log information.

        Args:
            mac (str): filter event log by MAC address. Required.

        Returns:
            str: response content

        """
        data = {"service": f"Devices.Device.{mac.upper()}", "method": "getEventLog", "parameters": {"type": "network"}}
        return self.post("/ws", data)

    def open_channel(self, events: Sequence[Mapping[str, Any]]) -> str:
        """Open a new event channel with event subscriptions.

        Creates a new event channel and subscribes to the specified events.
        Returns immediately with the assigned channel ID.
        Use poll() to retrieve events from the channel.

        Args:
            events (Sequence[Mapping[str, Any]]): list of event subscription dicts. Each dict can be:
                - {"service": "<service>", "event": "<event_type>"} for service events
                - {"service": "<service>", "event": "<event_type>", "data": {"key": "value"}} for queried events
                - {"handler": "<handler_path>"} for handler events
                Multiple types can be mixed in the same list.

        Returns:
            str: response containing the channel ID

        Example:
            events = [
                {"service": "Devices.Device", "event": "wifi_device_updated"},
                {"service": "Devices.Device", "event": "eth_device_updated"},
                {"handler": "NMC.Wifi"},
            ]
            result = events_client.open_channel(events)

        """
        data = {"service": "eventmanager", "method": "open_channel", "parameters": {"events": events}}
        return self.post("/ws", data)

    def subscribe(self, events: Sequence[Mapping[str, Any]], id: int) -> str:
        """Subscribe to additional events on an existing event channel.

        Args:
            events (Sequence[Mapping[str, Any]]): list of event subscription dicts (same format as open_channel).
            id (int): existing channel ID to add subscriptions to.

        Returns:
            str: response content

        """
        data = {"service": "eventmanager", "method": "subscribe", "parameters": {"channelid": id, "events": events}}
        return self.post("/ws", data)

    def unsubscribe(self, events: Sequence[Mapping[str, Any]], id: int) -> str:
        """Unsubscribe from events on an existing event channel.

        Args:
            events (Sequence[Mapping[str, Any]]): list of event subscription dicts (same format as open_channel).
            id (int): existing channel ID to remove subscriptions from.

        Returns:
            str: response content

        """
        data = {"service": "eventmanager", "method": "unsubscribe", "parameters": {"channelid": id, "events": events}}
        return self.post("/ws", data)

    def poll(self, id: int) -> str:
        """Poll for events on an existing event channel (long polling).

        Blocks until events are available or times out after ~30 seconds.
        Must be called again within ~10 seconds to keep the channel alive.

        Args:
            id (int): channel ID to poll.

        Returns:
            str: response with channelid and events list

        """
        data = {"service": "eventmanager", "method": "get_events", "parameters": {"channelid": id}}
        return self.post("/ws", data)

    def device_network(self, macs: Sequence[str]) -> str:
        """Open an event channel to monitor network events for specific devices.

        Convenience method that creates an event channel subscribed to network
        events for each provided MAC address.

        Args:
            macs (Sequence[str]): list of MAC addresses to monitor.

        Returns:
            str: response containing the channel ID

        """
        events = [{"service": f"Devices.Device.{mac.upper()}", "event": "network", "data": {"types": "network"}} for mac in macs]
        data = {"service": "eventmanager", "method": "open_channel", "parameters": {"events": events}}
        return self.post("/ws", data)

    def ethernet_ports(self, ports: Sequence[str] | None = None) -> str:
        """Open an event channel to monitor ethernet port network events.

        Subscribes to eth_device_updated and network events for each ethernet port.

        Args:
            ports (Sequence[str] | None): list of port identifiers.
                Default is ["ETH0", "ETH1", "ETH2", "ETH3", "ETH4"].

        Returns:
            str: response containing the channel ID

        """
        if ports is None:
            ports = ["ETH0", "ETH1", "ETH2", "ETH3", "ETH4"]
        events = [{"service": "Devices.Device", "event": "eth_device_updated"}]
        events.extend({"service": f"Devices.Device.{port}", "event": "network", "data": {"types": "network"}} for port in ports)
        data = {"service": "eventmanager", "method": "open_channel", "parameters": {"events": events}}
        return self.post("/ws", data)
