# Usage without a password

A limited selection of methods are available without authentication, which means they can be used even if you don't have the password to your router.

| **Method**              | **API**                           | **CLI**                         |
| ----------------------- | --------------------------------- | ------------------------------- |
| Devices.info            | `ibox.devices.info()`             | `ibox devices info`             |
| DNS.status              | `ibox.dns.status()`               | `ibox dns status`               |
| Mitigation.status       | `ibox.mitigation.status()`        | `ibox mitigation status`        |
| NMC.status              | `ibox.nmc.status()`               | `ibox nmc status`               |
| NMC.ip_conflicts        | `ibox.nmc.ip_conflicts()`         | `ibox nmc ip-conflicts`         |
| NMC.wan_status          | `ibox.nmc.wan_status()`           | `ibox nmc wan-status`           |
| NMC.orientation         | `ibox.nmc.orientation()`          | `ibox nmc orientation`          |
| PasswordRecovery.status | `ibox.password_recovery.status()` | `ibox password-recovery status` |
| Static.settings         | `ibox.static.settings()`          | `ibox static settings`          |
| Static.translations     | `ibox.static.translations()`      | `ibox static translations`      |
| Sysbus.gpios            | `ibox.sysbus.gpios()`             | `ibox sysbus gpios`             |
| Sysbus.mibs             | `ibox.sysbus.mibs()`              | `ibox sysbus mibs`              |
| Sysbus.veip             | `ibox.sysbus.veip()`              | `ibox sysbus veip`              |
| Sysbus.veip_mibs        | `ibox.sysbus.veip_mibs()`         | `ibox sysbus veip-mibs`         |
| Sysbus.net_dev_stats    | `ibox.sysbus.net_dev_stats()`     | `ibox sysbus net-dev-stats`     |
| Voice.status            | `ibox.voice.status()`             | `ibox voice status`             |
| Voice.trunks            | `ibox.voice.trunks()`             | `ibox voice trunks`             |
| Wifi.status             | `ibox.wifi.status()`              | `ibox wifi status`              |
| WWAN.status             | `ibox.wwan.status()`              | `ibox wwan status`              |
| WWAN.mibs               | `ibox.wwan.mibs()`                | `ibox wwan mibs`                |

\*Methods that do not require authentication have the following parameter set within their respective method: `auth_required=False`. Search for this in codebase if you need to identify them.
