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

VALID_SPLIT_STATES: frozenset[str] = frozenset(
    {
        "CORPORATE_ACTION_UNKNOWN",
        "KNOWN_SPLIT_LOW_POWER",
        "KNOWN_SPLIT_PASS",
        "KNOWN_SPLIT_MISMATCH",
        "LEDGER_ONLY_LOW_POWER",
        "CLEAN",
        "SPLIT_UNKNOWN",
        "SPLIT_AUDIT_AMBIGUOUS_HIGH_DISPERSION",
    }
)

PRIMARY_INCLUDE_SPLIT_STATES: frozenset[str] = frozenset(
    {
        "KNOWN_SPLIT_LOW_POWER",
        "KNOWN_SPLIT_PASS",
        "LEDGER_ONLY_LOW_POWER",
        "CLEAN",
    }
)


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
    """Tracks coverage sets, projection mappings, and conversion attrition across pipeline stages."""
    # D1 Scope: Raw SEC cash-equity holdings
    d1_keys: set[D1Key] = field(default_factory=set)
    d1_filer_count: dict[D1Key, int] = field(default_factory=lambda: defaultdict(int))
    d1_value_usd: dict[D1Key, float] = field(default_factory=lambda: defaultdict(float))

    # D1 -> D2 projection and mapping
    d1_to_d2: dict[D1Key, D2Key] = field(default_factory=dict)
    d2_to_d1: dict[D2Key, set[D1Key]] = field(default_factory=lambda: defaultdict(set))

    # Attrition tracking from D1
    unmapped_cusip_keys: set[D1Key] = field(default_factory=set)
    ambiguous_mapping_keys: set[D1Key] = field(default_factory=set)
    non_equity_or_etf_keys: set[D1Key] = field(default_factory=set)
    corporate_action_unknown_keys: set[D1Key] = field(default_factory=set)

    # D2 Scope: Mapped primary stocks
    d2_mapped_keys: set[D2Key] = field(default_factory=set)
    d2_price_covered_keys: set[D2Key] = field(default_factory=set)
    d2_price_missing_keys: set[D2Key] = field(default_factory=set)

    # Split state classification counts within D2 price-covered scope
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
        """Register successful mapping from D1 key to D2 stock ID.

        Enforces that D1 key has been registered and rejects conflicting remaps.
        """
        if not raw_cusip or not str(raw_cusip).strip():
            raise ValueError("raw_cusip cannot be blank or empty.")
        if not primary_stock_id or not str(primary_stock_id).strip():
            raise ValueError("primary_stock_id cannot be blank or empty.")
        period_clean = _validate_iso_date(period, "period_of_report")
        cusip_clean = str(raw_cusip).strip().upper()
        stock_clean = str(primary_stock_id).strip()

        d1_key = (cusip_clean, period_clean)
        d2_key = (stock_clean, period_clean)

        if d1_key not in self.d1_keys:
            raise ValueError(f"Cannot map unregistered D1 key: {d1_key}. Call record_d1 first.")

        if d1_key in self.d1_to_d2 and self.d1_to_d2[d1_key] != d2_key:
            raise ValueError(
                f"Conflicting D2 remap for D1 key {d1_key}: already mapped to {self.d1_to_d2[d1_key]}, cannot remap to {d2_key}"
            )

        self.d1_to_d2[d1_key] = d2_key
        self.d2_to_d1[d2_key].add(d1_key)
        self.d2_mapped_keys.add(d2_key)

    def record_d2_price_covered(self, primary_stock_id: str, period: str) -> None:
        """Register a D2 key as having valid price coverage.

        Requires mapped D2 key and mutual exclusivity with price_missing.
        """
        if not primary_stock_id or not str(primary_stock_id).strip():
            raise ValueError("primary_stock_id cannot be blank or empty.")
        period_clean = _validate_iso_date(period, "period_of_report")
        d2_key = (str(primary_stock_id).strip(), period_clean)

        if d2_key not in self.d2_mapped_keys:
            raise ValueError(f"Cannot record price coverage for unmapped D2 key: {d2_key}")

        if d2_key in self.d2_price_missing_keys:
            raise ValueError(f"D2 key {d2_key} is already recorded as price missing.")

        self.d2_price_covered_keys.add(d2_key)

    def record_d2_price_missing(self, primary_stock_id: str, period: str) -> None:
        """Register a D2 key as missing price coverage.

        Requires mapped D2 key and mutual exclusivity with price_covered.
        """
        if not primary_stock_id or not str(primary_stock_id).strip():
            raise ValueError("primary_stock_id cannot be blank or empty.")
        period_clean = _validate_iso_date(period, "period_of_report")
        d2_key = (str(primary_stock_id).strip(), period_clean)

        if d2_key not in self.d2_mapped_keys:
            raise ValueError(f"Cannot record price missing for unmapped D2 key: {d2_key}")

        if d2_key in self.d2_price_covered_keys:
            raise ValueError(f"D2 key {d2_key} is already recorded as price covered.")

        self.d2_price_missing_keys.add(d2_key)

    def record_split_state(self, primary_stock_id: str, period: str, state: str) -> None:
        """Record split state classification for a price-covered D2 key.

        Enforces that D2 key is price-covered, state is one of the 8 frozen states, and no conflicting state exists.
        """
        if not primary_stock_id or not str(primary_stock_id).strip():
            raise ValueError("primary_stock_id cannot be blank or empty.")
        if not state or not str(state).strip():
            raise ValueError("state cannot be blank or empty.")
        period_clean = _validate_iso_date(period, "period_of_report")
        state_clean = str(state).strip()

        if state_clean not in VALID_SPLIT_STATES:
            raise ValueError(f"Invalid split state: {state_clean!r}. Must be one of {sorted(VALID_SPLIT_STATES)}")

        d2_key = (str(primary_stock_id).strip(), period_clean)

        if d2_key not in self.d2_price_covered_keys:
            raise ValueError(f"Cannot record split state for non-price-covered D2 key: {d2_key}")

        for existing_state, keys in self.split_state_keys.items():
            if d2_key in keys and existing_state != state_clean:
                raise ValueError(
                    f"Conflicting split state for {d2_key}: already {existing_state}, cannot set to {state_clean}"
                )

        self.split_state_keys[state_clean].add(d2_key)

    def record_final_ic_eligible(self, primary_stock_id: str, period: str) -> None:
        """Record a D2 key as passing all gates and eligible for final IC evaluation.

        Requires mapped + price-covered and a Primary-INCLUDE split state.
        """
        if not primary_stock_id or not str(primary_stock_id).strip():
            raise ValueError("primary_stock_id cannot be blank or empty.")
        period_clean = _validate_iso_date(period, "period_of_report")
        d2_key = (str(primary_stock_id).strip(), period_clean)

        if d2_key not in self.d2_price_covered_keys:
            raise ValueError(f"Cannot mark {d2_key} as IC eligible: not in price covered keys.")

        current_state = None
        for s, keys in self.split_state_keys.items():
            if d2_key in keys:
                current_state = s
                break

        if current_state not in PRIMARY_INCLUDE_SPLIT_STATES:
            raise ValueError(
                f"Cannot mark {d2_key} as IC eligible: split state is {current_state!r} (must be in Primary-INCLUDE)"
            )

        self.final_ic_eligible_keys.add(d2_key)

    def record_attrition(self, raw_cusip: str, period: str, category: str) -> None:
        """Record D1 key attrition reason.

        Requires an existing D1 key.
        """
        if not raw_cusip or not str(raw_cusip).strip():
            raise ValueError("raw_cusip cannot be blank or empty.")
        period_clean = _validate_iso_date(period, "period_of_report")
        key = (str(raw_cusip).strip().upper(), period_clean)

        if key not in self.d1_keys:
            raise ValueError(f"Cannot record attrition for unregistered D1 key: {key}")

        cat = str(category).strip().lower()
        if cat == "unmapped_cusip":
            self.unmapped_cusip_keys.add(key)
        elif cat == "ambiguous_mapping":
            self.ambiguous_mapping_keys.add(key)
        elif cat == "non_equity_or_etf":
            self.non_equity_or_etf_keys.add(key)
        elif cat == "corporate_action_unknown":
            self.corporate_action_unknown_keys.add(key)
        else:
            raise ValueError(f"Unknown attrition category: {category!r}")

    def generate_coverage_summary(self) -> dict[str, Any]:
        """Compute dual-denominator summary statistics, penetration rates, and loss breakdown."""
        d1_count = len(self.d1_keys)
        d1_total_filer_count = sum(self.d1_filer_count.values())
        d1_total_value_usd = sum(self.d1_value_usd.values())

        d1_mapped_keys = set(self.d1_to_d2.keys())
        d1_mapped_count = len(d1_mapped_keys)
        d1_mapped_filer_count = sum(self.d1_filer_count[k] for k in d1_mapped_keys)
        d1_mapped_value_usd = sum(self.d1_value_usd[k] for k in d1_mapped_keys)

        d1_mapping_rate = (d1_mapped_count / d1_count) if d1_count > 0 else 0.0
        d1_filer_penetration_rate = (d1_mapped_filer_count / d1_total_filer_count) if d1_total_filer_count > 0 else 0.0
        d1_value_penetration_rate = (d1_mapped_value_usd / d1_total_value_usd) if d1_total_value_usd > 0 else 0.0

        d2_mapped_count = len(self.d2_mapped_keys)
        d2_price_count = len(self.d2_price_covered_keys)
        price_coverage_rate = (d2_price_count / d2_mapped_count) if d2_mapped_count > 0 else 0.0

        # Split state distribution relative to D2 PRICE-COVERED denominator
        state_distribution = {
            state: {
                "count": len(keys),
                "pct_of_price_covered_d2": (len(keys) / d2_price_count * 100.0) if d2_price_count > 0 else 0.0,
            }
            for state, keys in sorted(self.split_state_keys.items())
        }

        # Final conversion retention
        final_ic_d2_count = len(self.final_ic_eligible_keys)
        final_ic_d1_keys = {
            d1 for d2 in self.final_ic_eligible_keys for d1 in self.d2_to_d1.get(d2, set())
        }
        d1_conversion_retention_rate = (len(final_ic_d1_keys) / d1_count) if d1_count > 0 else 0.0
        d2_conversion_retention_rate = (final_ic_d2_count / d2_mapped_count) if d2_mapped_count > 0 else 0.0

        return {
            "d1_raw_sec_keys_total": d1_count,
            "d1_total_filer_count": d1_total_filer_count,
            "d1_total_value_usd": d1_total_value_usd,
            "d1_mapped_keys_total": d1_mapped_count,
            "d1_mapped_filer_count": d1_mapped_filer_count,
            "d1_mapped_value_usd": d1_mapped_value_usd,
            "d1_key_mapping_rate": round(d1_mapping_rate, 4),
            "d1_filer_count_penetration_rate": round(d1_filer_penetration_rate, 4),
            "d1_value_penetration_rate": round(d1_value_penetration_rate, 4),
            "openfigi_mapping_rate": round(d1_mapping_rate, 4),
            "d2_mapped_keys_total": d2_mapped_count,
            "d2_price_covered_keys_total": d2_price_count,
            "d2_price_missing_keys_total": len(self.d2_price_missing_keys),
            "price_coverage_rate": round(price_coverage_rate, 4),
            "final_ic_eligible_d2_keys_total": final_ic_d2_count,
            "d1_conversion_retention_rate": round(d1_conversion_retention_rate, 4),
            "d2_conversion_retention_rate": round(d2_conversion_retention_rate, 4),
            "attrition_breakdown": {
                "unmapped_cusips": len(self.unmapped_cusip_keys),
                "ambiguous_mappings": len(self.ambiguous_mapping_keys),
                "non_equity_or_etf": len(self.non_equity_or_etf_keys),
                "corporate_action_unknown": len(self.corporate_action_unknown_keys),
                "price_missing": len(self.d2_price_missing_keys),
            },
            "split_state_distribution": state_distribution,
        }
