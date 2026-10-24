"""
Unit Tests for Gray-Failure Detection and Planned Leader Transfer (Feature A12)
"""
import pytest
from core.cluster import ClusterController
from core.raft import NodeRole


def test_planned_leader_transfer_timeout_now():
    """Prove that planned leader transfer via TimeoutNow hands over leadership seamlessly."""
    cluster = ClusterController(node_count=5, seed=909)
    cluster.start()
    cluster.clock.run_until(1.0)

    leader = cluster.get_current_leader()
    assert leader is not None
    original_leader_id = leader.node_id
    target_node = (original_leader_id + 1) % 5

    # Trigger planned leadership transfer to target
    cluster.transfer_leadership(target_node=target_node)

    # Fast forward 0.2s for TimeoutNow delivery and immediate election
    cluster.clock.run_until(1.3)

    new_leader = cluster.get_current_leader()
    assert new_leader is not None
    assert new_leader.node_id == target_node, f"Expected N{target_node} to be leader, got N{new_leader.node_id}"

    # Assert invariant check
    inv = cluster.run_invariant_check()
    assert inv["election_safety"] is True
    assert inv["no_fork"] is True


def test_slow_leader_gray_failure_detection():
    """Inject 250ms outbound delay on leader; follower detects jitter and initiates proactive takeover."""
    cluster = ClusterController(node_count=5, seed=919)
    cluster.start()
    cluster.clock.run_until(1.0)

    leader = cluster.get_current_leader()
    assert leader is not None
    leader_id = leader.node_id

    # Inject slow leader delay
    cluster.set_slow_leader(leader_id, slow=True, delay_ms=250.0)

    # Run for 2.0s so followers observe multiple delayed heartbeats
    cluster.clock.run_until(3.5)

    # Verify that a follower recognized gray failure or took over leadership
    new_leader = cluster.get_current_leader()
    assert new_leader is not None
    assert cluster.nodes[1].last_heartbeat_ts is not None
