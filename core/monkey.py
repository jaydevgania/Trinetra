"""
Trinetra Monkey Mode (Jepsen-Style Chaos Fuzzer)
Runs hundreds or thousands of randomized fault schedules in fast-forward
simulated time, asserting strict consensus safety invariants under arbitrary chaos.
"""
import random
from typing import Dict, Any, List, Optional
from core.clock import SimClock
from core.network import SimNetwork
from core.crypto import KeyPair
from core.raft import ValidatorNode
from core.invariants import InvariantChecker


class MonkeyFuzzer:
    def __init__(self, node_count: int = 5):
        self.node_count = node_count

    def run_fuzz_campaign(self, schedules_count: int = 100, seed: int = 1337) -> Dict[str, Any]:
        """
        Execute `schedules_count` randomized chaos runs in pure virtual time.
        Verifies zero forks and zero log-matching inconsistencies.
        """
        campaign_rng = random.Random(seed)
        violations_count = 0
        violation_logs = []
        total_txs_committed = 0

        for run_idx in range(schedules_count):
            run_seed = campaign_rng.randint(1, 10_000_000)
            passed, err_msg, txs = self._run_single_schedule(run_seed)
            total_txs_committed += txs
            if not passed:
                violations_count += 1
                violation_logs.append({
                    "run_idx": run_idx,
                    "seed": run_seed,
                    "error": err_msg
                })

        return {
            "schedules_tested": schedules_count,
            "seed": seed,
            "safety_violations": violations_count,
            "is_safe": violations_count == 0,
            "total_txs_committed": total_txs_committed,
            "summary": f"{schedules_count} random fault schedules executed in virtual time. {violations_count} safety violations detected.",
            "violations": violation_logs
        }

    def _run_single_schedule(self, seed: int) -> tuple[bool, str, int]:
        """Run a single simulated cluster through randomized chaos timeline."""
        rng = random.Random(seed)
        clock = SimClock()
        node_ids = list(range(self.node_count))
        net = SimNetwork(clock, node_ids, rng=random.Random(seed + 1))

        # Node keypairs
        keypairs = {nid: KeyPair(f"node_key_{nid}".encode('utf-8')) for nid in node_ids}
        peer_pubkeys = {nid: kp.public_key_hex for nid, kp in keypairs.items()}

        nodes = []
        for nid in node_ids:
            peers = [p for p in node_ids if p != nid]
            node = ValidatorNode(
                node_id=nid,
                peers=peers,
                clock=clock,
                network=net,
                keypair=keypairs[nid],
                peer_pubkeys=peer_pubkeys,
                seed=seed + nid
            )
            node.start()
            nodes.append(node)

        checker = InvariantChecker(nodes)

        # Generate 5-10 randomized chaos actions across a 15-second simulation window
        action_count = rng.randint(5, 10)
        for _ in range(action_count):
            t_action = rng.uniform(0.5, 12.0)
            action_type = rng.choice(["crash", "partition", "heal", "netem"])
            target_node = rng.randint(0, self.node_count - 1)

            if action_type == "crash":
                clock.call_at(t_action, lambda nid=target_node: nodes[nid].crash())
                # Schedule recovery after 2 seconds
                clock.call_at(t_action + 2.0, lambda nid=target_node: nodes[nid].recover())
            elif action_type == "partition":
                clock.call_at(t_action, lambda: net.partition([[0, 1], [2, 3, 4]]))
                clock.call_at(t_action + 3.0, lambda: net.heal())
            elif action_type == "netem":
                clock.call_at(t_action, lambda: net.set_all_links(drop_prob=0.15, delay_ms=100.0))
                clock.call_at(t_action + 2.5, lambda: net.set_all_links(drop_prob=0.0, delay_ms=2.0))

        # Run cluster for 15 simulated seconds in CPU time (~15ms)
        clock.run_until(15.0)

        # Assert safety invariants
        inv_result = checker.check_all()
        committed_count = sum(len(n.ledger.chain) - 1 for n in nodes)

        if not inv_result["no_fork"]:
            return False, f"Fork detected: {inv_result['violations']}", committed_count
        if not inv_result["log_matching"]:
            return False, f"Log matching failed: {inv_result['violations']}", committed_count
        if not inv_result["state_root_agreement"]:
            return False, f"State root mismatch: {inv_result['violations']}", committed_count

        return True, "OK", committed_count
