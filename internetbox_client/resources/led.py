import time
from typing import Literal

from internetbox_client.utils.APIClient import APIClient
from internetbox_client.utils.helpers import camel


class LED(APIClient):
    """Control and LED brightness on the Internet Box."""

    def status(self, type: Literal["Status", "Wireless"]) -> str:
        """Get LED Brightness Status

        Args:
            type (str): LED type. "Status" for main status LED, "Wireless" for Wi-Fi LED (usally on top of device).

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/LEDs/LED/{camel(type)}:get", data)

    def set(self, type: Literal["Status", "Wireless"], brightness: int = 100) -> str:
        """Set LED brightness on device.

        Args:
            type (str): LED type. "Status" for main status LED, "Wireless" for Wi-Fi LED (usually on top of device).
            brightness (int): LED brightness level (0-100). Default is 100.

        Returns:
            str: response content

        """
        data = {"parameters": {"Brightness": brightness}}
        return self.post(f"/sysbus/LEDs/LED/{camel(type)}:set", data)

    def nmc_status(self, type: Literal["Status", "Wireless"]) -> str:
        """Get NMC LED status

        Args:
            type (str): LED type. "Status" for main status LED, "Wireless" for Wi-Fi LED.

        Returns:
            str: response content

        """
        data = {"parameters": {}}
        return self.post(f"/sysbus/NMC/LEDs/LED/{camel(type)}:get", data)

    def party_time(self, mode: Literal["on", "off"] = "on", flashes: int = 10, interval: float = 0.3) -> str:
        """Flash the Status and Wireless LEDs alternately for a fun party effect.

        Args:
            mode (str): "on" to start flashing, "off" to stop (sets both LEDs to full brightness).
            flashes (int): Number of flash cycles when mode is "on". Default is 10.
            interval (float): Time in seconds between brightness changes. Default is 0.3.

        """
        if mode == "off":
            self.set("Status", 100)
            self.set("Wireless", 100)
            return "Party stopped. Lights restored."

        for _ in range(flashes):
            self.set("Status", 100)
            self.set("Wireless", 0)
            time.sleep(interval)
            self.set("Status", 0)
            self.set("Wireless", 100)
            time.sleep(interval)

        self.set("Status", 100)
        self.set("Wireless", 100)
        return "Party over. Lights restored."

    _MORSE_CODE: dict[str, str] = {
        "A": ".-",
        "B": "-...",
        "C": "-.-.",
        "D": "-..",
        "E": ".",
        "F": "..-.",
        "G": "--.",
        "H": "....",
        "I": "..",
        "J": ".---",
        "K": "-.-",
        "L": ".-..",
        "M": "--",
        "N": "-.",
        "O": "---",
        "P": ".--.",
        "Q": "--.-",
        "R": ".-.",
        "S": "...",
        "T": "-",
        "U": "..-",
        "V": "...-",
        "W": ".--",
        "X": "-..-",
        "Y": "-.--",
        "Z": "--..",
        "0": "-----",
        "1": ".----",
        "2": "..---",
        "3": "...--",
        "4": "....-",
        "5": ".....",
        "6": "-....",
        "7": "--...",
        "8": "---..",
        "9": "----.",
        ".": ".-.-.-",
        ",": "--..--",
        "?": "..--..",
        "!": "-.-.--",
        "/": "-..-.",
        "-": "-....-",
        "(": "-.--.",
        ")": "-.--.-",
    }

    def morse_code(self, message: str, led: Literal["Status", "Wireless"] = "Status", dot_duration: float = 0.15) -> str:
        """Flash a message in Morse code on the specified LED(s).

        Args:
            message (str): The text message to encode and flash.
            led (str): Which LED to flash. "Status" or "Wireless". Default is "Status".
            dot_duration (float): Duration in seconds of a single dot. A dash is 3x this. Default is 0.15.

        Returns:
            str: The Morse code representation of the message.

        """
        dash_duration = dot_duration * 3
        symbol_gap = dot_duration  # gap between dots/dashes within a character
        char_gap = dot_duration * 3  # gap between characters
        word_gap = dot_duration * 7  # gap between words

        leds: list[Literal["Status", "Wireless"]] = [led]

        def _flash(duration: float) -> None:
            for led in leds:
                self.set(led, 100)
            time.sleep(duration)
            for led in leds:
                self.set(led, 0)

        morse_str_parts: list[str] = []
        words = message.upper().split(" ")

        for word_idx, word in enumerate(words):
            morse_str_parts.append("  ".join(self._MORSE_CODE.get(ch, "") for ch in word if ch in self._MORSE_CODE))
            for char_idx, char in enumerate(word):
                code = self._MORSE_CODE.get(char)
                if code is None:
                    continue
                for sym_idx, symbol in enumerate(code):
                    _flash(dot_duration if symbol == "." else dash_duration)
                    if sym_idx < len(code) - 1:
                        time.sleep(symbol_gap)
                if char_idx < len(word) - 1:
                    time.sleep(char_gap)
            if word_idx < len(words) - 1:
                time.sleep(word_gap)

        for led in leds:
            self.set(led, 100)

        morse_display = "   ".join(morse_str_parts)
        return f"Morse code for '{message}': {morse_display}"
