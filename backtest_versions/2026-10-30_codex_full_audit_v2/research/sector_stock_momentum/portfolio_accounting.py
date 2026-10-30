"""Codex correction: self-financing proportional-cost rebalance, then holding return."""
import math


def capital_after_costs(target, previous, cost):
    """Solve k + cost * sum(abs(k * target - previous)) == 1.

    Targets are weights AFTER fees. The old ledger deducted inception fees at
    period end, allowing a fully invested unlevered loss to exceed 100%.
    """
    if not 0 <= cost < 1:
        raise ValueError("invalid transaction cost")
    keys = set(target) | set(previous)
    if any(not math.isfinite(v) or v < 0 for v in [*target.values(), *previous.values()]):
        raise ValueError("long-only weights must be finite and nonnegative")
    if cost * sum(target.values()) >= 1:
        raise ValueError("fee/exposure combination has no stable rebalance")
    turnover = lambda k: sum(abs(k * target.get(s, 0) - previous.get(s, 0)) for s in keys)
    if cost * turnover(0) >= 1:
        return 0.0, turnover(0)
    lo, hi = 0.0, 1.0
    for _ in range(60):
        k = (lo + hi) / 2
        if k + cost * turnover(k) > 1:
            hi = k
        else:
            lo = k
    k = (lo + hi) / 2
    return k, turnover(k)
