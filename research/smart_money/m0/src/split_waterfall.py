"""Corporate action and split waterfall state machine (Gates 0, 1, 2) and rational factor dictionary."""

from dataclasses import dataclass
import math
import statistics
from typing import Any


def _build_rational_factors() -> set[float]:
    """Construct frozen 204 rational split factor set K_rational."""
    base: list[float] = [1.25, 4.0 / 3.0, 1.50] + [float(k) for k in range(2, 101)]
    reciprocals: list[float] = [1.0 / x for x in base]
    return set(base + reciprocals)


FROZEN_RATIONAL_SPLIT_FACTORS: set[float] = _build_rational_factors()


@dataclass(frozen=True)
class SplitEvent:
    """Split event record from vendor ledger."""
    ex_date: str  # YYYY-MM-DD
    ratio: float  # e.g., 2.0 for 2:1, 0.1 for 1:10


@dataclass(frozen=True)
class ContinuousHolder:
    """Continuous holder shares across consecutive quarters (Q-1 -> Q)."""
    entity_id: str
    prev_shares: float
    curr_shares: float


@dataclass(frozen=True)
class SplitWaterfallResult:
    """Evaluation result from ordered split waterfall gates."""
    state: str
    action: str  # 'INCLUDE' or 'EXCLUDE'
    split_factor: float | None
    sensitivity_action: str  # 'INCLUDE' or 'EXCLUDE'
    k_ledger: float
    holder_count: int
    median_ratio: float | None
    mad_log: float | None
    adj_median_ratio: float | None


def compute_k_ledger(
    prev_period: str, curr_period: str, vendor_splits: list[SplitEvent]
) -> float:
    """Compute period-pair split coefficient K_ledger(Q-1, Q).
    
    Includes splits with prev_period < ex_date <= curr_period.
    Product of all split ratios; returns 1.0 if empty.
    """
    applicable_splits = [
        s for s in vendor_splits if prev_period < s.ex_date <= curr_period
    ]
    if not applicable_splits:
        return 1.0

    k = 1.0
    for s in applicable_splits:
        if not math.isfinite(s.ratio) or s.ratio <= 0:
            raise ValueError(f"Invalid non-positive or non-finite split ratio: {s.ratio}")
        k *= float(s.ratio)
    return k


def compute_holder_log_statistics(
    holders: list[ContinuousHolder], k_ledger: float
) -> tuple[float | None, float | None, float | None, int]:
    """Compute log-ratio median, MAD_log, and K_ledger-adjusted median for continuous holders.
    
    Returns:
        (tilde_r, mad_log, tilde_r_prime, N)
    """
    valid_ratios: list[float] = []
    for h in holders:
        if h.prev_shares > 0 and h.curr_shares > 0:
            r = h.curr_shares / h.prev_shares
            if math.isfinite(r) and r > 0:
                valid_ratios.append(r)

    n = len(valid_ratios)
    if n == 0:
        return None, None, None, 0

    log_ratios = [math.log(r) for r in valid_ratios]
    mu_log = statistics.median(log_ratios)
    tilde_r = math.exp(mu_log)

    abs_deviations = [abs(y - mu_log) for y in log_ratios]
    mad_log = statistics.median(abs_deviations)

    if k_ledger <= 0 or not math.isfinite(k_ledger):
        raise ValueError(f"Invalid k_ledger: {k_ledger}")

    mu_adj_log = mu_log - math.log(k_ledger)
    tilde_r_prime = math.exp(mu_adj_log)

    return tilde_r, mad_log, tilde_r_prime, n


def is_rational_split_factor_match(ratio: float, tolerance: float = 0.05) -> bool:
    """Check if ratio matches any factor in FROZEN_RATIONAL_SPLIT_FACTORS within relative tolerance."""
    if ratio <= 0 or not math.isfinite(ratio):
        return False

    for factor in FROZEN_RATIONAL_SPLIT_FACTORS:
        rel_err = abs(ratio - factor) / factor
        if rel_err <= tolerance:
            return True
    return False


