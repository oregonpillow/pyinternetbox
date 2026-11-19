from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.helpers import normalize_mac


class DHCP(APIClient):
    """DHCPv4 and DHCPv6 server settings and leases."""

    def static_leases(self) -> str:
        """Get DHCPv4 static leases"""
        data = {"parameters": {}}
        return self.post("/sysbus/DHCPv4/Server/Pool/default:getStaticLeases", data)

    def add_static_lease(self, mac: str, ip: str) -> str:
        """Reserve an IP address for a device (static DHCP lease).

        The device gets the address the next time it renews its lease, e.g. when it reconnects.

        Args:
            mac (str): device MAC address, e.g. "AA:BB:CC:DD:EE:FF".
            ip (str): IPv4 address in the LAN subnet, e.g. "192.168.1.20".

        Returns:
            str: response content

        """
        data = {"parameters": {"MACAddress": normalize_mac(mac), "IPAddress": ip}}
        return self.post("/sysbus/DHCPv4/Server/Pool/default:addStaticLease", data)

    def delete_static_lease(self, mac: str) -> str:
        """Remove a device's IP address reservation (static DHCP lease).

        Args:
            mac (str): device MAC address.

        Returns:
            str: response content

        """
        data = {"parameters": {"MACAddress": normalize_mac(mac)}}
        return self.post("/sysbus/DHCPv4/Server/Pool/default:deleteStaticLease", data)

    def server_pool(self) -> str:
        """Get DHCPv4 server pool"""
        data = {"parameters": {}}
        return self.post("/sysbus/DHCPv4/Server:getDHCPServerPool", data)

    def ipv6_prefix_information(self) -> str:
        """Get DHCPv6 prefix information"""
        data = {"parameters": {"pool": "lan"}}
        return self.post("/sysbus/DHCPv6/Server:getPrefixInformation", data)


# curl 'https://internetbox.swisscom.ch/sysbus/DHCPv6/Server:getPrefixInformation' \
#   -H 'Accept: */*' \
#   -H 'Accept-Language: en-US,en;q=0.9' \
#   -H 'Authorization: X-Sah VZ5hID+8zYFgPJgKts01TKCYixE/Rg6II2Y2x1cio2cjlQ80vw+BsECndJe13cnV' \
#   -H 'Connection: keep-alive' \
#   -H 'Content-Type: application/x-sah-ws-4-call+json' \
#   -b '_pin_unauth=dWlkPU1EZGxOak16TURZdE1EQmhNaTAwWldVekxXSTVOREF0WW1SbE5URmhPR0psTWpJdw; _ga=GA1.1.1833477817.1754924397; _scid_r=JKwFT0m2cdf89OSeSZAKcU4xwcudGBJ3BIgXxA; _sc_cspv=https%3A%2F%2Ftr.snapchat.com%2Fp; wisepops_visitor=%7B%22S5wX5Go3J2%22%3A%228205efce-df8e-401f-b247-cd3893e32e7c%22%7D; _ga_J1S0GD1BDW=GS2.1.s1755080195$o2$g1$t1755081686$j60$l0$h0; OPTIN=0; OptanonAlertBoxClosed=2025-09-02T09:36:26.636Z; s_ecid=MCMID%7C44394798375469508152277418652908095303; _ga_EV684GVP1F=GS2.1.s1757078959$o1$g1$t1757079453$j60$l0$h0; mycloud-language=en; _cq_duid=1.1762859733.T2582Dlh7m2OVdXa; AMCV_A174401053C92A7E0A490D4C%40AdobeOrg=-1176276602%7CMCIDTS%7C20462%7CMCMID%7C44394798375469508152277418652908095303%7CMCAAMLH-1768485964%7C6%7CMCAAMB-1768485964%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1767888364s%7CNONE%7CMCAID%7CNONE%7CMCCIDH%7C-1107325138; mbox=PC#32b359c6d2de4e34a6266e134827eb05.37_0#1831125970|session#1d2ce5c665a54ec7aa5080fb46003bdf#1767883030; kndctr_A174401053C92A7E0A490D4C_AdobeOrg_consent=general%3Dout; _cs_c=1; _cs_id=69c7b94e-e741-aea3-b764-1a18e46e39a7.1772194743.2.1774617403.1774617379.1764944825.1806358743440.1.x; kndctr_A174401053C92A7E0A490D4C_AdobeOrg_identity=CiYwMjIxMjQzNzEzMTAzMzQ5Mzg0MTYyMTczNTkxMzkzMzE5MDAzMFITCPvUo86QMxABGAEqBElSTDEwAPABj%5FPJ7dUz; OptanonConsent=isGpcEnabled=0&datestamp=Sun+Apr+05+2026+14%3A51%3A32+GMT%2B0200+(Central+European+Summer+Time)&version=202501.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=2b79eab2-b115-4848-872f-529c46c18e35&interactionCount=5&isAnonUser=1&landingPath=NotLandingPage&groups=C0002%3A0%2CC0011%3A0%2CC0004%3A0%2CC0009%3A0%2CC0001%3A1&AwaitingReconsent=false&intType=6&geolocation=%3B; _cq_suid=1.1775575373.qqj4NShSWNQEwGbe; _cq_session=4.1775575373176.yR2ofLhXueBqgIwG.1775575373175; bcb9452d/accept-language=en-US,en; test=test; bcb9452d/sessid=1Vm1U4SnHjvVocuow9fI5NKY; swc/deviceID=bcb9452d; bcb9452d/context=VZ5hID+8zYFgPJgKts01TKCYixE/Rg6II2Y2x1cio2cjlQ80vw+BsECndJe13cnV' \
#   -H 'DNT: 1' \
#   -H 'Origin: https://internetbox.swisscom.ch' \
#   -H 'Referer: https://internetbox.swisscom.ch/' \
#   -H 'Sec-Fetch-Dest: empty' \
#   -H 'Sec-Fetch-Mode: cors' \
#   -H 'Sec-Fetch-Site: same-origin' \
#   -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36' \
#   -H 'X-Context: VZ5hID+8zYFgPJgKts01TKCYixE/Rg6II2Y2x1cio2cjlQ80vw+BsECndJe13cnV' \
#   -H 'X-Requested-With: XMLHttpRequest' \
#   -H 'sec-ch-ua: "Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"' \
#   -H 'sec-ch-ua-mobile: ?0' \
#   -H 'sec-ch-ua-platform: "macOS"' \
#   --data-raw '{"parameters":{"pool":"lan"}}'
