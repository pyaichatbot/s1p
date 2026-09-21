"""Fail-closed software checks for explicit operator promotion, not proof of evidence honesty."""

from __future__ import annotations

import math
from typing import Any


def number(value: Any, low: float, high: float) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def risk_upper(errors: int, accepted: int) -> float:
    """One-sided 95% exact binomial upper bound by monotone CDF inversion."""
    if (
        type(errors) is not int
        or type(accepted) is not int
        or not 0 <= errors <= accepted
        or accepted <= 0
    ):
        raise ValueError("invalid risk counts")
    if errors == accepted:
        return 1.0
    lower, upper = 0.0, 1.0
    for _ in range(60):
        p = (lower + upper) / 2
        terms = [
            math.lgamma(accepted + 1)
            - math.lgamma(i + 1)
            - math.lgamma(accepted - i + 1)
            + i * math.log(p)
            + (accepted - i) * math.log1p(-p)
            for i in range(errors + 1)
        ]
        peak = max(terms)
        log_cdf = peak + math.log(math.fsum(math.exp(t - peak) for t in terms))
        if log_cdf > math.log(0.05):
            lower = p
        else:
            upper = p
    return (lower + upper) / 2


def check_quality(quality: dict[str, Any]) -> None:
    n, k, eligible = (quality.get(key) for key in ("accepted_count", "errors", "eligible_count"))
    if any(type(v) is not int for v in (n, k, eligible)) or not 200 <= n <= eligible <= 100_000:
        raise ValueError("insufficient reviewed quality evidence")
    if not 0 <= k <= n or n / eligible < 0.3 or risk_upper(k, n) > 0.05:
        raise ValueError("quality risk or coverage gate failed")
    for key in ("ece", "nll", "brier", "baseline_nll", "baseline_brier"):
        if not number(quality.get(key), 0, 1e6):
            raise ValueError("invalid quality metric")
    if (
        quality["ece"] > 0.05
        or quality["nll"] > quality["baseline_nll"]
        or quality["brier"] > quality["baseline_brier"]
    ):
        raise ValueError("calibration or baseline gate failed")


def check_hardware(report: dict[str, Any]) -> None:
    limits = {
        "bundle_bytes": 1_073_741_824,
        "peak_rss_bytes": 4_294_967_296,
        "warm_p95_ms": 500,
        "cold_p95_ms": 15_000,
        "router_p95_ms": 10,
    }
    if report.get("runtime") != "python-stdlib-v1" or report.get("precision") != "fp64":
        raise ValueError("hardware runtime mismatch")
    if not isinstance(report.get("machine"), str) or not report["machine"].strip():
        raise ValueError("hardware identity missing")
    if report.get("warm_count") != 1000 or report.get("cold_count") != 20:
        raise ValueError("hardware sampling protocol incomplete")
    for key, maximum in limits.items():
        if not number(report.get(key), 0, maximum) or report[key] == 0:
            raise ValueError(f"hardware gate failed: {key}")
