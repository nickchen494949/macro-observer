"""Manifest integrity, strict canonical JSON serialization, SHA-256 computation, and cross-stage binding."""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
from typing import Any

_HEX_64_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX_40_OR_64_PATTERN = re.compile(r"^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_SAFE_RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_canonical_json_value(val: Any) -> None:
    """Recursively validate that value conforms strictly to standard canonical JSON data types.

    Rejects:
    - Non-string dictionary keys (e.g. ints, tuples)
    - Tuples (must be standard lists)
    - Sets
    - NaN, Inf, -Inf
    - Custom / non-primitive objects
    """
    if isinstance(val, bool) or val is None or isinstance(val, str):
        return
    if isinstance(val, int):
        return
    if isinstance(val, float):
        if not math.isfinite(val):
            raise ValueError(f"Non-finite float value in canonical JSON: {val}")
        return
    if isinstance(val, list):
        for item in val:
            validate_canonical_json_value(item)
        return
    if isinstance(val, dict):
        for k, v in val.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"Dictionary keys in canonical JSON must be strings, got {type(k).__name__}: {k!r}"
                )
            validate_canonical_json_value(v)
        return
    raise TypeError(f"Disallowed type in canonical JSON: {type(val).__name__} ({val!r})")


def canonical_json_dumps(obj: Any) -> str:
    """Serialize object to canonical deterministic JSON after strict type validation.

    Enforces sort_keys=True, indent=2, UTF-8 unicode output, and allow_nan=False.
    Raises TypeError if non-string keys, tuples, sets, or non-standard types are found.
    Raises ValueError if NaN or Inf values are present.
    """
    validate_canonical_json_value(obj)
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)


def compute_sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hexadecimal hash for raw bytes."""
    if not isinstance(data, bytes):
        raise TypeError("compute_sha256_bytes requires bytes input.")
    return hashlib.sha256(data).hexdigest()


def compute_sha256_str(text: str) -> str:
    """Compute SHA-256 hexadecimal hash for a string encoded in UTF-8."""
    if not isinstance(text, str):
        raise TypeError("compute_sha256_str requires str input.")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_sha256_file(file_path: str | Path) -> str:
    """Compute SHA-256 hexadecimal hash of a file by streaming in chunks."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for SHA-256 computation: {file_path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_sha256_json(obj: Any) -> str:
    """Compute SHA-256 hexadecimal hash of canonical deterministic JSON."""
    return compute_sha256_str(canonical_json_dumps(obj))


def check_git_clean_tree(repo_path: str | Path | None = None) -> bool:
    """Check whether the git working tree is completely clean.

    Returns True if clean (no uncommitted or untracked changes), False otherwise.
    """
    cwd = str(repo_path) if repo_path is not None else os.getcwd()
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return len(res.stdout.strip()) == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def verify_clean_tree_gate(repo_path: str | Path | None = None) -> None:
    """Enforce working tree clean invariant before production runs.

    Raises RuntimeError if git working tree contains any uncommitted changes.
    """
    if not check_git_clean_tree(repo_path):
        raise RuntimeError("Clean tree gate violated: git_tree_dirty == True. Production aborted.")


def verify_cache_integrity(cache_data: bytes | str, expected_sha256: str) -> bool:
    """Verify raw cache payload against expected SHA-256 hash.

    Validates that expected_sha256 is exactly 64 hexadecimal characters.
    Raises ValueError if expected_sha256 is invalid or payload hash does not match.
    """
    if not isinstance(expected_sha256, str) or not _HEX_64_PATTERN.match(expected_sha256.strip()):
        raise ValueError(
            f"expected_sha256 must be exactly 64 hexadecimal characters, got {expected_sha256!r}"
        )

    if isinstance(cache_data, str):
        actual_hash = compute_sha256_str(cache_data)
    elif isinstance(cache_data, bytes):
        actual_hash = compute_sha256_bytes(cache_data)
    else:
        raise TypeError(f"cache_data must be bytes or str, got {type(cache_data).__name__}")

    if actual_hash.lower() != expected_sha256.strip().lower():
        raise ValueError(
            f"Cache integrity verification failed: expected {expected_sha256}, got {actual_hash}"
        )
    return True


def parse_and_validate_manifest(
    manifest_bytes: bytes,
) -> tuple[dict[str, Any], bytes, str]:
    """Parse raw manifest bytes, enforce exact canonical JSON byte representation, and compute SHA-256.

    Requires raw bytes input. Rejects non-canonical JSON byte streams (e.g. unformatted or differently sorted).
    """
    if not isinstance(manifest_bytes, bytes):
        raise TypeError(f"Manifest input must be raw bytes, got {type(manifest_bytes).__name__}")

    try:
        raw_text = manifest_bytes.decode("utf-8")
        parsed = json.loads(raw_text)
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ValueError(f"Failed to parse manifest JSON bytes: {err}") from err

    validate_canonical_json_value(parsed)

    # Require exact canonical byte match without reformatting
    expected_bytes = canonical_json_dumps(parsed).encode("utf-8")
    if manifest_bytes != expected_bytes:
        raise ValueError(
            "Supplied manifest bytes do not match exact canonical JSON serialization format."
        )

    sha256_hex = hashlib.sha256(manifest_bytes).hexdigest()
    return parsed, manifest_bytes, sha256_hex


