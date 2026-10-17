"""SignalGate Evaluation and Benchmarking Layer (Gate G5).

Contains:
- ComprehensiveEvaluationMetrics, compute_comprehensive_metrics, compute_calibration_ece
- BootstrapResult, compute_paired_bootstrap
- LatencyBenchmarkReport, benchmark_latency
"""

from eval.bootstrap import BootstrapResult, compute_paired_bootstrap
from eval.latency import LatencyBenchmarkReport, benchmark_latency
from eval.metrics import (
    ComprehensiveEvaluationMetrics,
    compute_calibration_ece,
    compute_comprehensive_metrics,
)

__all__ = [
    "ComprehensiveEvaluationMetrics",
    "compute_comprehensive_metrics",
    "compute_calibration_ece",
    "BootstrapResult",
    "compute_paired_bootstrap",
    "LatencyBenchmarkReport",
    "benchmark_latency",
]
