"""Validate numeric time boundaries before execution-state mutations."""

import math

MAX_TIME = 1e15


def finite_time(value: object, label: str = "clock") -> float:
    """Reject booleans, coercible strings, overflow and non-finite times."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"invalid {label}")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"invalid {label}") from exc
    if not math.isfinite(result) or abs(result) > MAX_TIME:
        raise ValueError(f"invalid {label}")
    return result
