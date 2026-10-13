"""Checksum validators for Turkish identifiers.

Each identifier has a "compute check digits" helper and an "is_valid" function.
The helpers are shared with the fake data generator so that generated test data
always passes the same rules the recognizers use.
"""

import re

_NON_DIGIT = re.compile(r"[\s\-./]")


def normalize_digits(value: str) -> str:
    """Remove spaces and common separators (1234 5678, 0532-123-45-67)."""
    return _NON_DIGIT.sub("", value)


# --- TCKN (T.C. Kimlik No, 11 digits) ---

def tckn_check_digits(first9: str) -> str:
    """Return the 10th and 11th digits for the given first 9 digits."""
    d = [int(c) for c in first9]
    odd = d[0] + d[2] + d[4] + d[6] + d[8]
    even = d[1] + d[3] + d[5] + d[7]
    d10 = (odd * 7 - even) % 10
    d11 = (sum(d) + d10) % 10
    return f"{d10}{d11}"


def is_valid_tckn(value: str) -> bool:
    v = normalize_digits(value)
    if len(v) != 11 or not v.isdigit() or v[0] == "0":
        return False
    return v[9:] == tckn_check_digits(v[:9])


# --- VKN (Vergi Kimlik No, 10 digits) ---

def vkn_check_digit(first9: str) -> str:
    """Return the 10th digit of a tax number (GİB algorithm)."""
    total = 0
    for i, c in enumerate(first9):
        t = (int(c) + 9 - i) % 10
        r = (t * 2 ** (9 - i)) % 9
        if t != 0 and r == 0:
            r = 9
        total += r
    return str((10 - total % 10) % 10)


def is_valid_vkn(value: str) -> bool:
    v = normalize_digits(value)
    if len(v) != 10 or not v.isdigit():
        return False
    return v[9] == vkn_check_digit(v[:9])


# --- IBAN (Turkey: TR + 2 check digits + 22 digits = 26 chars) ---

def _iban_mod97(rearranged: str) -> int:
    # Letters become numbers (A=10 ... Z=35), then the whole string is one big integer.
    numeric = "".join(str(int(c, 36)) for c in rearranged)
    return int(numeric) % 97


def iban_check_digits(country: str, bban: str) -> str:
    """Return the 2 check digits for a country code and account part (BBAN)."""
    return f"{98 - _iban_mod97(bban + country + '00'):02d}"


def is_valid_iban(value: str) -> bool:
    v = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"TR\d{24}", v):
        return False
    return _iban_mod97(v[4:] + v[:4]) == 1


# --- Payment card number (Luhn, 13-19 digits) ---

def _luhn_sum(digits: str) -> int:
    total = 0
    # From the right: every second digit is doubled; 2-digit results lose 9.
    for i, c in enumerate(reversed(digits)):
        n = int(c)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total


def luhn_check_digit(partial: str) -> str:
    """Return the last digit that makes `partial + digit` pass Luhn."""
    return str((10 - _luhn_sum(partial + "0") % 10) % 10)


def is_valid_card(value: str) -> bool:
    v = normalize_digits(value)
    if not (13 <= len(v) <= 19) or not v.isdigit():
        return False
    return _luhn_sum(v) % 10 == 0
