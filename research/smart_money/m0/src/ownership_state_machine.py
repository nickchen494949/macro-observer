"""Ownership resolution, SEC 13F filing deadline calendar, and per-origin-filer state machine."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
import zoneinfo

_EASTERN_TZ = zoneinfo.ZoneInfo("America/New_York")
_UTC_TZ = zoneinfo.ZoneInfo("UTC")


def _get_sec_holidays(year: int) -> set[date]:
    """Calculate US Federal / SEC official holidays for a given year."""
    holidays: set[date] = set()

    # 1. New Year's Day (Jan 1)
    nyd = date(year, 1, 1)
    if nyd.weekday() == 6:  # Sunday -> Monday
        holidays.add(date(year, 1, 2))
    elif nyd.weekday() == 5:  # Saturday -> Friday Dec 31 prior year
        holidays.add(date(year - 1, 12, 31))
    else:
        holidays.add(nyd)

    # 2. Martin Luther King Jr. Day (3rd Monday in Jan)
    first_jan = date(year, 1, 1)
    mlk_offset = (0 - first_jan.weekday()) % 7 + 14
    holidays.add(date(year, 1, 1 + mlk_offset))

    # 3. Washington's Birthday / Presidents' Day (3rd Monday in Feb)
    first_feb = date(year, 2, 1)
    pres_offset = (0 - first_feb.weekday()) % 7 + 14
    holidays.add(date(year, 2, 1 + pres_offset))

    # 4. Memorial Day (Last Monday in May)
    last_may = date(year, 5, 31)
    mem_offset = (last_may.weekday() - 0) % 7
    holidays.add(date(year, 5, 31 - mem_offset))

    # 5. Juneteenth National Independence Day (June 19, recognized 2021+)
    if year >= 2021:
        jt = date(year, 6, 19)
        if jt.weekday() == 6:
            holidays.add(date(year, 6, 20))
        elif jt.weekday() == 5:
            holidays.add(date(year, 6, 18))
        else:
            holidays.add(jt)

    # 6. Independence Day (July 4)
    ind = date(year, 7, 4)
    if ind.weekday() == 6:
        holidays.add(date(year, 7, 5))
    elif ind.weekday() == 5:
        holidays.add(date(year, 7, 3))
    else:
        holidays.add(ind)

    # 7. Labor Day (1st Monday in Sep)
    first_sep = date(year, 9, 1)
    lab_offset = (0 - first_sep.weekday()) % 7
    holidays.add(date(year, 9, 1 + lab_offset))

    # 8. Columbus Day (2nd Monday in Oct)
    first_oct = date(year, 10, 1)
    col_offset = (0 - first_oct.weekday()) % 7 + 7
    holidays.add(date(year, 10, 1 + col_offset))

    # 9. Veterans Day (Nov 11)
    vet = date(year, 11, 11)
    if vet.weekday() == 6:
        holidays.add(date(year, 11, 12))
    elif vet.weekday() == 5:
        holidays.add(date(year, 11, 10))
    else:
        holidays.add(vet)

    # 10. Thanksgiving Day (4th Thursday in Nov)
    first_nov = date(year, 11, 1)
    thx_offset = (3 - first_nov.weekday()) % 7 + 21
    holidays.add(date(year, 11, 1 + thx_offset))

    # 11. Christmas Day (Dec 25)
    xmas = date(year, 12, 25)
    if xmas.weekday() == 6:
        holidays.add(date(year, 12, 26))
    elif xmas.weekday() == 5:
        holidays.add(date(year, 12, 24))
    else:
        holidays.add(xmas)

    return holidays


def compute_13f_deadline(period_of_report: str) -> str:
    """Compute SEC 13F filing deadline (SEC Rule 0-3).
    
    Base: 45 calendar days after period_of_report.
    If falling on Saturday, Sunday, or US Federal Holiday, rolls forward to the next business day.
    """
    q_end = date.fromisoformat(period_of_report)
    target = q_end + timedelta(days=45)

    holidays = _get_sec_holidays(target.year) | _get_sec_holidays(target.year + 1)

    while target.weekday() >= 5 or target in holidays:
        target += timedelta(days=1)

    return target.isoformat()


def parse_datetime_to_utc(dt_str: str) -> datetime:
    """Parse acceptance datetime string into an aware UTC datetime object."""
    dt_str = dt_str.strip()
    if dt_str.endswith("Z"):
        dt = datetime.fromisoformat(dt_str[:-1] + "+00:00")
    else:
        dt = datetime.fromisoformat(dt_str)
    
    if dt.tzinfo is None:
        # Default naive string to Eastern time if not specified, then convert to UTC
        dt = dt.replace(tzinfo=_EASTERN_TZ)
    return dt.astimezone(_UTC_TZ)


def is_pit_accepted(acceptance_datetime: str, period_of_report: str) -> bool:
    """Check if acceptance datetime converted to Eastern calendar date <= 13F deadline."""
    utc_dt = parse_datetime_to_utc(acceptance_datetime)
    eastern_dt = utc_dt.astimezone(_EASTERN_TZ)
    eastern_date_str = eastern_dt.date().isoformat()
    deadline_str = compute_13f_deadline(period_of_report)
    return eastern_date_str <= deadline_str


def resolve_ownership(
    row_other_manager: str | None,
    origin_filer_cik: str,
    other_manager_map: dict[str, str] | None = None,
) -> tuple[str | None, bool]:
    """Resolve economic owner CIK from row's other_manager entry.
    
    Returns:
        (economic_owner_cik, ownership_unresolved)
    """
    if row_other_manager is None:
        return origin_filer_cik, False
    
    cleaned = str(row_other_manager).strip()
    if not cleaned:
        return origin_filer_cik, False
    
    if other_manager_map and cleaned in other_manager_map:
        return other_manager_map[cleaned], False
    
    # Present but cannot be resolved
    return None, True


@dataclass(frozen=True)
class FilingHeader:
    """Header information for a single 13F submission."""
    accession_number: str
    origin_filer_cik: str
    period_of_report: str
    acceptance_datetime: str
    form_type: str = "13F-HR"
    amendment_type: str | None = None  # 'RESTATEMENT', 'ADD_NEW_HOLDINGS', None
    is_confidential_omit: bool = False


@dataclass(frozen=True)
class HoldingRow:
    """Detail holding line from 13F information table."""
    accession_number: str
    origin_filer_cik: str
    period_of_report: str
    cusip: str
    asset_class: str
    economic_owner_cik: str | None
    ownership_unresolved: bool
    total_shares: float
    total_value_usd: float
    total_vote_sole: float = 0.0
    total_vote_shared: float = 0.0
    total_vote_none: float = 0.0


def aggregate_accession_holdings(
    holdings: list[HoldingRow],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Aggregate holding rows within a single accession by (cusip, asset_class, economic_owner_cik).
    
    Excludes rows where ownership_unresolved == True.
    """
    aggregated: dict[tuple[str, str, str], dict[str, Any]] = {}

    for row in holdings:
        if row.ownership_unresolved or row.economic_owner_cik is None:
            continue
        
        key = (row.cusip, row.asset_class, row.economic_owner_cik)
        if key not in aggregated:
            aggregated[key] = {
                "cusip": row.cusip,
                "asset_class": row.asset_class,
                "economic_owner_cik": row.economic_owner_cik,
                "total_shares": 0.0,
                "total_value_usd": 0.0,
                "total_vote_sole": 0.0,
                "total_vote_shared": 0.0,
                "total_vote_none": 0.0,
            }
        
        agg = aggregated[key]
        agg["total_shares"] += float(row.total_shares)
        agg["total_value_usd"] += float(row.total_value_usd)
        agg["total_vote_sole"] += float(row.total_vote_sole)
        agg["total_vote_shared"] += float(row.total_vote_shared)
        agg["total_vote_none"] += float(row.total_vote_none)

    return aggregated


