import random
import re

ALLOWED = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
TRANSLIT = {
    **{str(i): i for i in range(10)},
    **dict(zip("ABCDEFGH", range(1, 9))),
    **dict(zip("JKLMN", range(1, 6))),
    "P": 7, "R": 9,
    **dict(zip("STUVWXYZ", range(2, 10))),
}
WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def check_digit(vin: str) -> str:
    total = sum(TRANSLIT[c] * w for c, w in zip(vin, WEIGHTS))
    r = total % 11
    return "X" if r == 10 else str(r)


def is_valid_vin(vin: str) -> bool:
    return bool(VIN_RE.match(vin)) and check_digit(vin) == vin[8]


def generate_vin(rng: random.Random) -> str:
    body = [rng.choice(ALLOWED) for _ in range(17)]
    body[8] = check_digit("".join(body))
    return "".join(body)