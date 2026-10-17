"""Unit and integration tests for HeterogeneousEnsemble (G2).

Tests confirm:
- Ensemble has the expected number of members with correct IDs.
- predict_proba returns an array of shape (n,) in [0, 1].
- predict_member_proba returns a matrix of shape (n, n_members).
- Ensemble mean equals column-wise mean of member scores.
- Fitting is deterministic: two equal-seed ensembles give byte-identical scores.
- Ensemble is not fitted before fit() is called.
"""

from __future__ import annotations

import numpy as np
import pytest

from models.ensemble import HeterogeneousEnsemble, SEEDS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def small_dataset():
    rng = np.random.default_rng(42)
    n, d = 200, 20
    X = rng.standard_normal((n, d)).astype(np.float32)
    y = rng.integers(0, 2, size=n)
    return X, y


@pytest.fixture(scope="module")
def fitted_ensemble(small_dataset):
    X, y = small_dataset
    ens = HeterogeneousEnsemble(seeds=SEEDS)
    ens.fit(X, y)
    return ens


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_ensemble_n_members(fitted_ensemble):
    """Ensemble must have len(SEEDS) + 2 members (HGBC * seeds + ET + LR)."""
    expected = len(SEEDS) + 2
    assert fitted_ensemble.n_members == expected


def test_ensemble_member_ids(fitted_ensemble):
    ids = fitted_ensemble.member_ids
    # Each seed has one HGBC member
    for seed in SEEDS:
        assert f"hgbc_s{seed}" in ids
    assert "et_s11" in ids
    assert "lr_s11" in ids


def test_predict_proba_shape(fitted_ensemble, small_dataset):
    X, _ = small_dataset
    p = fitted_ensemble.predict_proba(X)
    assert p.shape == (len(X),), f"Expected ({len(X)},), got {p.shape}"


def test_predict_proba_range(fitted_ensemble, small_dataset):
    X, _ = small_dataset
    p = fitted_ensemble.predict_proba(X)
    assert np.all(p >= 0.0), "Some probabilities are negative"
    assert np.all(p <= 1.0), "Some probabilities exceed 1"


def test_member_proba_shape(fitted_ensemble, small_dataset):
    X, _ = small_dataset
    mp = fitted_ensemble.predict_member_proba(X)
    assert mp.proba_matrix.shape == (len(X), fitted_ensemble.n_members)


def test_ensemble_mean_equals_member_mean(fitted_ensemble, small_dataset):
    """predict_proba must equal the column-wise mean of member proba_matrix."""
    X, _ = small_dataset
    mp = fitted_ensemble.predict_member_proba(X)
    mean_from_matrix = mp.proba_matrix.mean(axis=1)
    direct_mean = fitted_ensemble.predict_proba(X)
    np.testing.assert_allclose(direct_mean, mean_from_matrix, atol=1e-10)


def test_ensemble_deterministic(small_dataset):
    """Two ensembles with identical seeds must produce identical predictions."""
    X, y = small_dataset
    ens_a = HeterogeneousEnsemble(seeds=SEEDS)
    ens_b = HeterogeneousEnsemble(seeds=SEEDS)
    ens_a.fit(X, y)
    ens_b.fit(X, y)
    p_a = ens_a.predict_proba(X)
    p_b = ens_b.predict_proba(X)
    np.testing.assert_array_equal(p_a, p_b)


def test_unfitted_ensemble_raises():
    ens = HeterogeneousEnsemble()
    X = np.ones((5, 3), dtype=np.float32)
    with pytest.raises(RuntimeError, match="fitted"):
        ens.predict_proba(X)


def test_unfitted_member_proba_raises():
    ens = HeterogeneousEnsemble()
    X = np.ones((5, 3), dtype=np.float32)
    with pytest.raises(RuntimeError, match="fitted"):
        ens.predict_member_proba(X)
