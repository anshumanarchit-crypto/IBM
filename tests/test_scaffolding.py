"""Test suite for Step 0 repository scaffolding and architectural invariants."""

from pathlib import Path
import yaml


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_required_directories_exist() -> None:
    root = get_repo_root()
    expected_dirs = [
        "agents",
        "governance",
        "schemas",
        "models",
        "models/signals",
        "data",
        "eval",
        "policy",
        "app",
        "infra",
        "figs",
        "results",
        "docs",
        "scripts",
        "tests",
    ]
    for d in expected_dirs:
        dir_path = root / d
        assert dir_path.is_dir(), f"Expected directory missing: {d}"


def test_required_init_files_exist() -> None:
    root = get_repo_root()
    expected_inits = [
        "agents/__init__.py",
        "schemas/__init__.py",
        "models/__init__.py",
        "models/signals/__init__.py",
    ]
    for init_file in expected_inits:
        file_path = root / init_file
        assert file_path.is_file(), f"Expected __init__.py missing: {init_file}"


def test_required_project_files_exist() -> None:
    root = get_repo_root()
    expected_files = [
        "README.md",
        ".gitignore",
        "requirements.txt",
        "requirements-ml.txt",
        "pyproject.toml",
        "Makefile",
        "config.yaml",
        "docs/architecture.md",
    ]
    for f in expected_files:
        file_path = root / f
        assert file_path.is_file(), f"Expected project file missing: {f}"


def test_config_architectural_invariants() -> None:
    root = get_repo_root()
    config_path = root / "config.yaml"
    assert config_path.is_file(), "config.yaml not found"

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 1. Project mode: decision-support simulation, not a live payment-blocking engine
    assert cfg["project"]["name"] == "SignalGate"
    assert cfg["project"]["mode"] == "decision_support_simulation"

    # 2. Strict reproducibility: 5 fixed seeds and bootstrap resampling
    assert cfg["reproducibility"]["seeds"] == [11, 22, 33, 44, 55]
    assert cfg["reproducibility"]["bootstrap_resamples"] == 1000

    # 3. Ground truth target isolation and chronological partitioning
    assert cfg["data"]["target_column"] == "isFraud"
    split = cfg["data"]["chronological_split"]
    assert split["train"] == [0, 60]
    assert split["calibration"] == [60, 70]
    assert split["validation"] == [70, 80]
    assert split["test"] == [80, 100]

    # 4. Agent boundaries & guardrails
    assert cfg["agent_acceptance"]["AG1_seeded_false_claim_block_rate"] == 1.0
    assert cfg["agent_acceptance"]["AG3_chain_verifies_and_tamper_detected"] is True
    assert cfg["agent_acceptance"]["AG4_routing_byte_identical_if_agents_disabled"] is True
    assert cfg["agent_acceptance"]["AG5_test_label_access_fails_closed"] is True

    # 5. Latency & performance bounds (IBM Z SLA: p95 <= 50ms)
    assert cfg["acceptance"]["AC5_p95_ms"] == 50
