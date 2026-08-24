"""Corporate action and split waterfall state machine (Gates 0, 1, 2) and rational factor dictionary."""

from dataclasses import dataclass
from datetime import date
import math
import statistics
from typing import Any

from research.smart_money.m0.src.ownership_state_machine import (
    is_strict_nonnegative_number,
    is_strict_positive_number,
)


def _build_rational_factors() -> set[float]:
    """Construct frozen 204 rational split factor set K_rational."""
    base: list[float] = [1.25, 4.0 / 3.0, 1.50] + [float(k) for k in range(2, 101)]
    reciprocals: list[float] = [1.0 / x for x in base]
    return set(base + reciprocals)


FROZEN_RATIONAL_SPLIT_FACTORS: frozenset[float] = frozenset(_build_rational_factors())


@dataclass(frozen=True)
class SplitEvent:
    """Split event record from vendor ledger."""
    ex_date: str  # YYYY-MM-DD
    ratio: int | float  # e.g., 2.0 for 2:1, 0.1 for 1:10

    def validate(self) -> None:
        """Validate split event fields, rejecting bool and invalid date/ratios."""
        if not self.ex_date or not isinstance(self.ex_date, str):
            raise ValueError(f"Invalid ex_date in split event: {self.ex_date!r}")
        try:
            date.fromisoformat(self.ex_date.strip())
        except ValueError as err:
            raise ValueError(f"Invalid date format in split event ex_date: {self.ex_date!r}") from err
        if not is_strict_positive_number(self.ratio):
            raise ValueError(f"Invalid non-positive or non-numeric split ratio: {self.ratio!r}")


@dataclass(frozen=True)
class ContinuousHolder:
    """Continuous holder shares across consecutive quarters (Q-1 -> Q)."""
    entity_id: str
    prev_shares: int | float
    curr_shares: int | float

    def validate(self) -> None:
        """Validate continuous holder shares and entity_id, rejecting bool."""
        if not self.entity_id or not str(self.entity_id).strip():
            raise ValueError("ContinuousHolder entity_id cannot be blank or empty.")
        if not is_strict_positive_number(self.prev_shares):
            raise ValueError(f"Invalid non-positive or non-numeric prev_shares: {self.prev_shares!r}")
        if not is_strict_positive_number(self.curr_shares):
            raise ValueError(f"Invalid non-positive or non-numeric curr_shares: {self.curr_shares!r}")


@dataclass(frozen=True)
class SplitWaterfallResult:
    """Evaluation result from ordered split waterfall gates."""
    state: str
    action: str  # 'INCLUDE' or 'EXCLUDE'
    split_factor: float | None
    sensitivity_action: str  # 'INCLUDE' or 'EXCLUDE'
    k_ledger: float
    has_vendor_splits: bool
    holder_count: int
    median_ratio: float | None
    mad_log: float | None
    adj_median_ratio: float | None


def validate_all_vendor_splits(vendor_splits: list[SplitEvent]) -> None:
    """Validate every event in vendor ledger snapshot."""
    for s in vendor_splits:
        s.validate()


def compute_k_ledger_and_presence(
    prev_period: str, curr_period: str, vendor_splits: list[SplitEvent]
) -> tuple[float, bool]:
    """Compute period-pair split coefficient K_ledger and whether vendor split events occurred.

    Validates ISO date format and enforces prev_period < curr_period.
    Compares parsed date objects rather than raw strings.
    Includes splits with prev_period < ex_date <= curr_period.
    Enforces that cumulative split factor product remains finite and positive.
    """
    try:
        prev_d = date.fromisoformat(prev_period.strip())
        curr_d = date.fromisoformat(curr_period.strip())
    except (TypeError, ValueError) as err:
        raise ValueError(f"Invalid ISO period string: prev={prev_period!r}, curr={curr_period!r}") from err

    if prev_d >= curr_d:
        raise ValueError(f"prev_period ({prev_period}) must be strictly before curr_period ({curr_period})")

    validate_all_vendor_splits(vendor_splits)

    applicable_splits = [
        s for s in vendor_splits
        if prev_d < date.fromisoformat(s.ex_date.strip()) <= curr_d
    ]
    has_splits = len(applicable_splits) > 0
    if not applicable_splits:
        return 1.0, False

    k = 1.0
    for s in applicable_splits:
        k *= float(s.ratio)
        if not math.isfinite(k) or k <= 0.0:
            raise ValueError(f"Cumulative split factor product overflow or non-finite: {k}")

    return k, has_splits


