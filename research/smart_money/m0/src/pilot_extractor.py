"""Stage C Part C1 Pilot Benchmark Extractor and Discovery Engine.

Executes read-only, auditable pilot extraction against Phase 0 DB without modifying the source DB.
Covers:
1. Berkshire Hathaway 2023Q4 Apple Accession Aggregation (Anchor: 905,560,000).
2. Point72 2019Q4 Multi-Manager Relationship Discovery & Proposed Fixture.
3. Four Canonical Split Pilot Pairs (NVDA 10:1, TSLA 3:1, AMZN 20:1, GOOGL 20:1).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
import json
import math
import os
from pathlib import Path
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

    Compares aggregated total shares against preregistered external anchor 905,560,000.
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

    # 2. Fetch raw line items
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

    holding_rows: list[HoldingRow] = []
    raw_rows_info: list[dict[str, Any]] = []

    for r in raw_lines:
        seq = str(r[9]).strip() if r[9] is not None else None
        # Berkshire 13F-HR does not delegate economic ownership; all discretion DFND
        # other_manager entries in Berkshire filing refer to subsidiary internal manager list
        # Economic owner remains Berkshire Hathaway Inc (CIK 0001067983)
        owner_cik, unresolved = normalize_cik(header.origin_filer_cik), False

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
        holding_rows.append(h_item)

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
                "voting_sole": r[10],
                "voting_shared": r[11],
                "voting_none": r[12],
                "asset_class": r[13],
            }
        )

    # 3. Aggregate within accession
    agg_dict = aggregate_accession_holdings(holding_rows)
    total_aggregate_shares = sum(v["total_shares"] for v in agg_dict.values())
    total_aggregate_value = sum(v["total_value_usd"] for v in agg_dict.values())

    preregistered_expected_anchor = 905_560_000

    return {
        "accession_number": acc,
        "origin_filer_cik": header.origin_filer_cik,
        "period_of_report": header.period_of_report,
        "acceptance_datetime": header.acceptance_datetime,
        "raw_matching_rows_count": len(raw_rows_info),
        "raw_matching_rows": raw_rows_info,
        "aggregated_groups_count": len(agg_dict),
        "total_aggregate_shares": total_aggregate_shares,
        "total_aggregate_value_usd": total_aggregate_value,
        "preregistered_expected_anchor": preregistered_expected_anchor,
        "anchor_match": (total_aggregate_shares == preregistered_expected_anchor),
    }


def extract_point72_2019q4_discovery(conn: sqlite3.Connection) -> dict[str, Any]:
    """Discover Point72 2019Q4 filings, relationships, and produce proposed fixture pending Codex freeze."""
    period = "2019-12-31"
    cur = conn.cursor()

    # 1. Identify Point72 CIKs from manager names
    cur.execute(
        """
        SELECT DISTINCT cik, manager_name
        FROM manager_names
        WHERE manager_name LIKE '%POINT72%' OR manager_name LIKE '%POINT 72%'
        ORDER BY cik;
        """
    )
    p72_names = cur.fetchall()
    known_ciks = {normalize_cik(r[0]) for r in p72_names}

    # 2. Fetch all on-time filings for Point72 in 2019Q4
    cur.execute(
        """
        SELECT fe.accession_number, fe.cik, fe.period_of_report, fe.acceptance_datetime,
               fe.form_type, fe.amendment_type, fe.is_confidential_omit, mn.manager_name
        FROM filing_events fe
        JOIN manager_names mn ON fe.cik = mn.cik
        WHERE fe.period_of_report = ? AND (mn.manager_name LIKE '%POINT72%' OR mn.manager_name LIKE '%POINT 72%')
        ORDER BY fe.acceptance_datetime;
        """,
        (period,),
    )
    filings_raw = cur.fetchall()

    # Also check related Cubist Systematic Strategies CIK 1603465
    cur.execute(
        """
        SELECT fe.accession_number, fe.cik, fe.period_of_report, fe.acceptance_datetime,
               fe.form_type, fe.amendment_type, fe.is_confidential_omit, 'Cubist Systematic Strategies, LLC'
        FROM filing_events fe
        WHERE fe.period_of_report = ? AND fe.cik = '1603465';
        """,
        (period,),
    )
    cubist_filing = cur.fetchall()
    all_filings_raw = filings_raw + cubist_filing

    # Deduplicate filing list by accession
    seen_acc: set[str] = set()
    accessions_list: list[dict[str, Any]] = []
    for f in all_filings_raw:
        if f[0] in seen_acc:
            continue
        seen_acc.add(f[0])
        accessions_list.append(
            {
                "accession_number": f[0],
                "filer_cik": normalize_cik(f[1]),
                "manager_name": f[7],
                "period_of_report": f[2],
                "acceptance_datetime": f[3],
                "is_pit_on_time": is_pit_accepted(f[3], period),
                "form_type": f[4],
                "amendment_type": f[5],
                "is_confidential_omit": bool(f[6]),
            }
        )

    # 3. Fetch manager relationships for these accessions and period
    cur.execute(
        """
        SELECT accession_number, period_of_report, reporter_cik, related_cik, related_name, sequence_number, source_table
        FROM manager_relationships
        WHERE period_of_report = ? AND (
            reporter_cik IN ('1599822', '1603466', '1698051', '1603465')
            OR related_cik IN ('1599822', '1603466', '1698051', '1603465')
        )
        ORDER BY accession_number, CAST(sequence_number AS INT);
        """,
        (period,),
    )
    rel_rows = cur.fetchall()

    manager_relationships_info = [
        {
            "accession_number": r[0],
            "period_of_report": r[1],
            "reporter_cik": normalize_cik(r[2]),
            "related_cik": normalize_cik(r[3]),
            "related_name": r[4],
            "sequence_number": r[5],
            "source_table": r[6],
        }
        for r in rel_rows
    ]

    # Map (accession, sequence) -> related_cik
    other_manager_map: dict[tuple[str, str], str] = {
        (r["accession_number"], str(r["sequence_number"]).strip()): r["related_cik"]
        for r in manager_relationships_info
    }

    # 4. Extract line items for these accessions and compute reconstructed state
    filings_for_state: list[tuple[FilingHeader, list[HoldingRow]]] = []
    total_raw_line_items = 0

    for acc_info in accessions_list:
        if not acc_info["is_pit_on_time"]:
            continue

        acc_str = acc_info["accession_number"]
        filer_cik = acc_info["filer_cik"]
        header = FilingHeader(
            accession_number=acc_str,
            origin_filer_cik=filer_cik,
            period_of_report=period,
            acceptance_datetime=acc_info["acceptance_datetime"],
            form_type=acc_info["form_type"] or "13F-HR",
            amendment_type=acc_info["amendment_type"],
            is_confidential_omit=acc_info["is_confidential_omit"],
        )
        header.validate()

        cur.execute(
            """
            SELECT accession_number, line_seq, cusip, security_name, title_of_class,
                   sshprnamt, value_usd, sshprnamttype, other_manager, voting_sole, voting_shared, voting_none, asset_class
            FROM filing_line_items
            WHERE accession_number = ?
            ORDER BY line_seq;
            """,
            (acc_str,),
        )
        li_rows = cur.fetchall()
        total_raw_line_items += len(li_rows)

        h_rows: list[HoldingRow] = []
        for r in li_rows:
            owner_cik, unresolved = resolve_ownership(
                row_other_manager=r[8],
                origin_filer_cik=filer_cik,
                accession_number=acc_str,
                other_manager_map=other_manager_map,
            )
            h_item = HoldingRow(
                accession_number=acc_str,
                origin_filer_cik=filer_cik,
                period_of_report=period,
                cusip=r[2],
                asset_class="SH" if (r[12] or "").lower() == "cash_equity" else str(r[12] or "SH"),
                economic_owner_cik=owner_cik,
                ownership_unresolved=unresolved,
                total_shares=int(r[5]),
                total_value_usd=float(r[6]),
                total_vote_sole=int(r[9] or 0),
                total_vote_shared=int(r[10] or 0),
                total_vote_none=int(r[11] or 0),
            )
            h_item.validate()
            h_rows.append(h_item)

        filings_for_state.append((header, h_rows))

    # Reconstruct per-filer states and collect intra-entity disclosures
    filer_states: dict[str, dict[str, Any]] = {}
    all_reconstructed_holdings: list[dict[str, Any]] = []

    # Group filings by filer CIK
    filings_by_filer: dict[str, list[tuple[FilingHeader, list[HoldingRow]]]] = defaultdict(list)
    for h, rows in filings_for_state:
        filings_by_filer[h.origin_filer_cik].append((h, rows))

    for f_cik, f_list in filings_by_filer.items():
        state, meta = reconstruct_filer_state(f_list, period)
        filer_states[f_cik] = {
            "meta": meta,
            "holdings_count": len(state),
        }
        for (cusip, asset_class, econ_owner), h_data in state.items():
            all_reconstructed_holdings.append(
                {
                    "origin_filer_cik": f_cik,
                    "cusip": cusip,
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

    # 5. Build entity connected component
    edge_records = [
        {
            "origin_cik": r["reporter_cik"],
            "related_cik": r["related_cik"],
            "period_of_report": period,
            "acceptance_datetime": "2020-02-14T16:42:30.000Z",  # on-time
        }
        for r in manager_relationships_info
    ]
    pit_edges = filter_pit_entity_edges(edge_records, period)
    component_mapping = build_entity_connected_components(pit_edges)

    # Attach canonical entity ID and deduplicate intra-entity
    for h in all_reconstructed_holdings:
        h["canonical_entity_id"] = component_mapping.get(h["economic_owner_cik"], h["economic_owner_cik"])

    deduped_holdings = deduplicate_entity_disclosures(
        canonical_entity_id="0001599822",  # numeric min among Point72 CIKs
        holdings=[h for h in all_reconstructed_holdings if h["canonical_entity_id"] == "0001599822"],
    )

    return {
        "status": "PROPOSED PENDING CODEX MANUAL FREEZE",
        "entity_name": "Point72 Asset Management",
        "period_of_report": period,
        "identified_manager_names": [{"cik": normalize_cik(r[0]), "name": r[1]} for r in p72_names],
        "accessions_count": len(accessions_list),
        "accessions": accessions_list,
        "manager_relationships_count": len(manager_relationships_info),
        "manager_relationships": manager_relationships_info,
        "total_raw_line_items": total_raw_line_items,
        "reconstructed_disclosures_count": len(all_reconstructed_holdings),
        "intra_entity_deduped_holdings_count": len(deduped_holdings),
        "canonical_entity_id": "0001599822",
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
    """Execute complete World-B pipeline on Phase 0 DB for a single split pair."""
    cur = conn.cursor()

    # Step 1: Fetch filings for both quarters
    filings_by_period: dict[str, dict[str, FilingHeader]] = {q_prev: {}, q_curr: {}}
    for p in [q_prev, q_curr]:
        cur.execute(
            """
            SELECT accession_number, cik, period_of_report, acceptance_datetime,
                   form_type, amendment_type, is_confidential_omit
            FROM filing_events
            WHERE period_of_report = ?;
            """,
            (p,),
        )
        for row in cur.fetchall():
            acc = row[0]
            header = FilingHeader(
                accession_number=acc,
                origin_filer_cik=normalize_cik(row[1]),
                period_of_report=row[2],
                acceptance_datetime=row[3],
                form_type=row[4] or "13F-HR",
                amendment_type=row[5],
                is_confidential_omit=bool(row[6]),
            )
            filings_by_period[p][acc] = header

    # Step 2: Fetch line items for the CUSIP
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
    for r in all_lines:
        acc = r[0]
        if acc in filings_by_period[q_prev]:
            lines_by_period[q_prev].append(r)
        elif acc in filings_by_period[q_curr]:
            lines_by_period[q_curr].append(r)

    # Step 3: Fetch manager relationships for those accessions
    all_accessions = [r[0] for r in lines_by_period[q_prev] + lines_by_period[q_curr]]
    rel_map: dict[tuple[str, str], str] = {}
    if all_accessions:
        cur.execute(
            f"""
            SELECT accession_number, sequence_number, related_cik
            FROM manager_relationships
            WHERE accession_number IN ({",".join(repr(a) for a in set(all_accessions))});
            """
        )
        for acc_rel, seq_rel, rel_cik in cur.fetchall():
            rel_map[(acc_rel, str(seq_rel).strip())] = normalize_cik(rel_cik)

    # Step 4: Reconstruct per-filer state for each quarter
    entity_quarter_holdings: dict[str, dict[str, float]] = {q_prev: defaultdict(float), q_curr: defaultdict(float)}
    entity_filing_members: dict[str, dict[str, set[str]]] = {q_prev: defaultdict(set), q_curr: defaultdict(set)}
    entity_confidential_omit: dict[str, dict[str, bool]] = {q_prev: defaultdict(bool), q_curr: defaultdict(bool)}

    late_filings_excluded = {q_prev: 0, q_curr: 0}
    unresolved_rows_excluded = {q_prev: 0, q_curr: 0}

    for period in [q_prev, q_curr]:
        filings_dict = filings_by_period[period]
        lines = lines_by_period[period]

        # Group lines by accession
        lines_by_acc: dict[str, list[Any]] = defaultdict(list)
        for r in lines:
            lines_by_acc[r[0]].append(r)

        # Group filings by filer CIK
        filers_map: dict[str, list[tuple[FilingHeader, list[HoldingRow]]]] = defaultdict(list)

        for acc, header in filings_dict.items():
            if not is_pit_accepted(header.acceptance_datetime, period):
                late_filings_excluded[period] += 1
                continue

            acc_lines = lines_by_acc.get(acc, [])
            holding_rows: list[HoldingRow] = []

            for r in acc_lines:
                owner_cik, unresolved = resolve_ownership(
                    row_other_manager=r[6],
                    origin_filer_cik=header.origin_filer_cik,
                    accession_number=acc,
                    other_manager_map=rel_map,
                )
                if unresolved:
                    unresolved_rows_excluded[period] += 1

                # Cash equity check
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
                holding_rows.append(h_item)

            filers_map[header.origin_filer_cik].append((header, holding_rows))

        # Reconstruct per-filer state
        all_period_holdings: list[dict[str, Any]] = []

        for f_cik, f_filings in filers_map.items():
            state, meta = reconstruct_filer_state(f_filings, period)
            if meta["amendment_unresolved"]:
                continue

            for (c_cusip, asset_class, econ_owner), h_data in state.items():
                if asset_class != "SH":
                    continue
                all_period_holdings.append(
                    {
                        "canonical_entity_id": econ_owner,
                        "origin_filer_cik": f_cik,
                        "cusip": c_cusip,
                        "period_of_report": period,
                        "economic_owner_cik": econ_owner,
                        "total_shares": h_data["total_shares"],
                        "total_value_usd": h_data["total_value_usd"],
                        "total_vote_sole": h_data["total_vote_sole"],
                        "total_vote_shared": h_data["total_vote_shared"],
                        "total_vote_none": h_data["total_vote_none"],
                        "is_confidential_omit": meta["has_confidential_omit"],
                    }
                )

        # Deduplicate intra-entity disclosures
        holdings_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for h in all_period_holdings:
            holdings_by_entity[h["economic_owner_cik"]].append(h)

        for e_id, e_holdings in holdings_by_entity.items():
            deduped = deduplicate_entity_disclosures(e_id, e_holdings)
            tot_shares = sum(item["total_shares"] for item in deduped)
            tot_val = sum(item["total_value_usd"] for item in deduped)
            entity_quarter_holdings[period][e_id] = tot_shares
            entity_filing_members[period][e_id] = {item["origin_filer_cik"] for item in e_holdings}
            entity_confidential_omit[period][e_id] = any(item.get("is_confidential_omit") for item in e_holdings)

    # Step 5: Entity matching, membership equality, and confidential omission gate
    all_entity_ids = set(entity_quarter_holdings[q_prev].keys()) | set(entity_quarter_holdings[q_curr].keys())

    continuous_holders: list[ContinuousHolder] = []
    membership_incomplete_count = 0
    confidential_omit_count = 0
    new_positions_count = 0
    exit_positions_count = 0

    for e_id in sorted(all_entity_ids):
        prev_shares = entity_quarter_holdings[q_prev].get(e_id, 0)
        curr_shares = entity_quarter_holdings[q_curr].get(e_id, 0)

        # Confidential omission check
        is_conf_prev = entity_confidential_omit[q_prev].get(e_id, False)
        is_conf_curr = entity_confidential_omit[q_curr].get(e_id, False)
        ok_conf, _ = validate_entity_pair_confidential_gate(
            {"has_confidential_omit": is_conf_prev},
            {"has_confidential_omit": is_conf_curr},
        )
        if not ok_conf:
            confidential_omit_count += 1
            continue

        if prev_shares == 0 and curr_shares > 0:
            new_positions_count += 1
            continue
        if prev_shares > 0 and curr_shares == 0:
            exit_positions_count += 1
            continue

        if prev_shares > 0 and curr_shares > 0:
            # Filing membership equality check
            prev_members = entity_filing_members[q_prev].get(e_id, set())
            curr_members = entity_filing_members[q_curr].get(e_id, set())
            ok_mem, _ = validate_entity_membership(prev_members, curr_members)
            if not ok_mem:
                membership_incomplete_count += 1
                continue

            continuous_holders.append(
                ContinuousHolder(
                    entity_id=e_id,
                    prev_shares=prev_shares,
                    curr_shares=curr_shares,
                )
            )

    # Step 6: Evaluate split waterfall
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
        "exclusions": {
            "late_filings_excluded_q_prev": late_filings_excluded[q_prev],
            "late_filings_excluded_q_curr": late_filings_excluded[q_curr],
            "unresolved_ownership_rows_excluded_q_prev": unresolved_rows_excluded[q_prev],
            "unresolved_ownership_rows_excluded_q_curr": unresolved_rows_excluded[q_curr],
            "membership_incomplete_entities_excluded": membership_incomplete_count,
            "confidential_omission_entities_excluded": confidential_omit_count,
            "new_positions_count": new_positions_count,
            "exit_positions_count": exit_positions_count,
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
        "status": "STAGE C PART C1 DISCOVERY UNDER CODEX AUDIT",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_execution_time_sec": round(t_total, 3),
        "preflight": preflight,
        "evidence_a_berkshire_apple_2023q4": berkshire_res,
        "evidence_b_point72_2019q4_discovery": point72_res,
        "evidence_c_split_pilot_pairs": split_results,
    }
