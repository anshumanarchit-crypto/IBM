"""Unit tests for CandidateP5Policy (policy/p5_candidate.py).

Verifies:
- Config hash determinism.
- Score combination with lambda=0 (pure risk) and lambda > 0.
- Top-budget routing respects exact review volume.
- Deterministic secondary sort on TransactionID ascending.
"""

from __future__ import annotations

import numpy as np
import pytest

from policy.p5_candidate import CandidateP5Policy, P5PolicyConfig


def test_p5_config_hash_deterministic():
    cfg1 = P5PolicyConfig()
    cfg2 = P5PolicyConfig()
    assert cfg1.config_hash() == cfg2.config_hash()
    assert len(cfg1.config_hash()) == 64


def test_p5_scoring_lambda_zero():
    policy = CandidateP5Policy(P5PolicyConfig(disagreement_weight_lambda=0.0))
    p = np.array([0.2, 0.7, 0.9])
    u = np.array([0.05, 0.12, 0.03])
    scores = policy.score(p, u)
    np.testing.assert_array_equal(scores, p)


def test_p5_scoring_lambda_nonzero():
    policy = CandidateP5Policy(P5PolicyConfig(disagreement_weight_lambda=0.5))
    p = np.array([0.2, 0.7])
    u = np.array([0.1, 0.2])
    scores = policy.score(p, u)
    np.testing.assert_allclose(scores, np.array([0.25, 0.80]))


def test_p5_routing_exact_budget():
    policy = CandidateP5Policy(P5PolicyConfig(budget_multiple=1.5))
    n = 1000
    train_prevalence = 0.05  # 5%
    # Expected budget = floor(1.5 * 0.05 * 1000) = 75
    scores = np.linspace(0, 1, n)
    tx_ids = np.arange(n)

    decisions = policy.route(scores, tx_ids, train_prevalence)
    assert np.sum(decisions == 1) == 75
    # Highest scores must be reviewed
    assert np.all(decisions[-75:] == 1)
    assert np.all(decisions[:-75] == 0)


def test_p5_routing_deterministic_tie_breaking():
    policy = CandidateP5Policy()
    # Identical scores, different IDs
    scores = np.array([0.8, 0.8, 0.8, 0.8])
    tx_ids = np.array([300, 100, 400, 200])
    train_prevalence = 0.25  # multiple 1.5 -> floor(1.5 * 0.25 * 4) = 1 case
    d = policy.route(scores, tx_ids, train_prevalence)
    # tx_id 100 is smallest -> must be chosen
    assert d[1] == 1
    assert np.sum(d) == 1
