"""
Unit Tests for Adaptive Timeouts (Jacobson/Karels vs Static Baseline)
"""
import pytest
from bench.run_bench import compare_static_vs_adaptive


def test_adaptive_timers_reduce_churn_during_latency_storm():
    """Assert that adaptive timers yield lower or equal median churn than static timers."""
    results = compare_static_vs_adaptive(scenario="latency_storm", runs=4, base_seed=505)

    static_churn = results["static"]["median_churn"]
    adaptive_churn = results["adaptive"]["median_churn"]
    adaptive_score = results["adaptive"]["median_score"]

    print(f"\nStatic churn: {static_churn}, Adaptive churn: {adaptive_churn}, Adaptive Score: {adaptive_score}")

    # Adaptive churn must be <= static churn
    assert adaptive_churn <= static_churn
    # Adaptive score should be superior or equal
    assert adaptive_score >= results["static"]["median_score"]
    assert results["adaptive"]["all_safe"] is True
