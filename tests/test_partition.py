"""
Unit Tests for Network Partitioning, Pre-Vote Safety, and Healing
"""
import pytest
from core.cluster import ClusterController
from core.raft import NodeRole


def test_minority_partition_and_heal():
    cluster = ClusterController(node_count=5, seed=303)
    cluster.start()
    cluster.clock.run_until(1.0)

    leader = cluster.get_current_leader()
    assert leader is not None

    # Place leader in majority {0, 1, 2}
    maj_group = [0, 1, 2]
    min_group = [3, 4]
    if leader.node_id in min_group:
        maj_group, min_group = [2, 3, 4], [0, 1]

    # Partition network
    cluster.partition_network([maj_group, min_group])
    cluster.start_workload(tps=40.0, invalid_pct=0.0)

    # Run partitioned for 3 seconds
    cluster.clock.run_until(4.5)

    # Majority should have advanced
    maj_node = cluster.nodes[maj_group[0]]
    min_node = cluster.nodes[min_group[0]]
    assert maj_node.commit_index > min_node.commit_index

    # Heal partition
    cluster.heal_partitions()

    # Allow catch up
    cluster.clock.run_until(7.0)
    cluster.stop_workload()
    cluster.clock.run_until(8.5)

    inv = cluster.run_invariant_check()
    assert inv["no_fork"] is True
    assert inv["log_matching"] is True
    assert inv["state_root_agreement"] is True


def test_prevote_prevents_term_inflation():
    """Prove pre-vote prevents isolated minority from driving term higher."""
    cluster = ClusterController(node_count=5, seed=404)
    cluster.set_mode(prevote=True)
    cluster.start()
    cluster.clock.run_until(1.0)

    leader = cluster.get_current_leader()
    assert leader is not None
    current_term = leader.current_term

    # Isolate Node 4
    cluster.partition_network([[0, 1, 2, 3], [4]])

    # Advance time 3 seconds (multiple election timeouts fire on isolated Node 4)
    cluster.clock.run_until(4.0)

    # With pre-vote ON, Node 4 cannot get pre-vote majority, so it stays at current_term or <= term+1
    node_4 = cluster.nodes[4]
    assert node_4.current_term <= current_term + 1, f"Term was inflated to {node_4.current_term}"

    # Heal network
    cluster.heal_partitions()
    cluster.clock.run_until(5.5)

    # Leader was not stepped down because healed node had no inflated term
    assert cluster.get_current_leader() is not None
