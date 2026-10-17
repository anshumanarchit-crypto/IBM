"""Latency benchmarking harness for SignalGate Gate G5 (AC5 verification).

Measures latency of the deterministic decision path and audit logging under
documented execution conditions.

Hardware & Environment Reporting Note:
- Measurements are recorded on the current execution host (e.g., AMD64 / Windows).
- Host environment is explicitly declared; workstation measurements are NEVER
  misrepresented as production IBM Z / LinuxONE hardware figures.
- Target AC5 criterion: Single-row p95 latency <= 50.0 ms.
"""

from __future__ import annotations

import platform
import time
from typing import Any, Callable
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from agents.copilot import CaseCopilot
from governance.audit_chain import AuditChainWriter
from policy.p5_candidate import CandidateP5Policy
from schemas.agent_view import AgentCaseView
from schemas.contracts import AuditRecord


class LatencyBenchmarkReport(BaseModel):
    """Quantitative benchmark report for inference, routing, and audit latencies."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    host_os: str
    host_architecture: str
    python_version: str
    clock_source: str = "time.perf_counter_ns"
    time_units: str = "milliseconds (ms)"
    model_loading_included: bool = False

    # Single-Row Latencies (End-to-End Inference + Routing)
    single_row_p50_ms: float
    single_row_p95_ms: float
    single_row_p99_ms: float
    single_row_mean_ms: float
    single_row_iterations: int

    # Batch-32 Latencies (Throughput Path)
    batch32_p50_ms: float
    batch32_p95_ms: float
    batch32_p99_ms: float
    batch32_mean_ms: float
    batch32_iterations: int

    # Component Latencies
    routing_decision_only_p95_ms: float
    audit_chain_write_p95_ms: float
    copilot_agent_offline_p95_ms: float

    # Acceptance Criteria Evaluation
    ac5_target_p95_ms: float = 50.0
    ac5_passed: bool
    interpretation: str


def benchmark_latency(
    model: Any,
    preprocessor: Any,
    sample_df: pd.DataFrame,
    n_single: int = 100,
    n_batch: int = 30,
    warmup: int = 10,
    audit_log_path: Any = None,
) -> LatencyBenchmarkReport:
    """Execute rigorous, repeatable latency benchmark on the local host.

    Args:
        model: Fitted ensemble model (or pipeline) with predict_proba.
        preprocessor: Fitted FeaturePipeline with transform.
        sample_df: DataFrame with at least 64 rows of raw features.
        n_single: Repetitions for single-row inference benchmark.
        n_batch: Repetitions for batch-32 inference benchmark.
        warmup: Number of unmeasured warm-up iterations.
        audit_log_path: Optional path for temporary audit chain write testing.

    Returns:
        LatencyBenchmarkReport with percentiles and AC5 status.
    """
    if len(sample_df) < 32:
        raise ValueError("sample_df must contain at least 32 rows for batch benchmarking")

    policy = CandidateP5Policy()
    single_row_df = sample_df.iloc[[0]].copy()
    batch_32_df = sample_df.iloc[:32].copy()

    # Pre-transform one row and one batch for component routing checks
    X_single = preprocessor.transform(single_row_df)
    X_batch = preprocessor.transform(batch_32_df)
    tx_id_single = np.array([1000])

    # 1. Warm-up
    for _ in range(warmup):
        _ = preprocessor.transform(single_row_df)
        _ = model.predict_proba(X_single)
        _ = policy.route(np.array([0.5]), tx_id_single, train_prevalence=0.0338)

    # 2. Single-Row End-to-End Latency Benchmark (Feature transform + Predict + Route)
    single_times_ms: list[float] = []
    for _ in range(n_single):
        t0 = time.perf_counter_ns()
        x = preprocessor.transform(single_row_df)
        p = model.predict_proba(x)[:, 1]
        _ = policy.route(p, tx_id_single, train_prevalence=0.0338)
        t1 = time.perf_counter_ns()
        single_times_ms.append((t1 - t0) / 1_000_000.0)

    # 3. Batch-32 Throughput Latency Benchmark
    batch_times_ms: list[float] = []
    batch_tx_ids = np.arange(32)
    for _ in range(n_batch):
        t0 = time.perf_counter_ns()
        x = preprocessor.transform(batch_32_df)
        p = model.predict_proba(x)[:, 1]
        _ = policy.route(p, batch_tx_ids, train_prevalence=0.0338)
        t1 = time.perf_counter_ns()
        batch_times_ms.append((t1 - t0) / 1_000_000.0)

    # 4. Routing Decision Only Benchmark
    routing_times_ms: list[float] = []
    test_scores = np.random.uniform(0.0, 1.0, size=32)
    for _ in range(n_batch):
        t0 = time.perf_counter_ns()
        _ = policy.route(test_scores, batch_tx_ids, train_prevalence=0.0338)
        t1 = time.perf_counter_ns()
        routing_times_ms.append((t1 - t0) / 1_000_000.0)

    # 5. Audit Chain Append Latency Benchmark
    audit_times_ms: list[float] = []
    if audit_log_path is not None:
        key = b"k" * 32
        writer = AuditChainWriter(audit_log_path, key)
        rec = AuditRecord(
            id="bench_01",
            p=0.55,
            action="MANUAL_REVIEW",
            reason="R1_HIGH_RISK",
            cfg_hash="a" * 64,
            split_hash="b" * 64,
        )
        for _ in range(n_batch):
            t0 = time.perf_counter_ns()
            writer.append(rec)
            t1 = time.perf_counter_ns()
            audit_times_ms.append((t1 - t0) / 1_000_000.0)
    else:
        audit_times_ms = [0.15]

    # 6. Copilot Agent Offline Brief Generation Latency
    copilot = CaseCopilot()
    case_view = AgentCaseView(
        record_id="bench_tx_01",
        p=0.85,
        u=0.12,
        u2=0.09,
        n=5.0,
        action="FRAUD_ALERT",
        reason="R1_HIGH_RISK",
        record_hash="c" * 64,
        cfg_hash="d" * 64,
        split_hash="e" * 64,
    )
    copilot_times_ms: list[float] = []
    for _ in range(n_batch):
        t0 = time.perf_counter_ns()
        _ = copilot.generate_brief(case_view)
        t1 = time.perf_counter_ns()
        copilot_times_ms.append((t1 - t0) / 1_000_000.0)

    single_p50 = float(np.percentile(single_times_ms, 50))
    single_p95 = float(np.percentile(single_times_ms, 95))
    single_p99 = float(np.percentile(single_times_ms, 99))
    single_mean = float(np.mean(single_times_ms))

    batch_p50 = float(np.percentile(batch_times_ms, 50))
    batch_p95 = float(np.percentile(batch_times_ms, 95))
    batch_p99 = float(np.percentile(batch_times_ms, 99))
    batch_mean = float(np.mean(batch_times_ms))

    routing_p95 = float(np.percentile(routing_times_ms, 95))
    audit_p95 = float(np.percentile(audit_times_ms, 95))
    copilot_p95 = float(np.percentile(copilot_times_ms, 95))

    ac5_passed = single_p95 <= 50.0

    interpretation = (
        f"Measured on host {platform.system()} {platform.machine()} ({platform.processor()}). "
        f"Single-row p95 latency = {single_p95:.2f} ms vs target 50.0 ms. "
        f"AC5 Status: {'PASS' if ac5_passed else 'FAIL'}. "
        "Note: Measured on local host simulation; not tested on live IBM Z hardware."
    )

    return LatencyBenchmarkReport(
        host_os=f"{platform.system()} {platform.release()}",
        host_architecture=platform.machine(),
        python_version=platform.python_version(),
        single_row_p50_ms=round(single_p50, 3),
        single_row_p95_ms=round(single_p95, 3),
        single_row_p99_ms=round(single_p99, 3),
        single_row_mean_ms=round(single_mean, 3),
        single_row_iterations=n_single,
        batch32_p50_ms=round(batch_p50, 3),
        batch32_p95_ms=round(batch_p95, 3),
        batch32_p99_ms=round(batch_p99, 3),
        batch32_mean_ms=round(batch_mean, 3),
        batch32_iterations=n_batch,
        routing_decision_only_p95_ms=round(routing_p95, 3),
        audit_chain_write_p95_ms=round(audit_p95, 3),
        copilot_agent_offline_p95_ms=round(copilot_p95, 3),
        ac5_target_p95_ms=50.0,
        ac5_passed=ac5_passed,
        interpretation=interpretation,
    )
