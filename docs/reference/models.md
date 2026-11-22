# Routers

## Supported models

| **Model**          | **Tested** | **Notes**                                        |
| ------------------ | ---------- | ------------------------------------------------ |
| Internet Box 2     | No         | Expected to work partially                       |
| Internet Box 3     | No         | Expected to work partially                       |
| Internet Box 4     | ✅         | Tested and confirmed to work (firmware 15.21.36) |
| Internet Box 5     | No         | Expected to work                                 |
| Internet Box 5 Pro | No         | Expected to work                                 |

To check your model run `ibox devices info`. Submit a PR if you have a model not listed here.

## Hardware

The Internet Boxes Swisscom has sold since 2019. Wingo uses the Internet Box 3 and 4 too. All four are made by Arcadyan, and run software by SoftAtHome, which also makes the software of Orange's Livebox. The web interface talks to the router through SoftAtHome's API, and so does this library.

|                       | **Internet Box 3**                                            | **Internet Box 4**                                | **Internet Box 5**                                | **Internet Box 5 Pro**                            |
| --------------------- | ------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------- |
| **Released**          | 2019                                                          | 2022                                              | 2025                                              | 2024                                              |
| **Arcadyan model**    | GRV951AZWAX34-A-LSW                                           | PRV65AX34AB-B-LSW                                 | unknown                                           | PRV65BE3448B-B-H1-LSW                             |
| **Reports itself as** | unknown                                                       | `IB4-00`                                          | unknown                                           | unknown                                           |
| **Copper line**       | ADSL, VDSL, G.fast                                            | –                                                 | ADSL, VDSL, G.fast                                | –                                                 |
| **Fibre line**        | 1 Gbit/s fibre module; 10 Gbit/s XGS-PON with the XGS-PON kit | 10 Gbit/s XGS-PON built in; 1 Gbit/s fibre module | 10 Gbit/s XGS-PON built in; 1 Gbit/s fibre module | 10 Gbit/s XGS-PON built in; 1 Gbit/s fibre module |
| **Ethernet ports**    | 1 × 2.5 Gbit/s, 4 × 1 Gbit/s                                  | 1 × 10 Gbit/s, 4 × 1 Gbit/s                       | 1 × 2.5 Gbit/s, 4 × 1 Gbit/s                      | 1 × 10 Gbit/s, 4 × 1 Gbit/s                       |
| **Wi-Fi**             | Wi-Fi 6                                                       | Wi-Fi 6                                           | Wi-Fi 7                                           | Wi-Fi 7                                           |
| **2.4 GHz**           | 3 × 3, 40 MHz, 860 Mbit/s                                     | 3 × 3, 40 MHz, 860 Mbit/s                         | 3 × 3, 1 Gbit/s                                   | 3 × 3, 1 Gbit/s                                   |
| **5 GHz**             | 4 × 4, 160 MHz, 4.8 Gbit/s                                    | 4 × 4, 160 MHz, 4.8 Gbit/s                        | 4 × 4, 5.8 Gbit/s                                 | 4 × 4, 5.8 Gbit/s                                 |
| **6 GHz**             | –                                                             | –                                                 | –                                                 | 4 × 4, 320 MHz, 11.5 Gbit/s                       |
| **Wi-Fi antennas**    | unknown                                                       | unknown                                           | 7                                                 | 11                                                |
| **Phone**             | 2 analog ports, DECT CAT-iq 2.0                               | 2 analog ports, DECT CAT-iq 2.0                   | 1 analog port, DECT CAT-iq 2.0                    | 1 analog port, DECT CAT-iq 2.0                    |
| **USB**               | USB 3.0                                                       | 1 × USB 3.0                                       | 1 × USB 3.0                                       | USB 3.0                                           |
| **Processor**         | unknown                                                       | unknown; Broadcom Wi-Fi                           | unknown                                           | unknown; Broadcom, says SoftAtHome                |
| **Memory**            | unknown                                                       | 1 GB                                              | unknown                                           | unknown                                           |
| **Power use**         | 10.1–11.6 W                                                   | 9.6–10.3 W                                        | 11.6–12 W                                         | 15.5–15.7 W                                       |
| **Power supply**      | 12 V, 3.2 A (38 W)                                            | 12 V, 3.2 A (38 W)                                | 12 V, 3.5 A (42 W)                                | 12 V, 3.5 A (42 W)                                |
| **Size**              | 33 × 213 × 237 mm                                             | 33 × 213 × 237 mm                                 | 33 × 211 × 233 mm                                 | 65 × 186 × 190 mm                                 |
| **Weight**            | 818 g                                                         | 865 g                                             | 860 g                                             | 1005 g                                            |

