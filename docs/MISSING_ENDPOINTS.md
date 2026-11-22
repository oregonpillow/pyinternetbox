# Missing Endpoints

What pyinternetbox doesn't implement, and why. Found on an Internet Box 4 (IB4-00, firmware 15.21.36).

[API_MAP.md](API_MAP.md) is the complete list: every endpoint the web interface calls and every function the router exposes, with their parameters, and which ones pyinternetbox implements. `scripts/discover_endpoints.py` generates it, and its summary has the counts. This page sorts what's left: what could still be added, what's left out on purpose, what isn't possible on the internetbox4 and what isn't needed. How the implemented endpoints behave is in their methods' docstrings.

- 🌐 used by the web interface: its JavaScript, and the parameters in API_MAP.md, show how to call it
- 🚫 left out because a mistake could lock you out of the router or wipe its settings

## Adding an endpoint

An endpoint is implemented by a method in `internetbox_client/resources/`. The CLI and the MCP server are built from those methods, so a new method shows up in both without more work: as an `ibox` command, and in the MCP server's `call_router_function` (reads) or `change_router_setting` (changes). A new resource file also needs its group in `internetbox_client/client.py`. Label methods that change settings with `@write`, and those that also cut the internet, Wi-Fi or phone for others with `@disruptive` (see `internetbox_client/utils/labels.py`): the MCP server only offers them when it's allowed to.

