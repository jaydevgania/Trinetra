"""
Trinetra Cluster Controller
Coordinates the discrete-event clock, simulated network, 5 validator nodes,
workload generator, invariant checker, metrics engine, live narrator,
message tracer, and automated autopilot.
"""
import random
from typing import Dict, List, Optional, Any, Callable
import time

from core.clock import SimClock
from core.network import SimNetwork, PacketTrace
from core.crypto import KeyPair
from core.ledger import Transaction, Block
from core.raft import ValidatorNode, NodeRole
from core.invariants import InvariantChecker
from core.metrics import MetricsEngine
from core.workload import WorkloadGenerator
from core.narrator import LiveNarrator
from core.tracer import MessageTracer
from core.autopilot import AutopilotController
from core.scenarios import SCENARIO_LIBRARY, ScenarioDefinition


class ClusterController:
    def __init__(self, node_count: int = 5, seed: int = 42):
        self.node_count = node_count
        self.seed = seed
        self.rng = random.Random(seed)

        # 1. Clock
        self.clock = SimClock()

        # 2. Network
        self.node_ids = list(range(node_count))
        self.network = SimNetwork(self.clock, self.node_ids, rng=random.Random(seed + 1))

        # 3. Cryptographic Identities
        self.keypairs: Dict[int, KeyPair] = {
            nid: KeyPair(f"trinetra_validator_node_seed_{nid}_{seed}".encode('utf-8'))
            for nid in self.node_ids
        }
        self.peer_pubkeys: Dict[int, str] = {
            nid: kp.public_key_hex for nid, kp in self.keypairs.items()
        }

        # 4. Workload Generator
        self.workload = WorkloadGenerator(self.clock, account_count=20, initial_balance=50_000, rng_seed=seed + 10)
        self.workload.submit_callback = self._handle_client_workload

        # 5. Nodes
        self.nodes: List[ValidatorNode] = []
        for nid in self.node_ids:
            peers = [p for p in self.node_ids if p != nid]
            node = ValidatorNode(
                node_id=nid,
                peers=peers,
                clock=self.clock,
                network=self.network,
                keypair=self.keypairs[nid],
                peer_pubkeys=self.peer_pubkeys,
                genesis_accounts=self.workload.genesis_balances,
                seed=seed + nid
            )
            node.event_callback = self._handle_node_event
            self.nodes.append(node)

        # 6. Invariant Checker & Metrics
        self.invariants = InvariantChecker(self.nodes)
        self.metrics = MetricsEngine(self.clock)

        # 7. Live Narrator & Tracer
        self.narrator = LiveNarrator()
        self.tracer = MessageTracer(max_capacity=1000)
        self.network.add_trace_listener(self._handle_packet_trace)

        # 8. Autopilot
        self.autopilot = AutopilotController(self)

        # Cluster configuration
        self.timers_mode: str = "adaptive"  # "static" or "adaptive"
        self.prevote_enabled: bool = True
        self.consensus_mode: str = "cft"    # "cft" or "hardened"
        self.geo_preset: str = "dc"

        # Cached invariant status
        self.last_invariant_status: Dict[str, Any] = self.invariants.check_all()

    def start(self) -> None:
        """Start validators and kick off initial consensus timers."""
        for node in self.nodes:
            node.start()
        self.emit_narrative("cluster_started", {"node_count": self.node_count})

    def emit_narrative(self, event_type: str, data: Dict[str, Any]) -> None:
        self.narrator.narrate(event_type, data, self.clock.t)

    def _handle_node_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Receive internal node events to update metrics and live narrator."""
        if event_name == "election_started":
            self.metrics.record_election_started()
        elif event_name == "leader_elected":
            self.metrics.record_leader_elected()
        elif event_name == "block_committed":
            tx_count = payload.get("tx_count", 1)
            self.metrics.record_commit(tx_count)

        self.emit_narrative(event_name, payload)

    def _handle_packet_trace(self, trace: PacketTrace) -> None:
        self.tracer.record_packet(trace)

    def _handle_client_workload(self, txs: List[Transaction]) -> None:
        """Deliver generated client transactions to active leader."""
        leader = self.get_current_leader()
        if leader:
            leader.propose_transactions(txs)
        self.metrics.update_workload_state(self.workload.is_running, self.network.messages_sent)

    def get_current_leader(self) -> Optional[ValidatorNode]:
        for n in self.nodes:
            if n.role == NodeRole.LEADER:
                return n
        return None

    def get_current_leader_id(self) -> Optional[int]:
        leader = self.get_current_leader()
        return leader.node_id if leader else None

    # ---------------------------------------------------------
    # Cluster Controls (Chaos, Modes, Workload)
    # ---------------------------------------------------------
    def set_mode(self, timers: Optional[str] = None, prevote: Optional[bool] = None, consensus: Optional[str] = None) -> None:
        if timers is not None:
            self.timers_mode = timers
            for n in self.nodes:
                n.adaptive.mode = timers
        if prevote is not None:
            self.prevote_enabled = prevote
            for n in self.nodes:
                n.adaptive.prevote_enabled = prevote
        if consensus is not None:
            self.consensus_mode = consensus
            for n in self.nodes:
                n.consensus_mode = consensus

    def apply_geo_preset(self, preset_name: str) -> None:
        self.geo_preset = preset_name
        self.network.apply_preset(preset_name)

    def crash_node(self, node_id: int) -> None:
        if 0 <= node_id < self.node_count:
            self.nodes[node_id].crash()
            self.metrics.record_fault_injected()

    def recover_node(self, node_id: int) -> None:
        if 0 <= node_id < self.node_count:
            self.nodes[node_id].recover()

    def partition_network(self, groups: List[List[int]]) -> None:
        self.network.partition(groups)
        self.metrics.record_fault_injected()
        self.emit_narrative("partition_active", {"groups": groups})

    def heal_partitions(self) -> None:
        self.network.heal()
        self.emit_narrative("partition_healed", {})

    def inject_netem(self, drop_prob: Optional[float] = None, delay_ms: Optional[float] = None, jitter_ms: Optional[float] = None) -> None:
        self.network.set_all_links(drop_prob=drop_prob, delay_ms=delay_ms, jitter_ms=jitter_ms)
        if (delay_ms or 0) > 50 or (drop_prob or 0) > 0.05:
            self.metrics.record_fault_injected()
            self.emit_narrative("latency_storm_started", {"delay_ms": delay_ms or 100})
        else:
            self.emit_narrative("latency_storm_cleared", {})

    def set_slow_leader(self, node_id: int, slow: bool = True, delay_ms: float = 250.0) -> None:
        """Inject Gray Failure: delay leader outbound heartbeats/proposals."""
        if 0 <= node_id < self.node_count:
            self.nodes[node_id].is_slow_leader = slow
            self.nodes[node_id].slow_delay_ms = delay_ms
            if slow:
                self.emit_narrative("gray_failure_detected", {"leader": node_id, "jitter_ms": delay_ms})

    def transfer_leadership(self, target_node: Optional[int] = None) -> None:
        """Trigger planned leader transfer."""
        leader = self.get_current_leader()
        if leader:
            leader.transfer_leadership(target_node)

    def submit_client_tx(self, sender_idx: int, recipient_idx: int, amount: int) -> Dict[str, Any]:
        """Submit a manual client transfer transaction from Transaction Studio."""
        if not (0 <= sender_idx < len(self.workload.keypairs)) or not (0 <= recipient_idx < len(self.workload.keypairs)):
            raise ValueError("Invalid account index")

        sender_kp = self.workload.keypairs[sender_idx]
        recipient_kp = self.workload.keypairs[recipient_idx]
        sender_pubkey = sender_kp.public_key_hex
        recipient_pubkey = recipient_kp.public_key_hex

        self.workload.account_nonces[sender_pubkey] += 1
        nonce = self.workload.account_nonces[sender_pubkey]

        tx = Transaction(
            sender=sender_pubkey,
            recipient=recipient_pubkey,
            amount=amount,
            nonce=nonce,
            timestamp=self.clock.t
        )
        tx.sign(sender_kp)

        leader = self.get_current_leader()
        if leader:
            leader.propose_transactions([tx])
            self.emit_narrative("custom_tx_submitted", {"tx_id": tx.tx_id, "amount": amount})
            return {
                "status": "submitted",
                "tx_id": tx.tx_id,
                "sender": sender_pubkey[:12] + "..",
                "recipient": recipient_pubkey[:12] + "..",
                "amount": amount,
                "nonce": nonce,
                "sig": tx.sig[:16] + ".."
            }
        else:
            return {"status": "error", "message": "No active leader available"}

    def run_custom_scenario(self, events: List[Dict[str, Any]]) -> None:
        """Execute custom timeline events from Visual Scenario Composer."""
        start_t = self.clock.t
        for ev in events:
            offset = float(ev.get("time_offset_sec", 1.0))
            action = ev.get("action")
            params = ev.get("params", {})
            narration = ev.get("narration", "")

            def _act(a=action, p=params, n=narration):
                if n:
                    self.emit_narrative("scenario_event", {"text": n})
                if a == "crash":
                    self.crash_node(int(p.get("node", 0)))
                elif a == "recover":
                    self.recover_node(int(p.get("node", 0)))
                elif a == "partition":
                    self.partition_network(p.get("groups", [[0, 1], [2, 3, 4]]))
                elif a == "heal":
                    self.heal_partitions()
                elif a == "netem":
                    self.inject_netem(drop_prob=p.get("drop_prob"), delay_ms=p.get("delay_ms"), jitter_ms=p.get("jitter_ms"))
                elif a == "malicious":
                    self.inject_malicious_equivocation(int(p.get("node", 0)))
                elif a == "slow_leader":
                    self.set_slow_leader(int(p.get("node", 0)), slow=True, delay_ms=float(p.get("delay_ms", 250.0)))
                elif a == "clear_slow_leader":
                    self.set_slow_leader(int(p.get("node", 0)), slow=False)

            self.clock.call_later(offset, _act)

    def inject_malicious_equivocation(self, node_id: int) -> None:
        """Arm specified node to equivocate on its next proposed block."""
        if 0 <= node_id < self.node_count:
            node = self.nodes[node_id]
            if node.role == NodeRole.LEADER:
                next_h = node.log[-1].block.height + 1
                node.equivocate_target_height = next_h
                # Trigger immediate proposal to execute equivocation
                node.propose_block(txs=[])
            else:
                # If follower, target next height
                node.equivocate_target_height = node.log[-1].block.height + 1

    def start_workload(self, tps: float = 150.0, invalid_pct: float = 2.0) -> None:
        self.workload.start(target_tps=tps, invalid_pct=invalid_pct)
        self.metrics.update_workload_state(True, self.network.messages_sent)

    def stop_workload(self) -> None:
        self.workload.stop()
        self.metrics.update_workload_state(False, self.network.messages_sent)

    # ---------------------------------------------------------
    # Invariant Checks & Snapshot Generation
    # ---------------------------------------------------------
    def run_invariant_check(self) -> Dict[str, Any]:
        result = self.invariants.check_all()
        self.last_invariant_status = result
        if not result["no_fork"]:
            self.emit_narrative("fork_detected", {"details": result["violations"]})
        return result

    def step(self, dt: float = 0.050) -> None:
        """Step cluster simulation forward by dt seconds."""
        self.clock.step_dt(dt)
        self.run_invariant_check()

    def get_snapshot(self) -> Dict[str, Any]:
        """Produce full cluster state for UI WebSocket and REST API."""
        inv = self.run_invariant_check()
        has_safety_violation = not (inv["no_fork"] and inv["state_root_agreement"])
        metrics_snap = self.metrics.get_snapshot(has_safety_violation)

        nodes_data = []
        for n in self.nodes:
            chain_len = len(n.ledger.chain)
            head_block = n.ledger.chain[-1] if n.ledger.chain else None
            nodes_data.append({
                "id": n.node_id,
                "role": n.role.value,
                "term": n.current_term,
                "commit_index": n.commit_index,
                "last_applied": n.last_applied,
                "height": head_block.height if head_block else 0,
                "head_hash": head_block.hash[:12] if head_block else "000000000000",
                "state_root": head_block.state_root[:12] if head_block else "000000000000",
                "status": "CRASHED" if n.role == NodeRole.CRASHED else ("QUARANTINED" if n.node_id in self.nodes[0].byzantine.quarantine else "HEALTHY"),
                "trust_score": round(self.nodes[0].byzantine.trust_scores.get(n.node_id, 100.0), 1),
                "is_quarantined": n.node_id in self.nodes[0].byzantine.quarantine,
                "is_leader": n.role == NodeRole.LEADER
            })

        links_data = []
        for (src, dst), cfg in self.network.links.items():
            links_data.append({
                "src": src,
                "dst": dst,
                "latency_ms": round(cfg.base_latency_ms, 1),
                "drop_prob": round(cfg.drop_prob, 2),
                "blocked": cfg.blocked
            })

        return {
            "t": round(self.clock.t, 3),
            "is_paused": self.clock.is_paused,
            "speed": self.clock.speed,
            "mode": {
                "timers": self.timers_mode,
                "prevote": self.prevote_enabled,
                "consensus": self.consensus_mode,
                "geo": self.geo_preset
            },
            "nodes": nodes_data,
            "links": links_data,
            "metrics": metrics_snap,
            "invariants": inv,
            "latest_narrative": self.narrator.get_latest(),
            "recent_narratives": self.narrator.get_recent(limit=8),
            "autopilot": self.autopilot.get_status(),
            "workload": {
                "is_running": self.workload.is_running,
                "target_tps": self.workload.target_tps,
                "invalid_pct": self.workload.invalid_pct,
                "txs_generated": self.workload.txs_generated
            },
            "accounts": [
                {
                    "index": i,
                    "pubkey": kp.public_key_hex[:10] + "..",
                    "full_pubkey": kp.public_key_hex,
                    "balance": self.nodes[0].ledger.balances.get(kp.public_key_hex, 0)
                } for i, kp in enumerate(self.workload.keypairs[:10])
            ]
        }
