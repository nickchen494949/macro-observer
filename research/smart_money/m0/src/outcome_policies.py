"""Return calculation, cash M&A settlement, rolling day selection, and cardinality invariant LEFT JOIN."""

import math
from typing import Any


def compute_adjusted_open_price(
    raw_open: float | None,
    raw_close: float | None,
    adj_close: float | None,
) -> float | None:
    """Compute split/dividend forward-adjusted open price.
    
    Formula: adjusted_open(T) = raw_open(T) * (adj_close(T) / raw_close(T))
    Validates that all inputs are strictly positive, finite numbers.
    """
    if raw_open is None or raw_close is None or adj_close is None:
        return None

    try:
        o, c, ac = float(raw_open), float(raw_close), float(adj_close)
    except (TypeError, ValueError):
        return None

    if not (math.isfinite(o) and math.isfinite(c) and math.isfinite(ac)):
        return None
    if o <= 0.0 or c <= 0.0 or ac <= 0.0:
        return None

    return o * (ac / c)


def compute_forward_return(
    entry_adj_open: float | None,
    exit_adj_open: float | None,
) -> float | None:
    """Compute open-to-open forward total return: (exit_adj_open / entry_adj_open) - 1.0."""
    if entry_adj_open is None or exit_adj_open is None:
        return None

    try:
        p_in, p_out = float(entry_adj_open), float(exit_adj_open)
    except (TypeError, ValueError):
        return None

    if not (math.isfinite(p_in) and math.isfinite(p_out)) or p_in <= 0.0 or p_out <= 0.0:
        return None

    return (p_out / p_in) - 1.0


def settle_cash_m_and_a(
    entry_adj_open: float | None,
    cash_consideration_per_share: float | None,
    is_cash_only: bool,
) -> tuple[float | None, str]:
    """Settle pure-cash M&A privatization against entry open price.
    
    Non-cash or unknown cash consideration is excluded (returns None, 'CORPORATE_ACTION_UNKNOWN').
    """
    if not is_cash_only or cash_consideration_per_share is None or entry_adj_open is None:
        return None, "CORPORATE_ACTION_UNKNOWN"

    try:
        p_in = float(entry_adj_open)
        cash = float(cash_consideration_per_share)
    except (TypeError, ValueError):
        return None, "CORPORATE_ACTION_UNKNOWN"

    if not (math.isfinite(p_in) and math.isfinite(cash)) or p_in <= 0.0 or cash <= 0.0:
        return None, "CORPORATE_ACTION_UNKNOWN"

    ret = (cash / p_in) - 1.0
    return ret, "CASH_M_AND_A_SETTLED"


def select_open_price_with_roll(
    trading_days_calendar: list[str],
    price_by_date: dict[str, float | None],
    target_date: str,
    max_roll_days: int = 5,
) -> tuple[float | None, int, str | None]:
    """Select open price with exchange calendar roll forward up to max_roll_days.
    
    Days with no quote still consume an exchange trading day slot.
    Returns:
        (price, days_rolled, actual_trade_date)
    """
    # Find start trading day index on or after target_date
    cal_sorted = sorted(trading_days_calendar)
    start_idx = None
    for i, d in enumerate(cal_sorted):
        if d >= target_date:
            start_idx = i
            break

    if start_idx is None:
        return None, 0, None

    for roll in range(max_roll_days):
        current_idx = start_idx + roll
        if current_idx >= len(cal_sorted):
            break
        current_date = cal_sorted[current_idx]
        price = price_by_date.get(current_date)
        if price is not None:
            try:
                p_val = float(price)
                if math.isfinite(p_val) and p_val > 0.0:
                    return p_val, roll, current_date
            except (TypeError, ValueError):
                pass

    return None, max_roll_days, None


