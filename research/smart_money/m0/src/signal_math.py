"""M0 delta-shares calculation, 3x censor-risk heuristic weighting, and (stock, period) aggregation."""

from collections import defaultdict
import math
from typing import Any

from research.smart_money.m0.src.ownership_state_machine import (
    is_strict_nonnegative_number,
    is_strict_positive_number,
)


def compute_censor_weight(
    is_new: bool,
    is_exit: bool,
    prev_shares: int | float,
    prev_value_usd: int | float,
    curr_shares: int | float,
    curr_value_usd: int | float,
) -> tuple[float, str]:
    """Apply conservative 3x Censor-Risk Heuristic weighting and validate state consistency.

    SEC Exemption statutory threshold is (shares < 10,000 AND value < $200,000).
    Conservative 3x heuristic uses OR condition: (shares < 30,000 OR value < $600,000).

    Rejects bool and non-numeric/negative data.
    Returns:
        (censor_weight, label)
    """
    if type(is_new) is not bool or type(is_exit) is not bool:
        raise TypeError("is_new and is_exit flags must be strict boolean.")

    for name, val in [
        ("prev_shares", prev_shares),
        ("prev_value_usd", prev_value_usd),
        ("curr_shares", curr_shares),
        ("curr_value_usd", curr_value_usd),
    ]:
        if not is_strict_nonnegative_number(val):
            raise ValueError(f"Invalid non-numeric, non-finite or negative value for {name}: {val!r}")

    p_s, p_v = float(prev_shares), float(prev_value_usd)
    c_s, c_v = float(curr_shares), float(curr_value_usd)

    if is_new and is_exit:
        raise ValueError("Holding cannot simultaneously be NEW and EXIT.")

    if is_new:
        if p_s != 0.0 or p_v != 0.0:
            raise ValueError(
                f"NEW position consistency error: prev_shares={p_s}, prev_value_usd={p_v} must be 0"
            )
        if c_s <= 0.0 or c_v <= 0.0:
            raise ValueError(
                f"NEW position consistency error: curr_shares={c_s}, curr_value_usd={c_v} must be > 0"
            )
        if c_s < 30_000.0 or c_v < 600_000.0:
            return 0.3, "LOW_CONFIDENCE_NEW"
        return 1.0, "REGULAR_NEW"

    elif is_exit:
        if c_s != 0.0 or c_v != 0.0:
            raise ValueError(
                f"EXIT position consistency error: curr_shares={c_s}, curr_value_usd={c_v} must be 0"
            )
        if p_s <= 0.0 or p_v <= 0.0:
            raise ValueError(
                f"EXIT position consistency error: prev_shares={p_s}, prev_value_usd={p_v} must be > 0"
            )
        if p_s < 30_000.0 or p_v < 600_000.0:
            return 0.3, "LOW_CONFIDENCE_EXIT"
        return 1.0, "REGULAR_EXIT"

    else:
        # Existing continuous holding
        if p_s <= 0.0 or c_s <= 0.0 or p_v <= 0.0 or c_v <= 0.0:
            raise ValueError(
                f"Continuous holding consistency error: non-positive values without NEW/EXIT flag: "
                f"prev=({p_s}, {p_v}), curr=({c_s}, {c_v})"
            )
        return 1.0, "REGULAR_HOLDING"


def compute_entity_delta_shares(
    prev_shares: int | float,
    curr_shares: int | float,
    split_factor: int | float,
) -> float:
    """Compute split-adjusted delta shares for an entity: curr_shares - (prev_shares * split_factor)."""
    if not is_strict_positive_number(split_factor):
        raise ValueError(f"Invalid split_factor for delta calculation: {split_factor!r}")
    if not is_strict_nonnegative_number(prev_shares) or not is_strict_nonnegative_number(curr_shares):
        raise ValueError(f"Invalid non-finite or negative shares: prev={prev_shares!r}, curr={curr_shares!r}")

    adjusted_prev = float(prev_shares) * float(split_factor)
    return float(curr_shares) - adjusted_prev


def aggregate_m0_signals(
    entity_signals: list[dict[str, Any]],
) -> dict[tuple[str, str], float]:
    """Aggregate entity-level delta shares to (primary_stock_id, period_of_report) level M0 signals.

    Censor weight input MUST be exactly 0.3 or 1.0.
    Preserves exact (stock, period) composite key.
    M0_signal(stock, Q) = sum(delta_shares * censor_weight)

    Returns:
        dict: (primary_stock_id, period_of_report) -> aggregated m0_signal
    """
    signals: dict[tuple[str, str], float] = defaultdict(float)

    for item in entity_signals:
        stock_id = str(item.get("primary_stock_id", "")).strip()
        if not stock_id:
            raise ValueError("Blank or empty primary_stock_id in entity signal")

        period = str(item.get("period_of_report", "")).strip()
        if not period:
            raise ValueError(f"Blank or empty period_of_report for stock {stock_id}")

        delta = item.get("delta_shares")
        if isinstance(delta, bool) or not isinstance(delta, (int, float)) or not math.isfinite(delta):
            raise ValueError(f"Invalid non-numeric or non-finite delta_shares for stock {stock_id}: {delta!r}")

        weight = item.get("censor_weight", 1.0)
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
            raise ValueError(f"Invalid non-numeric censor_weight for stock {stock_id}: {weight!r}")

        w_val = float(weight)
        if not (math.isclose(w_val, 0.3, rel_tol=1e-7) or math.isclose(w_val, 1.0, rel_tol=1e-7)):
            raise ValueError(
                f"Censor weight input for stock {stock_id} must be exactly 0.3 or 1.0, got: {weight!r}"
            )

        key = (stock_id, period)
        signals[key] += float(delta) * w_val

    return dict(signals)
