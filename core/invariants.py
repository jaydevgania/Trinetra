"""
Trinetra Consistency Checker & Invariant Monitor
Validates election safety, log matching, chain cryptographic integrity,
fork detection, state-root consensus agreement, and follower lag.
"""
from typing import List, Dict, Any, Tuple, Optional
from core.raft import ValidatorNode, NodeRole


class InvariantChecker:
    def __init__(self, nodes: List[ValidatorNode]):
        self.nodes = nodes

    def check_all(self) -> Dict[str, Any]:
        """
        Execute comprehensive invariant checks across all active cluster nodes.
        Returns a structured dictionary with pass/fail flags and detailed violation logs.
        """
        violations = []

        election_safety, e_err = self.check_election_safety()
        if not election_safety:
            violations.append(e_err)

        log_matching, l_err = self.check_log_matching()
        if not log_matching:
            violations.append(l_err)

        chain_integrity, c_err = self.check_chain_integrity()
        if not chain_integrity:
            violations.append(c_err)

        no_fork, fork_details = self.check_for_forks()
        if not no_fork:
            violations.append(fork_details)

        state_root_ok, s_err = self.check_state_root_agreement()
        if not state_root_ok:
            violations.append(s_err)

        lag_map = self.check_lag()

        return {
            "election_safety": election_safety,
            "log_matching": log_matching,
            "chain_integrity": chain_integrity,
            "no_fork": no_fork,
            "state_root_agreement": state_root_ok,
            "fork_detected": not no_fork,
            "lag": lag_map,
            "violations": violations
        }

    def check_election_safety(self) -> Tuple[bool, str]:
        """Verify at most one leader per term."""
        term_leaders: Dict[int, List[int]] = {}
        for node in self.nodes:
            if node.role == NodeRole.LEADER:
                term_leaders.setdefault(node.current_term, []).append(node.node_id)

        for term, leaders in term_leaders.items():
            if len(leaders) > 1:
                return False, f"ELECTION_SAFETY_VIOLATION: Multiple leaders in term {term}: {leaders}"
        return True, "OK"

    def check_log_matching(self) -> Tuple[bool, str]:
        """
        Verify that if two nodes have an entry at the same index and term,
        the entries are identical.
        """
        honest_nodes = [n for n in self.nodes if n.role != NodeRole.CRASHED]
        for i in range(len(honest_nodes)):
            for j in range(i + 1, len(honest_nodes)):
                n1, n2 = honest_nodes[i], honest_nodes[j]
                min_len = min(len(n1.log), len(n2.log))
                for idx in range(min_len):
                    e1 = n1.log[idx]
                    e2 = n2.log[idx]
                    if e1.term == e2.term and e1.entry_hash != e2.entry_hash:
                        return False, f"LOG_MATCHING_VIOLATION: Node {n1.node_id} and Node {n2.node_id} conflict at index {idx}, term {e1.term}"
        return True, "OK"

    def check_chain_integrity(self) -> Tuple[bool, str]:
        """Verify prev_hash pointers and Merkle roots across all committed chains."""
        for node in self.nodes:
            chain = node.ledger.chain
            for h in range(1, len(chain)):
                prev = chain[h - 1]
                curr = chain[h]
                if curr.prev_hash != prev.hash:
                    return False, f"CHAIN_INTEGRITY_VIOLATION: Node {node.node_id} height {curr.height} prev_hash mismatch"
                valid_int, reason = curr.verify_integrity()
                if not valid_int:
                    return False, f"CHAIN_INTEGRITY_VIOLATION: Node {node.node_id} block {curr.height}: {reason}"
        return True, "OK"

    def check_for_forks(self) -> Tuple[bool, str]:
        """
        Detect whether any two nodes have committed different block hashes at the same height.
        This is the primary Byzantine safety failure check.
        """
        height_commits: Dict[int, Dict[str, List[int]]] = {}
        for node in self.nodes:
            chain = node.ledger.chain
            for b in chain:
                if b.height == 0:
                    continue  # Genesis
                height_commits.setdefault(b.height, {}).setdefault(b.hash, []).append(node.node_id)

        for height, hash_map in height_commits.items():
            if len(hash_map) > 1:
                details = "; ".join(f"Hash {h[:8]}.. on nodes {nodes}" for h, nodes in hash_map.items())
                return False, f"FORK_VIOLATION: Incompatible blocks committed at height {height}: {details}"

        return True, "OK"

    def check_state_root_agreement(self) -> Tuple[bool, str]:
        """Ensure all nodes with committed blocks at height H compute the exact same state_root."""
        height_roots: Dict[int, Dict[str, List[int]]] = {}
        for node in self.nodes:
            chain = node.ledger.chain
            for b in chain:
                if b.height == 0:
                    continue
                height_roots.setdefault(b.height, {}).setdefault(b.state_root, []).append(node.node_id)

        for height, root_map in height_roots.items():
            if len(root_map) > 1:
                details = "; ".join(f"Root {r[:8]}.. on nodes {nodes}" for r, nodes in root_map.items())
                return False, f"STATE_ROOT_MISMATCH: Inconsistent ledger state at height {height}: {details}"

        return True, "OK"

    def check_lag(self) -> Dict[int, int]:
        """Compute block lag relative to cluster highest commit."""
        max_height = max((len(n.ledger.chain) - 1 for n in self.nodes), default=0)
        return {
            n.node_id: max(0, max_height - (len(n.ledger.chain) - 1))
            for n in self.nodes
        }
