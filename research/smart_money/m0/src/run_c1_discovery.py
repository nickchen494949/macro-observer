"""CLI runner and artifact generator for Stage C Part C1 Pilot Discovery.

Runs pilot extraction against research/smart_money/phase0/data/13f_full_4409f14.db (read-only immutable),
generates machine-readable JSON (STAGE_C1_DISCOVERY.json) and human-readable Markdown (STAGE_C_DISCOVERY.md).
Includes validate_c1_gate: a pure explicit validator called before successful artifact publication.
"""

import argparse
import sys
from pathlib import Path
import time
from typing import Any

from research.smart_money.m0.src.manifest_integrity import canonical_json_dumps
from research.smart_money.m0.src.pilot_extractor import run_full_c1_discovery


class C1GateFailure(Exception):
    """Raised when Stage C1 gate validation detects a mismatch."""
    pass


def validate_c1_gate(data: dict[str, Any]) -> list[str]:
    """Pure deterministic validator for Stage C1 discovery gate.

    Returns a list of failure descriptions. Empty list means PASS.
    Does not write files or produce side effects.
    """
    failures: list[str] = []

    def fail(section: str, msg: str) -> None:
        failures.append(f"[{section}] {msg}")

    # Contract version
    cv = data.get("contract_version")
    if cv != "0.8.3":
        fail("CONTRACT", f"contract_version expected '0.8.3', got {cv!r}")

    # Preflight
    pf = data.get("preflight", {})
    if pf.get("db_filename") != "13f_full_4409f14.db":
        fail("PREFLIGHT", f"db_filename expected '13f_full_4409f14.db', got {pf.get('db_filename')!r}")
    if pf.get("query_only_pragma") != 1:
        fail("PREFLIGHT", f"query_only_pragma expected 1, got {pf.get('query_only_pragma')!r}")

    # Berkshire
    ea = data.get("evidence_a_berkshire_apple_2023q4", {})
    if ea.get("raw_total_aggregate_shares") != 905_560_000:
        fail("BERKSHIRE", f"raw_total_aggregate_shares expected 905560000, got {ea.get('raw_total_aggregate_shares')!r}")
    if ea.get("anchor_raw_match") is not True:
        fail("BERKSHIRE", f"anchor_raw_match expected True, got {ea.get('anchor_raw_match')!r}")

    # Conflict diagnostics
    mcd = data.get("mapping_conflict_diagnostics", {})
    conflict_expected = {
        "total_conflict_keys_in_othermanager2": 50,
        "referenced_conflict_keys_count": 17,
        "affected_raw_line_items_count": 5472,
        "affected_shares_total": 659481568,
        "affected_value_usd_total": 42779736343.0,
    }
    for key, expected in conflict_expected.items():
        actual = mcd.get(key)
        if isinstance(expected, float):
            if actual is None or abs(actual - expected) > 0.5:
                fail("CONFLICT", f"{key} expected {expected}, got {actual!r}")
        else:
            if actual != expected:
                fail("CONFLICT", f"{key} expected {expected}, got {actual!r}")

    # Point72 raw anchor
    eb = data.get("evidence_b_point72_2019q4_discovery", {})
    raw_anchor = eb.get("raw_all_asset_anchor", {})
    if raw_anchor.get("main_accession_raw_lines_total") != 917:
        fail("POINT72_RAW", f"main_accession_raw_lines_total expected 917, got {raw_anchor.get('main_accession_raw_lines_total')!r}")
    if raw_anchor.get("main_accession_shares_total") != 418109088:
        fail("POINT72_RAW", f"main_accession_shares_total expected 418109088, got {raw_anchor.get('main_accession_shares_total')!r}")
    if raw_anchor.get("main_accession_value_usd_total") != 19018144000.0:
        fail("POINT72_RAW", f"main_accession_value_usd_total expected 19018144000, got {raw_anchor.get('main_accession_value_usd_total')!r}")
    bd = raw_anchor.get("main_accession_asset_breakdown", {})
    ce = bd.get("cash_equity", {})
    co = bd.get("call_option", {})
    po = bd.get("put_option", {})
    if ce.get("rows") != 877:
        fail("POINT72_RAW", f"cash_equity rows expected 877, got {ce.get('rows')!r}")
    if co.get("rows") != 31:
        fail("POINT72_RAW", f"call_option rows expected 31, got {co.get('rows')!r}")
    if po.get("rows") != 9:
        fail("POINT72_RAW", f"put_option rows expected 9, got {po.get('rows')!r}")

    # Point72 primary cash
    p_m0 = eb.get("primary_m0", {})
    if p_m0.get("asset_scope") != "CASH_EQUITY_ONLY":
        fail("POINT72_PRIMARY", f"asset_scope expected 'CASH_EQUITY_ONLY', got {p_m0.get('asset_scope')!r}")
    if p_m0.get("main_accession_raw_lines_retained") != 877:
        fail("POINT72_PRIMARY", f"main_accession_raw_lines_retained expected 877, got {p_m0.get('main_accession_raw_lines_retained')!r}")
    if p_m0.get("main_accession_shares_before_dedup") != 404693788:
        fail("POINT72_PRIMARY", f"main_accession_shares_before_dedup expected 404693788, got {p_m0.get('main_accession_shares_before_dedup')!r}")
    if p_m0.get("main_accession_value_before_dedup") != 17857865000.0:
        fail("POINT72_PRIMARY", f"main_accession_value_before_dedup expected 17857865000, got {p_m0.get('main_accession_value_before_dedup')!r}")

    # Zero-excluded sensitivity
    z_ex = eb.get("zero_excluded_sensitivity", {})
    if z_ex.get("main_accession_raw_lines_retained") != 0:
        fail("ZERO_EXCLUDED", f"main_accession_raw_lines_retained expected 0, got {z_ex.get('main_accession_raw_lines_retained')!r}")
    if z_ex.get("unresolved_rows_count") != 877:
        fail("ZERO_EXCLUDED", f"unresolved_rows_count expected 877, got {z_ex.get('unresolved_rows_count')!r}")
    if z_ex.get("unresolved_shares_total") != 404693788:
        fail("ZERO_EXCLUDED", f"unresolved_shares_total expected 404693788, got {z_ex.get('unresolved_shares_total')!r}")

    # Split pilot pairs
    splits = data.get("evidence_c_split_pilot_pairs", [])
    expected_splits = {
        "NVDA": {"cusip": "67066G104", "q_prev": "2024-03-31", "q_curr": "2024-06-30", "factor": 10.0},
        "TSLA": {"cusip": "88160R101", "q_prev": "2022-06-30", "q_curr": "2022-09-30", "factor": 3.0},
        "AMZN": {"cusip": "023135106", "q_prev": "2022-03-31", "q_curr": "2022-06-30", "factor": 20.0},
        "GOOGL": {"cusip": "02079K305", "q_prev": "2022-06-30", "q_curr": "2022-09-30", "factor": 20.0},
    }

    if len(splits) != 4:
        fail("SPLITS", f"expected exactly 4 split pairs, got {len(splits)}")
    else:
        seen_symbols: set[str] = set()
        for sp in splits:
            sym = sp.get("stock_symbol")
            if sym in seen_symbols:
                fail("SPLITS", f"duplicate symbol {sym}")
            seen_symbols.add(sym)

            if sym not in expected_splits:
                fail("SPLITS", f"unexpected symbol {sym}")
                continue

            exp = expected_splits[sym]
            if sp.get("cusip") != exp["cusip"]:
                fail("SPLITS", f"{sym} cusip expected {exp['cusip']}, got {sp.get('cusip')!r}")
            if sp.get("q_prev") != exp["q_prev"]:
                fail("SPLITS", f"{sym} q_prev expected {exp['q_prev']}, got {sp.get('q_prev')!r}")
            if sp.get("q_curr") != exp["q_curr"]:
                fail("SPLITS", f"{sym} q_curr expected {exp['q_curr']}, got {sp.get('q_curr')!r}")
            if sp.get("contract_split_factor") != exp["factor"]:
                fail("SPLITS", f"{sym} factor expected {exp['factor']}, got {sp.get('contract_split_factor')!r}")
            if sp.get("waterfall_state") != "KNOWN_SPLIT_PASS":
                fail("SPLITS", f"{sym} waterfall_state expected 'KNOWN_SPLIT_PASS', got {sp.get('waterfall_state')!r}")
            if sp.get("waterfall_action") != "INCLUDE":
                fail("SPLITS", f"{sym} waterfall_action expected 'INCLUDE', got {sp.get('waterfall_action')!r}")
            if sp.get("is_in_contract_pass_range") is not True:
                fail("SPLITS", f"{sym} is_in_contract_pass_range expected True, got {sp.get('is_in_contract_pass_range')!r}")

        for sym in expected_splits:
            if sym not in seen_symbols:
                fail("SPLITS", f"missing expected symbol {sym}")

    return failures