def evaluate_split_waterfall(
    is_corporate_action_unknown: bool,
    k_ledger: float,
    holders: list[ContinuousHolder],
) -> SplitWaterfallResult:
    """Execute ordered split waterfall precedence (Gates 0, 1, 2) matching Contract v0.8.1 Section 11.
    
    Returns exhaustive state classification and action.
    """
    tilde_r, mad_log, tilde_r_prime, n = compute_holder_log_statistics(holders, k_ledger)

    # Gate 0: Corporate action unknown / identity broken / unresolved ownership
    if is_corporate_action_unknown:
        return SplitWaterfallResult(
            state="CORPORATE_ACTION_UNKNOWN",
            action="EXCLUDE",
            split_factor=None,
            sensitivity_action="EXCLUDE",
            k_ledger=k_ledger,
            holder_count=n,
            median_ratio=tilde_r,
            mad_log=mad_log,
            adj_median_ratio=tilde_r_prime,
        )

    # Gate 1: Vendor ledger has split record (k_ledger != 1.0)
    if abs(k_ledger - 1.0) > 1e-7:
        if n < 20:
            # Branch 1.1: Low statistical power
            return SplitWaterfallResult(
                state="KNOWN_SPLIT_LOW_POWER",
                action="INCLUDE",
                split_factor=k_ledger,
                sensitivity_action="EXCLUDE",
                k_ledger=k_ledger,
                holder_count=n,
                median_ratio=tilde_r,
                mad_log=mad_log,
                adj_median_ratio=tilde_r_prime,
            )
        else:
            # Branch 1.2: Sample adequate (N >= 20)
            assert tilde_r_prime is not None
            if 0.8 <= tilde_r_prime <= 1.2:
                # Branch 1.2a: Passed verification
                return SplitWaterfallResult(
                    state="KNOWN_SPLIT_PASS",
                    action="INCLUDE",
                    split_factor=k_ledger,
                    sensitivity_action="INCLUDE",
                    k_ledger=k_ledger,
                    holder_count=n,
                    median_ratio=tilde_r,
                    mad_log=mad_log,
                    adj_median_ratio=tilde_r_prime,
                )
            else:
                # Branch 1.2b: Discrepancy between ledger and holdings
                return SplitWaterfallResult(
                    state="KNOWN_SPLIT_MISMATCH",
                    action="EXCLUDE",
                    split_factor=None,
                    sensitivity_action="EXCLUDE",
                    k_ledger=k_ledger,
                    holder_count=n,
                    median_ratio=tilde_r,
                    mad_log=mad_log,
                    adj_median_ratio=tilde_r_prime,
                )

    # Gate 2: Vendor ledger has no split record (k_ledger == 1.0)
    if n < 20:
        # Branch 2.1: Low power without ledger split
        return SplitWaterfallResult(
            state="LEDGER_ONLY_LOW_POWER",
            action="INCLUDE",
            split_factor=1.0,
            sensitivity_action="EXCLUDE",
            k_ledger=1.0,
            holder_count=n,
            median_ratio=tilde_r,
            mad_log=mad_log,
            adj_median_ratio=tilde_r_prime,
        )
    else:
        # Branch 2.2: Sample adequate (N >= 20)
        assert tilde_r is not None
        assert mad_log is not None
        matched = is_rational_split_factor_match(tilde_r, tolerance=0.05)
        if not matched:
            # Branch 2.2a: Clean holdings, no split detected
            return SplitWaterfallResult(
                state="CLEAN",
                action="INCLUDE",
                split_factor=1.0,
                sensitivity_action="INCLUDE",
                k_ledger=1.0,
                holder_count=n,
                median_ratio=tilde_r,
                mad_log=mad_log,
                adj_median_ratio=tilde_r_prime,
            )
        elif mad_log <= 0.15:
            # Branch 2.2b: Unreported split cleanly clustered
            return SplitWaterfallResult(
                state="SPLIT_UNKNOWN",
                action="EXCLUDE",
                split_factor=None,
                sensitivity_action="EXCLUDE",
                k_ledger=1.0,
                holder_count=n,
                median_ratio=tilde_r,
                mad_log=mad_log,
                adj_median_ratio=tilde_r_prime,
            )
        else:
            # Branch 2.2c: Unreported split with high dispersion
            return SplitWaterfallResult(
                state="SPLIT_AUDIT_AMBIGUOUS_HIGH_DISPERSION",
                action="EXCLUDE",
                split_factor=None,
                sensitivity_action="EXCLUDE",
                k_ledger=1.0,
                holder_count=n,
                median_ratio=tilde_r,
                mad_log=mad_log,
                adj_median_ratio=tilde_r_prime,
            )