def verify_manifest_binding(
    signal_manifest_bytes: bytes,
    price_manifest_bytes: bytes,
) -> None:
    """Verify cryptographic and identifier binding between Signal Manifest and Price Manifest.

    Requires exact canonical raw bytes for both manifests.
    Validates manifest_type, non-blank provenance IDs, git_tree_dirty is exactly False, and matching binding hashes.
    """
    if not isinstance(signal_manifest_bytes, bytes) or not isinstance(price_manifest_bytes, bytes):
        raise TypeError("verify_manifest_binding requires raw bytes for both signal and price manifests.")

    signal_manifest, _, signal_hash = parse_and_validate_manifest(signal_manifest_bytes)
    price_manifest, _, _ = parse_and_validate_manifest(price_manifest_bytes)

    # Validate manifest_type
    sig_type = signal_manifest.get("manifest_type")
    pri_type = price_manifest.get("manifest_type")
    if sig_type != "SIGNAL_MANIFEST":
        raise ValueError(f"Signal manifest has invalid manifest_type: {sig_type!r}")
    if pri_type != "PRICE_MANIFEST":
        raise ValueError(f"Price manifest has invalid manifest_type: {pri_type!r}")

    # Validate git_tree_dirty is strictly False
    sig_dirty = signal_manifest.get("git_tree_dirty")
    pri_dirty = price_manifest.get("git_tree_dirty")
    if sig_dirty is not False or type(sig_dirty) is not bool:
        raise ValueError(f"Signal manifest git_tree_dirty must be exactly False, got {sig_dirty!r}")
    if pri_dirty is not False or type(pri_dirty) is not bool:
        raise ValueError(f"Price manifest git_tree_dirty must be exactly False, got {pri_dirty!r}")

    # Validate run_id syntax
    run_id_sig = signal_manifest.get("run_id")
    run_id_pri = price_manifest.get("run_id")
    if not isinstance(run_id_sig, str) or not _SAFE_RUN_ID_PATTERN.match(run_id_sig.strip()):
        raise ValueError(f"Signal manifest has invalid/blank run_id: {run_id_sig!r}")
    if not isinstance(run_id_pri, str) or not _SAFE_RUN_ID_PATTERN.match(run_id_pri.strip()):
        raise ValueError(f"Price manifest has invalid/blank run_id: {run_id_pri!r}")
    if run_id_sig.strip() != run_id_pri.strip():
        raise ValueError(f"run_id mismatch: signal has {run_id_sig!r}, price has {run_id_pri!r}")

    # Validate contract_sha256 (strictly 64 hex)
    contract_sig = signal_manifest.get("contract_sha256")
    contract_pri = price_manifest.get("contract_sha256")
    if not isinstance(contract_sig, str) or not _HEX_64_PATTERN.match(contract_sig.strip()):
        raise ValueError(f"Signal manifest has invalid/blank contract_sha256: {contract_sig!r}")
    if not isinstance(contract_pri, str) or not _HEX_64_PATTERN.match(contract_pri.strip()):
        raise ValueError(f"Price manifest has invalid/blank contract_sha256: {contract_pri!r}")
    if contract_sig.strip().lower() != contract_pri.strip().lower():
        raise ValueError(f"contract_sha256 mismatch: signal has {contract_sig!r}, price has {contract_pri!r}")

    # Validate source_git_sha and m0_code_git_sha (40 or 64 hex)
    for git_key in ["source_git_sha", "m0_code_git_sha"]:
        sig_val = signal_manifest.get(git_key)
        pri_val = price_manifest.get(git_key)
        if not isinstance(sig_val, str) or not _HEX_40_OR_64_PATTERN.match(sig_val.strip()):
            raise ValueError(f"Signal manifest has invalid/blank {git_key}: {sig_val!r}")
        if not isinstance(pri_val, str) or not _HEX_40_OR_64_PATTERN.match(pri_val.strip()):
            raise ValueError(f"Price manifest has invalid/blank {git_key}: {pri_val!r}")
        if sig_val.strip().lower() != pri_val.strip().lower():
            raise ValueError(f"{git_key} mismatch: signal has {sig_val!r}, price has {pri_val!r}")

    expected_signal_hash = price_manifest.get("signal_manifest_sha256")
    if not expected_signal_hash:
        raise ValueError("Price manifest missing 'signal_manifest_sha256' binding.")

    if not isinstance(expected_signal_hash, str) or not _HEX_64_PATTERN.match(expected_signal_hash.strip()):
        raise ValueError(
            f"Price manifest signal_manifest_sha256 must be 64 hex chars, got {expected_signal_hash!r}"
        )

    if expected_signal_hash.strip().lower() != signal_hash.lower():
        raise ValueError(
            f"Signal manifest SHA-256 binding mismatch: expected {expected_signal_hash}, computed {signal_hash}"
        )