def reconstruct_filer_state(
    filings: list[tuple[FilingHeader, list[HoldingRow]]],
    period_of_report: str,
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, Any]]:
    """Reconstruct point-in-time holdings state for a single origin filer in a given quarter.
    
    Sorts strictly by UTC instant ASC, accession_number ASC.
    Applies REPLACE for Original/RESTATEMENT, and UPSERT (overwrite key) for ADD_NEW_HOLDINGS.
    """
    if not filings:
        return {}, {
            "origin_filer_cik": None,
            "period_of_report": period_of_report,
            "filings_count": 0,
            "has_confidential_omit": False,
            "amendment_unresolved": False,
            "ownership_unresolved_rows": 0,
        }

    # Validate input consistency
    expected_filer = filings[0][0].origin_filer_cik
    for header, rows in filings:
        if header.origin_filer_cik != expected_filer:
            raise ValueError(
                f"Inconsistent origin_filer_cik in batch: expected {expected_filer}, got {header.origin_filer_cik}"
            )
        if header.period_of_report != period_of_report:
            raise ValueError(
                f"Inconsistent period_of_report in batch: expected {period_of_report}, got {header.period_of_report}"
            )
        for r in rows:
            if (
                r.accession_number != header.accession_number
                or r.origin_filer_cik != header.origin_filer_cik
                or r.period_of_report != header.period_of_report
            ):
                raise ValueError(
                    f"HoldingRow metadata mismatch with FilingHeader: row={r}, header={header}"
                )

    # Filter to PIT valid filings
    pit_filings: list[tuple[FilingHeader, list[HoldingRow], datetime]] = []
    for header, rows in filings:
        if is_pit_accepted(header.acceptance_datetime, period_of_report):
            utc_dt = parse_datetime_to_utc(header.acceptance_datetime)
            pit_filings.append((header, rows, utc_dt))

    # Sort strictly by (UTC instant ASC, accession_number ASC)
    pit_filings.sort(key=lambda item: (item[2], item[0].accession_number))

    state: dict[tuple[str, str, str], dict[str, Any]] = {}
    has_confidential_omit = False
    amendment_unresolved = False
    ownership_unresolved_rows = 0

    for header, rows, _ in pit_filings:
        if header.is_confidential_omit:
            has_confidential_omit = True

        for r in rows:
            if r.ownership_unresolved or r.economic_owner_cik is None:
                ownership_unresolved_rows += 1

        agg_holdings = aggregate_accession_holdings(rows)

        form_upper = (header.form_type or "").upper()
        amend_upper = (header.amendment_type or "").upper() if header.amendment_type else None

        if form_upper == "13F-HR" or amend_upper == "RESTATEMENT":
            # REPLACE entire state
            state = dict(agg_holdings)
        elif amend_upper == "ADD_NEW_HOLDINGS":
            # UPSERT: overwrite matching keys, do NOT accumulate shares
            for k, v in agg_holdings.items():
                state[k] = dict(v)
        else:
            # Unrecognized amendment or invalid combination
            amendment_unresolved = True

    metadata = {
        "origin_filer_cik": expected_filer,
        "period_of_report": period_of_report,
        "filings_count": len(pit_filings),
        "has_confidential_omit": has_confidential_omit,
        "amendment_unresolved": amendment_unresolved,
        "ownership_unresolved_rows": ownership_unresolved_rows,
    }

    return state, metadata
