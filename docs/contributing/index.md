# Contributing

So far the project is in early stages and I'm the only contributor, but I welcome contributions from the community! If you want to contribute, please fork the repository and create a pull request with your changes. At the moment I've only tested with an IB4 box, if you have a different box any testing you can provide would be greatly appreciaited! :)

## How to contribute

- Read [Missing endpoints](../MISSING_ENDPOINTS.md) if you want to work on implementing missing endpoints: what could still be added, and what's left out or not possible, and why
- Check the [API map](../API_MAP.md) for every endpoint the web interface calls and every function the router exposes, and which ones are implemented. Re-generate it for your model or firmware with `uv run scripts/discover_endpoints.py -H 192.168.1.1 -k`
- Try creating more complex methods, see below for more details
- Take a stab at implementing any bugs or features raised in the [issues](https://github.com/oregonpillow/pyinternetbox/issues)
- Test the library with different Swisscom/Wingo Internet Box models and report any issues you find - testers are much appreciaited!!
- Contribute more dashboards :)
- Add missing metrics in the exporter: only a subset of methods in this client are currently implemented
- Improve the pipeline
- Buy me a coffee ☕️ ;)

[Development](development.md) explains how to set up the project and run the tests.

## Creating more complex methods

When logged into the web interface, within developer tools you can see the REST-API logic within the js scripts.

Pretty much all the REST-API logic is contained within these. These scripts could be parsed to find missing endpoints and provide a template for how to interact and combine calls for more powerful dynamic methods. `scripts/discover_endpoints.py` does the first part: it lists the endpoints and parameter names the scripts use in the [API map](../API_MAP.md).

The scripts likely differ based on the Web portal version.
The `Web portal version` can be found in the web gui: `Diagnostics > Internet-Box`.

To view the js scripts:

> 1. Open your Internet Box web interface (e.g. `https://internetbox.swisscom.ch`) and log in
> 2. Open your browser's Developer Tools (F12) → **Network** tab
> 3. Reload the page and filter by JS — download `app.min.js` and `core.min.js`