def compute_holder_log_statistics(
    holders: list[ContinuousHolder], k_ledger: float
) -> tuple[float | None, float | None, float | None, int]:
    """Compute log-ratio median, MAD_log, and K_ledger-adjusted median for continuous holders.

    Rejects invalid holders and enforces N consistency (N == len(holders)).
    Guarantees numeric closure: raises ValueError on overflow or non-finite statistics.
    """
    if not is_strict_positive_number(k_ledger):
        raise ValueError(f"Invalid k_ledger: {k_ledger!r}")

    if not holders:
        return None, None, None, 0

    valid_ratios: list[float] = []
    for h in holders:
        h.validate()
        r = float(h.curr_shares) / float(h.prev_shares)
        if not math.isfinite(r) or r <= 0.0:
            raise ValueError(f"Holder ratio overflow or non-positive: {r}")
        valid_ratios.append(r)

    n = len(valid_ratios)
    assert n == len(holders), "Holder count consistency check"

    try:
        log_ratios = [math.log(r) for r in valid_ratios]
        mu_log = statistics.median(log_ratios)
        tilde_r = math.exp(mu_log)

        abs_deviations = [abs(y - mu_log) for y in log_ratios]
        mad_log = statistics.median(abs_deviations)

        mu_adj_log = mu_log - math.log(float(k_ledger))
        tilde_r_prime = math.exp(mu_adj_log)
    except (OverflowError, ValueError) as err:
        raise ValueError(f"Holder log statistics overflow or calculation error: {err}") from err

    if not (math.isfinite(tilde_r) and math.isfinite(mad_log) and math.isfinite(tilde_r_prime)):
        raise ValueError("Holder log statistics produced non-finite value.")

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
    has_vendor_splits: bool,
    k_ledger: float,
    holders: list[ContinuousHolder],
) -> SplitWaterfallResult:
    """Execute ordered split waterfall precedence (Gates 0, 1, 2) matching Contract v0.8.1.

    Executes Gate 0 STOP before holder calculation, ensuring unusable holder data cannot defeat exclusion.
    """
    if type(is_corporate_action_unknown) is not bool:
        raise TypeError(f"is_corporate_action_unknown must be strict bool, got {type(is_corporate_action_unknown).__name__}")
    if type(has_vendor_splits) is not bool:
        raise TypeError(f"has_vendor_splits must be strict bool, got {type(has_vendor_splits).__name__}")
    if not is_strict_positive_number(k_ledger):
        raise ValueError(f"Invalid k_ledger: {k_ledger!r}")

    # Gate 0: Corporate action unknown / identity broken / unresolved ownership (STOP IMMEDIATELY)
    if is_corporate_action_unknown:
        return SplitWaterfallResult(
            state="CORPORATE_ACTION_UNKNOWN",
            action="EXCLUDE",
            split_factor=None,
            sensitivity_action="EXCLUDE",
            k_ledger=float(k_ledger),
            has_vendor_splits=has_vendor_splits,
            holder_count=len(holders),
            median_ratio=None,
            mad_log=None,
            adj_median_ratio=None,
        )

    if not has_vendor_splits and abs(k_ledger - 1.0) > 1e-9:
        raise ValueError(f"has_vendor_splits=False requires k_ledger=1.0, got {k_ledger}")

    tilde_r, mad_log, tilde_r_prime, n = compute_holder_log_statistics(holders, k_ledger)

    # Gate 1: Vendor ledger has split records (has_vendor_splits == True)
    if has_vendor_splits:
        if n < 20:
            return SplitWaterfallResult(
                state="KNOWN_SPLIT_LOW_POWER",
                action="INCLUDE",
                split_factor=float(k_ledger),
                sensitivity_action="EXCLUDE",
                k_ledger=float(k_ledger),
                has_vendor_splits=True,
                holder_count=n,
                median_ratio=tilde_r,
                mad_log=mad_log,
                adj_median_ratio=tilde_r_prime,
            )
        else:
            assert tilde_r_prime is not None
            if 0.8 <= tilde_r_prime <= 1.2:
                return SplitWaterfallResult(
                    state="KNOWN_SPLIT_PASS",
                    action="INCLUDE",
                    split_factor=float(k_ledger),
                    sensitivity_action="INCLUDE",
                    k_ledger=float(k_ledger),
                    has_vendor_splits=True,
                    holder_count=n,
                    median_ratio=tilde_r,
                    mad_log=mad_log,
                    adj_median_ratio=tilde_r_prime,
                )
            else:
                return SplitWaterfallResult(
                    state="KNOWN_SPLIT_MISMATCH",
                    action="EXCLUDE",
                    split_factor=None,
                    sensitivity_action="EXCLUDE",
                    k_ledger=float(k_ledger),
                    has_vendor_splits=True,
                    holder_count=n,
                    median_ratio=tilde_r,
                    mad_log=mad_log,
                    adj_median_ratio=tilde_r_prime,
                )

    # Gate 2: Vendor ledger has NO split records (has_vendor_splits == False)
    if n < 20:
        return SplitWaterfallResult(
            state="LEDGER_ONLY_LOW_POWER",
            action="INCLUDE",
            split_factor=1.0,
            sensitivity_action="EXCLUDE",
            k_ledger=1.0,
            has_vendor_splits=False,
            holder_count=n,
            median_ratio=tilde_r,
            mad_log=mad_log,
            adj_median_ratio=tilde_r_prime,
        )
    else:
        assert tilde_r is not None
        assert mad_log is not None
        matched = is_rational_split_factor_match(tilde_r, tolerance=0.05)
        if not matched:
            return SplitWaterfallResult(
                state="CLEAN",
                action="INCLUDE",
                split_factor=1.0,
                sensitivity_action="INCLUDE",
                k_ledger=1.0,
                has_vendor_splits=False,
                holder_count=n,
                median_ratio=tilde_r,
                mad_log=mad_log,
                adj_median_ratio=tilde_r_prime,
            )
        elif mad_log <= 0.15:
            return SplitWaterfallResult(
                state="SPLIT_UNKNOWN",
                action="EXCLUDE",
                split_factor=None,
                sensitivity_action="EXCLUDE",
                k_ledger=1.0,
                has_vendor_splits=False,
                holder_count=n,
                median_ratio=tilde_r,
                mad_log=mad_log,
                adj_median_ratio=tilde_r_prime,
            )
        else:
            return SplitWaterfallResult(
                state="SPLIT_AUDIT_AMBIGUOUS_HIGH_DISPERSION",
                action="EXCLUDE",
                split_factor=None,
                sensitivity_action="EXCLUDE",
                k_ledger=1.0,
                has_vendor_splits=False,
                holder_count=n,
                median_ratio=tilde_r,
                mad_log=mad_log,
                adj_median_ratio=tilde_r_prime,
            )
