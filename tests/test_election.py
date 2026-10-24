"""
Unit Tests for Leader Election and Failover
"""
import pytest
from core.cluster import ClusterController
from core.raft import NodeRole


def test_single_leader_elected_after_startup():
    cluster = ClusterController(node_count=5, seed=42)
    cluster.start()

    # Step simulation forward for 1.0 second
    cluster.clock.run_until(1.0)

    leaders = [n for n in cluster.nodes if n.role == NodeRole.LEADER]
    assert len(leaders) == 1, f"Expected exactly 1 leader, got {len(leaders)}"
    assert leaders[0].current_term >= 1


def test_leader_failover_on_crash():
    cluster = ClusterController(node_count=5, seed=101)
    cluster.start()
    cluster.clock.run_until(1.0)

    leader = cluster.get_current_leader()
    assert leader is not None
    original_leader_id = leader.node_id
    original_term = leader.current_term

    # Crash leader
    cluster.crash_node(original_leader_id)

    # Step clock forward 1.5 seconds for election timeout to trigger and new leader to win
    cluster.clock.run_until(2.5)

    new_leader = cluster.get_current_leader()
    assert new_leader is not None
    assert new_leader.node_id != original_leader_id
    assert new_leader.current_term > original_term

    # Ensure invariant checker confirms election safety
    inv = cluster.run_invariant_check()
    assert inv["election_safety"] is True
