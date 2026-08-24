"""Stage C Part C1 Pilot Benchmark Extractor and Discovery Engine.

Executes read-only, auditable pilot extraction against Phase 0 DB without modifying the source DB.
Full World-B Implementation covering:
1. Berkshire Hathaway 2023Q4 Apple Accession Aggregation (Raw Anchor: 905,560,000; Primary Ineligibility Breakdown).
2. Point72 2019Q4 Multi-Manager Relationship Discovery & Proposed Fixture (Actual PIT Timestamps & Graph Closure).
3. Four Canonical Split Pilot Pairs (NVDA 10:1, TSLA 3:1, AMZN 20:1, GOOGL 20:1) with True G(Q-1, Q) Graph,
   13F-HR/HR/A Scope, All-Member Component Gates, Strict Economic Owner Mapping, and Robust Other-Manager Classification.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any

from research.smart_money.m0.src.entity_membership_dedup import (
    build_entity_connected_components,
    deduplicate_entity_disclosures,
    filter_pit_entity_edges,
    validate_entity_membership,
    validate_entity_pair_confidential_gate,
)
from research.smart_money.m0.src.ownership_state_machine import (
    FilingHeader,
    HoldingRow,
    OwnershipPolicy,
    aggregate_accession_holdings,
    is_pit_accepted,
    is_valid_cik,
    normalize_cik,
    reconstruct_filer_state,
    resolve_ownership,
)
from research.smart_money.m0.src.split_waterfall import (
    ContinuousHolder,
    SplitEvent,
    compute_k_ledger_and_presence,
    evaluate_split_waterfall,
)
from research.smart_money.m0.src.storage_guard import open_readonly_sqlite


def classify_other_manager(om_val: str | None) -> tuple[str, list[str]]:
    """Classify the other_manager field into distinct semantic categories under Contract v0.8.2.

    Categories:
    - BLANK: None or empty string.
    - OFFICIAL_NA: exact case-insensitive 'N/A' (authorized by SEC FAQ Q48/Q49).
    - ZERO_SENTINEL: exact string '0' (empirical SEC data compatibility sentinel).
    - SINGLE_NUMERIC: exactly one strictly positive integer sequence (> 0, e.g. '1', '4', '602').
    - MULTI_NUMERIC_LIST: multiple integer sequence numbers (e.g. '1,2,4,11', '1 3 4').
    - FREE_TEXT_NAME: free-text manager names or dirty variants (e.g. 'NONE', 'NA', '00', '0.0', 'Blue Chip Partners LLC').

    Returns:
        (category, tokens)
    """
    if om_val is None:
        return "BLANK", []
    s = om_val.strip()
    if not s:
        return "BLANK", []

    if s.upper() == "N/A":
        return "OFFICIAL_NA", ["N/A"]

    if s == "0":
        return "ZERO_SENTINEL", ["0"]

    tokens = [t for t in re.split(r"[,\s]+", s) if t]
    if not tokens:
        return "BLANK", []

    if all(t.isdigit() for t in tokens):
        if len(tokens) == 1:
            val = int(tokens[0])
            if val > 0 and str(val) == tokens[0]:
                return "SINGLE_NUMERIC", tokens
            return "FREE_TEXT_NAME", tokens
        return "MULTI_NUMERIC_LIST", tokens

    return "FREE_TEXT_NAME", tokens


def build_line_level_manager_map(
    relationship_rows: list[Any],
    period: str | None = None,
) -> dict[tuple[str, str], str]:
    """Build line-level Column 7 sequence lookup map strictly from OTHERMANAGER2.tsv.

    Filters source_table == 'OTHERMANAGER2.tsv' and acceptance_datetime if period is provided.
    """
    rel_map: dict[tuple[str, str], str] = {}
    for r in relationship_rows:
        if isinstance(r, dict):
            acc = str(r["accession_number"]).strip()
            seq = str(r["sequence_number"]).strip()
            rel_cik = r["related_cik"]
            src = str(r.get("source_table", "")).strip()
            acc_dt = r.get("acceptance_datetime")
        elif len(r) == 8:
            # (acc, p_rep, rep_cik, rel_cik, rel_name, seq, src, acc_dt)
            acc = str(r[0]).strip()
            rel_cik = r[3]
            seq = str(r[5]).strip()
            src = str(r[6]).strip()
            acc_dt = r[7]
        elif len(r) == 6:
            # (acc, rep_cik, rel_cik, seq, src, acc_dt)
            acc = str(r[0]).strip()
            rel_cik = r[2]
            seq = str(r[3]).strip()
            src = str(r[4]).strip()
            acc_dt = r[5]
        elif len(r) == 5:
            # (acc, seq, rel_cik, src, acc_dt)
            acc = str(r[0]).strip()
            seq = str(r[1]).strip()
            rel_cik = r[2]
            src = str(r[3]).strip()
            acc_dt = r[4]
        elif len(r) == 4:
            # (acc, seq, rel_cik, src)
            acc = str(r[0]).strip()
            seq = str(r[1]).strip()
            rel_cik = r[2]
            src = str(r[3]).strip()
            acc_dt = None
        else:
            continue

        if src != "OTHERMANAGER2.tsv":
            continue

        if period is not None and acc_dt is not None:
            if not is_pit_accepted(acc_dt, period):
                continue

        if is_valid_cik(rel_cik):
            rel_map[(acc, seq)] = normalize_cik(rel_cik)

    return rel_map


def build_entity_graph_edges(
    relationship_rows: list[Any],
    period: str | None = None,
) -> list[tuple[str, str]]:
    """Build institutional relationship graph edges unioning both OTHERMANAGER.tsv and OTHERMANAGER2.tsv.

    Filters source_table IN ('OTHERMANAGER.tsv', 'OTHERMANAGER2.tsv') and acceptance_datetime if period is provided.
    """
    edges: list[tuple[str, str]] = []
    for r in relationship_rows:
        if isinstance(r, dict):
            u = r["reporter_cik"]
            v = r["related_cik"]
            src = str(r.get("source_table", "")).strip()
            acc_dt = r.get("acceptance_datetime")
        elif len(r) == 8:
            # (acc, p_rep, rep_cik, rel_cik, rel_name, seq, src, acc_dt)
            u = r[2]
            v = r[3]
            src = str(r[6]).strip()
            acc_dt = r[7]
        elif len(r) == 6:
            # (acc, rep_cik, rel_cik, seq, src, acc_dt)
            u = r[1]
            v = r[2]
            src = str(r[4]).strip()
            acc_dt = r[5]
        elif len(r) == 3:
            # (rep_cik, rel_cik, src)
            u = r[0]
            v = r[1]
            src = str(r[2]).strip()
            acc_dt = None
        else:
            continue

        if src not in ("OTHERMANAGER.tsv", "OTHERMANAGER2.tsv"):
            continue

        if period is not None and acc_dt is not None:
            if not is_pit_accepted(acc_dt, period):
                continue

        if is_valid_cik(u) and is_valid_cik(v):
            edges.append((normalize_cik(u), normalize_cik(v)))

    return edges


def resolve_owner_component_strict(
    econ_owner: str | None,
    filer_comp: str,
    component_mapping: dict[str, str],
) -> tuple[bool, str, str | None]:
    """Strictly resolve economic owner to its canonical entity component.

    Explicitly handles:
    1. Missing economic owner -> (False, "MISSING_ECONOMIC_OWNER", None)
    2. Owner CIK absent from component mapping -> (False, "OWNER_NOT_IN_GRAPH", None)
    3. Cross-component owner -> (False, "CROSS_COMPONENT_OWNER", owner_comp)
    4. Same-component owner -> (True, "SAME_COMPONENT_OWNER", filer_comp)

    Returns:
        (is_valid, reason, resolved_component_id)
    """
    if econ_owner is None:
        return False, "MISSING_ECONOMIC_OWNER", None

    c_norm = normalize_cik(econ_owner)
    if c_norm not in component_mapping:
        return False, "OWNER_NOT_IN_GRAPH", None

    owner_comp = component_mapping[c_norm]
    if owner_comp != filer_comp:
        return False, "CROSS_COMPONENT_OWNER", owner_comp

    return True, "SAME_COMPONENT_OWNER", filer_comp


def check_source_db_preflight(db_path: str | Path) -> dict[str, Any]:
    """Verify source DB existence, byte size, and lack of sidecars before opening."""
    p = Path(db_path)
    if not p.is_file():
        raise FileNotFoundError(f"Source database not found: {p}")

    size_bytes = p.stat().st_size
    conn = open_readonly_sqlite(p, immutable=True)
    cur = conn.cursor()
    cur.execute("PRAGMA query_only;")
    qo = cur.fetchone()[0]
    conn.close()

    return {
        "db_path": str(p),
        "db_filename": p.name,
        "size_bytes": size_bytes,
        "query_only_pragma": qo,
    }


def extract_berkshire_apple_2023q4(conn: sqlite3.Connection) -> dict[str, Any]:
    """Extract Berkshire Hathaway 2023Q4 Apple holdings from accession 0000950123-24-002518.

    Reports:
    1. Raw within-accession total (validates 905,560,000 external anchor).
    2. Primary-eligible resolved total, unresolved row/shares count, multi-sequence counts.
    3. Confidential treatment flag and explicit Primary eligibility assessment.
    """
    acc = "0000950123-24-002518"
    cusip = "037833100"
    cur = conn.cursor()

    # 1. Fetch header
    cur.execute(
        """
        SELECT accession_number, cik, period_of_report, acceptance_datetime, form_type, amendment_type, is_confidential_omit
        FROM filing_events
        WHERE accession_number = ?;
        """,
        (acc,),
    )
    h_row = cur.fetchone()
    if not h_row:
        raise ValueError(f"Filing header not found for accession: {acc}")

    header = FilingHeader(
        accession_number=h_row[0],
        origin_filer_cik=normalize_cik(h_row[1]),
        period_of_report=h_row[2],
        acceptance_datetime=h_row[3],
        form_type=h_row[4] or "13F-HR",
        amendment_type=h_row[5],
        is_confidential_omit=bool(h_row[6]),
    )
    header.validate()

    # 2. Fetch manager relationships for this accession
    cur.execute(
        """
        SELECT accession_number, sequence_number, related_cik, source_table
        FROM manager_relationships
        WHERE accession_number = ?;
        """,
        (acc,),
    )
    rel_rows = cur.fetchall()
    rel_map = build_line_level_manager_map(rel_rows)

    # 3. Fetch raw line items
    cur.execute(
        """
        SELECT accession_number, line_seq, cusip, security_name, title_of_class,
               sshprnamt, value_usd, sshprnamttype, investment_discretion, other_manager,
               voting_sole, voting_shared, voting_none, asset_class
        FROM filing_line_items
        WHERE accession_number = ? AND cusip = ?
        ORDER BY line_seq;
        """,
        (acc, cusip),
    )
    raw_lines = cur.fetchall()

    raw_total_shares = sum(int(r[5]) for r in raw_lines)
    raw_total_value = sum(float(r[6]) for r in raw_lines)

    holding_rows_resolved: list[HoldingRow] = []
    raw_rows_info: list[dict[str, Any]] = []

    unresolved_rows_count = 0
    unresolved_shares_total = 0
    unresolved_value_total = 0.0
    multi_sequence_rows_count = 0
    free_text_name_rows_count = 0
    multi_sequence_samples: list[str] = []

    for r in raw_lines:
        om_raw = r[9]
        om_cat, om_tokens = classify_other_manager(om_raw)

        if om_cat == "MULTI_NUMERIC_LIST":
            multi_sequence_rows_count += 1
            if len(multi_sequence_samples) < 5:
                multi_sequence_samples.append(str(om_raw).strip())
        elif om_cat == "FREE_TEXT_NAME":
            free_text_name_rows_count += 1

        # Resolve ownership using actual manager_relationships mapping under Primary policy
        owner_cik, unresolved = resolve_ownership(
            row_other_manager=om_raw,
            origin_filer_cik=header.origin_filer_cik,
            accession_number=acc,
            other_manager_map=rel_map,
            policy=OwnershipPolicy.PRIMARY_EMPIRICAL_ZERO,
        )

        if unresolved or owner_cik is None:
            unresolved_rows_count += 1
            unresolved_shares_total += int(r[5])
            unresolved_value_total += float(r[6])

        h_item = HoldingRow(
            accession_number=r[0],
            origin_filer_cik=header.origin_filer_cik,
            period_of_report=header.period_of_report,
            cusip=r[2],
            asset_class="SH" if (r[13] or "").lower() == "cash_equity" else str(r[13] or "SH"),
            economic_owner_cik=owner_cik,
            ownership_unresolved=unresolved,
            total_shares=int(r[5]),
            total_value_usd=float(r[6]),
            total_vote_sole=int(r[10] or 0),
            total_vote_shared=int(r[11] or 0),
            total_vote_none=int(r[12] or 0),
        )
        h_item.validate()
        holding_rows_resolved.append(h_item)

        raw_rows_info.append(
            {
                "line_seq": r[1],
                "cusip": r[2],
                "security_name": r[3],
                "title_of_class": r[4],
                "shares": r[5],
                "value_usd": r[6],
                "sshprnamttype": r[7],
                "investment_discretion": r[8],
                "other_manager": r[9],
                "other_manager_category": om_cat,
                "resolved_owner_cik": owner_cik,
                "ownership_unresolved": unresolved,
                "voting_sole": r[10],
                "voting_shared": r[11],
                "voting_none": r[12],
                "asset_class": r[13],
            }
        )

    # Aggregated resolved holdings (excludes unresolved rows per Contract v0.8.1)
    agg_resolved_dict = aggregate_accession_holdings(holding_rows_resolved)
    primary_resolved_shares = sum(v["total_shares"] for v in agg_resolved_dict.values())
    primary_resolved_value = sum(v["total_value_usd"] for v in agg_resolved_dict.values())

    preregistered_expected_anchor = 905_560_000

    # Primary eligibility assessment:
    is_primary_eligible = (not header.is_confidential_omit) and (primary_resolved_shares > 0)
    ineligibility_reasons = []
    if header.is_confidential_omit:
        ineligibility_reasons.append("CONFIDENTIAL_TREATMENT_OMISSION (is_confidential_omit=1)")
    if unresolved_rows_count == len(raw_lines):
        ineligibility_reasons.append("ALL_ROWS_UNRESOLVED_OTHER_MANAGER (missing manager_relationships mappings)")

    return {
        "accession_number": acc,
        "origin_filer_cik": header.origin_filer_cik,
        "period_of_report": header.period_of_report,
        "acceptance_datetime": header.acceptance_datetime,
        "is_confidential_omit": header.is_confidential_omit,
        "raw_matching_rows_count": len(raw_rows_info),
        "raw_matching_rows": raw_rows_info,
        "raw_total_aggregate_shares": raw_total_shares,
        "raw_total_aggregate_value_usd": raw_total_value,
        "preregistered_expected_anchor": preregistered_expected_anchor,
        "anchor_raw_match": (raw_total_shares == preregistered_expected_anchor),
        "primary_resolved_shares": primary_resolved_shares,
        "primary_resolved_value_usd": primary_resolved_value,
        "unresolved_rows_count": unresolved_rows_count,
        "unresolved_shares_total": unresolved_shares_total,
        "unresolved_value_total": unresolved_value_total,
        "multi_sequence_rows_count": multi_sequence_rows_count,
        "free_text_name_rows_count": free_text_name_rows_count,
        "multi_sequence_samples": multi_sequence_samples,
        "is_primary_eligible": is_primary_eligible,
        "ineligibility_reasons": ineligibility_reasons,
    }


def extract_point72_2019q4_discovery(conn: sqlite3.Connection) -> dict[str, Any]:
    """Discover Point72 2019Q4 filings, relationships with real PIT timestamps, and graph closure.

    Includes ONLY holdings report forms (13F-HR / 13F-HR/A).
    Never defaults unknown economic owners to Point72 canonical ID.
    """
    period = "2019-12-31"
    cur = conn.cursor()

    # 1. Seed Point72 CIKs from manager_names matches
    cur.execute(
        """
        SELECT DISTINCT cik, manager_name
        FROM manager_names
        WHERE manager_name LIKE '%POINT72%' OR manager_name LIKE '%POINT 72%'
        ORDER BY cik;
        """
    )
    p72_seed_rows = cur.fetchall()
    seed_ciks = {normalize_cik(r[0]) for r in p72_seed_rows}

    # 2. Fetch manager relationships for 2019Q4 joined with 13F-HR/HR/A filings
    cur.execute(
        """
        SELECT mr.accession_number, mr.period_of_report, mr.reporter_cik, mr.related_cik,
               mr.related_name, mr.sequence_number, mr.source_table, fe.acceptance_datetime
        FROM manager_relationships mr
        JOIN filing_events fe ON mr.accession_number = fe.accession_number
        WHERE mr.period_of_report = ? AND fe.form_type IN ('13F-HR', '13F-HR/A');
        """,
        (period,),
    )
    all_period_relationships = cur.fetchall()

    # Line lookup map strictly from OTHERMANAGER2.tsv
    rel_lookup = build_line_level_manager_map(all_period_relationships, period)
    # Institutional graph edges unioning both OTHERMANAGER.tsv and OTHERMANAGER2.tsv
    on_time_edges = build_entity_graph_edges(all_period_relationships, period)

    rel_records_for_closure: list[dict[str, Any]] = []
    for acc, p_rep, rep_cik, rel_cik, rel_name, seq, src, acc_dt in all_period_relationships:
        u_norm = normalize_cik(rep_cik)
        v_norm = normalize_cik(rel_cik)
        if is_pit_accepted(acc_dt, period):
            rel_records_for_closure.append(
                {
                    "accession_number": acc,
                    "period_of_report": p_rep,
                    "reporter_cik": u_norm,
                    "related_cik": v_norm,
                    "related_name": rel_name,
                    "sequence_number": str(seq).strip(),
                    "source_table": src,
                    "acceptance_datetime": acc_dt,
                    "is_on_time": True,
                }
            )

    # 3. Take relationship graph closure starting from Point72 primary entity CIK 0001603466
    comp_map = build_entity_connected_components(on_time_edges, all_ciks=seed_ciks)

    p72_main_seed = normalize_cik("1603466")
    p72_canonical_id = comp_map.get(p72_main_seed, p72_main_seed)
    component_ciks = sorted(list({normalize_cik(cik) for cik, c_id in comp_map.items() if c_id == p72_canonical_id}))

    # Filter relationships belonging to Point72 component
    p72_relationships = [
        r for r in rel_records_for_closure
        if r["reporter_cik"] in component_ciks or r["related_cik"] in component_ciks
    ]

    # 4. Fetch all 13F-HR / 13F-HR/A filings for component CIKs in 2019Q4
    query_ciks = sorted(list(set(component_ciks + [str(int(c)) for c in component_ciks])))
    cur.execute(
        f"""
        SELECT accession_number, cik, period_of_report, acceptance_datetime,
               form_type, amendment_type, is_confidential_omit
        FROM filing_events
        WHERE period_of_report = ? AND form_type IN ('13F-HR', '13F-HR/A')
          AND cik IN ({",".join("?" * len(query_ciks))})
        ORDER BY acceptance_datetime;
        """,
        [period] + query_ciks,
    )
    filings_raw = cur.fetchall()

    accessions_list: list[dict[str, Any]] = []
    filings_primary: dict[str, list[tuple[FilingHeader, list[HoldingRow]]]] = defaultdict(list)
    filings_zero_excl: dict[str, list[tuple[FilingHeader, list[HoldingRow]]]] = defaultdict(list)

    total_raw_line_items = 0
    on_time_confidential_filings_count = 0
    all_period_confidential_filings_count = 0
    on_time_amendment_filings_count = 0
    all_period_amendment_filings_count = 0

    unresolved_rows_p = 0
    unresolved_shares_p = 0
    unresolved_value_p = 0.0

    unresolved_rows_z = 0
    unresolved_shares_z = 0
    unresolved_value_z = 0.0

    main_acc = "0001567619-20-004063"
    main_acc_shares_p = 0
    main_acc_value_p = 0.0
    main_acc_lines_p = 0

    main_acc_shares_z = 0
    main_acc_value_z = 0.0
    main_acc_lines_z = 0

    for acc, cik, p_rep, acc_dt, f_type, a_type, is_conf in filings_raw:
        on_time = is_pit_accepted(acc_dt, period)
        if bool(is_conf):
            all_period_confidential_filings_count += 1
            if on_time:
                on_time_confidential_filings_count += 1
        if a_type:
            all_period_amendment_filings_count += 1
            if on_time:
                on_time_amendment_filings_count += 1

        header = FilingHeader(
            accession_number=acc,
            origin_filer_cik=normalize_cik(cik),
            period_of_report=p_rep,
            acceptance_datetime=acc_dt,
            form_type=f_type,
            amendment_type=a_type,
            is_confidential_omit=bool(is_conf),
        )
        header.validate()

        accessions_list.append(
            {
                "accession_number": acc,
                "filer_cik": normalize_cik(cik),
                "acceptance_datetime": acc_dt,
                "is_pit_on_time": on_time,
                "form_type": f_type,
                "amendment_type": a_type,
                "is_confidential_omit": bool(is_conf),
            }
        )

        if not on_time:
            continue

        # Fetch line items for accession
        cur.execute(
            """
            SELECT accession_number, line_seq, cusip, security_name, title_of_class,
               sshprnamt, value_usd, sshprnamttype, other_manager, voting_sole, voting_shared, voting_none, asset_class
            FROM filing_line_items
            WHERE accession_number = ?
            ORDER BY line_seq;
            """,
            (acc,),
        )
        li_rows = cur.fetchall()
        total_raw_line_items += len(li_rows)

        p_h_rows: list[HoldingRow] = []
        z_h_rows: list[HoldingRow] = []

        for r in li_rows:
            shrs = int(r[5])
            val = float(r[6])
            v_sole = int(r[9] or 0)
            v_shared = int(r[10] or 0)
            v_none = int(r[11] or 0)
            ac = "SH" if (r[12] or "").lower() == "cash_equity" else str(r[12] or "SH")

            # 1. Primary M0 Ownership Resolution
            owner_p, unres_p = resolve_ownership(
                row_other_manager=r[8],
                origin_filer_cik=header.origin_filer_cik,
                accession_number=acc,
                other_manager_map=rel_lookup,
                policy=OwnershipPolicy.PRIMARY_EMPIRICAL_ZERO,
            )
            if unres_p or owner_p is None:
                unresolved_rows_p += 1
                unresolved_shares_p += shrs
                unresolved_value_p += val

            p_item = HoldingRow(
                accession_number=acc,
                origin_filer_cik=header.origin_filer_cik,
                period_of_report=period,
                cusip=r[2],
                asset_class=ac,
                economic_owner_cik=owner_p,
                ownership_unresolved=unres_p,
                total_shares=shrs,
                total_value_usd=val,
                total_vote_sole=v_sole,
                total_vote_shared=v_shared,
                total_vote_none=v_none,
            )
            p_item.validate()
            p_h_rows.append(p_item)

            if acc == main_acc and not unres_p and owner_p is not None:
                main_acc_shares_p += shrs
                main_acc_value_p += val
                main_acc_lines_p += 1

            # 2. Zero-Excluded Sensitivity Resolution (Pre-Aggregation)
            owner_z, unres_z = resolve_ownership(
                row_other_manager=r[8],
                origin_filer_cik=header.origin_filer_cik,
                accession_number=acc,
                other_manager_map=rel_lookup,
                policy=OwnershipPolicy.ZERO_SENTINEL_EXCLUDED,
            )
            if unres_z or owner_z is None:
                unresolved_rows_z += 1
                unresolved_shares_z += shrs
                unresolved_value_z += val

            z_item = HoldingRow(
                accession_number=acc,
                origin_filer_cik=header.origin_filer_cik,
                period_of_report=period,
                cusip=r[2],
                asset_class=ac,
                economic_owner_cik=owner_z,
                ownership_unresolved=unres_z,
                total_shares=shrs,
                total_value_usd=val,
                total_vote_sole=v_sole,
                total_vote_shared=v_shared,
                total_vote_none=v_none,
            )
            z_item.validate()
            z_h_rows.append(z_item)

            if acc == main_acc and not unres_z and owner_z is not None:
                main_acc_shares_z += shrs
                main_acc_value_z += val
                main_acc_lines_z += 1

        filings_primary[header.origin_filer_cik].append((header, p_h_rows))
        filings_zero_excl[header.origin_filer_cik].append((header, z_h_rows))

    # Reconstruct state per filer for Primary M0
    all_reconstructed_p: list[dict[str, Any]] = []
    cross_component_excluded_count_p = 0

    for f_cik, f_list in filings_primary.items():
        state, meta = reconstruct_filer_state(f_list, period)
        if meta["amendment_unresolved"]:
            continue
        for (c_cusip, asset_class, econ_owner), h_data in state.items():
            if econ_owner is None:
                continue

            owner_comp = comp_map.get(econ_owner)
            if owner_comp is None or owner_comp != p72_canonical_id:
                cross_component_excluded_count_p += 1
                continue

            all_reconstructed_p.append(
                {
                    "canonical_entity_id": p72_canonical_id,
                    "origin_filer_cik": f_cik,
                    "cusip": c_cusip,
                    "period_of_report": period,
                    "asset_class": asset_class,
                    "economic_owner_cik": econ_owner,
                    "total_shares": h_data["total_shares"],
                    "total_value_usd": h_data["total_value_usd"],
                    "total_vote_sole": h_data["total_vote_sole"],
                    "total_vote_shared": h_data["total_vote_shared"],
                    "total_vote_none": h_data["total_vote_none"],
                }
            )

    deduped_holdings_p = deduplicate_entity_disclosures(
        canonical_entity_id=p72_canonical_id,
        holdings=all_reconstructed_p,
    )

    # Reconstruct state per filer for Zero-Excluded Sensitivity
    all_reconstructed_z: list[dict[str, Any]] = []
    cross_component_excluded_count_z = 0

    for f_cik, f_list in filings_zero_excl.items():
        state, meta = reconstruct_filer_state(f_list, period)
        if meta["amendment_unresolved"]:
            continue
        for (c_cusip, asset_class, econ_owner), h_data in state.items():
            if econ_owner is None:
                continue

            owner_comp = comp_map.get(econ_owner)
            if owner_comp is None or owner_comp != p72_canonical_id:
                cross_component_excluded_count_z += 1
                continue

            all_reconstructed_z.append(
                {
                    "canonical_entity_id": p72_canonical_id,
                    "origin_filer_cik": f_cik,
                    "cusip": c_cusip,
                    "period_of_report": period,
                    "asset_class": asset_class,
                    "economic_owner_cik": econ_owner,
                    "total_shares": h_data["total_shares"],
                    "total_value_usd": h_data["total_value_usd"],
                    "total_vote_sole": h_data["total_vote_sole"],
                    "total_vote_shared": h_data["total_vote_shared"],
                    "total_vote_none": h_data["total_vote_none"],
                }
            )

    deduped_holdings_z = deduplicate_entity_disclosures(
        canonical_entity_id=p72_canonical_id,
        holdings=all_reconstructed_z,
    )

    return {
        "status": "PROPOSED PENDING CODEX MANUAL FREEZE",
        "entity_name": "Point72 Asset Management",
        "period_of_report": period,
        "canonical_entity_id": p72_canonical_id,
        "seed_ciks": sorted(list(seed_ciks)),
        "component_closed_ciks": component_ciks,
        "accessions_count": len(accessions_list),
        "accessions": accessions_list,
        "manager_relationships_count": len(p72_relationships),
        "manager_relationships": p72_relationships,
        "source_tables_breakdown": {
            "line_lookup_source_table": "OTHERMANAGER2.tsv only",
            "graph_edges_source_tables": "OTHERMANAGER.tsv and OTHERMANAGER2.tsv union",
            "line_map_entries_count": len(rel_lookup),
            "graph_edges_count": len(on_time_edges),
        },
        "total_raw_line_items": total_raw_line_items,
        "on_time_confidential_filings_count": on_time_confidential_filings_count,
        "all_period_confidential_filings_count": all_period_confidential_filings_count,
        "on_time_amendment_filings_count": on_time_amendment_filings_count,
        "all_period_amendment_filings_count": all_period_amendment_filings_count,
        "cross_component_excluded_count": cross_component_excluded_count_p,
        "primary_m0": {
            "raw_line_items_count": total_raw_line_items,
            "unresolved_rows_count": unresolved_rows_p,
            "unresolved_shares_total": unresolved_shares_p,
            "unresolved_value_total": unresolved_value_p,
            "reconstructed_disclosures_count": len(all_reconstructed_p),
            "intra_entity_deduped_holdings_count": len(deduped_holdings_p),
            "duplicate_disclosures_removed_count": len(all_reconstructed_p) - len(deduped_holdings_p),
            "total_shares_deduped": sum(h["total_shares"] for h in deduped_holdings_p),
            "total_value_usd_deduped": sum(h["total_value_usd"] for h in deduped_holdings_p),
            "main_accession_shares_before_dedup": main_acc_shares_p,
            "main_accession_value_before_dedup": main_acc_value_p,
            "main_accession_raw_lines_retained": main_acc_lines_p,
        },
        "zero_excluded_sensitivity": {
            "raw_line_items_count": total_raw_line_items,
            "unresolved_rows_count": unresolved_rows_z,
            "unresolved_shares_total": unresolved_shares_z,
            "unresolved_value_total": unresolved_value_z,
            "reconstructed_disclosures_count": len(all_reconstructed_z),
            "intra_entity_deduped_holdings_count": len(deduped_holdings_z),
            "duplicate_disclosures_removed_count": len(all_reconstructed_z) - len(deduped_holdings_z),
            "total_shares_deduped": sum(h["total_shares"] for h in deduped_holdings_z),
            "total_value_usd_deduped": sum(h["total_value_usd"] for h in deduped_holdings_z),
            "main_accession_shares_before_dedup": main_acc_shares_z,
            "main_accession_value_before_dedup": main_acc_value_z,
            "main_accession_raw_lines_retained": main_acc_lines_z,
        },
        "reconstructed_disclosures_count": len(all_reconstructed_p),
        "intra_entity_deduped_holdings_count": len(deduped_holdings_p),
        "unresolved_rows_count": unresolved_rows_p,
        "unresolved_shares_total": unresolved_shares_p,
    }


def extract_split_pilot_pair(
    conn: sqlite3.Connection,
    cusip: str,
    stock_symbol: str,
    q_prev: str,
    q_curr: str,
    split_factor: float,
    ex_date: str,
    is_googl_note: bool = False,
) -> dict[str, Any]:
    """Execute complete World-B pipeline on 13F-HR/HR/A with all-member component gates."""
    cur = conn.cursor()

    # Step 1: Fetch all on-time 13F-HR and 13F-HR/A filings for Q-1 and Q (strictly excluding 13F-NT)
    on_time_filings: dict[str, dict[str, FilingHeader]] = {q_prev: {}, q_curr: {}}
    on_time_filers: dict[str, set[str]] = {q_prev: set(), q_curr: set()}
    filers_all_headers: dict[str, dict[str, list[FilingHeader]]] = {
        q_prev: defaultdict(list),
        q_curr: defaultdict(list),
    }
    late_filings_count = {q_prev: 0, q_curr: 0}

    for p in [q_prev, q_curr]:
        cur.execute(
            """
            SELECT accession_number, cik, period_of_report, acceptance_datetime,
                   form_type, amendment_type, is_confidential_omit
            FROM filing_events
            WHERE period_of_report = ? AND form_type IN ('13F-HR', '13F-HR/A');
            """,
            (p,),
        )
        for r in cur.fetchall():
            acc = r[0]
            c_norm = normalize_cik(r[1])
            acc_dt = r[3]
            if is_pit_accepted(acc_dt, p):
                header = FilingHeader(
                    accession_number=acc,
                    origin_filer_cik=c_norm,
                    period_of_report=r[2],
                    acceptance_datetime=acc_dt,
                    form_type=r[4],
                    amendment_type=r[5],
                    is_confidential_omit=bool(r[6]),
                )
                header.validate()
                on_time_filings[p][acc] = header
                on_time_filers[p].add(c_norm)
                filers_all_headers[p][c_norm].append(header)
            else:
                late_filings_count[p] += 1

    # Step 2: Fetch all manager relationships joined to on-time 13F-HR/HR/A filings
    on_time_edges: set[tuple[str, str]] = set()
    rel_map: dict[tuple[str, str], str] = {}

    for p in [q_prev, q_curr]:
        cur.execute(
            """
            SELECT mr.accession_number, mr.reporter_cik, mr.related_cik, mr.sequence_number, mr.source_table, fe.acceptance_datetime
            FROM manager_relationships mr
            JOIN filing_events fe ON mr.accession_number = fe.accession_number
            WHERE mr.period_of_report = ? AND fe.form_type IN ('13F-HR', '13F-HR/A');
            """,
            (p,),
        )
        all_rel_rows = cur.fetchall()
        rel_map.update(build_line_level_manager_map(all_rel_rows, p))
        on_time_edges.update(build_entity_graph_edges(all_rel_rows, p))

    # Step 3: Build unified connected components G(Q-1, Q) with all on-time 13F-HR filers
    all_on_time_filers = on_time_filers[q_prev] | on_time_filers[q_curr]
    component_mapping = build_entity_connected_components(list(on_time_edges), all_ciks=all_on_time_filers)

    # Step 4: Derive actual filing members per canonical component (independent of target stock holdings)
    component_filing_members: dict[str, dict[str, set[str]]] = {q_prev: defaultdict(set), q_curr: defaultdict(set)}
    all_components = set(component_mapping.values())

    for f_cik in on_time_filers[q_prev]:
        c_id = component_mapping[f_cik]
        component_filing_members[q_prev][c_id].add(f_cik)

    for f_cik in on_time_filers[q_curr]:
        c_id = component_mapping[f_cik]
        component_filing_members[q_curr][c_id].add(f_cik)

    # Step 5: Evaluate component-level confidential omission and unresolved amendment gates across ALL members
    component_confidential_omit: dict[str, dict[str, bool]] = {q_prev: defaultdict(bool), q_curr: defaultdict(bool)}
    component_amendment_unresolved: dict[str, dict[str, bool]] = {q_prev: defaultdict(bool), q_curr: defaultdict(bool)}

    for p in [q_prev, q_curr]:
        for f_cik, headers in filers_all_headers[p].items():
            c_id = component_mapping[f_cik]
            # Reconstruct metadata across all filing headers of this filer (empty holdings)
            f_tuples = [(h, []) for h in headers]
            _, meta = reconstruct_filer_state(f_tuples, p)
            if meta["has_confidential_omit"]:
                component_confidential_omit[p][c_id] = True
            if meta["amendment_unresolved"]:
                component_amendment_unresolved[p][c_id] = True

    # Step 6: Fetch line items matching target CUSIP
    cur.execute(
        """
        SELECT accession_number, line_seq, cusip, sshprnamt, value_usd, sshprnamttype,
               other_manager, voting_sole, voting_shared, voting_none, asset_class
        FROM filing_line_items
        WHERE cusip = ?;
        """,
        (cusip,),
    )
    all_lines = cur.fetchall()

    lines_by_period: dict[str, list[Any]] = {q_prev: [], q_curr: []}
    multi_sequence_count = {q_prev: 0, q_curr: 0}
    free_text_count = {q_prev: 0, q_curr: 0}
    multi_sequence_samples: list[str] = []

    for r in all_lines:
        acc = r[0]
        om_raw = r[6]
        om_cat, _ = classify_other_manager(om_raw)

        if acc in on_time_filings[q_prev]:
            lines_by_period[q_prev].append(r)
            if om_cat == "MULTI_NUMERIC_LIST":
                multi_sequence_count[q_prev] += 1
                if len(multi_sequence_samples) < 5:
                    multi_sequence_samples.append(str(om_raw).strip())
            elif om_cat == "FREE_TEXT_NAME":
                free_text_count[q_prev] += 1
        elif acc in on_time_filings[q_curr]:
            lines_by_period[q_curr].append(r)
            if om_cat == "MULTI_NUMERIC_LIST":
                multi_sequence_count[q_curr] += 1
                if len(multi_sequence_samples) < 5:
                    multi_sequence_samples.append(str(om_raw).strip())
            elif om_cat == "FREE_TEXT_NAME":
                free_text_count[q_curr] += 1

    # Step 7: Reconstruct target-CUSIP state per origin filer
    component_period_holdings: dict[str, dict[str, float]] = {q_prev: defaultdict(float), q_curr: defaultdict(float)}
    unresolved_rows_count = {q_prev: 0, q_curr: 0}
    duplicate_disclosures_removed = {q_prev: 0, q_curr: 0}

    for period in [q_prev, q_curr]:
        filings_dict = on_time_filings[period]
        lines = lines_by_period[period]

        lines_by_acc: dict[str, list[Any]] = defaultdict(list)
        for r in lines:
            lines_by_acc[r[0]].append(r)

        # Group filers who hold the target stock
        target_filers = {filings_dict[acc].origin_filer_cik for acc in lines_by_acc}
        filers_map: dict[str, list[tuple[FilingHeader, list[HoldingRow]]]] = defaultdict(list)

        for acc, header in filings_dict.items():
            if header.origin_filer_cik not in target_filers:
                continue

            acc_lines = lines_by_acc.get(acc, [])
            h_rows: list[HoldingRow] = []

            for r in acc_lines:
                om_raw = r[6]
                owner_cik, unresolved = resolve_ownership(
                    row_other_manager=om_raw,
                    origin_filer_cik=header.origin_filer_cik,
                    accession_number=acc,
                    other_manager_map=rel_map,
                    policy=OwnershipPolicy.PRIMARY_EMPIRICAL_ZERO,
                )
                if unresolved or owner_cik is None:
                    unresolved_rows_count[period] += 1

                asset_class = "SH" if (r[10] or "").lower() == "cash_equity" else str(r[10] or "SH")

                h_item = HoldingRow(
                    accession_number=acc,
                    origin_filer_cik=header.origin_filer_cik,
                    period_of_report=period,
                    cusip=cusip,
                    asset_class=asset_class,
                    economic_owner_cik=owner_cik,
                    ownership_unresolved=unresolved,
                    total_shares=int(r[3]),
                    total_value_usd=float(r[4]),
                    total_vote_sole=int(r[7] or 0),
                    total_vote_shared=int(r[8] or 0),
                    total_vote_none=int(r[9] or 0),
                )
                h_item.validate()
                h_rows.append(h_item)

            filers_map[header.origin_filer_cik].append((header, h_rows))

        # Reconstruct per-filer state
        all_period_disclosures: list[dict[str, Any]] = []

        for f_cik, f_filings in filers_map.items():
            state, meta = reconstruct_filer_state(f_filings, period)
            filer_comp = component_mapping[f_cik]

            if meta["amendment_unresolved"]:
                continue

            for (c_cusip, asset_class, econ_owner), h_data in state.items():
                if asset_class != "SH":
                    continue

                is_ok_owner, reason, resolved_comp = resolve_owner_component_strict(
                    econ_owner=econ_owner,
                    filer_comp=filer_comp,
                    component_mapping=component_mapping,
                )
                if not is_ok_owner:
                    unresolved_rows_count[period] += 1
                    continue

                all_period_disclosures.append(
                    {
                        "canonical_entity_id": filer_comp,
                        "origin_filer_cik": f_cik,
                        "cusip": c_cusip,
                        "period_of_report": period,
                        "economic_owner_cik": econ_owner,
                        "total_shares": h_data["total_shares"],
                        "total_value_usd": h_data["total_value_usd"],
                        "total_vote_sole": h_data["total_vote_sole"],
                        "total_vote_shared": h_data["total_vote_shared"],
                        "total_vote_none": h_data["total_vote_none"],
                    }
                )

        # Deduplicate intra-component disclosures
        disclosures_by_comp: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for h in all_period_disclosures:
            disclosures_by_comp[h["canonical_entity_id"]].append(h)

        pre_dedup_count = len(all_period_disclosures)
        post_dedup_count = 0

        for c_id, c_disclosures in disclosures_by_comp.items():
            deduped = deduplicate_entity_disclosures(c_id, c_disclosures)
            post_dedup_count += len(deduped)
            tot_shares = sum(item["total_shares"] for item in deduped)
            component_period_holdings[period][c_id] = tot_shares

        duplicate_disclosures_removed[period] = pre_dedup_count - post_dedup_count

    # Step 8: Component-level gates and continuous holder formation
    continuous_holders: list[ContinuousHolder] = []

    membership_incomplete_components = 0
    confidential_omit_components = 0
    amendment_unresolved_components = 0
    new_positions_count = 0
    exit_positions_count = 0

    for c_id in sorted(all_components):
        prev_members = component_filing_members[q_prev].get(c_id, set())
        curr_members = component_filing_members[q_curr].get(c_id, set())

        prev_shares = component_period_holdings[q_prev].get(c_id, 0)
        curr_shares = component_period_holdings[q_curr].get(c_id, 0)

        # Check if entity participated in trading this stock
        if prev_shares == 0 and curr_shares == 0:
            continue

        # Gate A: Filing membership equality across all on-time members
        ok_mem, _ = validate_entity_membership(prev_members, curr_members)
        if not ok_mem:
            membership_incomplete_components += 1
            continue

        # Gate B: Confidential omission across ALL on-time members in component
        is_conf_prev = component_confidential_omit[q_prev].get(c_id, False)
        is_conf_curr = component_confidential_omit[q_curr].get(c_id, False)
        if is_conf_prev or is_conf_curr:
            confidential_omit_components += 1
            continue

        # Gate C: Unresolved amendment across ALL on-time members in component
        is_amend_prev = component_amendment_unresolved[q_prev].get(c_id, False)
        is_amend_curr = component_amendment_unresolved[q_curr].get(c_id, False)
        if is_amend_prev or is_amend_curr:
            amendment_unresolved_components += 1
            continue

        # Directional position classification
        if prev_shares == 0 and curr_shares > 0:
            new_positions_count += 1
            continue
        if prev_shares > 0 and curr_shares == 0:
            exit_positions_count += 1
            continue

        if prev_shares > 0 and curr_shares > 0:
            continuous_holders.append(
                ContinuousHolder(
                    entity_id=c_id,
                    prev_shares=prev_shares,
                    curr_shares=curr_shares,
                )
            )

    # Step 9: Evaluate split waterfall
    split_event = SplitEvent(ex_date=ex_date, ratio=split_factor)
    k_calc, has_splits = compute_k_ledger_and_presence(q_prev, q_curr, [split_event])

    waterfall_res = evaluate_split_waterfall(
        is_corporate_action_unknown=False,
        has_vendor_splits=has_splits,
        k_ledger=k_calc,
        holders=continuous_holders,
    )

    return {
        "stock_symbol": stock_symbol,
        "cusip": cusip,
        "q_prev": q_prev,
        "q_curr": q_curr,
        "contract_split_factor": split_factor,
        "contract_ex_date": ex_date,
        "is_googl_note": is_googl_note,
        "eligible_continuous_entity_count": waterfall_res.holder_count,
        "raw_median_ratio": round(waterfall_res.median_ratio, 4) if waterfall_res.median_ratio else None,
        "mad_log": round(waterfall_res.mad_log, 4) if waterfall_res.mad_log else None,
        "adjusted_median_ratio": round(waterfall_res.adj_median_ratio, 4) if waterfall_res.adj_median_ratio else None,
        "waterfall_state": waterfall_res.state,
        "waterfall_action": waterfall_res.action,
        "waterfall_sensitivity_action": waterfall_res.sensitivity_action,
        "is_in_contract_pass_range": (
            0.8 <= waterfall_res.adj_median_ratio <= 1.2
            if waterfall_res.adj_median_ratio is not None
            else False
        ),
        "multi_sequence_other_manager": {
            "q_prev_multi_sequence_rows": multi_sequence_count[q_prev],
            "q_curr_multi_sequence_rows": multi_sequence_count[q_curr],
            "q_prev_free_text_rows": free_text_count[q_prev],
            "q_curr_free_text_rows": free_text_count[q_curr],
            "samples": multi_sequence_samples,
        },
        "component_level_exclusions": {
            "membership_incomplete_components_excluded": membership_incomplete_components,
            "confidential_omission_components_excluded": confidential_omit_components,
            "amendment_unresolved_components_excluded": amendment_unresolved_components,
            "new_positions_count": new_positions_count,
            "exit_positions_count": exit_positions_count,
            "unresolved_ownership_rows_excluded_q_prev": unresolved_rows_count[q_prev],
            "unresolved_ownership_rows_excluded_q_curr": unresolved_rows_count[q_curr],
            "duplicate_disclosures_removed_q_prev": duplicate_disclosures_removed[q_prev],
            "duplicate_disclosures_removed_q_curr": duplicate_disclosures_removed[q_curr],
        },
        "global_dataset_context": {
            "total_on_time_filers_q_prev": len(on_time_filers[q_prev]),
            "total_on_time_filers_q_curr": len(on_time_filers[q_curr]),
            "late_filings_excluded_q_prev": late_filings_count[q_prev],
            "late_filings_excluded_q_curr": late_filings_count[q_curr],
            "total_connected_components_in_graph": len(all_components),
            "total_on_time_relationship_edges": len(on_time_edges),
        },
    }


def run_full_c1_discovery(db_path: str | Path) -> dict[str, Any]:
    """Execute complete Stage C Part C1 discovery against Phase 0 DB."""
    t0 = time.time()
    preflight = check_source_db_preflight(db_path)

    conn = open_readonly_sqlite(db_path, immutable=True)

    # 1. Berkshire Apple 2023Q4
    t_berk0 = time.time()
    berkshire_res = extract_berkshire_apple_2023q4(conn)
    t_berk1 = time.time()
    berkshire_res["execution_time_sec"] = round(t_berk1 - t_berk0, 3)

    # 2. Point72 2019Q4 Discovery
    t_p72_0 = time.time()
    point72_res = extract_point72_2019q4_discovery(conn)
    t_p72_1 = time.time()
    point72_res["execution_time_sec"] = round(t_p72_1 - t_p72_0, 3)

    # 3. Four Canonical Split Pairs
    split_configs = [
        ("67066G104", "NVDA", "2024-03-31", "2024-06-30", 10.0, "2024-06-10", False),
        ("88160R101", "TSLA", "2022-06-30", "2022-09-30", 3.0, "2022-08-25", False),
        ("023135106", "AMZN", "2022-03-31", "2022-06-30", 20.0, "2022-06-06", False),
        ("02079K305", "GOOGL", "2022-06-30", "2022-09-30", 20.0, "2022-07-18", True),
    ]

    split_results: list[dict[str, Any]] = []
    for cusip, sym, q_prev, q_curr, factor, ex_date, is_googl in split_configs:
        t_sp0 = time.time()
        sp_res = extract_split_pilot_pair(
            conn=conn,
            cusip=cusip,
            stock_symbol=sym,
            q_prev=q_prev,
            q_curr=q_curr,
            split_factor=factor,
            ex_date=ex_date,
            is_googl_note=is_googl,
        )
        t_sp1 = time.time()
        sp_res["execution_time_sec"] = round(t_sp1 - t_sp0, 3)
        split_results.append(sp_res)

    conn.close()
    t_total = time.time() - t0

    return {
        "status": "STAGE C PART C1 DISCOVERY UNDER CODEX RE-AUDIT",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_execution_time_sec": round(t_total, 3),
        "preflight": preflight,
        "evidence_a_berkshire_apple_2023q4": berkshire_res,
        "evidence_b_point72_2019q4_discovery": point72_res,
        "evidence_c_split_pilot_pairs": split_results,
    }
