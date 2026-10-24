"""
Unit Tests for Log Replication and State Convergence
"""
import pytest
from core.cluster import ClusterController
from core.raft import NodeRole


def test_log_replication_convergence():
    cluster = ClusterController(node_count=5, seed=202)
    cluster.start()

    # Allow leader election
    cluster.clock.run_until(1.0)
    leader = cluster.get_current_leader()
    assert leader is not None

    # Start workload
    cluster.start_workload(tps=50.0, invalid_pct=0.0)
    cluster.clock.run_until(4.0)
    cluster.stop_workload()

    # Allow remaining heartbeats to replicate and commit
    cluster.clock.run_until(5.5)

    # Invariants verification
    inv = cluster.run_invariant_check()
    assert inv["log_matching"] is True
    assert inv["chain_integrity"] is True
    assert inv["no_fork"] is True
    assert inv["state_root_agreement"] is True

    # Check commit index parity across followers
    leader_height = len(leader.ledger.chain) - 1
    assert leader_height > 1, "Leader should have committed blocks"

    for node in cluster.nodes:
        if node.role != NodeRole.CRASHED:
            node_height = len(node.ledger.chain) - 1
            # Honest nodes should be within 1 block of leader
            assert abs(leader_height - node_height) <= 1
            # Committed blocks must have identical hashes
            for h in range(min(leader_height, node_height) + 1):
                assert leader.ledger.chain[h].hash == node.ledger.chain[h].hash
                assert leader.ledger.chain[h].state_root == node.ledger.chain[h].state_root
