"""Dual-denominator coverage tracking (D1 Raw SEC Scope vs D2 Price-Covered Scope)."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
import math
from typing import Any

from research.smart_money.m0.src.ownership_state_machine import (
    is_strict_nonnegative_int,
    is_strict_nonnegative_number,
)

D1Key = tuple[str, str]  # (raw_cusip, period_of_report)
D2Key = tuple[str, str]  # (primary_stock_id, period_of_report)


def _validate_iso_date(date_str: Any, field_name: str = "period_of_report") -> str:
    """Validate string as a valid ISO YYYY-MM-DD date."""
    if not isinstance(date_str, str) or not date_str.strip():
        raise ValueError(f"{field_name} must be a non-empty ISO date string, got {date_str!r}")
    clean = date_str.strip()
    try:
        date.fromisoformat(clean)
    except ValueError as err:
        raise ValueError(f"Invalid ISO date format for {field_name}: {date_str!r}") from err
    return clean


@dataclass
class CoverageTracker:
    """Tracks coverage sets and conversion attrition across pipeline stages."""
    # D1 Scope: Raw SEC cash-equity holdings
    d1_keys: set[D1Key] = field(default_factory=set)
    d1_filer_count: dict[D1Key, int] = field(default_factory=lambda: defaultdict(int))
    d1_value_usd: dict[D1Key, float] = field(default_factory=lambda: defaultdict(float))

    # Attrition categories from D1
    unmapped_cusip_keys: set[D1Key] = field(default_factory=set)
    ambiguous_mapping_keys: set[D1Key] = field(default_factory=set)
    non_equity_or_etf_keys: set[D1Key] = field(default_factory=set)
    corporate_action_unknown_keys: set[D1Key] = field(default_factory=set)

    # D2 Scope: Mapped primary stocks
    d2_mapped_keys: set[D2Key] = field(default_factory=set)
    d2_price_covered_keys: set[D2Key] = field(default_factory=set)
    d2_price_missing_keys: set[D2Key] = field(default_factory=set)

    # Split state classification counts within D2
    split_state_keys: dict[str, set[D2Key]] = field(default_factory=lambda: defaultdict(set))

    # Final IC eligible keys
    final_ic_eligible_keys: set[D2Key] = field(default_factory=set)

    def record_d1(self, raw_cusip: str, period: str, filer_count: int = 1, value_usd: float = 0.0) -> None:
        """Register a raw SEC D1 key with strict field validation."""
        if not raw_cusip or not str(raw_cusip).strip():
            raise ValueError("raw_cusip cannot be blank or empty.")
        cusip_clean = str(raw_cusip).strip().upper()
        period_clean = _validate_iso_date(period, "period_of_report")

        if not is_strict_nonnegative_int(filer_count):
            raise ValueError(f"filer_count must be a non-negative integer, got {filer_count!r}")

        if not is_strict_nonnegative_number(value_usd):
            raise ValueError(f"value_usd must be a finite non-negative number, got {value_usd!r}")

        key = (cusip_clean, period_clean)
        self.d1_keys.add(key)
        self.d1_filer_count[key] += int(filer_count)
        self.d1_value_usd[key] += float(value_usd)

    def record_d2_mapping(self, raw_cusip: str, period: str, primary_stock_id: str) -> None:
        """Register successful mapping to D2 with strict validation."""
        if not raw_cusip or not str(raw_cusip).strip():
            raise ValueError("raw_cusip cannot be blank or empty.")
        if not primary_stock_id or not str(primary_stock_id).strip():
            raise ValueError("primary_stock_id cannot be blank or empty.")
        period_clean = _validate_iso_date(period, "period_of_report")

        d2_key = (str(primary_stock_id).strip(), period_clean)
        self.d2_mapped_keys.add(d2_key)

    def record_split_state(self, primary_stock_id: str, period: str, state: str) -> None:
        """Record split state classification for a D2 key with strict validation."""
        if not primary_stock_id or not str(primary_stock_id).strip():
            raise ValueError("primary_stock_id cannot be blank or empty.")
        if not state or not str(state).strip():
            raise ValueError("state cannot be blank or empty.")
        period_clean = _validate_iso_date(period, "period_of_report")

        d2_key = (str(primary_stock_id).strip(), period_clean)
        self.split_state_keys[str(state).strip()].add(d2_key)

    def generate_coverage_summary(self) -> dict[str, Any]:
        """Compute dual-denominator summary statistics and loss breakdown."""
        d1_count = len(self.d1_keys)
        d2_mapped_count = len(self.d2_mapped_keys)
        d2_price_count = len(self.d2_price_covered_keys)
        ic_eligible_count = len(self.final_ic_eligible_keys)

        mapping_rate = (d2_mapped_count / d1_count) if d1_count > 0 else 0.0
        price_coverage_rate = (d2_price_count / d2_mapped_count) if d2_mapped_count > 0 else 0.0
        conversion_retention_rate = (ic_eligible_count / d1_count) if d1_count > 0 else 0.0

        state_distribution = {
            state: {
                "count": len(keys),
                "pct_of_d2": (len(keys) / d2_mapped_count * 100.0) if d2_mapped_count > 0 else 0.0,
            }
            for state, keys in sorted(self.split_state_keys.items())
        }

        return {
            "d1_raw_sec_keys_total": d1_count,
            "d2_mapped_keys_total": d2_mapped_count,
            "d2_price_covered_keys_total": d2_price_count,
            "final_ic_eligible_keys_total": ic_eligible_count,
            "openfigi_mapping_rate": round(mapping_rate, 4),
            "price_coverage_rate": round(price_coverage_rate, 4),
            "conversion_retention_rate": round(conversion_retention_rate, 4),
            "attrition_breakdown": {
                "unmapped_cusips": len(self.unmapped_cusip_keys),
                "ambiguous_mappings": len(self.ambiguous_mapping_keys),
                "non_equity_or_etf": len(self.non_equity_or_etf_keys),
                "corporate_action_unknown": len(self.corporate_action_unknown_keys),
                "price_missing": len(self.d2_price_missing_keys),
            },
            "split_state_distribution": state_distribution,
        }
