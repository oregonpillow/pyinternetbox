# Missing Endpoints — a comparison against LiveboxMonitor

> For the complete, generated list of endpoints the web interface calls and functions the router exposes, and which ones pyinternetbox implements, see [API_MAP.md](API_MAP.md) (made by `scripts/discover_endpoints.py`).

After initially implementing `internetbox_client/resources/` methods based on some sniffing of the internetbox 4 API calls in the webui, I found the LiveboxMonitor github repo
which attempts to, in similar fashion to this project, provide a client for the French "Livebox" router. Livebox seems to also be based on an [Askey](https://www.askey.com.tw/) platform with very similar API built by [SoftatHome](https://www.softathome.com/2022/09/26/new-wi-fi-6e-box-launched-by-swisscom-is-powered-by-softathome/)
which allowed me to discover a number of additional API endpoints that I had not yet implemented in `internetbox_client/resources/`. This document is a running list of 
the endpoints in https://github.com/p-dor/LiveboxMonitor/tree/main/src/LiveboxMonitor/api which I have not tried implementing yet into this project.

Some of the methods from LiveboxMonitor are not directly translatable to this project (e.g. TV decoder control, DECT repeater status) and some are already covered by existing methods in `internetbox_client/resources/`.


The list of method names here refer to the methods in `LiveboxMonitor/api/*.py` and the corresponding resource calls refer to the methods in `internetbox_client/resources/*.py` that would need to be implemented or extended to cover the same functionality.

If you want to contribute to this project, implementing any of the missing endpoints below would be a great way to get started! Just make sure to follow the existing code style and patterns in `internetbox_client/resources/`, add appropriate unit test + E2E test for any new methods you implement then check it off here.

if a method from Livebox doesn't work on internetbox mark it with "⚠️" and a note below.

Methods left out on purpose, because a mistake could lock you out of the router or wipe its settings, are marked "🚫".

---

## `LmBackupRestoreApi` → `nmc.py` — Complete for the internetbox4

- [ ] ⚠️ **won't work on internetbox4** `set_auto_backup_enable(enable)` → `NMC.NetworkConfig:enableNetworkBR`
- [x] `do_backup()` → `NMC.NetworkConfig:launchNetworkBackup`
- [ ] ⚠️ **won't work on internetbox4** `do_restore()` → `NMC.NetworkConfig:launchNetworkRestore`

> Read-only `get_status()` → `NMC.NetworkConfig:get` is covered by `nmc.py:network_config()`. `do_backup()` is `nmc.py:backup_to_swisscom()`.
>
> ⚠️ On the internetbox4, `NMC.NetworkConfig` only has `get` and `launchNetworkBackup`: there's no `enableNetworkBR` or `launchNetworkRestore` (see [API_MAP.md](API_MAP.md)).

---

## `LmDeviceApi` → `devices.py` / `scheduler.py` — Name removal, DNS names, device type and schedule override missing

- [x] `set_name(key, name)` → `Devices.Device.{key}:setName` (source=`webui`)
- [ ] `del_name(key)` → `Devices.Device.{key}:removeName` (source=`webui`)
- [ ] `set_dns_name(key, name)` → `Devices.Device.{key}:setName` (source=`dns`)
- [ ] `del_dns_name(key)` → `Devices.Device.{key}:removeName` (source=`dns`)
- [ ] `set_type(key, type)` → `Devices.Device.{key}:setType`
- [x] `get_ip_addr(key)` → `Devices.Device.{key}:getFirstParameter` (parameter=`IPAddress`)
- [x] `get_schedule(key)` → `Scheduler:getSchedule` (type=`ToD`)
- [ ] `override_schedule(key, value)` → `Scheduler:overrideSchedule`
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
> `get_schedule()` and `add_schedule()` are `scheduler.py:device_schedule()` and `set_device_schedule()`. `block()` and `unblock()` are `devices.py:block()` and `unblock()`. Like the web UI's "Internet access blocked" switch, they turn the device's schedule on or off with `Scheduler:enableSchedule` instead of `overrideSchedule`, and turn its daily time limit on or off too. `is_blocked()` is covered by `scheduler.py:device_schedule()`: its `value` is `Disable` while the device is blocked.

---

## `LmDhcpApi` → `dhcp.py` — Guest pool, DHCPv6 and MIBs missing

- [ ] `get_leases(guest=True)` → `DHCPv4.Server.Pool.guest:getStaticLeases`
- [x] `add_lease(mac, ip, guest)` → `DHCPv4.Server.Pool.{domain}:addStaticLease`
- [x] `delete_lease(mac, guest)` → `DHCPv4.Server.Pool.{domain}:deleteStaticLease`
- [ ] 🚫 `set_setup(setup)` → `NetMaster.LAN.default.Bridge.lan:setIPv4`
- [ ] `get_v6_server_status()` → `DHCPv6.Server:getDHCPv6ServerStatus`
- [ ] `get_v6_prefix_leases()` → `DHCPv6.Server:getPDPrefixLeases`
- [ ] `get_mibs(dhcp_v4, dhcp_v6)` → `NeMo.Intf.data:getMIBs` (mibs=`dhcp`/`dhcpv6`)

> `add_lease()` and `delete_lease()` are `dhcp.py:add_static_lease()` and `delete_static_lease()`, for the home network's pool (`default`) only, not the guest pool.
>
> 🚫 `set_setup()` changes the router's LAN address and DHCP range. A mistake cuts every device off the router, including the one making the change, so it's left out on purpose.

---

## `LmDynDnsApi` → `dyndns.py` — Global enable missing

- [ ] `set_enable(enable)` → `DynDNS:setGlobalEnable`
- [x] `add_host(service, user, host, pw)` → `DynDNS:addHost`
- [x] `delete_host(hostname)` → `DynDNS:delHost`

> `add_host()` is `dyndns.py:set_host()`. It replaces the host of the same service or host name, and keeps the others. The web UI deletes every host except Swisscom's when it saves one. Neither changes Swisscom's own host.

---

## `LmFirewallApi` → `firewall.py` — Ping response, protocol forwarding and IPv6 pinholes missing

- [x] `get_ipv4_firewall_level()` → `Firewall:getFirewallLevel`
- [x] `set_ipv4_firewall_level(level)` → `Firewall:setFirewallLevel`
- [x] `set_ipv6_firewall_level(level)` → `Firewall:setFirewallIPv6Level`
- [ ] `get_respond_to_ping()` → `Firewall:getRespondToPing`
- [ ] `set_respond_to_ping(enable)` → `Firewall:setRespondToPing`
- [x] `add_dmz(id, dest_ip, ...)` → `Firewall:setDMZ`
- [x] `delete_dmz(id)` → `Firewall:deleteDMZ`
- [x] `set_ipv4_port_forwarding(rule)` → `Firewall:setPortForwarding`
- [x] `del_ipv4_port_forwarding(id, origin)` → `Firewall:deletePortForwarding`
- [ ] `del_all_ipv4_port_forwarding(origin)` → `Firewall:deletePortForwarding` (all)
- [ ] `get_ipv4_protocol_forwarding()` → `Firewall:getProtocolForwarding`
- [ ] `set_ipv4_protocol_forwarding(rule)` → `Firewall:setProtocolForwarding`
- [ ] `del_ipv4_protocol_forwarding(id)` → `Firewall:deleteProtocolForwarding`
- [ ] `get_ipv6_pinhole(id, origin)` → `Firewall:getPinhole`
- [ ] `set_ipv6_pinhole(rule)` → `Firewall:setPinhole`
- [ ] `del_ipv6_pinhole(id, origin)` → `Firewall:deletePinhole`
- [x] `commit()` → `Firewall:commit`

> Read operations `get_dmz()`, `get_ipv6_level()`, `get_port_forwarding()` are covered.
>
> The levels are `firewall.py:level()`, `set_level()` and `set_ipv6_level()`. `add_dmz()` and `delete_dmz()` are `firewall.py:set_dmz()` and `delete_dmz()`, for the web UI's DMZ host (ID `webui`). `set_ipv4_port_forwarding()` and `del_ipv4_port_forwarding()` are `firewall.py:set_port_forwarding()` and `delete_port_forwarding()`, for rules made in the web UI or by pyinternetbox (origin `webui`). There's no separate `commit()`: like the web UI, every method that changes a port forwarding or custom rule commits afterwards.
>
> Not in LiveboxMonitor: the custom firewall's rules (`Firewall:setCustomRule`, `Firewall:deleteCustomRule`) and basic actions (`Firewall:getChainPolicy`, `Firewall:setChainPolicy`) are `firewall.py:custom_rules()`, `set_custom_rule()`, `enable_custom_rule()`, `delete_custom_rule()`, `custom_policy()` and `set_custom_policy()`. Turning UPnP on or off (`Firewall:set`) is `firewall.py:set_upnp_enabled()`.

---

## `LmIntfApi` — Interface MIBs (no dedicated resource file)

- [ ] `get_eth_mibs()` → `NeMo.Intf.lan:getMIBs` (mibs=`base eth`)
- [ ] `get_ont_mibs(ont_intf)` → `NeMo.Intf.{intf}:getMIBs` (mibs=`gpon`)
- [ ] `get_sfp_info()` → `SFP:get`
- [ ] `get_key_list()` → `NeMo.Intf.lo:getIntfs` (traverse=`all`)
- [ ] `get_raw_list()` → `HomeLan.Interface:get`

> `get_wifi_mibs()`, `get_raw_mibs_lan()`, `get_raw_mibs_data()` partially covered by `lan.py:mibs()` and `sysbus.py:mibs()`.

---

## `LmIptvApi` — **ENTIRELY MISSING** (no equivalent resource file)

- [ ] `get_status()` → `NMC.OrangeTV:getIPTVStatus`
- [ ] `get_multi_screens_status()` → `NMC.OrangeTV:getIPTVMultiScreens`
- [ ] `get_config()` → `NMC.OrangeTV:getIPTVConfig`

---

## `LmLiveboxInfoApi` → `devices.py` / `nmc.py` / `sysbus.py` — Several read queries missing

- [ ] `get_device_config()` → `Devices.Device.{mac}:get`
- [ ] `get_model_info()` → `UPnP-IGD:get`
- [ ] `get_vlan_id()` → `NeMo.Intf.data:getFirstParameter` (name=`VLANID`)
- [ ] `get_mtu()` → `NeMo.Intf.data:getFirstParameter` (name=`MTU`)
- [ ] `get_uplink_info()` → `UplinkMonitor.DefaultGateway:get`
- [ ] `get_ipv6_status()` → `NMC.IPv6:get`
- [ ] `get_ipv6_mode()` → `NMC.Autodetect:get`
- [ ] `get_cgnat_status()` → `NMC.ServiceEligibility.DSLITE:get`
- [ ] `set_cgnat_enable(enable)` → `NMC.ServiceEligibility.DSLITE:set`

> `get_device_info()`, `get_memory_status()`, `get_time()`, `get_wan_status()`, `get_connection_status()` are all covered.

---

## `LmRebootApi` → `nmc.py` — Reboot info and history missing

- [ ] `get_info()` → `NMC.Reboot:get`
- [ ] `get_history()` → `NMC.Reboot.Reboot:get`
- [x] `reboot_device(reason)` → `NMC:reboot`
- [ ] 🚫 `factory_reset(reason, timeout)` → `NMC:reset`

> `reboot_device()` is `nmc.py:reboot()`.
>
> 🚫 `factory_reset()` wipes all the router's settings, so it's left out on purpose.

---

## `LmRoutingApi` → `nmc.py` — Turning a route on or off missing

- [x] `add(route)` → `NMC.LAN:addStaticRoute`
- [x] `delete(name)` → `NMC.LAN:deleteStaticRoute`
- [ ] `set_enable(name, enable)` → `NMC.LAN.IPv4Route.{name}:set`

> `get_list()` → `NMC.LAN:getStaticRoutes` is covered by `nmc.py:static_routes()`.
>
> `add()` and `delete()` are `nmc.py:set_static_route()` and `delete_static_route()`. `set_static_route()` changes the gateway of an existing route through `NMC.LAN.IPv4Route.{name}:set`. Routes can't be turned off, as in the web UI. Like the web UI, `delete_static_route()` also deletes the port forwarding rules to addresses behind the route.

---

## `LmScreenApi` → `led.py` — Screen password display missing

- [ ] `get_show_wifi_password()` → `Screen:getShowWifiPassword`
- [ ] `set_show_wifi_password(v)` → `Screen:setShowWifiPassword`

> Orange/White LED get/set are covered by `led.py` generically.

---

## `LmStatsApi` → `sysbus.py` — HomeLan traffic statistics missing

- [x] `get_intf(key)` → `NeMo.Intf.{key}:getNetDevStats`
- [ ] `get_intf_frequency()` → `HomeLan:getReadingInterval`
- [ ] `get_device_frequency()` → `HomeLan:getDevicesReadingInterval`
- [ ] `get_intf_list()` → `HomeLan.Interface:get`
- [ ] `get_device_list()` → `HomeLan.Device:get`
- [ ] `get_intf_results(id, start, end)` → `HomeLan:getResults`
- [ ] `get_device_results(id, start, end)` → `HomeLan:getDeviceResults`
- [ ] `get_wan_counters()` → `HomeLan:getWANCounters`
- [ ] `get_intf_counters(id)` → `HomeLan.Interface.{id}.Stats:get`

> `get_intf()` is `sysbus.py:net_dev_stats()`. `get_wifi_intf(key)` → `NeMo.Intf.{key}:getStationStats` is partially covered by `wifi.py:station_stats()`.

---

## `LmTvDecoderApi` — **ENTIRELY MISSING** (TV decoder / Orange TV remote control)

- [ ] `load_channels()` → `https://rp-ott-mediation-tv.woopic.com/...` (external HTTP)
- [ ] `key_press(key, mode)` → `http://{decoder_ip}:8080/remoteControl/cmd?operation=01`
- [ ] `change_channel(epg)` → `http://{decoder_ip}:8080/remoteControl/cmd?operation=09`
- [ ] `get_basic_description()` → `http://{decoder_ip}:8080/BasicDeviceDescription.xml`
- [ ] `get_description()` → `http://{decoder_ip}:52235/devicedescription.xml`
- [ ] `get_status()` → `http://{decoder_ip}:8080/remoteControl/cmd?operation=10`
- [ ] `get_epg_from_number(number)` → Local channel list lookup
- [ ] `get_epg_from_name(name)` → Local channel list lookup
- [ ] `get_channel_infos(epg)` → Local + `https://proxymedia.woopic.com/...`

---

## `LmVoipApi` → `voice.py` / `dect.py` / `phonebook.py` — Ring and DECT repeater status missing

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

---

## `LmWifiApi` → `wifi.py` / `scheduler.py` — Guest timer, configuration mode and MLO missing

- [x] `set_enable(enable)` → `NMC.Wifi:set` + `PowerManagement:setProfiles`
- [x] `set_guest_enable(enable, timer)` → `NMC.Guest:set`
- [ ] `set_guest_activation_timer(timer)` → `NMC.WlanTimer:setActivationTimer`
- [ ] `disable_guest_activation_timer()` → `NMC.WlanTimer:disableActivationTimer`
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
> `set_enable()` is `wifi.py:set_enabled()` (`NMC.Wifi:set` only, like the web UI), and `set_guest_enable()` is `wifi.py:set_guest_enabled()`, which also sets the guest timer when turning the guest network on. `set_config()` and `set_guest_config()` are `wifi.py:set_network()` and `wifi.py:set_guest_network()`: name, password and visibility, through `NeMo.Intf.{access point}:setWLANConfig` like the web UI. `wifi.py` also has WPS: `set_wps_enabled()`, `start_wps_pairing()` and `stop_wps_pairing()`.
>
> `set_scheduler_enable()` is `scheduler.py:set_wifi_schedule()` and `enable_wifi_schedule()`: the Wi-Fi schedule of the web UI's power settings, saved with `Scheduler:addSchedule` (type `WLAN`). The internetbox4 has no deep sleep profile, so there's no `PowerManagement:setScheduledProfiles` call. Its other power setting, 6 GHz power saving for WLAN-Box 3 extenders, is `power_management.py:set_wifi_6ghz_power_saving()` (`PowerManagement:setTriggeredProfiles`).
>
> Not in LiveboxMonitor: `wifi.py:set_channel()` sets a band's channel and width (`NeMo.Intf.{access point}:setWLANConfig` with `wlanradio`), and `wifi.py:search_channel()` lets the router choose it again (`NeMo.Intf.{radio}:startAutoChannelSelection`).
>
> `get_global_wifi_status()` is close to `wifi.py:summary()`: whether Wi-Fi and WPS are on, and each band's name, password, channel, status and devices, for the home and guest networks.

---

## WireGuard → `wireguard.py` — not in LiveboxMonitor

- [x] Turn the VPN server on or off → `WireGuard.Server.default:_set` (`wireguard.py:set_server_enabled()`)
- [x] Add a client and get its configuration → `WireGuard.Server.default.Client:_add`, `WireGuard.Server.default.Client.{name}:_set` and `:GeneratePrivateKeyAndGetQRConfig` (`wireguard.py:add_client()`)
- [x] Change a client → `WireGuard.Server.default.Client.{name}:_set` (`wireguard.py:set_client()`)
- [x] Delete a client → `WireGuard.Server.default.Client.{name}:_del` (`wireguard.py:delete_client()`)

> The older L2TP and IKEv2 VPN server (`VPN`) isn't implemented: on the internetbox4 the web UI only offers WireGuard.

---

## Summary

| Legacy Module | Status |
|---|---|
| `LmBackupRestoreApi` | Complete for the internetbox4 — the other two methods don't exist on it |
| `LmDeviceApi` | Partial — removing names, DNS names, device type and schedule override missing |
| `LmDhcpApi` | Partial — guest pool, DHCPv6 and MIBs missing; LAN setup left out on purpose |
| `LmDynDnsApi` | Partial — global enable missing |
| `LmFirewallApi` | Partial — ping response, protocol forwarding, IPv6 pinholes and deleting all port forwards missing |
| `LmIntfApi` | Partial — ethernet/ONT/SFP/key-list MIBs missing |
| `LmIptvApi` | **Not implemented** |
| `LmLiveboxInfoApi` | Partial — IPv6, CGNAT, VLAN, MTU, uplink missing |
| `LmRebootApi` | Partial — reboot info and history missing; factory reset left out on purpose |
| `LmRoutingApi` | Partial — turning a route on or off missing (not in the web UI either) |
| `LmScreenApi` | Partial — screen password methods missing |
| `LmStatsApi` | Partial — only interface counters; HomeLan statistics missing |
| `LmTvDecoderApi` | **Not implemented** (external TV decoder control) |
| `LmVoipApi` | Partial — ring and DECT repeater status missing (neither is on the internetbox4) |
| `LmWifiApi` | Partial — guest timer, configuration mode, MLO and raw WLAN config ops missing |