- **–**: the box doesn't have it
- **unknown**: no public source gives it
- **3 × 3, 4 × 4**: the Wi-Fi's antenna streams, sending × receiving
- **Mbit/s, Gbit/s** under Wi-Fi: the highest rate in theory, as Swisscom gives it

Notes:

- **Fibre**: the 1 Gbit/s fibre module plugs into a slot on the box. On the Internet Box 3, the XGS-PON kit replaces it for 10 Gbit/s.
- **6 GHz**: a WLAN-Box 3 adds 6 GHz Wi-Fi to the boxes without it, and every box extends its Wi-Fi with WLAN-Boxes (mesh).
- **Phone**: Swisscom gives CAT-iq 2.0 for the Internet Box 4, but the box itself reports CAT-iq 3.0 (`ibox dect standard-version`). Up to 5 HD-Phones connect to the DECT base.
- **USB**: for the Internet Box 3, sources differ between one and two USB ports.
- **Power use**: Swisscom's figure in normal use, with Wi-Fi, Ethernet and phone devices connected. It depends on the line, e.g. fibre or copper, so it's given from the lowest to the highest.
- **Weight**: the "module weight" in Swisscom's carbon footprint factsheets, which list the power supply separately.
- **Broadcom**: on the Internet Box 4, the Wi-Fi radios are called `wifi0_bcm` and `wifi1_bcm`, after Broadcom's driver. SoftAtHome says Swisscom's first Wi-Fi 7 box, the Internet Box 5 Pro, runs on Broadcom's chips.

## An Internet Box 4, as it reports itself

Read with this library from an Internet Box 4 with hardware version 4.3 and firmware 15.21.36:

- **Memory**: 1,001,700 kB, about 1 GB
- **Ethernet ports**: `ETH0` to `ETH3` at up to 1 Gbit/s, `ETH4` at up to 10 Gbit/s
- **Wi-Fi radios**:
  - `wifi0_bcm`: 5 GHz, 802.11a/n/ac/ax, channels up to 160 MHz
  - `wifi1_bcm`: 2.4 GHz, 802.11b/g/n/ax, channels up to 40 MHz
  - both: OFDMA, MU-MIMO and beamforming
- **Fibre line**: XGS-PON at 9.95 Gbit/s in each direction
- **Temperature sensors**: the processor, both Wi-Fi radios and the 10 Gbit/s Ethernet port
- **Position sensor**: an accelerometer, read by `ibox nmc orientation`
- **Phone**: 2 analog ports (`FXS1`, `FXS2`) and the DECT base, CAT-iq 3.0
- **USB**: 1 port

## Your router's hardware

| **What**                         | **Command**                               |
| -------------------------------- | ----------------------------------------- |
| Model, hardware and firmware     | `ibox devices info`                       |
| Memory                           | `ibox devices memory-status`              |
| An Ethernet port and its speed   | `ibox lan ethernet-port 4` (ports 0 to 4) |
| A Wi-Fi radio                    | `ibox wifi radio 0` (radios 0, 1, ...)    |
| The Wi-Fi standards of each band | `ibox wifi steering-operating-standards`  |
| The fibre line                   | `ibox sysbus veip`                        |
| Temperatures                     | `ibox temperature sensor`                 |
| Phone ports                      | `ibox voice handsets`                     |
| DECT standard                    | `ibox dect standard-version`              |
| Position sensor                  | `ibox nmc orientation`                    |

If your box isn't in the table above, or something differs, please open an [issue](https://github.com/oregonpillow/pyinternetbox/issues) with what these commands show. Leave out the serial numbers and MAC addresses.

## Sources

