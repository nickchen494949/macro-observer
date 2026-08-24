"""Entity connected component construction (numeric-min CIK), filing membership validation, and unrounded exact dedup."""

from collections import defaultdict
import math
from typing import Any

from research.smart_money.m0.src.ownership_state_machine import (
    is_strict_nonnegative_int,
    is_strict_nonnegative_number,
    is_valid_cik,
    normalize_cik,
)


def build_entity_connected_components(
    edges: list[tuple[str, str]], all_ciks: set[str] | None = None
) -> dict[str, str]:
    """Build connected components from undirected CIK relationship edges.
    
    Assigns canonical_entity_id = min(int(c) for c in component), zero-padded to 10 digits.
    Raises ValueError on ANY invalid or blank CIK in edges or all_ciks.
    """
    adj: dict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()

    if all_ciks:
        for c in all_ciks:
            if not is_valid_cik(c):
                raise ValueError(f"Invalid CIK in all_ciks: {c!r}")
            nodes.add(normalize_cik(c))

    for u, v in edges:
        if not is_valid_cik(u) or not is_valid_cik(v):
            raise ValueError(f"Invalid edge CIK pair: ({u!r}, {v!r})")
        u_norm, v_norm = normalize_cik(u), normalize_cik(v)
        nodes.add(u_norm)
        nodes.add(v_norm)
        adj[u_norm].add(v_norm)
        adj[v_norm].add(u_norm)

    visited: set[str] = set()
    cik_to_entity: dict[str, str] = {}

    for node in sorted(nodes, key=lambda x: int(x)):
        if node in visited:
            continue

        component: set[str] = set()
        queue = [node]
        visited.add(node)
        while queue:
            curr = queue.pop(0)
            component.add(curr)
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # Canonical CIK is NUMERIC minimum in the connected component
        numeric_min_val = min(int(c) for c in component)
        canonical_id = f"{numeric_min_val:010d}"

        for member in component:
            cik_to_entity[member] = canonical_id
            cik_to_entity[str(int(member))] = canonical_id

    return cik_to_entity


def validate_entity_membership(
    prev_filing_members: set[str], curr_filing_members: set[str]
) -> tuple[bool, str]:
    """Validate that filing membership is identical between Q-1 and Q.
    
    Raises ValueError on any invalid or blank CIK in members.
    Returns (is_eligible, reason).
    """
    for c in prev_filing_members:
        if not is_valid_cik(c):
            raise ValueError(f"Invalid CIK in prev_filing_members: {c!r}")
    for c in curr_filing_members:
        if not is_valid_cik(c):
            raise ValueError(f"Invalid CIK in curr_filing_members: {c!r}")

    prev_clean = {normalize_cik(c) for c in prev_filing_members}
    curr_clean = {normalize_cik(c) for c in curr_filing_members}

    if len(curr_clean) == 0 or len(prev_clean) == 0:
        return False, "EMPTY_FILING_MEMBERS"

    if prev_clean != curr_clean:
        return False, "MEMBERSHIP_INCOMPLETE"

    return True, "ELIGIBLE"


def deduplicate_entity_disclosures(
    canonical_entity_id: str,
    holdings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate disclosures within a single canonical entity.
    
    Cross-disclosure deduplication is STRICTLY confined within the same canonical_entity_id.
    Requires valid economic_owner_cik.
    Shares and voting fields must be finite non-negative INTEGERS.
    Value must be finite non-negative real number.
    Exact economic signatures MUST NOT be rounded.
    """
    canon_cik = normalize_cik(canonical_entity_id)

    seen_signatures: set[tuple[str, str, str, tuple[int, float, int, int, int]]] = set()
    deduped_rows: list[dict[str, Any]] = []

    for row in holdings:
        row_entity = normalize_cik(row.get("canonical_entity_id", canonical_entity_id))
        if row_entity != canon_cik:
            raise ValueError(
                f"Cross-entity deduplication prohibited: expected entity '{canon_cik}', got '{row_entity}'"
            )

        cusip = str(row.get("cusip", "")).strip().upper()
        if not cusip:
            raise ValueError("Blank or empty CUSIP in holding row.")

        period = str(row.get("period_of_report", "")).strip()
        if not period:
            raise ValueError("Blank or empty period_of_report in holding row.")

        econ_owner_raw = row.get("economic_owner_cik")
        if econ_owner_raw is None or not is_valid_cik(econ_owner_raw):
            raise ValueError(f"Missing or invalid economic_owner_cik in holding row: {econ_owner_raw!r}")
        econ_owner = normalize_cik(econ_owner_raw)

        shares = row.get("total_shares")
        val_usd = row.get("total_value_usd")
        v_sole = row.get("total_vote_sole", 0)
        v_shared = row.get("total_vote_shared", 0)
        v_none = row.get("total_vote_none", 0)

        # Validate integer fields (rejecting bool and fractions)
        for name, num in [
            ("total_shares", shares),
            ("total_vote_sole", v_sole),
            ("total_vote_shared", v_shared),
            ("total_vote_none", v_none),
        ]:
            if not is_strict_nonnegative_int(num):
                raise ValueError(f"Invalid non-integer or negative {name}: {num!r}")

        # Validate value USD
        if not is_strict_nonnegative_number(val_usd):
            raise ValueError(f"Invalid non-numeric or negative total_value_usd: {val_usd!r}")

        # Exact unrounded tuple signature with integer shares/votes
        sig = (
            int(shares),
            float(val_usd),
            int(v_sole),
            int(v_shared),
            int(v_none),
        )

        dedup_key = (cusip, period, econ_owner, sig)
        if dedup_key in seen_signatures:
            continue

        seen_signatures.add(dedup_key)
        deduped_rows.append(dict(row))

    return deduped_rows