def verify_cardinality_invariant(
    signals: list[dict[str, Any]],
    forward_returns: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Execute single official preregistered LEFT JOIN and enforce cardinality conservation.
    
    Enforces:
    1. Unique primary key (primary_stock_id, period_of_report) in signals;
    2. Unique primary key (primary_stock_id, period_of_report) in forward_returns;
    3. Output rows == Input signals count (COUNT(joined) == COUNT(signals)).
    """
    seen_signal_keys: set[tuple[str, str]] = set()
    for s in signals:
        key = (str(s["primary_stock_id"]).strip(), str(s["period_of_report"]).strip())
        if key in seen_signal_keys:
            raise ValueError(f"Duplicate key in m0_signals: {key}")
        seen_signal_keys.add(key)

    seen_return_keys: set[tuple[str, str]] = set()
    returns_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for r in forward_returns:
        key = (str(r["primary_stock_id"]).strip(), str(r["period_of_report"]).strip())
        if key in seen_return_keys:
            raise ValueError(f"Duplicate key in m0_forward_returns: {key}")
        seen_return_keys.add(key)
        returns_by_key[key] = r

    joined_rows: list[dict[str, Any]] = []
    missing_count = 0

    for s in signals:
        key = (str(s["primary_stock_id"]).strip(), str(s["period_of_report"]).strip())
        ret_record = returns_by_key.get(key)

        if ret_record is not None:
            fwd_ret = ret_record.get("forward_return")
            outcome_status = ret_record.get("outcome_status", "PRICE_COVERED")
            rolled_ret = ret_record.get("rolled_le_5_return")
        else:
            fwd_ret = None
            outcome_status = "PRICE_RECORD_MISSING"
            rolled_ret = None

        is_missing = 1 if fwd_ret is None else 0
        if is_missing == 1:
            missing_count += 1

        joined_rows.append(
            {
                "primary_stock_id": key[0],
                "period_of_report": key[1],
                "m0_signal": float(s["m0_signal"]),
                "forward_return": fwd_ret,
                "outcome_status": outcome_status,
                "rolled_le_5_return": rolled_ret,
                "is_outcome_missing": is_missing,
            }
        )

    # Cardinality Invariant Assertion
    if len(joined_rows) != len(signals):
        raise AssertionError(
            f"Cardinality invariant violated: joined_rows ({len(joined_rows)}) != signals ({len(signals)})"
        )

    metrics = {
        "signals_count": len(signals),
        "joined_count": len(joined_rows),
        "missing_count": missing_count,
        "valid_outcome_count": len(joined_rows) - missing_count,
        "cardinality_conserved": True,
    }

    return joined_rows, metrics


def derive_sensitivity_branches(
    joined_rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Derive 4 mandatory sensitivity branches from the single preregistered LEFT JOIN table."""
    primary_branch: list[dict[str, Any]] = []
    minus_100_branch: list[dict[str, Any]] = []
    zero_branch: list[dict[str, Any]] = []
    rolled_branch: list[dict[str, Any]] = []

    for row in joined_rows:
        is_missing = row["is_outcome_missing"] == 1 or row["forward_return"] is None

        # 1. Primary: Only keep valid returns
        if not is_missing:
            primary_branch.append(dict(row))

        # 2. Missing = -100% stress test
        r_m100 = dict(row)
        if is_missing:
            r_m100["forward_return"] = -1.0
        minus_100_branch.append(r_m100)

        # 3. Missing = 0% stress test
        r_zero = dict(row)
        if is_missing:
            r_zero["forward_return"] = 0.0
        zero_branch.append(r_zero)

        # 4. <= 5 days roll branch
        r_rolled = dict(row)
        if is_missing and row.get("rolled_le_5_return") is not None:
            r_rolled["forward_return"] = row["rolled_le_5_return"]
            r_rolled["is_outcome_missing"] = 0
            rolled_branch.append(r_rolled)
        elif not is_missing:
            rolled_branch.append(r_rolled)

    return {
        "primary": primary_branch,
        "missing_minus_100": minus_100_branch,
        "missing_zero": zero_branch,
        "rolled_le_5": rolled_branch,
    }
