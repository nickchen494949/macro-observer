"""OpenFIGI deterministic waterfall resolution, CUSIP validation, and Jaro-Winkler similarity."""

from dataclasses import dataclass
import re
from typing import Any

_VALID_SECURITY_TYPES = {
    "Common Stock",
    "ADR",
    "REIT",
    "Tracking Stock",
    "Units",
    "Closed-End Fund",
}

_VALID_EXCH_CODES = {"US", "UN", "UQ", "UR", "UA"}


def jaro_similarity(s1: str, s2: str) -> float:
    """Compute basic Jaro string similarity."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    for i, c1 in enumerate(s1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if not s2_matches[j] and c1 == s2[j]:
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    t = 0
    k = 0
    for i, is_match in enumerate(s1_matches):
        if is_match:
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                t += 1
            k += 1

    transpositions = t // 2
    return (matches / len1 + matches / len2 + (matches - transpositions) / matches) / 3.0


def jaro_winkler_similarity(s1: str, s2: str, p: float = 0.1, max_l: int = 4) -> float:
    """Compute Jaro-Winkler string similarity."""
    j = jaro_similarity(s1, s2)
    l = 0
    for c1, c2 in zip(s1, s2):
        if c1 == c2:
            l += 1
            if l == max_l:
                break
        else:
            break
    return j + (l * p * (1.0 - j))


def is_valid_cusip(cusip: str) -> bool:
    """Validate 9-character CUSIP format and checksum algorithm."""
    if not isinstance(cusip, str) or len(cusip) != 9:
        return False
    
    cusip_upper = cusip.upper()
    if not re.match(r"^[0-9A-Z]{9}$", cusip_upper):
        return False

    total = 0
    for i, char in enumerate(cusip_upper[:8]):
        if char.isdigit():
            val = int(char)
        elif char.isalpha():
            val = ord(char) - ord("A") + 10
        elif char == "*":
            val = 36
        elif char == "@":
            val = 37
        elif char == "#":
            val = 38
        else:
            return False

        if i % 2 == 1:
            val *= 2
        
        total += (val // 10) + (val % 10)

    check_digit = (10 - (total % 10)) % 10
    expected_char = cusip_upper[8]
    if not expected_char.isdigit():
        return False

    return int(expected_char) == check_digit


@dataclass(frozen=True)
class OpenFIGICandidate:
    """OpenFIGI API candidate response entity."""
    figi: str
    name: str
    ticker: str
    exchCode: str
    marketSector: str
    securityType2: str
    shareClassFIGI: str | None = None
    compositeFIGI: str | None = None


def resolve_openfigi_waterfall(
    cusip: str,
    sec_issuer_name: str,
    candidates: list[OpenFIGICandidate],
) -> tuple[str | None, dict[str, Any]]:
    """Resolve primary stock identifier via deterministic OpenFIGI waterfall.
    
    Returns:
        (primary_stock_id, metadata_dict)
    """
    if not is_valid_cusip(cusip):
        return None, {"status": "INVALID_CUSIP", "reason": "CUSIP failed format/checksum check"}

    clean_issuer = (sec_issuer_name or "").strip()
    if not clean_issuer:
        return None, {"status": "EMPTY_ISSUER_NAME", "reason": "SEC issuer name is empty"}

    surviving: list[tuple[OpenFIGICandidate, str, bool, float]] = []

    for cand in candidates:
        # Step 1: marketSector == 'Equity'
        if (cand.marketSector or "").strip().title() != "Equity":
            continue

        # Step 2: securityType2 in allowed set (strict ETF exclusion)
        st2 = (cand.securityType2 or "").strip()
        if st2 not in _VALID_SECURITY_TYPES:
            continue

        # Step 3: exchCode in allowed set
        if (cand.exchCode or "").strip().upper() not in _VALID_EXCH_CODES:
            continue

        # Step 4: Issuer name Jaro-Winkler similarity >= 0.75
        cand_name = (cand.name or "").strip().upper()
        sim = jaro_winkler_similarity(cand_name, clean_issuer.upper())
        if sim < 0.75:
            continue

        # Step 5: Primary key resolution (shareClassFIGI > compositeFIGI, venue FIGI forbidden)
        sc_figi = (cand.shareClassFIGI or "").strip()
        comp_figi = (cand.compositeFIGI or "").strip()

        if sc_figi:
            primary_id = sc_figi
            is_composite_fallback = False
        elif comp_figi:
            primary_id = comp_figi
            is_composite_fallback = True
        else:
            # No shareClassFIGI or compositeFIGI available
            continue

        surviving.append((cand, primary_id, is_composite_fallback, sim))

    if not surviving:
        return None, {"status": "NO_MATCH", "reason": "No candidate passed waterfall filters"}

    # Step 6: Check for ambiguity among surviving candidates
    unique_ids = {p_id for _, p_id, _, _ in surviving}
    if len(unique_ids) > 1:
        return None, {
            "status": "MAPPING_AMBIGUOUS",
            "reason": "Multiple distinct primary IDs matched top candidates",
            "unique_ids": sorted(list(unique_ids)),
        }

    # Exactly 1 unique primary ID resolved
    best_cand, best_id, best_fallback, best_sim = surviving[0]
    return best_id, {
        "status": "RESOLVED",
        "primary_stock_id": best_id,
        "composite_fallback": best_fallback,
        "name_similarity": best_sim,
        "ticker": best_cand.ticker,
        "securityType2": best_cand.securityType2,
    }
