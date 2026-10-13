import pytest

from kvkk_mask.validators import (
    iban_check_digits,
    is_valid_card,
    is_valid_iban,
    is_valid_tckn,
    is_valid_vkn,
    luhn_check_digit,
    tckn_check_digits,
    vkn_check_digit,
)


# --- TCKN ---

@pytest.mark.parametrize("value", ["10000000146", "100 000 001 46"])
def test_tckn_valid(value):
    assert is_valid_tckn(value)


@pytest.mark.parametrize(
    "value",
    [
        "10000000145",   # wrong last digit
        "10000000156",   # wrong 10th digit
        "01234567890",   # cannot start with 0
        "1000000014",    # 10 digits
        "100000001466",  # 12 digits
        "1000000014a",
        "",
    ],
)
def test_tckn_invalid(value):
    assert not is_valid_tckn(value)


def test_tckn_check_digits_roundtrip():
    first9 = "123456789"
    assert is_valid_tckn(first9 + tckn_check_digits(first9))


# --- VKN ---

@pytest.mark.parametrize("first9", ["123456789", "000000000", "999999999", "472105836"])
def test_vkn_check_digit_roundtrip(first9):
    assert is_valid_vkn(first9 + vkn_check_digit(first9))


def test_vkn_known_value():
    # Example from python-stdnum's tr.vkn documentation
    assert is_valid_vkn("4540536920")
    assert not is_valid_vkn("4540536921")


def test_vkn_invalid():
    first9 = "123456789"
    wrong = str((int(vkn_check_digit(first9)) + 1) % 10)
    assert not is_valid_vkn(first9 + wrong)
    assert not is_valid_vkn("12345")
    assert not is_valid_vkn("12345678901")


# --- IBAN ---

@pytest.mark.parametrize(
    "value",
    [
        "TR330006100519786457841326",
        "TR33 0006 1005 1978 6457 8413 26",
        "tr330006100519786457841326",
    ],
)
def test_iban_valid(value):
    assert is_valid_iban(value)


@pytest.mark.parametrize(
    "value",
    [
        "TR330006100519786457841327",  # one digit changed
        "TR33000610051978645784132",   # too short
        "DE89370400440532013000",      # valid IBAN, but not Turkish
        "TR33000610051978645784132X",
        "",
    ],
)
def test_iban_invalid(value):
    assert not is_valid_iban(value)


def test_iban_check_digits_roundtrip():
    bban = "0006100519786457841326"
    assert iban_check_digits("TR", bban) == "33"


# --- Card (Luhn) ---

@pytest.mark.parametrize("value", ["4111111111111111", "4111 1111 1111 1111", "5500-0000-0000-0004"])
def test_card_valid(value):
    assert is_valid_card(value)


@pytest.mark.parametrize("value", ["4111111111111112", "411111111111", "41111111111111111111", "abcd"])
def test_card_invalid(value):
    assert not is_valid_card(value)


def test_luhn_check_digit_roundtrip():
    partial = "411111111111111"
    assert is_valid_card(partial + luhn_check_digit(partial))
