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


def validate_canonical_json_value(val: Any) -> None:
    """Recursively validate that value conforms strictly to standard canonical JSON data types.
    
    Rejects:
    - Non-string dictionary keys (e.g. ints, tuples)
    - Tuples (must be standard lists)
    - Sets
    - NaN, Inf, -Inf
    - Custom / non-primitive objects
    """
    if isinstance(val, (str, int, bool, type(None))):
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
    return hashlib.sha256(data).hexdigest()


def compute_sha256_str(text: str) -> str:
    """Compute SHA-256 hexadecimal hash for a string encoded in UTF-8."""
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
    else:
        actual_hash = compute_sha256_bytes(cache_data)

    if actual_hash.lower() != expected_sha256.strip().lower():
        raise ValueError(
            f"Cache integrity verification failed: expected {expected_sha256}, got {actual_hash}"
        )
    return True


def parse_and_validate_manifest(
    manifest_input: bytes | str | dict[str, Any]
) -> tuple[dict[str, Any], bytes, str]:
    """Parse manifest, enforce canonical types, and return (dict, raw_canonical_bytes, sha256)."""
    if isinstance(manifest_input, bytes):
        raw_text = manifest_input.decode("utf-8")
        parsed = json.loads(raw_text)
    elif isinstance(manifest_input, str):
        parsed = json.loads(manifest_input)
    elif isinstance(manifest_input, dict):
        parsed = manifest_input
    else:
        raise TypeError(f"Invalid manifest input type: {type(manifest_input).__name__}")

    validate_canonical_json_value(parsed)
    canonical_str = canonical_json_dumps(parsed)
    raw_bytes = canonical_str.encode("utf-8")
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    return parsed, raw_bytes, sha256_hex


def verify_manifest_binding(
    signal_manifest_input: bytes | str | dict[str, Any],
    price_manifest_input: bytes | str | dict[str, Any],
) -> None:
    """Verify cryptographic and identifier binding between Signal Manifest and Price Manifest.
    
    Hashes and parses the exact canonical raw bytes of the manifest objects.
    Enforces matching run_id, contract_sha256, source_git_sha, m0_code_git_sha,
    and matching signal_manifest_sha256.
    """
    signal_manifest, _, signal_hash = parse_and_validate_manifest(signal_manifest_input)
    price_manifest, _, _ = parse_and_validate_manifest(price_manifest_input)

    required_keys = ["run_id", "contract_sha256", "source_git_sha", "m0_code_git_sha"]
    for key in required_keys:
        sig_val = signal_manifest.get(key)
        pri_val = price_manifest.get(key)
        if sig_val is None:
            raise ValueError(f"Signal manifest missing required binding field: '{key}'")
        if pri_val is None:
            raise ValueError(f"Price manifest missing required binding field: '{key}'")
        if sig_val != pri_val:
            raise ValueError(
                f"Manifest binding mismatch on '{key}': signal has '{sig_val}', price has '{pri_val}'"
            )

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
