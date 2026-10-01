import random
from services.common.vin import generate_vin, is_valid_vin


def test_known_valid():
    assert is_valid_vin("1HGCM82633A004352")


def test_bad_check_digit():
    assert not is_valid_vin("1HGCM82633A004353")


def test_forbidden_letter_and_length():
    assert not is_valid_vin("1HGCM82I33A004352")
    assert not is_valid_vin("1HGCM82633A00435")


def test_generated_vins_are_valid():
    rng = random.Random(1)
    assert all(is_valid_vin(generate_vin(rng)) for _ in range(1000))