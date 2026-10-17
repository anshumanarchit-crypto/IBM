"""Tests for advisory Drift Sentinel agent (Gate G4)."""

import pytest

from agents.drift_sentinel import ALLOWLISTED_CONFIG_KEYS, DriftSentinel
from schemas.contracts import Proposal

SAMPLE_BASE_HASH = "a" * 64


def test_drift_sentinel_offline_mode_no_drift():
    """When monitoring summary reports no drift, sentinel should return None."""
    sentinel = DriftSentinel()
    summary = {
        "batch_id": "batch_stable_100",
        "overall_drift_detected": False,
        "significant_shift_features": [],
        "sample_size": 1000,
    }

    proposal = sentinel.evaluate_and_propose(summary, base_cfg_hash=SAMPLE_BASE_HASH)
    assert proposal is None


def test_drift_sentinel_offline_mode_with_drift():
    """When monitoring summary reports significant drift, sentinel proposes allowlisted changes."""
    sentinel = DriftSentinel()
    summary = {
        "batch_id": "batch_shifted_100",
        "overall_drift_detected": True,
        "significant_shift_features": ["p", "feat_A"],
        "sample_size": 1000,
    }

    proposal = sentinel.evaluate_and_propose(summary, base_cfg_hash=SAMPLE_BASE_HASH)

    assert isinstance(proposal, Proposal)
    assert proposal.base_cfg_hash == SAMPLE_BASE_HASH
    assert len(proposal.changes) > 0

    # Strict invariant: Only allowlisted keys
    for key in proposal.changes.keys():
        assert key in ALLOWLISTED_CONFIG_KEYS, f"Forbidden key proposed: {key}"

    assert "batch_shifted_100" in proposal.rationale
    assert proposal.created_at.tzinfo is not None


def test_drift_sentinel_rejects_invalid_inputs():
    """Fail closed on invalid types or malformed base hashes."""
    sentinel = DriftSentinel()

    with pytest.raises(TypeError):
        sentinel.evaluate_and_propose("not_a_dict", base_cfg_hash=SAMPLE_BASE_HASH)  # type: ignore

    with pytest.raises(ValueError):
        sentinel.evaluate_and_propose({}, base_cfg_hash="short_hash")


def test_drift_sentinel_provider_timeout_and_exception_fails_closed():
    """External provider errors and timeouts fail closed without disrupting the caller."""
    def timeout_provider(summary):
        raise TimeoutError("Provider timed out after 5.0s")

    def failing_provider(summary):
        raise RuntimeError("Internal API connection failed")

    sentinel_timeout = DriftSentinel(llm_provider=timeout_provider)
    summary = {"overall_drift_detected": True}
    assert sentinel_timeout.evaluate_and_propose(summary, SAMPLE_BASE_HASH) is None

    sentinel_failing = DriftSentinel(llm_provider=failing_provider)
    assert sentinel_failing.evaluate_and_propose(summary, SAMPLE_BASE_HASH) is None


def test_drift_sentinel_rejects_forbidden_keys_from_external_provider():
    """If an external LLM tries to propose forbidden keys, sentinel fails closed and blocks it."""
    def malicious_provider(summary):
        return Proposal(
            proposal_id="prop_malicious",
            base_cfg_hash=SAMPLE_BASE_HASH,
            changes={"forbidden_key": "inject", "model.retrain": True},
            rationale="Unsafe attempt to alter core model",
        )

    sentinel = DriftSentinel(llm_provider=malicious_provider)
    summary = {"overall_drift_detected": True}
    # Sentinel validates proposal invariants and catches forbidden keys, returning None (fail closed)
    result = sentinel.evaluate_and_propose(summary, SAMPLE_BASE_HASH)
    assert result is None
