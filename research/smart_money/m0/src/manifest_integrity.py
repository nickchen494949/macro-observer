"""Manifest integrity, canonical JSON serialization, SHA-256 computation, and cross-stage binding."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


def canonical_json_dumps(obj: Any) -> str:
    """Serialize object to canonical deterministic JSON.
    
    Enforces sort_keys=True, indent=2, UTF-8 unicode output, and allow_nan=False.
    Raises ValueError if NaN or Inf values are present.
    """
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
        # If not a git repo or git fails, return False for safety
        return False


def verify_clean_tree_gate(repo_path: str | Path | None = None) -> None:
    """Enforce working tree clean invariant before production runs.
    
    Raises RuntimeError if git working tree contains any uncommitted changes.
    """
    if not check_git_clean_tree(repo_path):
        raise RuntimeError("Clean tree gate violated: git_tree_dirty == True. Production aborted.")


def verify_cache_integrity(cache_data: bytes | str, expected_sha256: str) -> bool:
    """Verify raw cache payload against expected SHA-256 hash.
    
    Raises ValueError if payload hash does not match expected_sha256.
    """
    if isinstance(cache_data, str):
        actual_hash = compute_sha256_str(cache_data)
    else:
        actual_hash = compute_sha256_bytes(cache_data)
    
    if actual_hash.lower() != expected_sha256.lower():
        raise ValueError(
            f"Cache integrity verification failed: expected {expected_sha256}, got {actual_hash}"
        )
    return True


def verify_manifest_binding(signal_manifest: dict[str, Any], price_manifest: dict[str, Any]) -> None:
    """Verify cryptographic and identifier binding between Signal Manifest and Price Manifest.
    
    Enforces matching run_id, contract_sha256, source_git_sha, m0_code_git_sha,
    and matching signal_manifest_sha256.
    """
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

    # Validate signal_manifest_sha256
    expected_signal_hash = price_manifest.get("signal_manifest_sha256")
    if not expected_signal_hash:
        raise ValueError("Price manifest missing 'signal_manifest_sha256' binding.")
    
    computed_signal_hash = compute_sha256_json(signal_manifest)
    if expected_signal_hash.lower() != computed_signal_hash.lower():
        raise ValueError(
            f"Signal manifest SHA-256 binding mismatch: expected {expected_signal_hash}, computed {computed_signal_hash}"
        )