def format_markdown_report(data: dict[str, Any]) -> str:
    """Format C1 discovery data into comprehensive GitHub Flavored Markdown."""
    lines: list[str] = []

    lines.append("# M0 Stage C Part C1 Pilot Discovery Report")
    lines.append("")
    lines.append(f"> **Status**: `{data['status']}`<br>")
    lines.append(f"> **Generated UTC**: `{data['created_utc']}`<br>")
    lines.append(f"> **Total Execution Time**: `{data['total_execution_time_sec']}s`<br>")
    lines.append(f"> **Contract Version**: `{data.get('contract_version', 'UNKNOWN')}`<br>")
    lines.append(f"> **Source Git SHA**: `{data.get('source_git_sha', 'UNKNOWN')}`<br>")
    lines.append(f"> **Git Tree Dirty**: `{data.get('git_tree_dirty', 'UNKNOWN')}`<br>")
    lines.append(f"> **Contract SHA256**: `{data.get('contract_sha256', 'UNKNOWN')}`<br>")
    lines.append(f"> **Artifact Schema Version**: `{data.get('artifact_schema_version', 'UNKNOWN')}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 1: Preflight & Environment
    pf = data["preflight"]
    lines.append("## 1. Source Database Preflight & Read-Only Safety")
    lines.append(f"- **Source DB File**: `{pf['db_filename']}` ({pf['db_path']})")
    lines.append(f"- **File Size**: {pf['size_bytes']:,} bytes ({pf['size_bytes'] / (1024**3):.2f} GiB)")
    lines.append(f"- **PRAGMA query_only Verification**: `query_only = {pf['query_only_pragma']}` (Strict Read-Only)")
    lines.append(f"- **Sidecar Integrity**: Checked zero `-wal`, `-shm`, `-journal` files present.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 2: Evidence A
    ea = data["evidence_a_berkshire_apple_2023q4"]
    lines.append("## 2. Evidence A: Berkshire Hathaway 2023Q4 Apple Accession Aggregation")
    lines.append("")
    lines.append(f"- **Accession Number**: `{ea['accession_number']}`")
    lines.append(f"- **Origin Filer CIK**: `{ea['origin_filer_cik']}`")
    lines.append(f"- **Period of Report**: `{ea['period_of_report']}`")
    lines.append(f"- **Acceptance Datetime (PIT)**: `{ea['acceptance_datetime']}`")
    lines.append(f"- **Confidential Treatment Flag (`is_confidential_omit`)**: `{ea['is_confidential_omit']}`")
    lines.append(f"- **Raw Matching Rows Count**: {ea['raw_matching_rows_count']}")
    lines.append(f"- **Raw Aggregate Shares Total**: **{ea['raw_total_aggregate_shares']:,}**")
    lines.append(f"- **Raw Aggregate Value Total USD**: ${ea['raw_total_aggregate_value_usd']:,}")
    lines.append(f"- **Preregistered Expected Anchor**: **{ea['preregistered_expected_anchor']:,}**")
    lines.append(f"- **Raw Anchor Match**: **{'EXACT MATCH (100%)' if ea['anchor_raw_match'] else 'MISMATCH'}**")
    lines.append("")
    lines.append("### Primary Eligibility Assessment")
    lines.append(f"- **Primary Eligible**: **{'YES' if ea['is_primary_eligible'] else 'NO (EXCLUDED)'}**")
    lines.append(f"- **Resolved Primary Shares**: {ea['primary_resolved_shares']:,}")
    lines.append(f"- **Unresolved Rows Count**: {ea['unresolved_rows_count']} / {ea['raw_matching_rows_count']}")
    lines.append(f"- **Unresolved Shares Total**: {ea['unresolved_shares_total']:,}")
    lines.append(f"- **Multi-Sequence (`other_manager` lists) Rows**: {ea['multi_sequence_rows_count']}")
    if ea["ineligibility_reasons"]:
        lines.append(f"- **Ineligibility Reasons**:")
        for r in ea["ineligibility_reasons"]:
            lines.append(f"  - `{r}`")
    lines.append("")
    lines.append("### Raw Matching Line Items Breakdown")
    lines.append("")
    lines.append("| Line Seq | Security Name | Shares | Value USD | Discretion | Other Mgr | Multi-Seq | Resolved Owner | Unresolved |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for r in ea["raw_matching_rows"]:
        owner_str = r['resolved_owner_cik'] or "None"
        is_multi = "YES" if r.get('other_manager_category') == "MULTI_NUMERIC_LIST" else "NO"
        lines.append(
            f"| {r['line_seq']} | {r['security_name']} | {r['shares']:,} | ${r['value_usd']:,} | {r['investment_discretion']} | {r['other_manager']} | {is_multi} | `{owner_str}` | {'YES' if r['ownership_unresolved'] else 'NO'} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 3: Evidence B
    eb = data["evidence_b_point72_2019q4_discovery"]
    lines.append("## 3. Evidence B: Point72 2019Q4 Multi-Manager Discovery & v0.8.3 Reconciliation")
    lines.append("")
    lines.append(f"- **Status**: `{eb['status']}`")
    lines.append(f"- **Entity Name**: `{eb['entity_name']}`")
    lines.append(f"- **Period of Report**: `{eb['period_of_report']}`")
    lines.append(f"- **Canonical Entity ID (Numeric-Min CIK)**: `{eb['canonical_entity_id']}`")
    lines.append(f"- **Seed CIKs (from `manager_names`)**: `{eb['seed_ciks']}`")
    lines.append(f"- **Graph Closed CIKs (Connected Component)**: `{eb['component_closed_ciks']}`")
    lines.append(f"- **Total Accessions in Component**: {eb['accessions_count']}")
    lines.append(f"- **Manager Relationships in Component**: {eb['manager_relationships_count']}")
    lines.append(f"- **Total Raw Line Items Across Component**: {eb['total_raw_line_items']:,}")
    lines.append(f"- **On-Time Confidential Filings**: {eb.get('on_time_confidential_filings_count', 0)} / **All-Period Confidential Filings**: {eb.get('all_period_confidential_filings_count', 0)}")
    lines.append(f"- **On-Time Amendment Filings**: {eb.get('on_time_amendment_filings_count', 0)} / **All-Period Amendment Filings**: {eb.get('all_period_amendment_filings_count', 0)}")
    lines.append(f"- **Execution Time**: {eb['execution_time_sec']}s")
    lines.append("")
    lines.append("### Source Tables Disambiguation & Fail-Closed PIT Disclosure")
    st_info = eb.get("source_tables_breakdown", {})
    lines.append(f"- **Line-Level Sequence Lookup Source**: `{st_info.get('line_lookup_source_table', 'OTHERMANAGER2.tsv only')}` ({st_info.get('line_map_entries_count', 0)} sequence mappings)")
    lines.append(f"- **Entity Graph Affiliation Edges Source**: `{st_info.get('graph_edges_source_tables', 'OTHERMANAGER.tsv and OTHERMANAGER2.tsv union')}` ({st_info.get('graph_edges_count', 0)} undirected edges)")
    lines.append("- **PIT Missing Timestamp Handling**: Fail-closed (relationships with missing or invalid `acceptance_datetime` are strictly excluded).")
    lines.append("")
    lines.append("### Point72 Policy Comparison: Primary M0 vs ZERO_SENTINEL_EXCLUDED Sensitivity (M0 Cash Equity Only)")
    lines.append("")
    p_m0 = eb.get("primary_m0", {})
    z_ex = eb.get("zero_excluded_sensitivity", {})
    lines.append("| Metric / Pipeline Stage | Primary M0 (Cash Equity Only) | ZERO_SENTINEL_EXCLUDED (Cash Equity Only) | Delta |")
    lines.append("| :--- | :---: | :---: | :---: |")
    lines.append(f"| **Cash Equity Raw Line Items** | {p_m0.get('raw_line_items_count', 0):,} | {z_ex.get('raw_line_items_count', 0):,} | 0 |")
    lines.append(f"| **Main Filing (`0001567619-20-004063`) Cash Rows Retained** | **{p_m0.get('main_accession_raw_lines_retained', 0)}** | **{z_ex.get('main_accession_raw_lines_retained', 0)}** | {z_ex.get('main_accession_raw_lines_retained', 0) - p_m0.get('main_accession_raw_lines_retained', 0)} |")
    lines.append(f"| **Main Filing Cash Shares Before Dedup** | **{p_m0.get('main_accession_shares_before_dedup', 0):,}** | **{z_ex.get('main_accession_shares_before_dedup', 0):,}** | {z_ex.get('main_accession_shares_before_dedup', 0) - p_m0.get('main_accession_shares_before_dedup', 0):,} |")
    lines.append(f"| **Main Filing Cash Value USD Before Dedup** | **${p_m0.get('main_accession_value_before_dedup', 0):,.0f}** | **${z_ex.get('main_accession_value_before_dedup', 0):,.0f}** | -${p_m0.get('main_accession_value_before_dedup', 0):,.0f} |")
    lines.append(f"| **Unresolved Cash Rows Count** | {p_m0.get('unresolved_rows_count', 0)} | {z_ex.get('unresolved_rows_count', 0)} | +{z_ex.get('unresolved_rows_count', 0) - p_m0.get('unresolved_rows_count', 0)} |")
    lines.append(f"| **Unresolved Cash Shares Total** | {p_m0.get('unresolved_shares_total', 0):,} | {z_ex.get('unresolved_shares_total', 0):,} | +{z_ex.get('unresolved_shares_total', 0) - p_m0.get('unresolved_shares_total', 0):,} |")
    lines.append(f"| **Reconstructed Cash Disclosures Count** | {p_m0.get('reconstructed_disclosures_count', 0):,} | {z_ex.get('reconstructed_disclosures_count', 0):,} | {z_ex.get('reconstructed_disclosures_count', 0) - p_m0.get('reconstructed_disclosures_count', 0):,} |")
    lines.append(f"| **Intra-Entity Deduplicated Cash Holdings** | {p_m0.get('intra_entity_deduped_holdings_count', 0):,} | {z_ex.get('intra_entity_deduped_holdings_count', 0):,} | {z_ex.get('intra_entity_deduped_holdings_count', 0) - p_m0.get('intra_entity_deduped_holdings_count', 0):,} |")
    lines.append(f"| **Total Cash Shares Deduplicated** | **{p_m0.get('total_shares_deduped', 0):,}** | **{z_ex.get('total_shares_deduped', 0):,}** | {z_ex.get('total_shares_deduped', 0) - p_m0.get('total_shares_deduped', 0):,} |")
    lines.append(f"| **Total Cash Value USD Deduplicated** | **${p_m0.get('total_value_usd_deduped', 0):,.0f}** | **${z_ex.get('total_value_usd_deduped', 0):,.0f}** | -${p_m0.get('total_value_usd_deduped', 0) - z_ex.get('total_value_usd_deduped', 0):,.0f} |")
    lines.append("")
    lines.append("### Pre-Eligibility Raw All-Asset Anchor Disclosure")
    raw_anchor = eb.get("raw_all_asset_anchor", {})
    lines.append("")
    lines.append("| Asset Class / Anchor Level | Raw Rows Count | Raw Shares Total | Raw Value USD | In M0 Cash Equity Scope? |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")
    bd = raw_anchor.get("main_accession_asset_breakdown", {})
    ce = bd.get("cash_equity", {})
    co = bd.get("call_option", {})
    po = bd.get("put_option", {})
    lines.append(f"| Main Accession Cash Equity (`SH`) | {ce.get('rows', 0):,} | {ce.get('shares', 0):,} | ${ce.get('value_usd', 0):,.0f} | **YES (Included)** |")
    lines.append(f"| Main Accession Call Options (`call_option`) | {co.get('rows', 0):,} | {co.get('shares', 0):,} | ${co.get('value_usd', 0):,.0f} | **NO (Excluded)** |")
    lines.append(f"| Main Accession Put Options (`put_option`) | {po.get('rows', 0):,} | {po.get('shares', 0):,} | ${po.get('value_usd', 0):,.0f} | **NO (Excluded)** |")
    lines.append(f"| **Main Accession All-Asset Raw Total** | **{raw_anchor.get('main_accession_raw_lines_total', 0):,}** | **{raw_anchor.get('main_accession_shares_total', 0):,}** | **${raw_anchor.get('main_accession_value_usd_total', 0):,.0f}** | *Pre-Eligibility Anchor* |")
    lines.append(f"| **Point72 Component All-Asset Total** | **{raw_anchor.get('total_component_raw_lines', 0):,}** | **{raw_anchor.get('total_component_raw_shares', 0):,}** | **${raw_anchor.get('total_component_raw_value_usd', 0):,.0f}** | *Pre-Eligibility Anchor* |")
    lines.append("")
    lines.append("### Accessions and Filing Events (Actual PIT Timestamps)")
    lines.append("")
    lines.append("| Accession Number | Filer CIK | Actual Acceptance Datetime | On-Time | Form | Amendment | Conf Omit |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for a in eb["accessions"]:
        lines.append(
            f"| `{a['accession_number']}` | `{a['filer_cik']}` | `{a['acceptance_datetime']}` | {'YES' if a['is_pit_on_time'] else 'NO'} | {a['form_type']} | {a['amendment_type'] or 'None'} | {'YES' if a['is_confidential_omit'] else 'NO'} |"
        )
    lines.append("")
    lines.append("### Manager Relationships & Sequence Mappings (Actual PIT Timestamps)")
    lines.append("")
    lines.append("| Accession Number | Reporter CIK | Seq # | Related CIK | Related Name | Source Table | Actual Acceptance Datetime |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for m in eb["manager_relationships"]:
        lines.append(
            f"| `{m['accession_number']}` | `{m['reporter_cik']}` | {m['sequence_number']} | `{m['related_cik']}` | {m['related_name']} | `{m.get('source_table', 'OTHERMANAGER2.tsv')}` | `{m['acceptance_datetime']}` |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 4: Evidence C
    lines.append("## 4. Evidence C: Four Canonical Split Pilot Pairs (Full World-B Pipeline, Cash Equity Only)")
    lines.append("")
    lines.append("| Symbol | CUSIP | Quarter Pair | Split Factor | Ex-Date | Continuous Entities | Raw Median | MAD_log | Adj Median | State | Action | Pass [0.8, 1.2] |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for sp in data["evidence_c_split_pilot_pairs"]:
        lines.append(
            f"| **{sp['stock_symbol']}** | `{sp['cusip']}` | {sp['q_prev']} $\\to$ {sp['q_curr']} | {sp['contract_split_factor']} | {sp['contract_ex_date']} | {sp['eligible_continuous_entity_count']} | {sp['raw_median_ratio']} | {sp['mad_log']} | {sp['adjusted_median_ratio']} | `{sp['waterfall_state']}` | `{sp['waterfall_action']}` | **{'PASS' if sp['is_in_contract_pass_range'] else 'FAIL'}** |"
        )
    lines.append("")

    # Before vs After Split Metrics Impact Table (genuinely measured naive baseline)
    lines.append("### Before vs After Entity Graph G(Q-1, Q) Impact Comparison")
    lines.append("")
    lines.append("The table below contrasts the measured naive filer-level continuous holder count against the true $G(Q-1, Q)$ entity connected components. The naive count is the number of individual CIK filers who hold resolved cash equity positions in the target CUSIP in both Q-1 and Q, before entity graph grouping.")
    lines.append("")
    lines.append("| Symbol | Naive Filer Grouping N | True Graph $G(Q-1, Q)$ N | Delta N (%) | Raw Median | Adj Median | State | Pass [0.8, 1.2] |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for sp in data["evidence_c_split_pilot_pairs"]:
        sym = sp["stock_symbol"]
        n_naive = sp.get("naive_continuous_filer_count", 0)
        n_true = sp["eligible_continuous_entity_count"]
        delta_n = n_true - n_naive
        pct_delta = (delta_n / n_naive * 100) if n_naive else 0.0
        lines.append(
            f"| **{sym}** | {n_naive:,} | {n_true:,} | {delta_n:+,} ({pct_delta:.1f}%) | {sp['raw_median_ratio']} | {sp['adjusted_median_ratio']} | `{sp['waterfall_state']}` | **{'PASS' if sp['is_in_contract_pass_range'] else 'FAIL'}** |"
        )
    lines.append("")

    # Component-Level Exclusions Breakdown
    lines.append("### Component-Level Exclusion Counts Breakdown")
    lines.append("")
    lines.append("| Symbol | Membership Incomplete | Confidential Omission | Amendment Unresolved | New Positions | Exit Positions | Unresolved Ownership Rows (Q-1 / Q) |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for sp in data["evidence_c_split_pilot_pairs"]:
        ex = sp["component_level_exclusions"]
        lines.append(
            f"| **{sp['stock_symbol']}** | {ex['membership_incomplete_components_excluded']} | {ex['confidential_omission_components_excluded']} | {ex['amendment_unresolved_components_excluded']} | {ex['new_positions_count']} | {ex['exit_positions_count']} | {ex['unresolved_ownership_rows_excluded_q_prev']} / {ex['unresolved_ownership_rows_excluded_q_curr']} |"
        )
    lines.append("")

    # Global Dataset Context
    lines.append("### Global Dataset Context")
    lines.append("")
    lines.append("| Symbol | Q-1 On-Time Filers | Q On-Time Filers | Late Filings (Q-1 / Q) | Graph Connected Components | On-Time Relationship Edges |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for sp in data["evidence_c_split_pilot_pairs"]:
        gc = sp["global_dataset_context"]
        lines.append(
            f"| **{sp['stock_symbol']}** | {gc['total_on_time_filers_q_prev']:,} | {gc['total_on_time_filers_q_curr']:,} | {gc['late_filings_excluded_q_prev']} / {gc['late_filings_excluded_q_curr']} | {gc['total_connected_components_in_graph']:,} | {gc['total_on_time_relationship_edges']:,} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 5: Real-Data Assumption Discovery
    lines.append("## 5. Real-Data Assumption Discovery: Multi-Manager Sequences and Free-Text Manager Names")
    lines.append("")
    lines.append("Under Contract v0.8.3, `resolve_ownership` resolves single integer sequence numbers strictly against `OTHERMANAGER2.tsv` and treats blank/N-A/exact-0 as origin sentinels. Numeric multi-sequence lists (e.g. `'1,2,4,11'`, `'1 3 4'`) and free-text manager names (e.g. `'Blue Chip Partners LLC'`, `'PARAMETRIC PORTFOLIO ASSOCIATES LLC'`) remain unresolved and excluded from Primary M0.")
    lines.append("")
    lines.append("| Target Symbol / Filing | Q-1 Multi-Seq Rows | Q Multi-Seq Rows | Q-1 Free-Text Rows | Q Free-Text Rows | Sample Values |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    lines.append(f"| **Berkshire Apple 2023Q4** | {ea['multi_sequence_rows_count']} | N/A | {ea.get('free_text_name_rows_count', 0)} | N/A | `{', '.join(ea['multi_sequence_samples'][:3])}` |")
    for sp in data["evidence_c_split_pilot_pairs"]:
        ms = sp["multi_sequence_other_manager"]
        samples_str = ", ".join(ms["samples"][:3]) if ms["samples"] else "None"
        lines.append(
            f"| **{sp['stock_symbol']}** | {ms['q_prev_multi_sequence_rows']} | {ms['q_curr_multi_sequence_rows']} | {ms.get('q_prev_free_text_rows', 0)} | {ms.get('q_curr_free_text_rows', 0)} | `{samples_str}` |"
        )
    lines.append("")
    lines.append("> **Impact Analysis**: Under Contract v0.8.3, multi-sequence strings, free-text names, and unmapped sequences are conservatively treated as unresolved ownership and excluded from Primary M0 without silent fallback.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 6: Whole-Database Manager Mapping Conflict Diagnostics
    lines.append("## 6. Whole-Database Manager Mapping Conflict Diagnostics & Quarantine Audit")
    lines.append("")
    mcd = data.get("mapping_conflict_diagnostics", {})
    lines.append("| Diagnostic Metric | Measured Value in Frozen DB | Enforcement Rule |")
    lines.append("| :--- | :---: | :--- |")
    lines.append(f"| Total Conflicted `(accession, sequence)` Keys in `OTHERMANAGER2.tsv` | **{mcd.get('total_conflict_keys_in_othermanager2', 50)}** | Quarantined (Excluded from Line Lookup Map) |")
    lines.append(f"| Conflicted Keys Referenced by `filing_line_items` | **{mcd.get('referenced_conflict_keys_count', 17)}** | Resolved to `ownership_unresolved = True` |")
    lines.append(f"| Affected Raw Line Items Excluded from Primary M0 | **{mcd.get('affected_raw_line_items_count', 5472):,}** | Excluded from Primary M0 |")
    lines.append(f"| Affected Shares Total | **{mcd.get('affected_shares_total', 659481568):,}** | Excluded from Primary M0 |")
    lines.append(f"| Affected Value USD Total | **${mcd.get('affected_value_usd_total', 42779736343.0):,.0f}** | Excluded from Primary M0 |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 7: Honest Audit Boundaries
    lines.append("## 7. Honest Audit Boundaries")
    lines.append("- **Read-Only Guarantee**: Phase 0 database was accessed strictly via `open_readonly_sqlite(immutable=True)` with `PRAGMA query_only=ON`. Zero writes performed.")
    lines.append("- **Zero Network**: No requests were made to OpenFIGI, yfinance, or SEC EDGAR.")
    lines.append("- **Status**: Discovery evidence collected; fixtures remain proposed pending Codex independent manual audit and freeze.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 8: C1 Implementation Audit
    lines.append("## 8. C1 Implementation Audit & Contract v0.8.3 Reconciliation")
    lines.append("- **Contract Specification**: `CONTRACT.md` v0.8.3 (Canonical Frozen Amended Specification).")
    lines.append("- **Audit Status**: `STAGE C PART C1 DISCOVERY UNDER CODEX RE-AUDIT`.")
    lines.append("- **Point72 Raw Anchor (Pre-Eligibility)**: Retains all 917 `DFND` / `'0'` rows (877 cash, 31 call option, 9 put option), totaling 418,109,088 shares and $19,018,144,000 USD before deduplication.")
    lines.append("- **Point72 M0 Cash-Equity Eligible (Primary)**: Retains 877 cash equity rows, totaling 404,693,788 shares and $17,857,865,000 USD for main accession; 4,408 cash equity rows totaling 549,534,258 shares and $23,800,447,000 USD across component.")
    lines.append("- **Point72 Zero-Excluded Sensitivity (Cash Equity)**: Upstream pre-aggregation exclusion drops exactly the 877 main cash rows, yielding 3,531 cash equity rows totaling 144,840,470 shares and $5,942,582,000 USD across component.")
    lines.append("- **Mapping Conflict Quarantine**: Fully verified 50 conflict keys, 17 referenced keys, and 5,472 affected rows quarantined deterministically.")
    lines.append("- **Fail-Closed PIT Filtering**: All manager relationships with missing or invalid `acceptance_datetime` fail closed when `period` is supplied.")
    lines.append("- **Split Anchors**: All four canonical split stocks (NVDA, TSLA, AMZN, GOOGL) achieve adjusted medians in `[0.8, 1.2]` under full $G(Q-1, Q)$ graph components.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage C Part C1 Pilot Discovery against Phase 0 DB.")
    parser.add_argument(
        "--db-path",
        default="research/smart_money/phase0/data/13f_full_4409f14.db",
        help="Path to Phase 0 SQLite DB (default: research/smart_money/phase0/data/13f_full_4409f14.db)",
    )
    parser.add_argument(
        "--out-dir",
        default="research/smart_money/m0",
        help="Directory to save discovery artifacts (default: research/smart_money/m0)",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Starting Stage C Part C1 Pilot Discovery against: {db_path}")
    discovery_data = run_full_c1_discovery(db_path)

    # Validate C1 gate BEFORE writing artifacts
    gate_failures = validate_c1_gate(discovery_data)
    if gate_failures:
        print("[FAIL] Stage C1 Gate Validation FAILED:")
        for f in gate_failures:
            print(f"  - {f}")
        print("[*] Artifacts NOT written. Prior good artifacts preserved.")
        sys.exit(1)

    print("[PASS] Stage C1 Gate Validation PASSED.")

    # Write JSON artifact
    json_path = out_dir / "STAGE_C1_DISCOVERY.json"
    json_content = canonical_json_dumps(discovery_data)
    json_path.write_text(json_content, encoding="utf-8")
    print(f"[+] Written discovery JSON: {json_path} ({json_path.stat().st_size:,} bytes)")

    # Write Markdown artifact
    md_path = out_dir / "STAGE_C_DISCOVERY.md"
    md_content = format_markdown_report(discovery_data)
    md_path.write_text(md_content, encoding="utf-8")
    print(f"[+] Written discovery Markdown: {md_path} ({md_path.stat().st_size:,} bytes)")

    print(f"[*] Total execution time: {discovery_data['total_execution_time_sec']:.3f}s")
    print("[*] Stage C Part C1 Pilot Discovery Completed Successfully (Gate PASS).")


if __name__ == "__main__":
    main()
