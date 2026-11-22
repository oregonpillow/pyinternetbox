# Library

`InternetBoxClient` logs in to the router and groups its functions by area, e.g. `ibox.wifi` or `ibox.firewall`. Each page in this section is one group, with every method's description: what it does, its arguments, and what the router does with them.

```python
from internetbox_client import InternetBoxClient

with InternetBoxClient(hostname="192.168.1.1", password="secret") as ibox:
    print(ibox.wifi.summary())
```

`InternetBoxClient` takes `hostname`, `password`, `username` and `ssl_verify`. The ones you leave out come from the [environment variables](../environment-variables.md). It logs in on the first call that needs the password, and logs out at the end of the `with` block, or when you call `close()`.

Methods return the router's answer as text, usually JSON: `json.loads()` turns it into Python objects.

Every method is also a CLI command: `ibox.wifi.set_guest_enabled()` is `ibox wifi set-guest-enabled`, and `ibox wifi set-guest-enabled --help` shows its options.

## Helpers

For tools built on the library, such as the [MCP server](../../mcp.md). The library and the CLI show passwords and keys.

<!-- prettier-ignore-start -->

::: internetbox_client.utils.labels.action
    options:
      show_root_heading: true
      heading_level: 3

::: internetbox_client.utils.helpers.hide_secrets
    options:
      show_root_heading: true
      heading_level: 3

<!-- prettier-ignore-end -->
