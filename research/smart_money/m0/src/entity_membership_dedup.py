"""Entity connected component construction, filing membership validation, and cross-disclosure dedup."""

from collections import defaultdict
from typing import Any


def build_entity_connected_components(
    edges: list[tuple[str, str]], all_ciks: set[str] | None = None
) -> dict[str, str]:
    """Build connected components from undirected CIK relationship edges.
    
    Assigns canonical_entity_id = min(ciks_in_component) for each component.
    Returns mapping: cik -> canonical_entity_id.
    """
    adj: dict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()

    if all_ciks:
        for c in all_ciks:
            c_str = str(c).strip()
            if c_str:
                nodes.add(c_str)

    for u, v in edges:
        u_str, v_str = str(u).strip(), str(v).strip()
        if u_str and v_str:
            nodes.add(u_str)
            nodes.add(v_str)
            adj[u_str].add(v_str)
            adj[v_str].add(u_str)

    visited: set[str] = set()
    cik_to_entity: dict[str, str] = {}

    for node in sorted(nodes):
        if node in visited:
            continue
        
        # Traverse component
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
        
        canonical_id = min(component)
        for member in component:
            cik_to_entity[member] = canonical_id

    return cik_to_entity


def validate_entity_membership(
    prev_filing_members: set[str], curr_filing_members: set[str]
) -> tuple[bool, str]:
    """Validate that filing membership is identical between Q-1 and Q.
    
    Only actual origin filers (not related-only advisor nodes) count toward filing_members.
    Returns (is_eligible, reason).
    """
    prev_clean = {str(c).strip() for c in prev_filing_members if str(c).strip()}
    curr_clean = {str(c).strip() for c in curr_filing_members if str(c).strip()}

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
    Two rows are folded into one iff:
    1. canonical_entity_id matches;
    2. cusip matches;
    3. period_of_report matches;
    4. economic_owner_cik matches;
    5. full economic signature (total_shares, total_value_usd, total_vote_sole,
       total_vote_shared, total_vote_none) matches exactly.
    """
    seen_signatures: set[tuple[str, str, str, tuple[float, float, float, float, float]]] = set()
    deduped_rows: list[dict[str, Any]] = []

    for row in holdings:
        row_entity = str(row.get("canonical_entity_id", canonical_entity_id))
        if row_entity != canonical_entity_id:
            raise ValueError(
                f"Cross-entity deduplication prohibited: expected entity '{canonical_entity_id}', got '{row_entity}'"
            )

        cusip = str(row.get("cusip", ""))
        period = str(row.get("period_of_report", ""))
        econ_owner = str(row.get("economic_owner_cik", ""))

        sig = (
            round(float(row.get("total_shares", 0.0)), 4),
            round(float(row.get("total_value_usd", 0.0)), 2),
            round(float(row.get("total_vote_sole", 0.0)), 4),
            round(float(row.get("total_vote_shared", 0.0)), 4),
            round(float(row.get("total_vote_none", 0.0)), 4),
        )

        dedup_key = (cusip, period, econ_owner, sig)
        if dedup_key in seen_signatures:
            # Identical economic disclosure from related filer, fold/skip
            continue

        seen_signatures.add(dedup_key)
        deduped_rows.append(dict(row))

    return deduped_rows
