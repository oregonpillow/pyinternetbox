"""Tests for helpers module."""

import pytest

from internetbox_client.utils.helpers import camel, hide_secrets, normalize_mac


class TestHideSecrets:
    def test_wifi_settings(self) -> None:
        mibs = {
            "status": {
                "wlanvap": {
                    "wl0": {
                        "SSID": "MyHome",
                        "Security": {"KeyPassPhrase": "Correct-Horse-9", "PreSharedKey": "", "SAEPassphrase": "Correct-Horse-9"},
                        "R0KHKey": "0123456789abcdef",
                        "RadiusSecret": "",
                    }
                }
            }
        }
        assert hide_secrets(mibs) == {
            "status": {
                "wlanvap": {
                    "wl0": {
                        "SSID": "MyHome",
                        "Security": {"KeyPassPhrase": "<hidden>", "PreSharedKey": "", "SAEPassphrase": "<hidden>"},
                        "R0KHKey": "<hidden>",
                        "RadiusSecret": "",
                    }
                }
            }
        }

    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "Password",
            "authPassword",
            "PassPhrase",
            "IPsecPreSharedKey",
            "IPsecConfigurationIKEv2PSK",
            "WEPKey",
            "SelfPIN",
            "SyncToken",
        ],
    )
    def test_secret_keys(self, key: str) -> None:
        assert hide_secrets([{key: "s3cret"}, {key: 1234}]) == [{key: "<hidden>"}, {key: "<hidden>"}]

    @pytest.mark.parametrize(
        "key", ["PublicKey", "Key", "PasswordRecovery", "PinholeNumberOfEntries", "UserName", "Show Password", "set-password"]
    )
    def test_other_keys(self, key: str) -> None:
        assert hide_secrets({key: "visible"}) == {key: "visible"}

    def test_booleans_and_empty_values_stay(self) -> None:
        data = {"UseSyncToken": True, "RequireSharedSecret": False, "Password": None, "PIN": "", "PreSharedKey": []}
        assert hide_secrets(data) == data

    def test_returns_a_copy(self) -> None:
        data = {"status": {"password": "s3cret"}}
        hide_secrets(data)
        assert data == {"status": {"password": "s3cret"}}

    @pytest.mark.parametrize("value", ["text", 1, None, True])
    def test_other_values(self, value: object) -> None:
        assert hide_secrets(value) == value


class TestNormalizeMac:
    @pytest.mark.parametrize("mac", ["aa:bb:cc:dd:ee:ff", "AA-BB-CC-DD-EE-FF", "aabb.ccdd.eeff", "aabbccddeeff", " AA:BB:CC:DD:EE:FF "])
    def test_notations(self, mac: str) -> None:
        assert normalize_mac(mac) == "AA:BB:CC:DD:EE:FF"

    @pytest.mark.parametrize("mac", ["", "aa:bb:cc:dd:ee", "aa:bb:cc:dd:ee:fg", "aa:bb:cc:dd:ee:ff:00", "Device-20"])
    def test_invalid(self, mac: str) -> None:
        with pytest.raises(ValueError, match="Not a MAC address"):
            normalize_mac(mac)


class TestCamel:
    def test_snake_case(self) -> None:
        assert camel("hello_world") == "HelloWorld"

    def test_kebab_case(self) -> None:
        assert camel("hello-world") == "HelloWorld"

    def test_space_separated(self) -> None:
        assert camel("hello world") == "HelloWorld"

    def test_single_word(self) -> None:
        assert camel("status") == "Status"

    def test_already_capitalised(self) -> None:
        assert camel("Status") == "Status"

    def test_mixed_separators(self) -> None:
        assert camel("foo_bar-baz qux") == "FooBarBazQux"

    def test_empty_string(self) -> None:
        assert camel("") == ""

    def test_uppercase_input(self) -> None:
        assert camel("HELLO_WORLD") == "HelloWorld"
