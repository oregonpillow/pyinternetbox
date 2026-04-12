# Missing Endpoints — a comparison against LiveboxMonitor

After initially implementing `internetbox_client/resources/` methods based on some sniffing of the internetbox 4 API calls in the webui, I found the LiveboxMonitor github repo
which attempts to, in similar fashion to this project, provide a client for the French "Livebox" router. Livebox seems to also be based on an [Askey](https://www.askey.com.tw/) platform with very similar API built by [SoftatHome](https://www.softathome.com/2022/09/26/new-wi-fi-6e-box-launched-by-swisscom-is-powered-by-softathome/)
which allowed me to discover a number of additional API endpoints that I had not yet implemented in `internetbox_client/resources/`. This document is a running list of 
the endpoints in https://github.com/p-dor/LiveboxMonitor/tree/main/src/LiveboxMonitor/api which I have not tried implementing yet into this project.

Some of the methods from LiveboxMonitor are not directly translatable to this project (e.g. TV decoder control, DECT repeater status) and some are already covered by existing methods in `internetbox_client/resources/`.


The list of method names here refer to the methods in `LiveboxMonitor/api/*.py` and the corresponding resource calls refer to the methods in `internetbox_client/resources/*.py` that would need to be implemented or extended to cover the same functionality.

If you want to contribute to this project, implementing any of the missing endpoints below would be a great way to get started! Just make sure to follow the existing code style and patterns in `internetbox_client/resources/`, add appropriate unit test + E2E test for any new methods you implement then check it off here.

if a method from Livebox doesn't work on internetbox mark it with "⚠️" and a note below.

---

## `LmBackupRestoreApi` → `nmc.py` — Write operations missing

- [ ] `set_auto_backup_enable(enable)` → `NMC.NetworkConfig:enableNetworkBR`
- [ ] `do_backup()` → `NMC.NetworkConfig:launchNetworkBackup`
- [ ] `do_restore()` → `NMC.NetworkConfig:launchNetworkRestore`

> Read-only `get_status()` → `NMC.NetworkConfig:get` is covered by `nmc.py:network_config()`.

---

## `LmDeviceApi` → `devices.py` — Write + scheduling operations missing

- [ ] `set_name(key, name)` → `Devices.Device.{key}:setName` (source=`webui`)
- [ ] `del_name(key)` → `Devices.Device.{key}:removeName` (source=`webui`)
- [ ] `set_dns_name(key, name)` → `Devices.Device.{key}:setName` (source=`dns`)
- [ ] `del_dns_name(key)` → `Devices.Device.{key}:removeName` (source=`dns`)
- [ ] `set_type(key, type)` → `Devices.Device.{key}:setType`
- [ ] `get_ip_addr(key)` → `Devices.Device.{key}:getFirstParameter` (parameter=`IPAddress`)
- [ ] `get_schedule(key)` → `Scheduler:getSchedule` (type=`ToD`)
- [ ] `override_schedule(key, value)` → `Scheduler:overrideSchedule`
- [ ] `add_schedule(key, schedule)` → `Scheduler:addSchedule` (type=`ToD`)
- [ ] `block(key)` → Composite: `getSchedule` + `overrideSchedule` / `addSchedule`
- [ ] `unblock(key)` → `Scheduler:overrideSchedule` (override=`Enable`)
- [ ] `is_blocked(key)` → `Scheduler:getSchedule`
- [ ] `delete(key)` → `Devices:destroyDevice`
- [ ] `wake_on_lan(key)` → `WOL:sendWakeOnLan`

> Read operations `get_list()`, `get_topology()`, `get_info()` are covered.

---

## `LmDhcpApi` → `dhcp.py` — Write + guest pool + DHCPv6 missing

- [ ] `get_leases(guest=True)` → `DHCPv4.Server.Pool.guest:getStaticLeases`
- [ ] `add_lease(mac, ip, guest)` → `DHCPv4.Server.Pool.{domain}:addStaticLease`
- [ ] `delete_lease(mac, guest)` → `DHCPv4.Server.Pool.{domain}:deleteStaticLease`
- [ ] `set_setup(setup)` → `NetMaster.LAN.default.Bridge.lan:setIPv4`
- [ ] `get_v6_server_status()` → `DHCPv6.Server:getDHCPv6ServerStatus`
- [ ] `get_v6_prefix_leases()` → `DHCPv6.Server:getPDPrefixLeases`
- [ ] `get_mibs(dhcp_v4, dhcp_v6)` → `NeMo.Intf.data:getMIBs` (mibs=`dhcp`/`dhcpv6`)

---

## `LmDynDnsApi` → `dyndns.py` — Write operations missing

- [ ] `set_enable(enable)` → `DynDNS:setGlobalEnable`
- [ ] `add_host(service, user, host, pw)` → `DynDNS:addHost`
- [ ] `delete_host(hostname)` → `DynDNS:delHost`

---

## `LmFirewallApi` → `firewall.py` — Nearly all write + several read operations missing

- [ ] `get_ipv4_firewall_level()` → `Firewall:getFirewallLevel`
- [ ] `set_ipv4_firewall_level(level)` → `Firewall:setFirewallLevel`
- [ ] `set_ipv6_firewall_level(level)` → `Firewall:setFirewallIPv6Level`
- [ ] `get_respond_to_ping()` → `Firewall:getRespondToPing`
- [ ] `set_respond_to_ping(enable)` → `Firewall:setRespondToPing`
- [ ] `add_dmz(id, dest_ip, ...)` → `Firewall:setDMZ`
- [ ] `delete_dmz(id)` → `Firewall:deleteDMZ`
- [ ] `set_ipv4_port_forwarding(rule)` → `Firewall:setPortForwarding`
- [ ] `del_ipv4_port_forwarding(id, origin)` → `Firewall:deletePortForwarding`
- [ ] `del_all_ipv4_port_forwarding(origin)` → `Firewall:deletePortForwarding` (all)
- [ ] `get_ipv4_protocol_forwarding()` → `Firewall:getProtocolForwarding`
- [ ] `set_ipv4_protocol_forwarding(rule)` → `Firewall:setProtocolForwarding`
- [ ] `del_ipv4_protocol_forwarding(id)` → `Firewall:deleteProtocolForwarding`
- [ ] `get_ipv6_pinhole(id, origin)` → `Firewall:getPinhole`
- [ ] `set_ipv6_pinhole(rule)` → `Firewall:setPinhole`
- [ ] `del_ipv6_pinhole(id, origin)` → `Firewall:deletePinhole`
- [ ] `commit()` → `Firewall:commit`

> Read operations `get_dmz()`, `get_ipv6_level()`, `get_port_forwarding()` are covered.

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

## `LmRebootApi` — **ENTIRELY MISSING** (no equivalent resource file)

- [ ] `get_info()` → `NMC.Reboot:get`
- [ ] `get_history()` → `NMC.Reboot.Reboot:get`
- [ ] `reboot_device(reason)` → `NMC:reboot`
- [ ] `factory_reset(reason, timeout)` → `NMC:reset`

---

## `LmRoutingApi` → `nmc.py` — Write operations missing

- [ ] `add(route)` → `NMC.LAN:addStaticRoute`
- [ ] `delete(name)` → `NMC.LAN:deleteStaticRoute`
- [ ] `set_enable(name, enable)` → `NMC.LAN.IPv4Route.{name}:set`

> `get_list()` → `NMC.LAN:getStaticRoutes` is covered by `nmc.py:static_routes()`.

---

## `LmScreenApi` → `led.py` — Screen password display missing

- [ ] `get_show_wifi_password()` → `Screen:getShowWifiPassword`
- [ ] `set_show_wifi_password(v)` → `Screen:setShowWifiPassword`

> Orange/White LED get/set are covered by `led.py` generically.

---

## `LmStatsApi` — **ENTIRELY MISSING** (HomeLan traffic statistics)

- [ ] `get_intf(key)` → `NeMo.Intf.{key}:getNetDevStats`
- [ ] `get_intf_frequency()` → `HomeLan:getReadingInterval`
- [ ] `get_device_frequency()` → `HomeLan:getDevicesReadingInterval`
- [ ] `get_intf_list()` → `HomeLan.Interface:get`
- [ ] `get_device_list()` → `HomeLan.Device:get`
- [ ] `get_intf_results(id, start, end)` → `HomeLan:getResults`
- [ ] `get_device_results(id, start, end)` → `HomeLan:getDeviceResults`
- [ ] `get_wan_counters()` → `HomeLan:getWANCounters`
- [ ] `get_intf_counters(id)` → `HomeLan.Interface.{id}.Stats:get`

> `get_wifi_intf(key)` → `NeMo.Intf.{key}:getStationStats` is partially covered by `wifi.py:station_stats()`.

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

## `LmVoipApi` → `voice.py` / `dect.py` / `phonebook.py` — Write + some read operations missing

- [ ] `delete_call(call_id)` → `VoiceService.VoiceApplication:clearCallList`
- [x] `get_contact(id)` → `Phonebook:getContactByUniqueID`
- [x] `add_contact(contact)` → `Phonebook:addContactAndGenUUID`
- [ ] `change_contact(id, contact)` → `Phonebook:modifyContactByUniqueID`
- [ ] `delete_contact(id)` → `Phonebook:removeContactByUniqueID` / `removeAllContacts`
- [ ] ⚠️ **won't work on internetbox4** `ring(ringtone)` → `VoiceService.VoiceApplication:ring`
- [x] `get_dect_name()` → `DECT:getName`
- [x] `get_dect_catiq_version()` → `DECT:getStandardVersion`
- [x] `get_dect_pairing_status()` → `DECT:getPairingStatus`
- [x] `get_dect_radio_state()` → `DECT:getRadioState`
- [ ] ⚠️ **won't work on internetbox4** `get_dect_repeater_status()` → `DECT.Repeater:get`


> Read operations `trunks()`, `call_list()`, `all_contacts()`, DECT `rfpi/pin/version` are covered.

---

## `LmWifiApi` → `wifi.py` — Write + advanced config missing

- [ ] `set_enable(enable)` → `NMC.Wifi:set` + `PowerManagement:setProfiles`
- [ ] `set_guest_enable(enable, timer)` → `NMC.Guest:set`
- [ ] `set_guest_activation_timer(timer)` → `NMC.WlanTimer:setActivationTimer`
- [ ] `disable_guest_activation_timer()` → `NMC.WlanTimer:disableActivationTimer`
- [ ] `set_configuration_mode(mode)` → `NMC.Wifi:set` (ConfigurationMode)
- [ ] `set_scheduler_enable(enable)` → `PowerManagement:setScheduledProfiles` + `Scheduler:addSchedule`
- [ ] `get_mlo_config()` → `SSW.DataElements.Network.APMLDTemplate.privMlo:get`
- [ ] `get_mlo_enable()` → Derived from `get_mlo_config()`
- [ ] `set_mlo_enable(enable)` → `SSW.DataElements.Network.APMLDTemplate.privMlo:set`
- [ ] `set_config(old, new)` → `NeMo.Intf.lan:setWLANConfig` (full SSID diff/apply)
- [ ] `set_guest_config(old, new)` → `NeMo.Intf.lan:setWLANConfig` (guest SSID diff/apply)
- [ ] `get_global_wifi_status(...)` → Composite status map across all radios
- [ ] `set_wlan_config(mibs)` → `NeMo.Intf.lan:setWLANConfig`

> Read operations `status()`, `guest()`, `activation_timer()`, `complete_schedules()`, `power_management_profiles()` are covered.

---

## Summary

| Legacy Module | Status |
|---|---|
| `LmBackupRestoreApi` | Partial — write ops missing |
| `LmDeviceApi` | Partial — device mutation + scheduling missing |
| `LmDhcpApi` | Partial — write ops + guest pool + DHCPv6 missing |
| `LmDynDnsApi` | Partial — write ops missing |
| `LmFirewallApi` | Partial — most write ops + several read ops missing |
| `LmIntfApi` | Partial — ethernet/ONT/SFP/key-list MIBs missing |
| `LmIptvApi` | **Not implemented** |
| `LmLiveboxInfoApi` | Partial — IPv6, CGNAT, VLAN, MTU, uplink missing |
| `LmRebootApi` | **Not implemented** |
| `LmRoutingApi` | Partial — write ops missing |
| `LmScreenApi` | Partial — screen password methods missing |
| `LmStatsApi` | **Not implemented** |
| `LmTvDecoderApi` | **Not implemented** (external TV decoder control) |
| `LmVoipApi` | Partial — phonebook write, DECT read, ring missing |
| `LmWifiApi` | Partial — all write/set ops missing |
