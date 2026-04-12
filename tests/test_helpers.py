"""Tests for helpers module."""

from internetbox_client.utils.helpers import camel


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
