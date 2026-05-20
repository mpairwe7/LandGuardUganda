"""Unique Parcel Identifier (UPI) helpers + NIN format checks.

UPI format: ``UG-DDD-NNNNNN/YYYY``
- ``UG`` = country code (constant for the prototype)
- ``DDD`` = 3-letter uppercase district code (MIT=Mityana, WAK=Wakiso, etc.)
- ``NNNNNN`` = zero-padded six-digit parcel number within the district
- ``YYYY`` = year of issuance (4 digits)

NIN format (Uganda NIRA): ``CM`` + 12 alphanumeric chars (uppercase).
We don't compute the real NIRA checksum here — only the structural
shape — because the official algorithm is not publicly documented.
NIRA itself validates the checksum during ``verify_nin``.
"""

from __future__ import annotations

import re
from datetime import datetime

UPI_REGEX = re.compile(r"^UG-[A-Z]{3}-\d{6}/\d{4}$")
NIN_REGEX = re.compile(r"^CM[0-9A-Z]{12}$")

DISTRICT_CODES = {
    1: "KCC",   # Kampala Central
    2: "WAK",   # Wakiso
    3: "MIT",   # Mityana
    4: "GUL",   # Gulu
}


def validate_upi(upi: str) -> bool:
    return bool(UPI_REGEX.match(upi))


def validate_nin(nin: str) -> bool:
    return bool(NIN_REGEX.match(nin))


def make_upi(district_id: int, parcel_number: int, year: int | None = None) -> str:
    """Construct a UPI from its components."""
    code = DISTRICT_CODES.get(district_id)
    if not code:
        raise ValueError(f"unknown district_id={district_id}")
    if not (0 < parcel_number < 1_000_000):
        raise ValueError(f"parcel_number out of range: {parcel_number}")
    year = year or datetime.utcnow().year
    return f"UG-{code}-{parcel_number:06d}/{year}"


def make_title_no(district_id: int, sequence: int, year: int | None = None) -> str:
    """Title number is a sibling identifier of the UPI; same shape but T- prefix."""
    code = DISTRICT_CODES.get(district_id, "XXX")
    year = year or datetime.utcnow().year
    return f"UG-{code}-T{sequence:05d}/{year}"
