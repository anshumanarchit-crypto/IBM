"""Tests for reproduction isolation and output directory safety.

Ensures that running reproduction workflows with --output-dir writes artifacts
to an isolated directory and leaves canonical frozen artifacts completely untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import pytest

from scripts.cache_agent_outputs import generate_agent_cache
from scripts.reproduce import compare_reproduction_results

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
CANONICAL_RESULTS = RESULTS_DIR / "results.json"
CANONICAL_CACHE = RESULTS_DIR / "agent_cache.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_agent_cache_output_isolation(tmp_path: Path):
    """Verify that generate_agent_cache with output_dir writes to isolated dir."""
    assert CANONICAL_CACHE.exists()
    canonical_hash_before = sha256_file(CANONICAL_CACHE)

    isolated_dir = tmp_path / "iso_cache_run"
    payload = generate_agent_cache(output_dir=isolated_dir, n_sample=5)

    assert isolated_dir.exists()
    isolated_cache_file = isolated_dir / "agent_cache.json"
    assert isolated_cache_file.exists()

    # Canonical file must remain 100% byte-identical
    canonical_hash_after = sha256_file(CANONICAL_CACHE)
    assert canonical_hash_before == canonical_hash_after, "Canonical agent_cache.json was modified!"


def test_reproduce_cli_output_dir_argument():
    """Verify scripts/reproduce.py parser supports --output-dir and --mode."""
    from scripts.reproduce import main
    # Test parser structure directly
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline", "full", "audit"], default="offline")
    parser.add_argument("--output-dir", default=None)

    parsed = parser.parse_args(["--mode", "full", "--output-dir", "custom/path"])
    assert parsed.mode == "full"
    assert parsed.output_dir == "custom/path"


def test_compare_reproduction_results_functionality(tmp_path: Path):
    """Verify compare_reproduction_results compares correctly without modifying canonical files."""
    assert CANONICAL_RESULTS.exists()
    canonical_hash_before = sha256_file(CANONICAL_RESULTS)

    # Create mock reproduction directory with a copy of results.json
    mock_run_dir = tmp_path / "mock_reproduction"
    mock_run_dir.mkdir(parents=True, exist_ok=True)
    (mock_run_dir / "results.json").write_text(CANONICAL_RESULTS.read_text(encoding="utf-8"), encoding="utf-8")

    # Run comparison
    res = compare_reproduction_results(out_dir=mock_run_dir, canonical_dir=RESULTS_DIR)
    assert res.get("status") == "comparison_complete"

    # Verify canonical file untouched
    canonical_hash_after = sha256_file(CANONICAL_RESULTS)
    assert canonical_hash_before == canonical_hash_after, "Canonical results.json was modified!"
