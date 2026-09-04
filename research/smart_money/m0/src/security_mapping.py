"""OpenFIGI deterministic waterfall resolution, CUSIP validation, and Jaro-Winkler similarity."""

from dataclasses import dataclass
import math
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
    """Compute standard Jaro string similarity."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    max_dist = max(len1, len2) // 2 - 1
    if max_dist < 0:
        max_dist = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(i + max_dist + 1, len2)
        for j in range(start, end):
            if s2_matches[j]:
                continue
            if s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    s1_matched_chars = [s1[i] for i in range(len1) if s1_matches[i]]
    s2_matched_chars = [s2[j] for j in range(len2) if s2_matches[j]]

    transpositions = sum(c1 != c2 for c1, c2 in zip(s1_matched_chars, s2_matched_chars)) // 2

    return (matches / len1 + matches / len2 + (matches - transpositions) / matches) / 3.0


def jaro_winkler_similarity(s1: str, s2: str, p: float = 0.1, max_l: int = 4) -> float:
    """Compute Jaro-Winkler string similarity."""
    j = jaro_similarity(s1, s2)
    l = 0
    for c1, c2 in zip(s1[:max_l], s2[:max_l]):
        if c1 == c2:
            l += 1
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

    Selects only highest-name-score candidates before ambiguity check.
    Two distinct IDs at different scores are not ambiguity (higher score wins).
    """
    if not is_valid_cusip(cusip):
        return None, {"status": "INVALID_CUSIP", "reason": "CUSIP failed format/checksum check"}

    clean_issuer = (sec_issuer_name or "").strip()
    if not clean_issuer or not any(c.isalnum() for c in clean_issuer):
        return None, {
            "status": "EMPTY_OR_NONALPHANUMERIC_ISSUER_NAME",
            "reason": "SEC issuer name is empty or contains no alphanumeric characters",
        }

    surviving: list[tuple[OpenFIGICandidate, str, bool, float]] = []

    for cand in candidates:
        # Step 0: Candidate name must contain at least one alphanumeric character
        cand_name = (cand.name or "").strip().upper()
        if not any(c.isalnum() for c in cand_name):
            continue

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
            continue

        surviving.append((cand, primary_id, is_composite_fallback, sim))

    if not surviving:
        return None, {"status": "NO_MATCH", "reason": "No candidate passed waterfall filters"}

    # Find highest score among surviving candidates
    max_sim = max(item[3] for item in surviving)
    # Retain only candidates matching highest score (within float precision)
    top_candidates = [
        item for item in surviving
        if math.isclose(item[3], max_sim, rel_tol=1e-9, abs_tol=1e-9)
    ]

    # Step 6: Check for ambiguity among TOP candidates ONLY
    unique_ids = {p_id for _, p_id, _, _ in top_candidates}
    if len(unique_ids) > 1:
        return None, {
            "status": "MAPPING_AMBIGUOUS",
            "reason": "Multiple distinct primary IDs matched with equal maximum name score",
            "unique_ids": sorted(list(unique_ids)),
            "max_score": max_sim,
        }

    # Exactly 1 unique primary ID resolved at top score
    best_cand, best_id, best_fallback, best_sim = top_candidates[0]
    return best_id, {
        "status": "RESOLVED",
        "primary_stock_id": best_id,
        "composite_fallback": best_fallback,
        "name_similarity": best_sim,
        "ticker": best_cand.ticker,
        "securityType2": best_cand.securityType2,
    }
