"""Ownership resolution, SEC 13F filing deadline calendar, and per-origin-filer state machine."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import math
import re
from typing import Any
import zoneinfo

_EASTERN_TZ = zoneinfo.ZoneInfo("America/New_York")
_UTC_TZ = zoneinfo.ZoneInfo("UTC")
_CIK_PATTERN = re.compile(r"^\d{1,10}$")
_DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_strict_nonnegative_int(val: Any) -> bool:
    """Check if value is a non-negative finite integer, rejecting bool and fractional numbers."""
    if isinstance(val, bool):
        return False
    if isinstance(val, int):
        return val >= 0
    if isinstance(val, float):
        return math.isfinite(val) and val >= 0.0 and val.is_integer()
    return False


def is_strict_nonnegative_number(val: Any) -> bool:
    """Check if value is a non-negative finite real number, rejecting bool."""
    if isinstance(val, bool):
        return False
    if isinstance(val, (int, float)):
        return math.isfinite(val) and val >= 0.0
    return False


def is_strict_positive_number(val: Any) -> bool:
    """Check if value is a strictly positive finite real number, rejecting bool."""
    if isinstance(val, bool):
        return False
    if isinstance(val, (int, float)):
        return math.isfinite(val) and val > 0.0
    return False


def is_valid_cik(cik: Any) -> bool:
    """Check if value is a valid non-empty 1-10 digit CIK, rejecting bool and numeric zero."""
    if cik is None or isinstance(cik, bool):
        return False
    s = str(cik).strip()
    if not _CIK_PATTERN.match(s):
        return False
    try:
        return int(s) > 0
    except ValueError:
        return False


def normalize_cik(cik: Any) -> str:
    """Normalize CIK to 10-digit zero-padded string; raises ValueError if invalid."""
    if not is_valid_cik(cik):
        raise ValueError(f"Invalid CIK: {cik!r}. Must be a 1-10 digit positive numeric string.")
    return f"{int(cik):010d}"


def _get_sec_holidays(year: int) -> set[date]:
    """Calculate US Federal / SEC official holidays for a given year."""
    holidays: set[date] = set()

    # 1. New Year's Day (Jan 1)
    nyd = date(year, 1, 1)
    if nyd.weekday() == 6:
        holidays.add(date(year, 1, 2))
    elif nyd.weekday() == 5:
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
    q_end = date.fromisoformat(period_of_report.strip())
    target = q_end + timedelta(days=45)

    holidays = _get_sec_holidays(target.year) | _get_sec_holidays(target.year + 1)

    while target.weekday() >= 5 or target in holidays:
        target += timedelta(days=1)

    return target.isoformat()


def parse_datetime_to_utc(dt_str: str) -> datetime:
    """Parse acceptance datetime string into an aware UTC datetime object.

    Requires a genuine datetime with a time component (rejects date-only strings).
    Accepts naive SEC timestamps (assumed Eastern) and timezone-aware timestamps.
    """
    if not isinstance(dt_str, str) or not dt_str.strip():
        raise ValueError("acceptance_datetime cannot be blank or empty.")

    clean = dt_str.strip()
    if _DATE_ONLY_PATTERN.match(clean) or ("T" not in clean and " " not in clean):
        raise ValueError(
            f"acceptance_datetime must contain a time component (YYYY-MM-DDTHH:MM:SS), got date-only: {dt_str!r}"
        )

    try:
        if clean.endswith("Z"):
            dt = datetime.fromisoformat(clean[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(clean)
    except ValueError as err:
        raise ValueError(f"Invalid ISO datetime in acceptance_datetime: {dt_str!r}") from err

    if dt.tzinfo is None:
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
    accession_number: str,
    other_manager_map: dict[tuple[str, str], str] | None = None,
) -> tuple[str | None, bool]:
    """Resolve economic owner CIK from row's other_manager sequence keyed by (accession_number, sequence).

    Returns:
        (economic_owner_cik, ownership_unresolved)
    """
    norm_filer = normalize_cik(origin_filer_cik)

    if row_other_manager is None:
        return norm_filer, False

    seq_str = str(row_other_manager).strip()
    if not seq_str:
        return norm_filer, False

    acc_str = str(accession_number).strip()
    if not acc_str:
        raise ValueError("accession_number must be non-empty for ownership resolution.")

    if other_manager_map is not None:
        mapped_cik = other_manager_map.get((acc_str, seq_str))
        if mapped_cik is None and seq_str.isdigit():
            mapped_cik = other_manager_map.get((acc_str, str(int(seq_str))))

        if mapped_cik is not None and is_valid_cik(mapped_cik):
            return normalize_cik(mapped_cik), False

    return None, True


@dataclass(frozen=True)
class FilingHeader:
    """Header information for a single 13F submission."""
    accession_number: str
    origin_filer_cik: str
    period_of_report: str
    acceptance_datetime: str
    form_type: str = "13F-HR"
    amendment_type: str | None = None
    is_confidential_omit: bool = False

    def validate(self) -> None:
        """Validate header fields, datetime time component, and form/amendment combinations."""
        if not self.accession_number or not str(self.accession_number).strip():
            raise ValueError("FilingHeader accession_number cannot be empty.")
        normalize_cik(self.origin_filer_cik)
        try:
            date.fromisoformat(self.period_of_report.strip())
        except ValueError as err:
            raise ValueError(f"Invalid period_of_report in FilingHeader: {self.period_of_report}") from err

        parse_datetime_to_utc(self.acceptance_datetime)

        if type(self.is_confidential_omit) is not bool:
            raise TypeError("is_confidential_omit must be a strict boolean.")

        form = (self.form_type or "").strip().upper()
        amend = (self.amendment_type or "").strip().upper() if self.amendment_type else None

        if form == "13F-HR":
            if amend:
                raise ValueError(f"Original 13F-HR filing cannot have amendment_type: {self.amendment_type!r}")
        elif form == "13F-HR/A":
            pass
        elif form in ("13F-NT", "13F-NT/A"):
            if amend in ("RESTATEMENT", "ADD_NEW_HOLDINGS"):
                raise ValueError(f"13F-NT Notice filing cannot have holding amendment_type: {self.amendment_type!r}")
        else:
            raise ValueError(f"Unsupported form_type in FilingHeader: {self.form_type!r}")


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
    total_shares: int | float
    total_value_usd: int | float
    total_vote_sole: int | float = 0
    total_vote_shared: int | float = 0
    total_vote_none: int | float = 0

    def validate(self) -> None:
        """Validate holding row fields, semantic invariant, and integral counts."""
        if not self.accession_number or not str(self.accession_number).strip():
            raise ValueError("HoldingRow accession_number cannot be blank or empty.")
        if not self.asset_class or not str(self.asset_class).strip():
            raise ValueError("HoldingRow asset_class cannot be blank or empty.")
        if not self.period_of_report or not str(self.period_of_report).strip():
            raise ValueError("HoldingRow period_of_report cannot be blank or empty.")
        try:
            date.fromisoformat(self.period_of_report.strip())
        except (TypeError, ValueError) as err:
            raise ValueError(f"Invalid ISO period_of_report in HoldingRow: {self.period_of_report!r}") from err
        if not self.cusip or not str(self.cusip).strip():
            raise ValueError("HoldingRow cusip cannot be blank or empty.")
        normalize_cik(self.origin_filer_cik)

        if type(self.ownership_unresolved) is not bool:
            raise TypeError("ownership_unresolved must be a strict boolean.")

        # Invariant: ownership_unresolved == True iff economic_owner_cik is None
        if self.ownership_unresolved:
            if self.economic_owner_cik is not None:
                raise ValueError(
                    "HoldingRow semantic invariant violated: ownership_unresolved=True requires economic_owner_cik=None"
                )
        else:
            if self.economic_owner_cik is None:
                raise ValueError(
                    "HoldingRow semantic invariant violated: ownership_unresolved=False requires economic_owner_cik to be provided"
                )
            normalize_cik(self.economic_owner_cik)

        # Shares and votes must be non-negative finite INTEGERS (rejecting bool and fractions)
        for name, val in [
            ("total_shares", self.total_shares),
            ("total_vote_sole", self.total_vote_sole),
            ("total_vote_shared", self.total_vote_shared),
            ("total_vote_none", self.total_vote_none),
        ]:
            if not is_strict_nonnegative_int(val):
                raise ValueError(f"HoldingRow {name} must be a non-negative integer, got: {val!r}")

        # Total value USD must be non-negative finite real number (rejecting bool)
        if not is_strict_nonnegative_number(self.total_value_usd):
            raise ValueError(f"HoldingRow total_value_usd must be non-negative finite number, got: {self.total_value_usd!r}")


def aggregate_accession_holdings(
    holdings: list[HoldingRow],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Aggregate holding rows within a single accession by (cusip, asset_class, economic_owner_cik).

    Rejects mixed accession_number, origin_filer_cik, or period_of_report.
    Excludes rows where ownership_unresolved == True.
    """
    if not holdings:
        return {}

    first = holdings[0]
    first.validate()
    exp_acc = first.accession_number
    exp_filer = normalize_cik(first.origin_filer_cik)
    exp_period = first.period_of_report.strip()

    aggregated: dict[tuple[str, str, str], dict[str, Any]] = {}

    for row in holdings:
        row.validate()
        if (
            row.accession_number != exp_acc
            or normalize_cik(row.origin_filer_cik) != exp_filer
            or row.period_of_report.strip() != exp_period
        ):
            raise ValueError(
                f"aggregate_accession_holdings: mixed accession/filer/period in batch: "
                f"expected ({exp_acc}, {exp_filer}, {exp_period}), "
                f"got ({row.accession_number}, {row.origin_filer_cik}, {row.period_of_report})"
            )

        if row.ownership_unresolved or row.economic_owner_cik is None:
            continue

        econ_cik = normalize_cik(row.economic_owner_cik)
        cusip = row.cusip.strip().upper()
        asset_class = row.asset_class.strip().upper()

        key = (cusip, asset_class, econ_cik)
        if key not in aggregated:
            aggregated[key] = {
                "cusip": cusip,
                "asset_class": asset_class,
                "economic_owner_cik": econ_cik,
                "total_shares": 0,
                "total_value_usd": 0.0,
                "total_vote_sole": 0,
                "total_vote_shared": 0,
                "total_vote_none": 0,
            }

        agg = aggregated[key]
        agg["total_shares"] += int(row.total_shares)
        agg["total_value_usd"] += float(row.total_value_usd)
        agg["total_vote_sole"] += int(row.total_vote_sole)
        agg["total_vote_shared"] += int(row.total_vote_shared)
        agg["total_vote_none"] += int(row.total_vote_none)

    return aggregated


