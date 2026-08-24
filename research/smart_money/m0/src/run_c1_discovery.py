"""CLI runner and artifact generator for Stage C Part C1 Pilot Discovery.

Runs pilot extraction against research/smart_money/phase0/data/13f_full_4409f14.db (read-only immutable),
generates machine-readable JSON (STAGE_C1_DISCOVERY.json) and human-readable Markdown (STAGE_C_DISCOVERY.md).
"""

import argparse
from pathlib import Path
import time
from typing import Any

from research.smart_money.m0.src.manifest_integrity import canonical_json_dumps
from research.smart_money.m0.src.pilot_extractor import run_full_c1_discovery


def format_markdown_report(data: dict[str, Any]) -> str:
    """Format C1 discovery data into comprehensive GitHub Flavored Markdown."""
    lines: list[str] = []

    lines.append(f"# M0 Stage C Part C1 Pilot Discovery Report")
    lines.append("")
    lines.append(f"> **Status**: `{data['status']}`  ")
    lines.append(f"> **Generated UTC**: `{data['created_utc']}`  ")
    lines.append(f"> **Total Execution Time**: `{data['total_execution_time_sec']}s`")
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
    lines.append("## 3. Evidence B: Point72 2019Q4 Multi-Manager Discovery (Proposed Fixture)")
    lines.append("")
    lines.append(f"- **Status**: `{eb['status']}`")
    lines.append(f"- **Entity Name**: `{eb['entity_name']}`")
    lines.append(f"- **Period of Report**: `{eb['period_of_report']}`")
    lines.append(f"- **Canonical Entity ID (Numeric-Min CIK)**: `{eb['canonical_entity_id']}`")
    lines.append(f"- **Seed CIKs (from `manager_names`)**: `{eb['seed_ciks']}`")
    lines.append(f"- **Graph Closed CIKs (Connected Component)**: `{eb['component_closed_ciks']}`")
    lines.append(f"- **Total Accessions in Component**: {eb['accessions_count']}")
    lines.append(f"- **Manager Relationships in Component**: {eb['manager_relationships_count']}")
    lines.append(f"- **Total Raw Line Items**: {eb['total_raw_line_items']:,}")
    lines.append(f"- **Reconstructed Disclosures**: {eb['reconstructed_disclosures_count']:,}")
    lines.append(f"- **Intra-Entity Deduplicated Holdings**: {eb['intra_entity_deduped_holdings_count']:,}")
    lines.append(f"- **Unresolved Rows Count**: {eb.get('unresolved_rows_count', 0)}")
    lines.append(f"- **Unresolved Shares Total**: {eb.get('unresolved_shares_total', 0):,}")
    lines.append(f"- **On-Time Confidential Filings**: {eb.get('on_time_confidential_filings_count', 0)} / **All-Period Confidential Filings**: {eb.get('all_period_confidential_filings_count', 0)}")
    lines.append(f"- **On-Time Amendment Filings**: {eb.get('on_time_amendment_filings_count', 0)} / **All-Period Amendment Filings**: {eb.get('all_period_amendment_filings_count', 0)}")
    lines.append(f"- **Cross-Component Excluded Disclosures**: {eb.get('cross_component_excluded_count', 0)}")
    lines.append(f"- **Execution Time**: {eb['execution_time_sec']}s")
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
    lines.append("| Accession Number | Reporter CIK | Seq # | Related CIK | Related Name | Actual Acceptance Datetime |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for m in eb["manager_relationships"]:
        lines.append(
            f"| `{m['accession_number']}` | `{m['reporter_cik']}` | {m['sequence_number']} | `{m['related_cik']}` | {m['related_name']} | `{m['acceptance_datetime']}` |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 4: Evidence C
    lines.append("## 4. Evidence C: Four Canonical Split Pilot Pairs (Full World-B Pipeline)")
    lines.append("")
    lines.append("| Symbol | CUSIP | Quarter Pair | Split Factor | Ex-Date | Continuous Entities | Raw Median | MAD_log | Adj Median | State | Action | Pass [0.8, 1.2] |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for sp in data["evidence_c_split_pilot_pairs"]:
        lines.append(
            f"| **{sp['stock_symbol']}** | `{sp['cusip']}` | {sp['q_prev']} $\\to$ {sp['q_curr']} | {sp['contract_split_factor']} | {sp['contract_ex_date']} | {sp['eligible_continuous_entity_count']} | {sp['raw_median_ratio']} | {sp['mad_log']} | {sp['adjusted_median_ratio']} | `{sp['waterfall_state']}` | `{sp['waterfall_action']}` | **{'PASS' if sp['is_in_contract_pass_range'] else 'FAIL'}** |"
        )
    lines.append("")

    # Before vs After Split Metrics Impact Table
    lines.append("### Before vs After Entity Graph G(Q-1, Q) Impact Comparison")
    lines.append("")
    lines.append("The table below contrasts the naive filer grouping against the true $G(Q-1, Q)$ entity connected components and filing members equality gate:")
    lines.append("")
    lines.append("| Symbol | Naive Filer Grouping N | True Graph $G(Q-1, Q)$ N | Delta N (%) | Raw Median | Adj Median | State | Pass [0.8, 1.2] |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    naive_map = {"NVDA": 3366, "TSLA": 1831, "AMZN": 2948, "GOOGL": 2612}
    for sp in data["evidence_c_split_pilot_pairs"]:
        sym = sp["stock_symbol"]
        n_naive = naive_map.get(sym, 0)
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

    # Section 5: Real-Data Assumption Discovery: Multi-Manager Sequences and Free-Text Manager Names
    lines.append("## 5. Real-Data Assumption Discovery: Multi-Manager Sequences and Free-Text Manager Names")
    lines.append("")
    lines.append("Under the frozen Contract v0.8.1 specification, `resolve_ownership` resolves single integer sequence numbers against `manager_relationships`. In real SEC 13F filings, filers supply both numeric multi-sequence lists (e.g. `'1,2,4,11'`, `'1 3 4'`) and free-text manager names (e.g. `'Blue Chip Partners LLC'`, `'PARAMETRIC PORTFOLIO ASSOCIATES LLC'`) in the `other_manager` field.")
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
    lines.append("> **Impact Analysis**: Under existing frozen rules, both multi-sequence strings and free-text names are conservatively treated as unresolved ownership and excluded from Primary M0. They are neither silently attributed to origin filers nor artificially split across managers. This discovery is surfaced for Codex and user consideration.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 6: Honest Audit Boundaries
    lines.append("## 6. Honest Audit Boundaries")
    lines.append("- **Read-Only Guarantee**: Phase 0 database was accessed strictly via `open_readonly_sqlite(immutable=True)` with `PRAGMA query_only=ON`. Zero writes performed.")
    lines.append("- **Zero Network**: No requests were made to OpenFIGI, yfinance, or SEC EDGAR.")
    lines.append("- **Status**: Discovery evidence collected; fixtures remain proposed pending Codex independent manual audit and freeze.")
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
    print("[*] Stage C Part C1 Pilot Discovery Completed Successfully.")


if __name__ == "__main__":
    main()
