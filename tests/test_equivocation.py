"""
Unit Tests for Byzantine Equivocation Detection and Hardened Echo Defense
"""
import pytest
from core.cluster import ClusterController
from core.monkey import MonkeyFuzzer


def test_equivocation_detection_and_quarantine():
    """In CFT mode, equivocation is flagged, EquivProof generated, and offender quarantined."""
    cluster = ClusterController(node_count=5, seed=606)
    cluster.set_mode(consensus="cft")
    cluster.start()
    cluster.clock.run_until(1.0)

    leader = cluster.get_current_leader()
    assert leader is not None
    leader_id = leader.node_id

    # Inject malicious equivocation
    cluster.inject_malicious_equivocation(leader_id)

    # Step clock to allow gossip and detection
    cluster.clock.run_until(3.0)

    # Leader must be quarantined
    for node in cluster.nodes:
        if node.node_id != leader_id:
            assert leader_id in node.byzantine.quarantine, f"Node {node.node_id} failed to quarantine offender"


def test_hardened_mode_prevents_fork():
    """In Hardened mode (4-of-5 echo quorum), conflicting blocks do NOT commit (0 forks)."""
    cluster = ClusterController(node_count=5, seed=707)
    cluster.set_mode(consensus="hardened")
    cluster.start()
    cluster.clock.run_until(1.0)

    leader = cluster.get_current_leader()
    assert leader is not None
    leader_id = leader.node_id

    # Inject malicious equivocation under Hardened mode
    cluster.inject_malicious_equivocation(leader_id)

    # Step clock to process echoes
    cluster.clock.run_until(3.0)

    # Invariants check: NO FORK MUST OCCUR!
    inv = cluster.run_invariant_check()
    assert inv["no_fork"] is True, "Hardened mode should prevent forks!"
    assert inv["state_root_agreement"] is True


def test_monkey_chaos_property_check():
    """Run 20 randomized chaos schedules; fork invariant must strictly hold."""
    fuzzer = MonkeyFuzzer(node_count=5)
    result = fuzzer.run_fuzz_campaign(schedules_count=20, seed=808)
    assert result["safety_violations"] == 0, f"Violations found: {result['violations']}"
    assert result["is_safe"] is True