- **All models**:
  - power use and power supplies: [energy consumption](https://www.swisscom.ch/en/residential/help/apps-and-services/energy-consumption.html) (Swisscom)
  - copper lines: [approved equipment list](https://www.swisscom.ch/content/dam/swisscom/de/ws/documents/D_BBCS-Dokumente/BBCS_CUG/e_bbcs_supporting-document_provedequipment.pdf) (Swisscom)
  - 6 GHz with a WLAN-Box: [WLAN-Box 3](https://www.swisscom.ch/en/residential/help/device/home-network/wlan-box3.html) (Swisscom)
  - SoftAtHome: [Internet Box 5 Pro](https://www.softathome.com/2024/11/27/swisscom-deploys-first-tri-band-wi-fi-7-home-gateway-in-switzerland-with-softathome/) and [Broadcom](https://www.softathome.com/2026/02/26/softathome-collaborates-with-broadcom-to-accelerate-wi-fi-8-roadmap-via-enhanced-prpl-integration/) (SoftAtHome)
  - Wingo: [Internet-Box hardware](https://www.wingo.ch/de/hilfe/internet-tv/internet-box-hardware) (Wingo)
- **Internet Box 3**:
  - [product page](https://web.archive.org/web/20250320044244/https://www.swisscom.ch/de/privatkunden/produkte/internetrouter/details.html/internet-box-3-ip-11039000) (archived, March 2025), [help page](https://www.swisscom.ch/en/residential/help/device/internet/internetbox3.html), [press release](https://www.swisscom.ch/de/about/news/2019/11/14-internet-box-3.html), [XGS-PON kit](https://www.swisscom.ch/content/dam/assets/b2c/products/internet/help/pdf/ib3_xgs-pon-kit_en.pdf) (Swisscom)
  - [declaration of conformity](https://www.swisscom.ch/content/dam/assets/b2c/products/internet/help/pdf/ib3_ce-doc_20230105.pdf) and [carbon footprint factsheet](https://www.swisscom.ch/content/dam/assets/b2c/products/internet/help/pdf/pcf_factsheet_ib3.pdf) (Swisscom)
  - [Wi-Fi certificate](https://api.cert.wi-fi.org/api/certificate/download/public?variantId=15729) (Wi-Fi Alliance)
- **Internet Box 4**:
  - [product page](https://web.archive.org/web/20220126101935/https://www.swisscom.ch/de/privatkunden/produkte/internetrouter/details.html/internet-box-4-fibre-11050518) (archived, January 2022), [help page](https://www.swisscom.ch/en/residential/help/device/internet/internetbox4.html), [manual](https://www.swisscom.ch/content/dam/assets/b2c/products/internet/help/pdf/ib4_a_fiber_11051369_07-23_en_web.pdf) (Swisscom)
  - [declaration of conformity](https://www.swisscom.ch/content/dam/assets/b2c/products/internet/help/pdf/ib4_ce-doc_r3.pdf) and [carbon footprint factsheet](https://www.swisscom.ch/content/dam/assets/b2c/products/internet/help/pdf/pcf_factsheet_ib4.pdf) (Swisscom)
  - [Wi-Fi certificate](https://api.cert.wi-fi.org/api/certificate/download/public?variantId=104576) (Wi-Fi Alliance)
  - "Reports itself as", memory and the Broadcom radio names: read from the router
- **Internet Box 5**:
  - [product page](https://www.swisscom.ch/de/privatkunden/produkte/internetrouter/details.html/internet-box-5-11063847), [help page](https://www.swisscom.ch/de/privatkunden/hilfe/geraet/internet/internetbox5.html) (Swisscom)
  - [declaration of conformity](https://www.swisscom.ch/content/dam/assets/b2c/products/internet/help/pdf/ib5_ce-doc_2024-0730r1.pdf) and [carbon footprint factsheet](https://www.swisscom.ch/content/dam/assets/b2c/products/internet/help/pdf/pcf_factsheet_ib5.pdf) (Swisscom)
- **Internet Box 5 Pro**:
  - [product page](https://www.swisscom.ch/de/privatkunden/produkte/internetrouter/details.html/internet-box-5-pro-11063851), [launch](https://www.swisscom.ch/de/about/news/2024/11/20-telco.html) (Swisscom)
  - [declaration of conformity](https://www.swisscom.ch/content/dam/assets/b2c/products/internet/help/pdf/ib5_pro_ce-doc_2024-0920r1.pdf) and [carbon footprint factsheet](https://www.swisscom.ch/content/dam/assets/b2c/products/internet/help/pdf/pcf_factsheet_ib5pro.pdf) (Swisscom)
  - [Wi-Fi certificate](https://api.cert.wi-fi.org/api/certificate/download/public?variantId=133878) (Wi-Fi Alliance)
