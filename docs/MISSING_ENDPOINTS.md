# Missing Endpoints

What pyinternetbox doesn't implement yet:

- [The web interface's missing endpoints](#the-web-interfaces-missing-endpoints): the endpoints the router's web interface calls that pyinternetbox doesn't implement, plus a few useful ones only the router has, starting with [what's worth adding next](#worth-adding-next).
- [Compared with LiveboxMonitor](#compared-with-liveboxmonitor): the methods of LiveboxMonitor, a client for the French Livebox router.

[API_MAP.md](API_MAP.md), made by `scripts/discover_endpoints.py`, is the complete, generated list of the endpoints the web interface calls and the functions the router exposes, and which ones pyinternetbox implements.

An endpoint is implemented by a method in `internetbox_client/resources/`. The CLI and the MCP server are built from those methods, so a new method shows up in both without more work: as an `ibox` command, and in the MCP server's `call_router_function` (reads) or `change_router_setting` (changes). A new resource file also needs its group in `internetbox_client/client.py`. Label methods that change settings with `@write`, and those that also cut the internet, Wi-Fi or phone for others with `@disruptive` (see `internetbox_client/utils/labels.py`): the MCP server only offers them when it's allowed to. The MCP server leaves out telephony (`voice`, `dect`, `phonebook` and `carddav`).

If you want to contribute to this project, implementing any of the missing endpoints below would be a great way to get started! Just make sure to follow the existing code style and patterns in `internetbox_client/resources/`, add appropriate unit test + E2E test for any new methods you implement then check it off here.

If a method doesn't work on the internetbox, mark it with "⚠️" and a note below it.

Methods left out on purpose, because a mistake could lock you out of the router or wipe its settings, are marked "🚫".

---

## The web interface's missing endpoints

From [API_MAP.md](API_MAP.md) of 2026-11-21 (IB4-00, firmware 15.21.36): the web interface calls 240 endpoints, and pyinternetbox implements all but 73. This section sorts those 73, plus a few useful ones that only the router has. The areas marked ✅ are done.

### Worth adding next

🌐 = the web interface uses the area's endpoints, so its JavaScript shows how to call them. Mark an area ✅ when it's done. Running `scripts/discover_endpoints.py` again updates each endpoint's state in API_MAP.md.

| Done | Area | What it would add | Endpoints | 🌐 |
| --- | --- | --- | --- | --- |
| ✅ | Wi-Fi band steering | Done: `wifi.set_steering_enabled()`, `set_device_steering()`, `set_standard()` and `set_wlan_box_sync()`. Like the internetbox4's web interface, `set_standard()` turns each standard on or off with `enable` and `disable`; the web interface uses `set` on other models. | `SSW.Steering:set`, `SSW.Steering.ExceptionList:createException`, `deleteException`, `SSW.Steering.MasterConfig.OperatingStandards:enable`, `disable`, `set`, `SSW.Steering.MasterConfig:set` | 🌐 |
| ✅ | DNS | Done: `dns.set_upstream_servers()`, `set_cache_enabled()` and `metrics()`. `set_upstream_servers()` also sets the DNS mode, like the web interface: `Custom` with servers, `All` (the provider's) without, so there's no separate `setMode` method. The exporter exports the DNS query counts (`internetbox_dns_*_total`). | `DNS.Server:setRoute`, `deleteRoute`, `DNS:setMode`, `DNS.Server:configureCache`, `getMetrics` | 🌐 |
| ✅ | Counters and logs | Done: `devices.reset_traffic_counters()`, `devices.clear_traffic_history()` (a Wi-Fi device's `network` log, its readings every 15 s; tested live: the `network_persistent` hourly snapshots aren't a GenLog topic on the internetbox4, so neither this nor the web interface's reset button clears them, and the "Bandwidth" totals stay), `debug.save_log_file()` and `debug.save_wifi_logs()`. ⚠️ The log file can't be downloaded: the web interface's "Save log file locally on the client" link (`/debug`) only appears on developer firmware (a version ending in e.g. `1a` or `1d`), and the router answers it with 503 on 15.21.36. Deleting the log file isn't possible either: the router refuses `NMC.Debug.DebugFile:set` with `DeleteFile` for `admin` ("Permission denied (DeleteFile)"), and the web interface has no button for it. Its connection tracking log ("Save log file", `Conntrack:openQuery` and `GenLog:readLogs`) needs the `superadmin` user; `admin` gets "Permission denied". | `Devices.Config.{id}:set` (`Reset`, id `bandwidth`), `GenLog:clearLogs`, `NMC.Debug.DebugFile:set`, `NMC.Debug:generateWiFiLogs` | 🌐 |
| ✅ | Firewall extras | Done: `firewall.respond_to_ping()`, `set_respond_to_ping()`, `protocol_forwarding()`, `set_protocol_forwarding()`, `delete_protocol_forwarding()`, `ipv6_pinholes()`, `set_ipv6_pinhole()`, `delete_ipv6_pinhole()` and `delete_all_port_forwarding()`. | `Firewall:getRespondToPing`, `setRespondToPing`, `getProtocolForwarding`, `setProtocolForwarding`, `deleteProtocolForwarding`, `getPinhole`, `setPinhole`, `deletePinhole`, `deletePortForwarding` (all) | |
| ✅ | Devices | Done: `devices.set_type()`, `set_dns_name()`, `remove_dns_name()` and `reset_name()`. `set_type()` sets `DeviceType` with `Devices.Device.{id}:set`, like the web interface, instead of `setType`. Tested live: a DNS name works straight away, also as `<name>.home`, and replaces the displayed name in the router's DNS until it's removed. | `Devices.Device.{id}:setType`, `setName` (source `dns`), `removeName` | |
| ✅ | WireGuard | Done: `wireguard.set_enabled()`, and `set_server_enabled(True)` and `add_client()` create the server first on a router without one. Tested live: while WireGuard is off, its `Status` is `Disabled`, the server and clients stay, and turning it on brings them back unchanged. The web interface defines `WireGuard:_set` but never calls it. Like the web interface, `WireGuard.Server:_add` is sent without parameters: the router names the server itself and allows only one. It refused a second server with "duplicate keys", with or without an `Alias`, port or subnet, so creating one couldn't be tested on a router that has one. | `WireGuard:_set`, `WireGuard.Server:_add` | 🌐 |
| ✅ | Small extras | Done: `dyndns.set_enabled()`, `dhcp.ipv6_server_status()`, `pool="guest"` for `dhcp.static_leases()`, `add_static_lease()` and `delete_static_lease()`, `scheduler.override_device_schedule()` and `firewall.upnp_description()`. Tested live: while DynDNS is off, each host's `status` is `BLOCKED`, and turning it on updates them again within seconds. The guest pool (`10.128.0.0/16`) refuses addresses outside its network and the router's own, and a reservation creates a device entry, like on the home network. `overrideSchedule` lasts until it's set back to `""`, also through turning the schedule off and on; `addSchedule` ends it. `overrideState` (`until_next_change=True`) sets `temporaryOverride` and lasts until the schedule next switches the other way. Neither works without a schedule ("Invalid function parameter (ID)"), and an override has no effect while the schedule is off. | `DynDNS:setGlobalEnable`, `DHCPv6.Server:getDHCPv6ServerStatus`, `DHCPv4.Server.Pool.{id}:getStaticLeases` (id `guest`), `Scheduler:overrideSchedule`, `overrideState`, `UPnP-IGD:get` | |
| ⬜ | Wi-Fi extenders | Unpair a WLAN-Box, set its LED brightness, its backhaul and roaming settings, and read its interfaces or call its own functions (the web interface reads its station stats and temperature that way). Needs a WLAN-Box to test. | `Devices.Device.{id}.SSW:unpair`, `Devices.Device.{id}.SSW.LED.Status:set`, `SSW.Steering.Device.{id}.APRoaming.Config:get`, `set`, `SSW.Steering.Device.{id}.APRoaming:get`, `Devices.Device.{id}.LDevice:get`, `Devices.Device.{id}.SSW:execAPI` | 🌐 |
| ⬜ | Telephony (library only) | DECT on or off, eco mode, PIN, pairing, reset, removing all handsets, the DECT signal strength, ringing or unpairing a handset, unpairing a DECT repeater, naming DECT ULE devices, handset settings, ring groups, marking calls as seen, ringing a line, detecting phones on the analog ports, the SIP settings, phonebook backup and CardDAV sync. | `NMC:set` (`GlobalEnableDect`), `DECT:setBaseState`, `setNEMoState`, `setPIN`, `startPairing`, `stopPairing`, `reset`, `removeAllHandsets`, `getRSSI`, `Devices.Device.{id}:ring`, `deRegister`, `unPair`, `setName`, `VoiceService.VoiceApplication:setHandset`, `deleteHandset`, `setGroups`, `setViewedCallList`, `ring`, `startFXSDetection`, `VoiceService.VoiceApplication.VoiceProfile.SIP-Extensions.SIP:get`, `NMC.PhonebookBackup:set`, `CardDav:syncContacts` | 🌐 |

### Possible, but risky

Each of these changes the internet connection or the home network for every device in the house, so they'd be `@disruptive`, and testing them live needs a quiet moment.

- [ ] IPv6 on or off for the internet connection → `NetMaster:set` (`EnableIPv6`)
- [ ] IPv6 prefixes for the home network → `NetMaster.LAN.default.Bridge.{id}:setIPv6Configuration` (`DHCPIAPDEnable`)
- [ ] Spanning Tree (STP) on the home network → `NeMo.Intf.{id}:setParameters` (`STPEnable` on `lan`). A wrong setting can cause a network loop.
- [ ] The fiber interface's measurement mode → `NeMo.Intf.{id}:set` (`Mode` on `veip0`, `Custom` or `Normal`). It's unclear what this changes on the fiber line.

### Left out on purpose

- [ ] 🚫 Factory reset → `NMC:reset`
- [ ] 🚫 The admin password → `NMC:changePassword`, and password recovery → `PasswordRecovery:setEnable`, `setPassword`, `start`, `stop`
- [ ] 🚫 The router's LAN address and DHCP range → `NetMaster.LAN.default.Bridge.{id}:setIPv4`
- [ ] 🚫 Upgrading the web interface → `WebuiupgradeService:upgrade`

### Not needed, or not on the internetbox4

The rest of the web interface's 73:

- Logging in and out: `sah.Device.Information:createContext`, `releaseContext` and `UserManagement:authenticate`. `utils/APIClient.py` does these; `scripts/discover_endpoints.py` only looks in `resources/`.
- Not in the internetbox4's self-description, so probably for other models that share the web interface: `Screen:getBrightTime`, `setBrightTime`, `getLanguage`, `setLanguage`, `getShowWifiPassword`, `setShowWifiPassword`, `getShowGuestPassword`, `setShowGuestPassword`, and the list of open connections, `Conntrack:openQuery`, `closeQuery` and `Conntrack.Query:get`. The web interface only calls `NMC.MCU:get` on another model (`stargatev5pro`).
- Hardware or a connection type the tested internetbox4 doesn't have: the mobile backup and the 5G box (`NMC.WWAN:set` with `EnableTethering`, `NMC.WWAN.Gateway:get`, `FMR5G.Devices.{id}:getResults`), the Internet Booster (`Devices.Device.{id}.UDevice:get`), DSL lines (`NeMo.Intf.{id}:getDSLChannelStats`) and deep sleep (`PowerManagement:setScheduledProfiles`; the internetbox4 has no deep sleep profile).
- The older L2TP and IKEv2 VPN: `VPN:getServer`, `setServer`, `getServerClient`, `setServerClient`, `disconnectServerClient`. The internetbox4's web interface only offers WireGuard.
- For the web interface itself: `DeviceManager.Connectivity:getStatus` (checks the connection before opening a page), `UserInterface:getLanguage`, `RouterSecurityAgent.Mapping:_get` and `RouterSecurityAgent.Mapping.Settings:_get`.
- `NMC:set` with `GlobalEnableWiFi`: a global switch that also hides the web interface's Wi-Fi menu. `wifi.set_enabled()` already turns the Wi-Fi on or off, with `NMC.Wifi:set` like the web interface.

---

## Compared with LiveboxMonitor

After initially implementing `internetbox_client/resources/` methods based on some sniffing of the internetbox 4 API calls in the webui, I found the LiveboxMonitor github repo
which attempts to, in similar fashion to this project, provide a client for the French "Livebox" router. Livebox seems to also be based on an [Askey](https://www.askey.com.tw/) platform with very similar API built by [SoftatHome](https://www.softathome.com/2022/09/26/new-wi-fi-6e-box-launched-by-swisscom-is-powered-by-softathome/)
which allowed me to discover a number of additional API endpoints that I had not yet implemented in `internetbox_client/resources/`. This document is a running list of 
the endpoints in https://github.com/p-dor/LiveboxMonitor/tree/main/src/LiveboxMonitor/api which I have not tried implementing yet into this project.

Some of the methods from LiveboxMonitor are not directly translatable to this project (e.g. TV decoder control, DECT repeater status) and some are already covered by existing methods in `internetbox_client/resources/`.


The list of method names here refer to the methods in `LiveboxMonitor/api/*.py` and the corresponding resource calls refer to the methods in `internetbox_client/resources/*.py` that would need to be implemented or extended to cover the same functionality. Methods marked "⚠️" don't exist on the internetbox4, according to its self-description in [API_MAP.md](API_MAP.md), or didn't work when tried.

---

### `LmBackupRestoreApi` → `nmc.py` — Complete for the internetbox4

- [ ] ⚠️ **won't work on internetbox4** `set_auto_backup_enable(enable)` → `NMC.NetworkConfig:enableNetworkBR`
- [x] `do_backup()` → `NMC.NetworkConfig:launchNetworkBackup`
- [ ] ⚠️ **won't work on internetbox4** `do_restore()` → `NMC.NetworkConfig:launchNetworkRestore`

> Read-only `get_status()` → `NMC.NetworkConfig:get` is covered by `nmc.py:network_config()`. `do_backup()` is `nmc.py:backup_to_swisscom()`.
>
> ⚠️ On the internetbox4, `NMC.NetworkConfig` only has `get` and `launchNetworkBackup`: there's no `enableNetworkBR` or `launchNetworkRestore` (see [API_MAP.md](API_MAP.md)).

---

### `LmDeviceApi` → `devices.py` / `scheduler.py` — Complete

- [x] `set_name(key, name)` → `Devices.Device.{key}:setName` (source=`webui`)
- [x] `del_name(key)` → `Devices.Device.{key}:removeName` (source=`webui`)
- [x] `set_dns_name(key, name)` → `Devices.Device.{key}:setName` (source=`dns`)
- [x] `del_dns_name(key)` → `Devices.Device.{key}:removeName` (source=`dns`)
- [x] `set_type(key, type)` → `Devices.Device.{key}:setType`
- [x] `get_ip_addr(key)` → `Devices.Device.{key}:getFirstParameter` (parameter=`IPAddress`)
- [x] `get_schedule(key)` → `Scheduler:getSchedule` (type=`ToD`)
- [x] `override_schedule(key, value)` → `Scheduler:overrideSchedule`
- [x] `add_schedule(key, schedule)` → `Scheduler:addSchedule` (type=`ToD`)
- [x] `block(key)` → Composite: `getSchedule` + `overrideSchedule` / `addSchedule`
- [x] `unblock(key)` → `Scheduler:overrideSchedule` (override=`Enable`)
- [x] `is_blocked(key)` → `Scheduler:getSchedule`
- [x] `delete(key)` → `Devices:destroyDevice`
- [x] `wake_on_lan(key)` → `WOL:sendWakeOnLan`

> Read operations `get_list()`, `get_topology()`, `get_info()` are covered.
>
> `set_name()` is `devices.py:rename()`, which sets `Name` through `Devices.Device.{key}:set` like the web UI. `get_ip_addr()` is covered by `devices.py:summary()`, which lists every device's addresses. `delete()` is `devices.py:remove()`, and `wake_on_lan()` is `devices.py:wake_on_lan()`.
>
> `del_name()` is `devices.py:reset_name()`, and `set_dns_name()` and `del_dns_name()` are `devices.py:set_dns_name()` and `remove_dns_name()`. `set_type()` is `devices.py:set_type()`, which sets `DeviceType` through `Devices.Device.{key}:set` like the web UI, and only accepts the types the web UI offers (`devices.DEVICE_TYPES`).
>
> `get_schedule()` and `add_schedule()` are `scheduler.py:device_schedule()` and `set_device_schedule()`. `override_schedule()` is `scheduler.py:override_device_schedule()`, with `"allow"`, `"block"` or `"schedule"` for the router's `Enable`, `Disable` or `""`; with `until_next_change=True` it uses `Scheduler:overrideState` instead, which lasts until the schedule next switches the other way. `block()` and `unblock()` are `devices.py:block()` and `unblock()`. Like the web UI's "Internet access blocked" switch, they turn the device's schedule on or off with `Scheduler:enableSchedule` instead of `overrideSchedule`, and turn its daily time limit on or off too. `block()` also ends an override that allows access. `is_blocked()` is covered by `scheduler.py:device_schedule()`: its `value` is `Disable` while the device is blocked.

---

### `LmDhcpApi` → `dhcp.py` — MIBs missing

- [x] `get_leases(guest=True)` → `DHCPv4.Server.Pool.guest:getStaticLeases`
- [x] `add_lease(mac, ip, guest)` → `DHCPv4.Server.Pool.{domain}:addStaticLease`
- [x] `delete_lease(mac, guest)` → `DHCPv4.Server.Pool.{domain}:deleteStaticLease`
- [ ] 🚫 `set_setup(setup)` → `NetMaster.LAN.default.Bridge.lan:setIPv4`
- [x] `get_v6_server_status()` → `DHCPv6.Server:getDHCPv6ServerStatus`
- [ ] ⚠️ **not on the internetbox4** `get_v6_prefix_leases()` → `DHCPv6.Server:getPDPrefixLeases`
- [ ] `get_mibs(dhcp_v4, dhcp_v6)` → `NeMo.Intf.data:getMIBs` (mibs=`dhcp`/`dhcpv6`)

> `get_leases()`, `add_lease()` and `delete_lease()` are `dhcp.py:static_leases()`, `add_static_lease()` and `delete_static_lease()`, with `pool="default"` (the home network) or `pool="guest"` (the guest Wi-Fi) instead of `guest`. The internetbox4's third pool, `fmr5gmgt`, seems to be for the 5G box's management network, so the methods refuse it. `get_v6_server_status()` is `dhcp.py:ipv6_server_status()`.
>
> ⚠️ The internetbox4's `DHCPv6.Server` has no `getPDPrefixLeases`.
>
> 🚫 `set_setup()` changes the router's LAN address and DHCP range. A mistake cuts every device off the router, including the one making the change, so it's left out on purpose.

---

### `LmDynDnsApi` → `dyndns.py` — Complete

- [x] `set_enable(enable)` → `DynDNS:setGlobalEnable`
- [x] `add_host(service, user, host, pw)` → `DynDNS:addHost`
- [x] `delete_host(hostname)` → `DynDNS:delHost`

> `set_enable()` is `dyndns.py:set_enabled()`. `add_host()` is `dyndns.py:set_host()`. It replaces the host of the same service or host name, and keeps the others. The web UI deletes every host except Swisscom's when it saves one. Neither changes Swisscom's own host.

---

### `LmFirewallApi` → `firewall.py` — Complete

- [x] `get_ipv4_firewall_level()` → `Firewall:getFirewallLevel`
- [x] `set_ipv4_firewall_level(level)` → `Firewall:setFirewallLevel`
- [x] `set_ipv6_firewall_level(level)` → `Firewall:setFirewallIPv6Level`
- [x] `get_respond_to_ping()` → `Firewall:getRespondToPing`
- [x] `set_respond_to_ping(enable)` → `Firewall:setRespondToPing`
- [x] `add_dmz(id, dest_ip, ...)` → `Firewall:setDMZ`
- [x] `delete_dmz(id)` → `Firewall:deleteDMZ`
- [x] `set_ipv4_port_forwarding(rule)` → `Firewall:setPortForwarding`
- [x] `del_ipv4_port_forwarding(id, origin)` → `Firewall:deletePortForwarding`
- [x] `del_all_ipv4_port_forwarding(origin)` → `Firewall:deletePortForwarding` (all)
- [x] `get_ipv4_protocol_forwarding()` → `Firewall:getProtocolForwarding`
- [x] `set_ipv4_protocol_forwarding(rule)` → `Firewall:setProtocolForwarding`
- [x] `del_ipv4_protocol_forwarding(id)` → `Firewall:deleteProtocolForwarding`
- [x] `get_ipv6_pinhole(id, origin)` → `Firewall:getPinhole`
- [x] `set_ipv6_pinhole(rule)` → `Firewall:setPinhole`
- [x] `del_ipv6_pinhole(id, origin)` → `Firewall:deletePinhole`
- [x] `commit()` → `Firewall:commit`

> Read operations `get_dmz()`, `get_ipv6_level()`, `get_port_forwarding()` are covered.
>
> The levels are `firewall.py:level()`, `set_level()` and `set_ipv6_level()`. `add_dmz()` and `delete_dmz()` are `firewall.py:set_dmz()` and `delete_dmz()`, for the web UI's DMZ host (ID `webui`). `set_ipv4_port_forwarding()` and `del_ipv4_port_forwarding()` are `firewall.py:set_port_forwarding()` and `delete_port_forwarding()`, for rules made in the web UI or by pyinternetbox (origin `webui`). There's no separate `commit()`: like the web UI, every method that changes a port forwarding or custom rule commits afterwards.
>
> Not in LiveboxMonitor: the custom firewall's rules (`Firewall:setCustomRule`, `Firewall:deleteCustomRule`) and basic actions (`Firewall:getChainPolicy`, `Firewall:setChainPolicy`) are `firewall.py:custom_rules()`, `set_custom_rule()`, `enable_custom_rule()`, `delete_custom_rule()`, `custom_policy()` and `set_custom_policy()`. Turning UPnP on or off (`Firewall:set`) is `firewall.py:set_upnp_enabled()`.
>
> The internetbox4's web interface doesn't use the ping response, protocol forwarding or IPv6 pinholes; `firewall.py` calls them like LiveboxMonitor. `respond_to_ping()` and `set_respond_to_ping()` are for pings from the internet (source interface `data`); `set_respond_to_ping()` can change IPv4 or IPv6 alone. `set_protocol_forwarding()` takes protocol numbers or the names `gre`, `esp` and `ah`. `set_ipv6_pinhole()` leaves the source port empty, like LiveboxMonitor, which found that it doesn't work, at least on a Livebox 5. `del_all_ipv4_port_forwarding()` is `firewall.py:delete_all_port_forwarding()`, for the rules made in the web UI or by pyinternetbox; ports opened with UPnP stay open.

---

### `LmIntfApi` — Interface MIBs (no dedicated resource file)

- [ ] `get_eth_mibs()` → `NeMo.Intf.lan:getMIBs` (mibs=`base eth`)
- [ ] `get_ont_mibs(ont_intf)` → `NeMo.Intf.{intf}:getMIBs` (mibs=`gpon`)
- [ ] ⚠️ **not on the internetbox4** `get_sfp_info()` → `SFP:get`
- [ ] `get_key_list()` → `NeMo.Intf.lo:getIntfs` (traverse=`all`)
- [ ] ⚠️ **not on the internetbox4** `get_raw_list()` → `HomeLan.Interface:get`

> `get_wifi_mibs()`, `get_raw_mibs_lan()`, `get_raw_mibs_data()` partially covered by `lan.py:mibs()` and `sysbus.py:mibs()`.
>
> ⚠️ The internetbox4 has no `SFP` or `HomeLan` objects.

---

### `LmIptvApi` — Not on the internetbox4

- [ ] ⚠️ `get_status()` → `NMC.OrangeTV:getIPTVStatus`
- [ ] ⚠️ `get_multi_screens_status()` → `NMC.OrangeTV:getIPTVMultiScreens`
- [ ] ⚠️ `get_config()` → `NMC.OrangeTV:getIPTVConfig`

> ⚠️ The internetbox4 has no `NMC.OrangeTV` object: it's for Orange's TV service.

---

### `LmLiveboxInfoApi` → `devices.py` / `nmc.py` / `sysbus.py` / `firewall.py` — Device config, VLAN and MTU missing

- [ ] `get_device_config()` → `Devices.Device.{mac}:get`
- [x] `get_model_info()` → `UPnP-IGD:get`
- [ ] `get_vlan_id()` → `NeMo.Intf.data:getFirstParameter` (name=`VLANID`)
- [ ] `get_mtu()` → `NeMo.Intf.data:getFirstParameter` (name=`MTU`)
- [ ] ⚠️ **not on the internetbox4** `get_uplink_info()` → `UplinkMonitor.DefaultGateway:get`
- [ ] ⚠️ **not on the internetbox4** `get_ipv6_status()` → `NMC.IPv6:get`
- [ ] ⚠️ **not on the internetbox4** `get_ipv6_mode()` → `NMC.Autodetect:get`
- [ ] ⚠️ **not on the internetbox4** `get_cgnat_status()` → `NMC.ServiceEligibility.DSLITE:get`
- [ ] ⚠️ **not on the internetbox4** `set_cgnat_enable(enable)` → `NMC.ServiceEligibility.DSLITE:set`

> `get_device_info()`, `get_memory_status()`, `get_time()`, `get_wan_status()`, `get_connection_status()` are all covered. `get_model_info()` is `firewall.py:upnp_description()`, next to the UPnP port forwarding switch.
>
> ⚠️ The internetbox4 has no `UplinkMonitor`, `NMC.IPv6`, `NMC.Autodetect` or `NMC.ServiceEligibility.DSLITE` objects.

---

### `LmRebootApi` → `nmc.py` — Reboot info missing

- [ ] `get_info()` → `NMC.Reboot:get`
- [ ] ⚠️ **not on the internetbox4** `get_history()` → `NMC.Reboot.Reboot:get`
- [x] `reboot_device(reason)` → `NMC:reboot`
- [ ] 🚫 `factory_reset(reason, timeout)` → `NMC:reset`

> `reboot_device()` is `nmc.py:reboot()`.
>
> ⚠️ The internetbox4's `NMC.Reboot` has no `Reboot` list of past restarts.
>
> 🚫 `factory_reset()` wipes all the router's settings, so it's left out on purpose.

---

### `LmRoutingApi` → `nmc.py` — Turning a route on or off missing

- [x] `add(route)` → `NMC.LAN:addStaticRoute`
- [x] `delete(name)` → `NMC.LAN:deleteStaticRoute`
- [ ] `set_enable(name, enable)` → `NMC.LAN.IPv4Route.{name}:set`

> `get_list()` → `NMC.LAN:getStaticRoutes` is covered by `nmc.py:static_routes()`.
>
> `add()` and `delete()` are `nmc.py:set_static_route()` and `delete_static_route()`. `set_static_route()` changes the gateway of an existing route through `NMC.LAN.IPv4Route.{name}:set`. Routes can't be turned off, as in the web UI. Like the web UI, `delete_static_route()` also deletes the port forwarding rules to addresses behind the route.

---

### `LmScreenApi` → `led.py` — Not on the internetbox4

- [ ] ⚠️ `get_show_wifi_password()` → `Screen:getShowWifiPassword`
- [ ] ⚠️ `set_show_wifi_password(v)` → `Screen:setShowWifiPassword`

> Orange/White LED get/set are covered by `led.py` generically.
>
> ⚠️ The internetbox4 has no `Screen` object. Its web interface has code for one, probably for other models.

---

### `LmStatsApi` → `sysbus.py` — Complete for the internetbox4

- [x] `get_intf(key)` → `NeMo.Intf.{key}:getNetDevStats`
- [ ] ⚠️ `get_intf_frequency()` → `HomeLan:getReadingInterval`
- [ ] ⚠️ `get_device_frequency()` → `HomeLan:getDevicesReadingInterval`
- [ ] ⚠️ `get_intf_list()` → `HomeLan.Interface:get`
- [ ] ⚠️ `get_device_list()` → `HomeLan.Device:get`
- [ ] ⚠️ `get_intf_results(id, start, end)` → `HomeLan:getResults`
- [ ] ⚠️ `get_device_results(id, start, end)` → `HomeLan:getDeviceResults`
- [ ] ⚠️ `get_wan_counters()` → `HomeLan:getWANCounters`
- [ ] ⚠️ `get_intf_counters(id)` → `HomeLan.Interface.{id}.Stats:get`

> `get_intf()` is `sysbus.py:net_dev_stats()`. `get_wifi_intf(key)` → `NeMo.Intf.{key}:getStationStats` is partially covered by `wifi.py:station_stats()`.
>
> ⚠️ The internetbox4 has no `HomeLan` object. The exporter gets traffic from `NeMo.Intf.{key}:getNetDevStats` and the devices' counters instead.

---

### `LmTvDecoderApi` — Not for the internetbox (Orange TV decoders)

- [ ] `load_channels()` → `https://rp-ott-mediation-tv.woopic.com/...` (external HTTP)
- [ ] `key_press(key, mode)` → `http://{decoder_ip}:8080/remoteControl/cmd?operation=01`
- [ ] `change_channel(epg)` → `http://{decoder_ip}:8080/remoteControl/cmd?operation=09`
- [ ] `get_basic_description()` → `http://{decoder_ip}:8080/BasicDeviceDescription.xml`
- [ ] `get_description()` → `http://{decoder_ip}:52235/devicedescription.xml`
- [ ] `get_status()` → `http://{decoder_ip}:8080/remoteControl/cmd?operation=10`
- [ ] `get_epg_from_number(number)` → Local channel list lookup
- [ ] `get_epg_from_name(name)` → Local channel list lookup
- [ ] `get_channel_infos(epg)` → Local + `https://proxymedia.woopic.com/...`

> These talk to Orange's TV decoders and Orange's servers, not to the router, so they don't apply to the internetbox.

---

### `LmVoipApi` → `voice.py` / `dect.py` / `phonebook.py` — Ring and DECT repeater status missing

- [x] `delete_call(call_id)` → `VoiceService.VoiceApplication:clearCallList`
- [x] `get_contact(id)` → `Phonebook:getContactByUniqueID`
- [x] `add_contact(contact)` → `Phonebook:addContactAndGenUUID`
- [x] `change_contact(id, contact)` → `Phonebook:modifyContactByUniqueID`
- [x] `delete_contact(id)` → `Phonebook:removeContactByUniqueID` / `removeAllContacts`
- [ ] ⚠️ **won't work on internetbox4** `ring(ringtone)` → `VoiceService.VoiceApplication:ring`
- [x] `get_dect_name()` → `DECT:getName`
- [x] `get_dect_catiq_version()` → `DECT:getStandardVersion`
- [x] `get_dect_pairing_status()` → `DECT:getPairingStatus`
- [x] `get_dect_radio_state()` → `DECT:getRadioState`
- [ ] ⚠️ **won't work on internetbox4** `get_dect_repeater_status()` → `DECT.Repeater:get`


> Read operations `trunks()`, `call_list()`, `all_contacts()`, DECT `rfpi/pin/version` are covered.
>
> `change_contact()` is `phonebook.py:modify_contact()`. `delete_contact()` deletes one contact (`removeAllContacts` isn't implemented), and `voice.py:clear_call_list()` deletes all calls.
>
> Worth trying again: the internetbox4's web interface rings a line with `VoiceService.VoiceApplication:ring` and the parameters `line` and `duration` (10000), and a DECT handset with `Devices.Device.{id}:ring`. Its `DECT.Repeater` object has `getRepeaters()` and `removeAllRepeaters()`.

---

### `LmWifiApi` → `wifi.py` / `scheduler.py` — Configuration mode, MLO and raw WLAN config missing

- [x] `set_enable(enable)` → `NMC.Wifi:set` + `PowerManagement:setProfiles`
- [x] `set_guest_enable(enable, timer)` → `NMC.Guest:set`
- [x] `set_guest_activation_timer(timer)` → `NMC.WlanTimer:setActivationTimer`
- [ ] ⚠️ **not on the internetbox4** `disable_guest_activation_timer()` → `NMC.WlanTimer:disableActivationTimer`
- [ ] `set_configuration_mode(mode)` → `NMC.Wifi:set` (ConfigurationMode)
- [x] `set_scheduler_enable(enable)` → `PowerManagement:setScheduledProfiles` + `Scheduler:addSchedule`
- [ ] `get_mlo_config()` → `SSW.DataElements.Network.APMLDTemplate.privMlo:get`
- [ ] `get_mlo_enable()` → Derived from `get_mlo_config()`
- [ ] `set_mlo_enable(enable)` → `SSW.DataElements.Network.APMLDTemplate.privMlo:set`
- [x] `set_config(old, new)` → `NeMo.Intf.lan:setWLANConfig` (full SSID diff/apply)
- [x] `set_guest_config(old, new)` → `NeMo.Intf.lan:setWLANConfig` (guest SSID diff/apply)
- [x] `get_global_wifi_status(...)` → Composite status map across all radios
- [ ] `set_wlan_config(mibs)` → `NeMo.Intf.lan:setWLANConfig`

> Read operations `status()`, `guest()`, `activation_timer()`, `complete_schedules()`, `power_management_profiles()` are covered.
>
> `set_enable()` is `wifi.py:set_enabled()` (`NMC.Wifi:set` only, like the web UI), and `set_guest_enable()` and `set_guest_activation_timer()` are `wifi.py:set_guest_enabled()`, which also sets the guest timer (`hours`) when turning the guest network on. `set_config()` and `set_guest_config()` are `wifi.py:set_network()` and `wifi.py:set_guest_network()`: name, password and visibility, through `NeMo.Intf.{access point}:setWLANConfig` like the web UI. `wifi.py` also has WPS: `set_wps_enabled()`, `start_wps_pairing()` and `stop_wps_pairing()`.
>
> ⚠️ The internetbox4's `NMC.WlanTimer` has no `disableActivationTimer`. `set_guest_enabled(True)` sets the timer to 0, so the guest network stays on until it's turned off.
>
> `set_configuration_mode()` would set whether the bands share their name, password and visibility (`ConfigurationMode`, shown as `bands_share_settings` by `wifi.py:summary()`). For MLO, the internetbox4 has `SSW.DataElements.Network.APMLDTemplate.{id}` objects with a writable `MLOEnable`.
>
> `set_scheduler_enable()` is `scheduler.py:set_wifi_schedule()` and `enable_wifi_schedule()`: the Wi-Fi schedule of the web UI's power settings, saved with `Scheduler:addSchedule` (type `WLAN`). The internetbox4 has no deep sleep profile, so there's no `PowerManagement:setScheduledProfiles` call. Its other power setting, 6 GHz power saving for WLAN-Box 3 extenders, is `power_management.py:set_wifi_6ghz_power_saving()` (`PowerManagement:setTriggeredProfiles`).
>
> Not in LiveboxMonitor: `wifi.py:set_channel()` sets a band's channel and width (`NeMo.Intf.{access point}:setWLANConfig` with `wlanradio`), and `wifi.py:search_channel()` lets the router choose it again (`NeMo.Intf.{radio}:startAutoChannelSelection`). Band steering, like the web UI: `wifi.py:set_steering_enabled()` (`SSW.Steering:set`), `set_device_steering()` (`SSW.Steering.ExceptionList:createException`, `deleteException`), `set_standard()` (`SSW.Steering.MasterConfig.OperatingStandards:enable`, `disable`) and `set_wlan_box_sync()` (`SSW.Steering.MasterConfig:set`).
>
> `get_global_wifi_status()` is close to `wifi.py:summary()`: whether Wi-Fi and WPS are on, and each band's name, password, channel, status and devices, for the home and guest networks.

---

### WireGuard → `wireguard.py` — not in LiveboxMonitor

- [x] Turn WireGuard as a whole on or off → `WireGuard:_set` (`wireguard.py:set_enabled()`)
- [x] Create the VPN server if the router has none → `WireGuard.Server:_add` (`set_server_enabled(True)` and `add_client()`)
- [x] Turn the VPN server on or off → `WireGuard.Server.default:_set` (`wireguard.py:set_server_enabled()`)
- [x] Add a client and get its configuration → `WireGuard.Server.default.Client:_add`, `WireGuard.Server.default.Client.{name}:_set` and `:GeneratePrivateKeyAndGetQRConfig` (`wireguard.py:add_client()`)
- [x] Change a client → `WireGuard.Server.default.Client.{name}:_set` (`wireguard.py:set_client()`)
- [x] Delete a client → `WireGuard.Server.default.Client.{name}:_del` (`wireguard.py:delete_client()`)

> The older L2TP and IKEv2 VPN server (`VPN`) isn't implemented: on the internetbox4 the web UI only offers WireGuard.

---

### Summary

| Legacy Module | Status |
|---|---|
| `LmBackupRestoreApi` | Complete for the internetbox4 — the other two methods don't exist on it |
| `LmDeviceApi` | Complete |
| `LmDhcpApi` | Partial — MIBs missing; LAN setup left out on purpose; prefix leases aren't on the internetbox4 |
| `LmDynDnsApi` | Complete |
| `LmFirewallApi` | Complete |
| `LmIntfApi` | Partial — ethernet/ONT/key-list MIBs missing; SFP and HomeLan aren't on the internetbox4 |
| `LmIptvApi` | Not on the internetbox4 |
| `LmLiveboxInfoApi` | Partial — device config, VLAN and MTU missing; IPv6, CGNAT and uplink aren't on the internetbox4 |
| `LmRebootApi` | Partial — reboot info missing; history isn't on the internetbox4; factory reset left out on purpose |
| `LmRoutingApi` | Partial — turning a route on or off missing (not in the web UI either) |
| `LmScreenApi` | Not on the internetbox4 |
| `LmStatsApi` | Complete for the internetbox4 — HomeLan isn't on it |
| `LmTvDecoderApi` | Not for the internetbox (Orange TV decoders) |
| `LmVoipApi` | Partial — ring and DECT repeater status missing (neither worked on the internetbox4) |
| `LmWifiApi` | Partial — configuration mode, MLO and raw WLAN config ops missing |
