"""M0 delta-shares calculation, 3x censor-risk heuristic weighting, and stock-level aggregation."""

from collections import defaultdict
import math
from typing import Any


def compute_censor_weight(
    is_new: bool,
    is_exit: bool,
    prev_shares: float,
    prev_value_usd: float,
    curr_shares: float,
    curr_value_usd: float,
) -> tuple[float, str]:
    """Apply conservative 3x Censor-Risk Heuristic weighting and validate state consistency.
    
    SEC Exemption statutory threshold is (shares < 10,000 AND value < $200,000).
    Conservative 3x heuristic uses OR condition: (shares < 30,000 OR value < $600,000).
    
    Returns:
        (censor_weight, label)
    """
    if is_new and is_exit:
        raise ValueError("Holding cannot simultaneously be NEW and EXIT.")

    if is_new:
        if prev_shares != 0.0 or prev_value_usd != 0.0:
            raise ValueError(
                f"NEW position consistency error: prev_shares={prev_shares}, prev_value_usd={prev_value_usd} must be 0"
            )
        if curr_shares <= 0.0 or curr_value_usd <= 0.0:
            raise ValueError(
                f"NEW position consistency error: curr_shares={curr_shares}, curr_value_usd={curr_value_usd} must be > 0"
            )
        if curr_shares < 30_000.0 or curr_value_usd < 600_000.0:
            return 0.3, "LOW_CONFIDENCE_NEW"
        return 1.0, "REGULAR_NEW"

    elif is_exit:
        if curr_shares != 0.0 or curr_value_usd != 0.0:
            raise ValueError(
                f"EXIT position consistency error: curr_shares={curr_shares}, curr_value_usd={curr_value_usd} must be 0"
            )
        if prev_shares <= 0.0 or prev_value_usd <= 0.0:
            raise ValueError(
                f"EXIT position consistency error: prev_shares={prev_shares}, prev_value_usd={prev_value_usd} must be > 0"
            )
        if prev_shares < 30_000.0 or prev_value_usd < 600_000.0:
            return 0.3, "LOW_CONFIDENCE_EXIT"
        return 1.0, "REGULAR_EXIT"

    else:
        # Existing continuous holding
        if prev_shares <= 0.0 or curr_shares <= 0.0 or prev_value_usd <= 0.0 or curr_value_usd <= 0.0:
            raise ValueError(
                f"Continuous holding consistency error: non-positive values without NEW/EXIT flag: "
                f"prev=({prev_shares}, {prev_value_usd}), curr=({curr_shares}, {curr_value_usd})"
            )
        return 1.0, "REGULAR_HOLDING"


def compute_entity_delta_shares(
    prev_shares: float,
    curr_shares: float,
    split_factor: float,
) -> float:
    """Compute split-adjusted delta shares for an entity: curr_shares - (prev_shares * split_factor)."""
    if split_factor <= 0 or not math.isfinite(split_factor):
        raise ValueError(f"Invalid split_factor for delta calculation: {split_factor}")
    if prev_shares < 0 or curr_shares < 0:
        raise ValueError(f"Negative shares encountered: prev={prev_shares}, curr={curr_shares}")
    
    adjusted_prev = prev_shares * split_factor
    return curr_shares - adjusted_prev


def aggregate_m0_signals(
    entity_signals: list[dict[str, Any]],
) -> dict[str, float]:
    """Aggregate entity-level delta shares weighted by censor_weight to stock-level M0 signals.
    
    M0_signal(stock, Q) = sum(delta_shares * censor_weight)
    
    Returns:
        dict: primary_stock_id -> aggregated m0_signal
    """
    signals: dict[str, float] = defaultdict(float)

    for item in entity_signals:
        stock_id = str(item["primary_stock_id"]).strip()
        delta = float(item["delta_shares"])
        weight = float(item.get("censor_weight", 1.0))
        
        if not math.isfinite(delta):
            raise ValueError(f"Non-finite delta_shares for stock {stock_id}: {delta}")
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError(f"Invalid censor_weight for stock {stock_id}: {weight}")

        signals[stock_id] += delta * weight

    return dict(signals)
