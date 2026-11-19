"""Tests for helpers module."""

import pytest

from internetbox_client.utils.helpers import camel, normalize_mac


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
