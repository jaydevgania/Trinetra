"""
Trinetra Benchmark Harness
Runs comparative benchmarks (Static Timers vs Adaptive Timers) across
multiple randomized seeds for scenarios like `latency_storm`, `minority_partition`, etc.
Provides CLI execution for CI gates (`--fail-under 80`).
"""
import argparse
import sys
import statistics
import random
from typing import Dict, Any, List

from core.clock import SimClock
from core.network import SimNetwork
from core.crypto import KeyPair
from core.raft import ValidatorNode
from core.metrics import MetricsEngine
from core.invariants import InvariantChecker
from core.workload import WorkloadGenerator


def run_benchmark_trial(scenario: str, mode: str, prevote: bool, seed: int, duration_sec: float = 20.0) -> Dict[str, Any]:
    """Execute a single scenario benchmark run in pure virtual time."""
    clock = SimClock()
    node_ids = [0, 1, 2, 3, 4]
    net = SimNetwork(clock, node_ids, rng=random.Random(seed + 1))
    keypairs = {nid: KeyPair(f"node_bench_{nid}_{seed}".encode('utf-8')) for nid in node_ids}
    peer_pubkeys = {nid: kp.public_key_hex for nid, kp in keypairs.items()}

    workload = WorkloadGenerator(clock, account_count=20, initial_balance=50_000, rng_seed=seed + 5)
    nodes: List[ValidatorNode] = []

    for nid in node_ids:
        peers = [p for p in node_ids if p != nid]
        node = ValidatorNode(
            node_id=nid,
            peers=peers,
            clock=clock,
            network=net,
            keypair=keypairs[nid],
            peer_pubkeys=peer_pubkeys,
            genesis_accounts=workload.genesis_balances,
            seed=seed + nid
        )
        node.adaptive.mode = mode
        node.adaptive.prevote_enabled = prevote
        node.start()
        nodes.append(node)

    metrics = MetricsEngine(clock)
    invariants = InvariantChecker(nodes)

    for n in nodes:
        def _hook(event_name, payload, m=metrics):
            if event_name == "election_started":
                m.record_election_started()
            elif event_name == "leader_elected":
                m.record_leader_elected()
            elif event_name == "block_committed":
                m.record_commit(payload.get("tx_count", 1))
        n.event_callback = _hook

    def _deliver_txs(txs):
        for n in nodes:
            if n.role.value == "Leader":
                n.propose_transactions(txs)
                break
        metrics.update_workload_state(workload.is_running, net.messages_sent)

    workload.submit_callback = _deliver_txs
    workload.start(target_tps=120.0, invalid_pct=2.0)

    # Inject scenario specific chaos
    if scenario == "latency_storm":
        # Surge to 300ms delay between t=5s and t=15s
        clock.call_at(5.0, lambda: net.set_all_links(delay_ms=300.0, jitter_ms=25.0, drop_prob=0.05))
        clock.call_at(5.0, lambda: metrics.record_fault_injected())
        clock.call_at(15.0, lambda: net.set_all_links(delay_ms=2.0, jitter_ms=0.5, drop_prob=0.0))
    elif scenario == "minority_partition":
        # Partition {0,1} vs {2,3,4} between t=5s and t=12s
        clock.call_at(5.0, lambda: net.partition([[0, 1], [2, 3, 4]]))
        clock.call_at(5.0, lambda: metrics.record_fault_injected())
        clock.call_at(12.0, lambda: net.heal())

    # Fast forward discrete clock
    clock.run_until(duration_sec)
    workload.stop()

    inv_result = invariants.check_all()
    has_safety_violation = not (inv_result["no_fork"] and inv_result["state_root_agreement"])
    metrics_snap = metrics.get_snapshot(has_safety_violation)

    return {
        "seed": seed,
        "score": metrics_snap["resilience"]["score"],
        "grade": metrics_snap["resilience"]["grade"],
        "churn": metrics_snap["churn_per_min"],
        "p95_ms": metrics_snap["p95_ms"],
        "availability_pct": metrics_snap["availability_pct"],
        "total_commits": metrics_snap["total_commits"],
        "safety_ok": not has_safety_violation
    }


def compare_static_vs_adaptive(scenario: str = "latency_storm", runs: int = 10, base_seed: int = 1000) -> Dict[str, Any]:
    """Run comparative suite of Static vs Adaptive consensus across N seeds."""
    static_trials = []
    adaptive_trials = []

    for i in range(runs):
        seed = base_seed + i * 17
        res_static = run_benchmark_trial(scenario, mode="static", prevote=False, seed=seed)
        res_adaptive = run_benchmark_trial(scenario, mode="adaptive", prevote=True, seed=seed)
        static_trials.append(res_static)
        adaptive_trials.append(res_adaptive)

    def _median(arr):
        return round(statistics.median(arr), 2) if arr else 0.0

    static_summary = {
        "median_score": _median([t["score"] for t in static_trials]),
        "median_churn": _median([t["churn"] for t in static_trials]),
        "median_p95_ms": _median([t["p95_ms"] for t in static_trials]),
        "median_availability": _median([t["availability_pct"] for t in static_trials]),
        "all_safe": all(t["safety_ok"] for t in static_trials)
    }

    adaptive_summary = {
        "median_score": _median([t["score"] for t in adaptive_trials]),
        "median_churn": _median([t["churn"] for t in adaptive_trials]),
        "median_p95_ms": _median([t["p95_ms"] for t in adaptive_trials]),
        "median_availability": _median([t["availability_pct"] for t in adaptive_trials]),
        "all_safe": all(t["safety_ok"] for t in adaptive_trials)
    }

    return {
        "scenario": scenario,
        "runs": runs,
        "static": static_summary,
        "adaptive": adaptive_summary,
        "trials": {
            "static": static_trials,
            "adaptive": adaptive_trials
        }
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Trinetra CI & Benchmark CLI")
    parser.add_argument("--scenario", type=str, default="latency_storm", help="Scenario to benchmark")
    parser.add_argument("--runs", type=int, default=5, help="Number of seed trials")
    parser.add_argument("--fail-under", type=float, default=80.0, help="Resilience score threshold for CI pass")
    args = parser.parse_args()

    import random
    print(f">> Running Trinetra Chaos Benchmark for '{args.scenario}' across {args.runs} seeds...")
    results = compare_static_vs_adaptive(args.scenario, runs=args.runs)

    adaptive_score = results["adaptive"]["median_score"]
    static_score = results["static"]["median_score"]

    print("\n" + "=" * 65)
    print(f"TRINETRA BENCHMARK RESULTS ({args.scenario.upper()})")
    print("=" * 65)
    print(f"Adaptive Mode Score : {adaptive_score} / 100  (Median churn: {results['adaptive']['median_churn']}/min, p95: {results['adaptive']['median_p95_ms']}ms)")
    print(f"Static Mode Score   : {static_score} / 100  (Median churn: {results['static']['median_churn']}/min, p95: {results['static']['median_p95_ms']}ms)")
    print("=" * 65)

    if adaptive_score < args.fail_under:
        print(f"\n[FAIL] Adaptive resilience score {adaptive_score} is below threshold {args.fail_under}!")
        sys.exit(1)
    else:
        print(f"\n[PASS] Adaptive resilience score {adaptive_score} meets CI gate (>= {args.fail_under})!")
        sys.exit(0)