def reconstruct_filer_state(
    filings: list[tuple[FilingHeader, list[HoldingRow]]],
    period_of_report: str,
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, Any]]:
    """Reconstruct point-in-time holdings state for a single origin filer in a given quarter.

    Rejects invalid form/amendment combinations.
    If an unknown amendment is encountered, marks amendment_unresolved=True and invalidates (wipes) the state.
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

    expected_filer = normalize_cik(filings[0][0].origin_filer_cik)
    period_clean = period_of_report.strip()

    for header, rows in filings:
        header.validate()
        if normalize_cik(header.origin_filer_cik) != expected_filer:
            raise ValueError(
                f"Inconsistent origin_filer_cik in batch: expected {expected_filer}, got {header.origin_filer_cik}"
            )
        if header.period_of_report.strip() != period_clean:
            raise ValueError(
                f"Inconsistent period_of_report in batch: expected {period_clean}, got {header.period_of_report}"
            )
        form_upper = (header.form_type or "").strip().upper()
        if form_upper in ("13F-NT", "13F-NT/A") and len(rows) > 0:
            raise ValueError("13F-NT notice filing cannot contain holding rows.")

        for r in rows:
            r.validate()
            if (
                r.accession_number != header.accession_number
                or normalize_cik(r.origin_filer_cik) != expected_filer
                or r.period_of_report.strip() != period_clean
            ):
                raise ValueError(
                    f"HoldingRow metadata mismatch with FilingHeader: row={r}, header={header}"
                )

    pit_filings: list[tuple[FilingHeader, list[HoldingRow], datetime]] = []
    for header, rows in filings:
        if is_pit_accepted(header.acceptance_datetime, period_clean):
            utc_dt = parse_datetime_to_utc(header.acceptance_datetime)
            pit_filings.append((header, rows, utc_dt))

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

        form_upper = (header.form_type or "").strip().upper()
        amend_upper = (header.amendment_type or "").strip().upper() if header.amendment_type else None

        if form_upper == "13F-HR":
            state = dict(agg_holdings)
        elif form_upper == "13F-HR/A":
            if amend_upper == "RESTATEMENT":
                state = dict(agg_holdings)
            elif amend_upper == "ADD_NEW_HOLDINGS":
                for k, v in agg_holdings.items():
                    state[k] = dict(v)
            else:
                amendment_unresolved = True
                state = {}
        else:
            amendment_unresolved = True
            state = {}

    if amendment_unresolved:
        state = {}

    metadata = {
        "origin_filer_cik": expected_filer,
        "period_of_report": period_clean,
        "filings_count": len(pit_filings),
        "has_confidential_omit": has_confidential_omit,
        "amendment_unresolved": amendment_unresolved,
        "ownership_unresolved_rows": ownership_unresolved_rows,
    }

    return state, metadata