Follow the code style and patterns in `internetbox_client/resources/`, add a unit test and an E2E test, and put what you learn about the router in the docstring. Then remove the endpoint from this page, or move it to [Not possible on the internetbox4](#not-possible-on-the-internetbox4) with the reason if the router refuses it.

## Could be added

### Wi-Fi extenders 🌐

Unpair a WLAN-Box, set its LED brightness, its backhaul and roaming settings, and read its interfaces or call its own functions (the web interface reads its station stats and temperature that way). Needs a WLAN-Box to test.

`Devices.Device.{id}.SSW:unpair`, `Devices.Device.{id}.SSW.LED.Status:set`, `SSW.Steering.Device.{id}.APRoaming.Config:get`, `set`, `SSW.Steering.Device.{id}.APRoaming:get`, `Devices.Device.{id}.LDevice:get`, `Devices.Device.{id}.SSW:execAPI`

### Other hardware 🌐

Needs the hardware, or a connection type the tested internetbox4 doesn't have:

- The mobile backup and the 5G box → `NMC.WWAN:set` (`EnableTethering`), `NMC.WWAN.Gateway:get`, `FMR5G.Devices.{id}:getResults`
- DSL lines → `NeMo.Intf.{id}:getDSLChannelStats`

### Changes that cut the connection for everyone 🌐

Each of these changes the internet connection or the home network for every device in the house, so they'd be `@disruptive`, and testing them live needs a quiet moment.

- IPv6 on or off for the internet connection → `NetMaster:set` (`EnableIPv6`)
- IPv6 prefixes for the home network → `NetMaster.LAN.default.Bridge.{id}:setIPv6Configuration` (`DHCPIAPDEnable`)
- Spanning Tree (STP) on the home network → `NeMo.Intf.{id}:setParameters` (`STPEnable` on `lan`). A wrong setting can cause a network loop.
- The fiber interface's measurement mode → `NeMo.Intf.{id}:set` (`Mode` on `veip0`, `Custom` or `Normal`). It's unclear what this changes on the fiber line.

### Small extras

- 🌐 Whether the Wi-Fi bands share their name, password and visibility → `NMC.Wifi:set` (`ConfigurationMode`). `wifi.summary()` shows it as `bands_share_settings`, and `wifi.set_enabled()` keeps it as it is.
- 🌐 One device's details → `Devices.Device.{id}:get`. `devices.get()` and `summary()` have every device's, and `lan.ethernet_port()` uses it for the Ethernet ports.
- Wi-Fi 7 MLO on or off → `SSW.DataElements.Network.APMLDTemplate.{id}:set` (`MLOEnable`)
- Turning a static route on or off → `NMC.LAN.IPv4Route.{id}:set` (`Enable`). The web interface can't either.
- The DHCP and DHCPv6 MIBs → `NeMo.Intf.data:getMIBs` (mibs `dhcp`, `dhcpv6`), and the list of the router's interfaces → `NeMo.Intf.lo:getIntfs` (traverse `all`). `lan.mibs()`, `sysbus.mibs()` and `sysbus.veip_mibs()` have the Ethernet and fiber MIBs.

The last three aren't in the web interface. [LiveboxMonitor](https://github.com/p-dor/LiveboxMonitor), a client for the French Livebox, which runs similar software, uses them or their objects.

## Left out on purpose

- 🚫 Factory reset → `NMC:reset`
- 🚫 The admin password → `NMC:changePassword`, and password recovery → `PasswordRecovery:setEnable`, `setPassword`, `start`, `stop`
- 🚫 The router's LAN address and DHCP range → `NetMaster.LAN.default.Bridge.{id}:setIPv4`. A mistake cuts every device off the router, including the one making the change.
- 🚫 Upgrading the web interface → `WebuiupgradeService:upgrade`
- 🌐 Telephony changes, not planned. The library reads the phone settings, the call list and the phone book, and changes a few of them; the MCP server leaves telephony out. The rest: DECT on or off (`NMC:set` with `GlobalEnableDect`), `DECT:setBaseState`, `setNEMoState`, `setPIN`, `startPairing`, `stopPairing`, `reset`, `removeAllHandsets`, `getRSSI`, `Devices.Device.{id}:ring`, `deRegister`, `unPair`, `VoiceService.VoiceApplication:setHandset`, `deleteHandset`, `setGroups`, `setViewedCallList`, `ring`, `startFXSDetection`, `VoiceService.VoiceApplication.VoiceProfile.SIP-Extensions.SIP:get`, `NMC.PhonebookBackup:set` and `CardDav:syncContacts`. LiveboxMonitor's way of ringing a phone didn't work on the internetbox4, but the web interface calls `VoiceService.VoiceApplication:ring` with `line` and `duration` (10000). `DECT.Repeater` has `getRepeaters()` and `removeAllRepeaters()`.

## Not possible on the internetbox4

- The internet connection's VLAN ID: there's no `VLANID` below the `data` interface, its `vlan` MIB is empty, and `admin` gets "Permission denied" for the VLAN interface itself (`NeMo.Intf.gvlan_data`).
- 🌐 The connection tracking log and the list of open connections (the web interface's "Save log file"): `Conntrack:openQuery`, `closeQuery` and `Conntrack.Query:get` need the `superadmin` user, and `admin` gets "Permission denied".
- Downloading or deleting the support log file, and clearing a device's hourly traffic snapshots: see `debug.save_log_file()` and `devices.clear_traffic_history()`.
- Functions the internetbox4 doesn't have, though LiveboxMonitor or the web interface uses them on other models:
  - restoring settings from Swisscom and automatic backups → `NMC.NetworkConfig:launchNetworkRestore`, `enableNetworkBR`
  - turning off the guest Wi-Fi's timer → `NMC.WlanTimer:disableActivationTimer`. `wifi.set_guest_enabled(True)` without `hours` keeps the guest Wi-Fi on.
  - 🌐 deep sleep → `PowerManagement:setScheduledProfiles`. The internetbox4 has no deep sleep profile.
  - DHCPv6 prefix leases → `DHCPv6.Server:getPDPrefixLeases`
  - 🌐 the screen settings of other models → `Screen:getBrightTime`, `setBrightTime`, `getLanguage`, `setLanguage`, `getShowWifiPassword`, `setShowWifiPassword`, `getShowGuestPassword`, `setShowGuestPassword`, and `NMC.MCU:get`
  - the objects `SFP`, `HomeLan` (traffic statistics; the exporter uses `getNetDevStats` and the devices' counters instead), `UplinkMonitor`, `NMC.IPv6`, `NMC.Autodetect`, `NMC.ServiceEligibility.DSLITE` (CGNAT) and `NMC.OrangeTV` (Orange's TV service)

## Not needed

- 🌐 Logging in and out: `sah.Device.Information:createContext`, `releaseContext` and `UserManagement:authenticate`. `utils/APIClient.py` does these; `scripts/discover_endpoints.py` only looks in `resources/`.
- 🌐 Calls the web interface makes for itself: `DeviceManager.Connectivity:getStatus` (checks the connection before opening a page), `UserInterface:getLanguage`, `RouterSecurityAgent.Mapping:_get` and `RouterSecurityAgent.Mapping.Settings:_get`.
- 🌐 The older L2TP and IKEv2 VPN: `VPN:getServer`, `setServer`, `getServerClient`, `setServerClient`, `disconnectServerClient`. The internetbox4's web interface only offers WireGuard.
- 🌐 `NMC:set` with `GlobalEnableWiFi`: a global switch that also hides the web interface's Wi-Fi menu. `wifi.set_enabled()` turns the Wi-Fi on or off with `NMC.Wifi:set`, like the web interface.
- 🌐 `SSW.Steering.MasterConfig.OperatingStandards:set`: the web interface uses it on other models. `wifi.set_standard()` uses `enable` and `disable`, like the internetbox4's.
- Setting any Wi-Fi parameter with `NeMo.Intf.{id}:setWLANConfig`: `wifi.set_network()`, `set_guest_network()` and `set_channel()` use it for what the web interface changes.
- LiveboxMonitor's Orange TV decoder control: it talks to the decoders and Orange's servers, not to the router.
