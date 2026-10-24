"""
Trinetra Prometheus Metrics Exporter
Formats live cluster telemetry into standard Prometheus exposition format.
"""
from typing import Dict, Any


def format_prometheus_metrics(snapshot: Dict[str, Any]) -> str:
    """Render Prometheus exposition text format."""
    metrics = snapshot.get("metrics", {})
    resilience = metrics.get("resilience", {})
    nodes = snapshot.get("nodes", [])

    lines = [
        "# HELP consensus_tps Current committed transactions per second (1s sliding window)",
        "# TYPE consensus_tps gauge",
        f"consensus_tps {metrics.get('tps', 0.0)}",
        "",
        "# HELP consensus_latency_seconds_p50 Median transaction confirmation latency",
        "# TYPE consensus_latency_seconds_p50 gauge",
        f"consensus_latency_seconds_p50 {metrics.get('p50_ms', 0.0) / 1000.0}",
        "",
        "# HELP consensus_latency_seconds_p95 95th percentile transaction confirmation latency",
        "# TYPE consensus_latency_seconds_p95 gauge",
        f"consensus_latency_seconds_p95 {metrics.get('p95_ms', 0.0) / 1000.0}",
        "",
        "# HELP consensus_mttr_seconds Mean Time to Recover from fault injection",
        "# TYPE consensus_mttr_seconds gauge",
        f"consensus_mttr_seconds {metrics.get('mttr_ms', 0.0) / 1000.0}",
        "",
        "# HELP consensus_elections_churn_per_min Elections initiated per minute",
        "# TYPE consensus_elections_churn_per_min gauge",
        f"consensus_elections_churn_per_min {metrics.get('churn_per_min', 0.0)}",
        "",
        "# HELP consensus_availability_ratio Fraction of 500ms windows with commits",
        "# TYPE consensus_availability_ratio gauge",
        f"consensus_availability_ratio {metrics.get('availability_pct', 0.0) / 1000.0}",
        "",
        "# HELP consensus_resilience_score Mathematical resilience score (0-100)",
        "# TYPE consensus_resilience_score gauge",
        f"consensus_resilience_score {resilience.get('score', 0.0)}",
        ""
    ]

    # Node roles
    lines.append("# HELP validator_node_state State of validator nodes (1 = active, 0 = crashed)")
    lines.append("# TYPE validator_node_state gauge")
    for n in nodes:
        is_active = 0 if n.get("status") == "CRASHED" else 1
        lines.append(f'validator_node_state{{node="N{n["id"]}",role="{n["role"]}",status="{n["status"]}"}} {is_active}')

    return "\n".join(lines) + "\n"
