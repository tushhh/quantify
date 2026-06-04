from __future__ import annotations


def hold_days_from_unit(value: int, unit: str) -> int:
    unit = unit.lower().strip()
    if unit == "days":
        return value
    if unit == "months":
        return value * 30
    if unit == "years":
        return value * 365
    raise ValueError(f"Unsupported hold unit: {unit}")
