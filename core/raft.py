"""
Trinetra Raft Validator Node Implementation
Supports Follower, PreCandidate, Candidate, Leader, and Crashed states.
Integrates Adaptive Timeouts (Jacobson/Karels), Pre-Vote protocol,
Byzantine Equivocation detection, and Hardened Echo Quorum mode.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any, Callable
import random
import time

from core.crypto import KeyPair, sha256_hash, canonical_json
from core.ledger import Block, Transaction, TokenLedger
from core.adaptive import AdaptiveController
from core.byzantine import ByzantineManager, SignedHeader, EquivProof, EchoMessage


class NodeRole(str, Enum):
    FOLLOWER = "Follower"
    PRECANDIDATE = "PreCandidate"
    CANDIDATE = "Candidate"
    LEADER = "Leader"
    CRASHED = "Crashed"


@dataclass
class LogEntry:
    term: int
    index: int
    block: Block
    entry_hash: str
    leader_sig: str = ""

    def compute_hash(self) -> str:
        return self.block.hash


@dataclass
class RPCMessage:
    type: str
    term: int
    src: int
    dst: int
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "term": self.term,
            "src": self.src,
            "dst": self.dst,
            "data": self.data
        }


class ValidatorNode:
    """
    Raft Consensus Node with hash-chained ledger and Byzantine defense.
    """
    def __init__(
        self,
        node_id: int,
        peers: List[int],
        clock: Any,
        network: Any,
        keypair: KeyPair,
        peer_pubkeys: Dict[int, str],
        genesis_accounts: Optional[Dict[str, int]] = None,
        seed: int = 42
    ):
        self.node_id = node_id
        self.peers = list(peers)
        self.clock = clock
        self.network = network
        self.network.register_node(self.node_id, self.on_message)
        self.keypair = keypair
        self.peer_pubkeys = peer_pubkeys
        self.rng = random.Random(seed + node_id * 100)

        # Consensus State
        self.role: NodeRole = NodeRole.FOLLOWER
        self.current_term: int = 0
        self.voted_for: Optional[int] = None
        self.log: List[LogEntry] = []  # 1-indexed conceptually, 0 is sentinel or genesis
        self.commit_index: int = 0
        self.last_applied: int = 0

        # Leader specific state
        self.next_index: Dict[int, int] = {}
        self.match_index: Dict[int, int] = {}
        self.pending_tx_pool: List[Transaction] = []

        # Subsystems
        self.ledger = TokenLedger(genesis_accounts=genesis_accounts)
        self.adaptive = AdaptiveController(node_id, peers)
        self.byzantine = ByzantineManager(node_id, keypair, peer_pubkeys)

        # Timers / Callback Handles
        self.election_timer_handle: Optional[int] = None
        self.heartbeat_timer_handle: Optional[int] = None

        # Voting book-keeping
        self.votes_received: Set[int] = set()
        self.prevotes_received: Set[int] = set()

        # Operational Mode Configuration
        self.consensus_mode: str = "cft"  # "cft" or "hardened"
        self.equivocate_target_height: Optional[int] = None
        self.is_slow_leader: bool = False
        self.slow_delay_ms: float = 250.0

        # Gray Failure Detection (A12)
        self.leader_health: float = 100.0
        self.slow_heartbeat_count: int = 0
        self.last_heartbeat_ts: Optional[float] = None

        # Event Bus notification hooks
        self.event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None

        # Initialize Genesis entry (index 0)
        self._init_genesis()

    def _init_genesis(self) -> None:
        """Create genesis block at height 0."""
        genesis_block = Block(
            height=0,
            term=0,
            prev_hash="0" * 64,
            txs=[],
            proposer=0,
            ts=0.0,
            merkle_root=sha256_hash("GENESIS_MERKLE"),
            state_root=self.ledger.compute_state_root()
        )
        genesis_block.finalize(self.keypair, genesis_block.state_root)
        self.ledger.chain.append(genesis_block)
        genesis_entry = LogEntry(
            term=0,
            index=0,
            block=genesis_block,
            entry_hash=genesis_block.hash
        )
        self.log.append(genesis_entry)

    def start(self) -> None:
        """Start node timers and join network as follower."""
        self.reset_election_timer()

    def emit_event(self, event_name: str, details: Dict[str, Any]) -> None:
        if self.event_callback:
            payload = {
                "node_id": self.node_id,
                "term": self.current_term,
                "role": self.role.value,
                "commit_index": self.commit_index,
                **details
            }
            self.event_callback(event_name, payload)

    # ---------------------------------------------------------
    # Timer Management
    # ---------------------------------------------------------
    def reset_election_timer(self) -> None:
        """Cancel existing election timer and schedule randomized new one."""
        if self.election_timer_handle is not None:
            self.clock.cancel(self.election_timer_handle)

        if self.role == NodeRole.LEADER or self.role == NodeRole.CRASHED:
            return

        timeout = self.adaptive.sample_election_timeout(self.rng)
        self.election_timer_handle = self.clock.call_later(timeout, self.handle_election_timeout)

    def reset_heartbeat_timer(self) -> None:
        """Cancel and rearm leader periodic heartbeat."""
        if self.heartbeat_timer_handle is not None:
            self.clock.cancel(self.heartbeat_timer_handle)

        if self.role != NodeRole.LEADER:
            return

        interval = self.adaptive.get_leader_heartbeat_interval()
        self.heartbeat_timer_handle = self.clock.call_later(interval, self.send_heartbeats)

    # ---------------------------------------------------------
    # State Machine Transitions
    # ---------------------------------------------------------
    def step_down(self, new_term: int) -> None:
        """Step down to Follower on discovering higher term."""
        prev_role = self.role
        self.current_term = new_term
        self.role = NodeRole.FOLLOWER
        self.voted_for = None
        self.votes_received.clear()
        self.prevotes_received.clear()

        if self.heartbeat_timer_handle is not None:
            self.clock.cancel(self.heartbeat_timer_handle)
            self.heartbeat_timer_handle = None

        self.reset_election_timer()
        if prev_role == NodeRole.LEADER:
            self.emit_event("leader_stepped_down", {"reason": "higher_term_seen"})

    def crash(self) -> None:
        """Simulate validator crash: drop in-memory timers, reject all messages."""
        self.role = NodeRole.CRASHED
        if self.election_timer_handle:
            self.clock.cancel(self.election_timer_handle)
            self.election_timer_handle = None
        if self.heartbeat_timer_handle:
            self.clock.cancel(self.heartbeat_timer_handle)
            self.heartbeat_timer_handle = None
        self.emit_event("node_crashed", {})

    def recover(self) -> None:
        """Simulate validator restart: reload disk state, rejoin as Follower."""
        if self.role != NodeRole.CRASHED:
            return
        self.role = NodeRole.FOLLOWER
        self.voted_for = None
        self.reset_election_timer()
        self.emit_event("node_recovered", {})

    # ---------------------------------------------------------
    # Election & Pre-Vote Mechanics
    # ---------------------------------------------------------
    def handle_election_timeout(self) -> None:
        """Fired when follower has not received heartbeats in time."""
        if self.role == NodeRole.CRASHED or self.role == NodeRole.LEADER:
            return

        if self.adaptive.prevote_enabled:
            self.start_prevote()
        else:
            self.start_real_election()

    def start_prevote(self) -> None:
        """Initiate Pre-Vote phase without incrementing term."""
        self.role = NodeRole.PRECANDIDATE
        self.prevotes_received = {self.node_id}
        target_term = self.current_term + 1
        last_log = self.log[-1]

        self.emit_event("prevote_started", {"target_term": target_term})

        msg_data = {
            "candidate_id": self.node_id,
            "next_term": target_term,
            "last_log_index": last_log.index,
            "last_log_term": last_log.term
        }
        for peer in self.peers:
            msg = RPCMessage(type="PreVote", term=target_term, src=self.node_id, dst=peer, data=msg_data)
            self.network.send(self.node_id, peer, msg, self._on_packet_delivered)

        self.reset_election_timer()

    def start_real_election(self) -> None:
        """Increment term, vote for self, and broadcast RequestVote."""
        self.role = NodeRole.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.votes_received = {self.node_id}
        last_log = self.log[-1]

        self.emit_event("election_started", {"new_term": self.current_term})

        msg_data = {
            "candidate_id": self.node_id,
            "last_log_index": last_log.index,
            "last_log_term": last_log.term
        }
        for peer in self.peers:
            msg = RPCMessage(type="RequestVote", term=self.current_term, src=self.node_id, dst=peer, data=msg_data)
            self.network.send(self.node_id, peer, msg, self._on_packet_delivered)

        self.reset_election_timer()

    def become_leader(self) -> None:
        """Elected as leader! Initialize next/match index and append initial no-op block."""
        self.role = NodeRole.LEADER
        if self.election_timer_handle:
            self.clock.cancel(self.election_timer_handle)
            self.election_timer_handle = None

        last_index = self.log[-1].index
        for peer in self.peers:
            self.next_index[peer] = last_index + 1
            self.match_index[peer] = 0

        self.emit_event("leader_elected", {"term": self.current_term})

        # Append initial no-op entry for new term (Raft safety requirement)
        self.propose_block(txs=[], is_noop=True)

        # Trigger immediate heartbeat
        self.send_heartbeats()
        self.reset_heartbeat_timer()

    # ---------------------------------------------------------
    # Log Proposal & Replication
    # ---------------------------------------------------------
    def propose_transactions(self, txs: List[Transaction]) -> Optional[int]:
        """Leader receives new client transactions to batch into block."""
        if self.role != NodeRole.LEADER:
            return None
        return self.propose_block(txs)

    def propose_block(self, txs: List[Transaction], is_noop: bool = False) -> int:
        """Batch transactions into a new Block and append to Raft log."""
        prev_entry = self.log[-1]
        new_height = prev_entry.block.height + 1
        new_index = prev_entry.index + 1

        # Check if malicious equivocation is targeted for this height
        if self.equivocate_target_height == new_height:
            return self._propose_equivocating_blocks(new_height, new_index, prev_entry.block.hash, txs)

        # Honest Block construction
        # Clone state machine to pre-calculate state root
        temp_ledger = self.ledger.clone()
        valid_txs = []
        for tx in txs:
            if temp_ledger.validate_tx(tx)[0]:
                temp_ledger.apply_tx(tx)
                valid_txs.append(tx)

        block = Block(
            height=new_height,
            term=self.current_term,
            prev_hash=prev_entry.block.hash,
            txs=valid_txs,
            proposer=self.node_id,
            ts=self.clock.t
        )
        state_root = temp_ledger.compute_state_root()
        block.finalize(self.keypair, state_root)

        header = SignedHeader(
            term=self.current_term,
            index=new_index,
            entry_hash=block.hash,
            leader_sig=self.keypair.sign(
                SignedHeader(self.current_term, new_index, block.hash, "", self.node_id).compute_hash()
            ),
            proposer=self.node_id
        )

        entry = LogEntry(
            term=self.current_term,
            index=new_index,
            block=block,
            entry_hash=block.hash,
            leader_sig=header.leader_sig
        )
        self.log.append(entry)

        self.emit_event("block_proposed", {"height": new_height, "tx_count": len(valid_txs), "hash": block.hash[:12]})
        self.send_append_entries_all()
        return new_index

    def _propose_equivocating_blocks(self, height: int, index: int, prev_hash: str, txs: List[Transaction]) -> int:
        """
        MALICIOUS ACTION (Equivocation):
        Propose two distinct blocks A and B with different hashes for the same (term, index).
        Send Block A to subset {peers[0], peers[1]} and Block B to {peers[2], peers[3]}.
        """
        self.emit_event("equivocation_injected", {"height": height, "index": index})

        # Block A
        block_a = Block(
            height=height,
            term=self.current_term,
            prev_hash=prev_hash,
            txs=txs[:len(txs)//2] if txs else [],
            proposer=self.node_id,
            ts=self.clock.t
        )
        block_a.finalize(self.keypair, sha256_hash(f"STATE_A_{height}"))

        # Block B (conflicting payload/hash)
        block_b = Block(
            height=height,
            term=self.current_term,
            prev_hash=prev_hash,
            txs=txs[len(txs)//2:] if txs else [],
            proposer=self.node_id,
            ts=self.clock.t + 0.001
        )
        block_b.finalize(self.keypair, sha256_hash(f"STATE_B_{height}"))

        sig_a = self.keypair.sign(SignedHeader(self.current_term, index, block_a.hash, "", self.node_id).compute_hash())
        sig_b = self.keypair.sign(SignedHeader(self.current_term, index, block_b.hash, "", self.node_id).compute_hash())

        entry_a = LogEntry(term=self.current_term, index=index, block=block_a, entry_hash=block_a.hash, leader_sig=sig_a)
        entry_b = LogEntry(term=self.current_term, index=index, block=block_b, entry_hash=block_b.hash, leader_sig=sig_b)

        # Leader locally records A
        self.log.append(entry_a)

        # Send A to first half of peers
        half = len(self.peers) // 2
        peers_a = self.peers[:half]
        peers_b = self.peers[half:]

        for peer in peers_a:
            self._send_append_to_peer(peer, [entry_a])
        for peer in peers_b:
            self._send_append_to_peer(peer, [entry_b])

        # Clear target trigger so it only happens once
        self.equivocate_target_height = None
        return index

    def send_heartbeats(self) -> None:
        """Periodic heartbeat broadcast to all peers."""
        if self.role != NodeRole.LEADER:
            return
        self.send_append_entries_all()
        self.reset_heartbeat_timer()

    def send_append_entries_all(self) -> None:
        """Send pending entries or heartbeats to all peers."""
        if self.role != NodeRole.LEADER:
            return
        for peer in self.peers:
            prev_idx = self.next_index.get(peer, self.log[-1].index) - 1
            entries_to_send = [e for e in self.log if e.index > prev_idx]
            self._send_append_to_peer(peer, entries_to_send)

    def _send_append_to_peer(self, peer: int, entries: List[LogEntry]) -> None:
        prev_idx = entries[0].index - 1 if entries else (self.next_index.get(peer, self.log[-1].index) - 1)
        prev_idx = max(0, min(prev_idx, len(self.log) - 1))
        prev_term = self.log[prev_idx].term if prev_idx < len(self.log) else 0

        data = {
            "leader_id": self.node_id,
            "prev_log_index": prev_idx,
            "prev_log_term": prev_term,
            "leader_commit": self.commit_index,
            "entries": [
                {
                    "term": e.term,
                    "index": e.index,
                    "block": e.block.to_dict(),
                    "entry_hash": e.entry_hash,
                    "leader_sig": e.leader_sig
                } for e in entries
            ],
            "send_ts": self.clock.t
        }
        msg = RPCMessage(type="AppendEntries", term=self.current_term, src=self.node_id, dst=peer, data=data)
        
        # If slow leader (Gray Failure injection), delay outbound RPCs
        if self.is_slow_leader:
            delay_sec = self.slow_delay_ms / 1000.0
            self.clock.call_later(delay_sec, lambda: self.network.send(self.node_id, peer, msg))
        else:
            self.network.send(self.node_id, peer, msg)

    def transfer_leadership(self, target_follower: Optional[int] = None) -> None:
        """
        Planned Leadership Transfer (Raft §3.10 / A12 Gray Failure Defense).
        Proactively hands over leadership to the healthiest follower without election delay.
        """
        if self.role != NodeRole.LEADER:
            return
        if target_follower is None:
            # Pick peer with lowest match lag / best RTT
            target_follower = self.peers[0] if self.peers else 0

        self.emit_event("planned_leader_transfer_started", {"target": target_follower})
        msg = RPCMessage(
            type="TimeoutNow",
            term=self.current_term,
            src=self.node_id,
            dst=target_follower,
            data={"leader_id": self.node_id}
        )
        self.network.send(self.node_id, target_follower, msg)

    # ---------------------------------------------------------
    # Message Dispatch & Handlers
    # ---------------------------------------------------------
    def _on_packet_delivered(self, dst: int, msg: RPCMessage) -> None:
        """Entry point called by SimNetwork when packet reaches this validator."""
        self.on_message(msg)

    def on_message(self, msg: RPCMessage) -> None:
        if self.role == NodeRole.CRASHED:
            return

        # Drop messages from quarantined malicious nodes
        if msg.src in self.byzantine.quarantine:
            return

        # Check for higher term (standard Raft rule)
        # PreVote and PreVoteReply do NOT cause step down or term increment
        if msg.term > self.current_term and msg.type not in ("PreVote", "PreVoteReply"):
            self.step_down(msg.term)

        match msg.type:
            case "PreVote":
                self.handle_prevote(msg)
            case "PreVoteReply":
                self.handle_prevote_reply(msg)
            case "RequestVote":
                self.handle_vote_request(msg)
            case "RequestVoteReply":
                self.handle_vote_reply(msg)
            case "AppendEntries":
                self.handle_append(msg)
            case "AppendEntriesReply":
                self.handle_append_reply(msg)
            case "Gossip":
                self.handle_gossip(msg)
            case "Echo":
                self.handle_echo(msg)
            case "EquivProof":
                self.handle_equiv_proof(msg)
            case "TimeoutNow":
                self.handle_timeout_now(msg)

    def handle_prevote(self, msg: RPCMessage) -> None:
        """Handle incoming PreVote from candidate."""
        candidate_id = msg.data["candidate_id"]
        next_term = msg.data["next_term"]
        last_log_index = msg.data["last_log_index"]
        last_log_term = msg.data["last_log_term"]

        vote_granted = False
        last_my_log = self.log[-1]

        # Peer grants PreVote if:
        # 1. Candidate's term is greater than current term
        # 2. Candidate's log is at least as up to date as receiver's log
        is_up_to_date = (
            (last_log_term > last_my_log.term) or
            (last_log_term == last_my_log.term and last_log_index >= last_my_log.index)
        )
        if next_term > self.current_term and is_up_to_date:
            vote_granted = True

        reply_data = {"granted": vote_granted, "responder": self.node_id}
        reply = RPCMessage(type="PreVoteReply", term=self.current_term, src=self.node_id, dst=candidate_id, data=reply_data)
        self.network.send(self.node_id, candidate_id, reply, self._on_packet_delivered)

    def handle_prevote_reply(self, msg: RPCMessage) -> None:
        if self.role != NodeRole.PRECANDIDATE:
            return
        if msg.data.get("granted"):
            self.prevotes_received.add(msg.src)
            # Majority of 5 is 3
            if len(self.prevotes_received) >= (len(self.peers) + 1) // 2 + 1:
                self.emit_event("prevote_quorum_reached", {"votes": len(self.prevotes_received)})
                self.start_real_election()

    def handle_vote_request(self, msg: RPCMessage) -> None:
        candidate_id = msg.data["candidate_id"]
        last_log_index = msg.data["last_log_index"]
        last_log_term = msg.data["last_log_term"]

        vote_granted = False
        last_my_log = self.log[-1]
        is_up_to_date = (
            (last_log_term > last_my_log.term) or
            (last_log_term == last_my_log.term and last_log_index >= last_my_log.index)
        )

        if (msg.term == self.current_term and
            (self.voted_for is None or self.voted_for == candidate_id) and
            is_up_to_date):
            vote_granted = True
            self.voted_for = candidate_id
            self.reset_election_timer()

        reply_data = {"granted": vote_granted, "responder": self.node_id}
        reply = RPCMessage(type="RequestVoteReply", term=self.current_term, src=self.node_id, dst=candidate_id, data=reply_data)
        self.network.send(self.node_id, candidate_id, reply, self._on_packet_delivered)

    def handle_vote_reply(self, msg: RPCMessage) -> None:
        if self.role != NodeRole.CANDIDATE or msg.term != self.current_term:
            return
        if msg.data.get("granted"):
            self.votes_received.add(msg.src)
            if len(self.votes_received) >= (len(self.peers) + 1) // 2 + 1:
                self.become_leader()

    def handle_timeout_now(self, msg: RPCMessage) -> None:
        """Planned Leader Transfer: Immediately trigger election without waiting for timer."""
        if self.role == NodeRole.CRASHED:
            return
        self.emit_event("timeout_now_received", {"from_leader": msg.src})
        self.start_real_election()

    def handle_append(self, msg: RPCMessage) -> None:
        """Handle AppendEntries / heartbeat from leader."""
        # Record arrival for adaptive follower EWMA jitter calculation
        self.adaptive.record_heartbeat(self.clock.t)

        leader_id = msg.data["leader_id"]

        # Gray Failure Monitoring (A12): Track heartbeat inter-arrival delays
        now_ts = self.clock.t
        if self.last_heartbeat_ts is not None:
            delta_ms = (now_ts - self.last_heartbeat_ts) * 1000.0
            if delta_ms > 200.0:
                self.slow_heartbeat_count += 1
                self.leader_health = max(0.0, self.leader_health - 25.0)
                if self.slow_heartbeat_count >= 3 and self.leader_health <= 40.0:
                    self.emit_event("gray_failure_detected", {
                        "leader": leader_id,
                        "health": self.leader_health,
                        "jitter_ms": round(delta_ms, 1)
                    })
                    # Proactively trigger planned leader transfer
                    self.start_real_election()
                    self.slow_heartbeat_count = 0
            else:
                self.slow_heartbeat_count = max(0, self.slow_heartbeat_count - 1)
                self.leader_health = min(100.0, self.leader_health + 10.0)
        self.last_heartbeat_ts = now_ts
        prev_log_index = msg.data["prev_log_index"]
        prev_log_term = msg.data["prev_log_term"]
        leader_commit = msg.data["leader_commit"]
        raw_entries = msg.data["entries"]
        send_ts = msg.data.get("send_ts", self.clock.t)

        if msg.term < self.current_term:
            reply_data = {"success": False, "match_index": self.log[-1].index, "send_ts": send_ts}
            reply = RPCMessage(type="AppendEntriesReply", term=self.current_term, src=self.node_id, dst=leader_id, data=reply_data)
            self.network.send(self.node_id, leader_id, reply, self._on_packet_delivered)
            return

        self.reset_election_timer()

        # Log consistency check
        if prev_log_index >= len(self.log) or self.log[prev_log_index].term != prev_log_term:
            reply_data = {"success": False, "match_index": len(self.log) - 1, "send_ts": send_ts}
            reply = RPCMessage(type="AppendEntriesReply", term=self.current_term, src=self.node_id, dst=leader_id, data=reply_data)
            self.network.send(self.node_id, leader_id, reply, self._on_packet_delivered)
            return

        # Append new entries and process Byzantine gossip/echo
        for raw in raw_entries:
            b_dict = raw["block"]
            txs = [Transaction.from_dict(t) for t in b_dict.get("txs", [])]
            block = Block(
                height=b_dict["height"],
                term=b_dict["term"],
                prev_hash=b_dict["prev_hash"],
                txs=txs,
                proposer=b_dict["proposer"],
                ts=b_dict["ts"],
                merkle_root=b_dict.get("merkle_root", ""),
                state_root=b_dict.get("state_root", ""),
                hash=b_dict["hash"],
                sig=b_dict.get("sig", "")
            )
            entry = LogEntry(
                term=raw["term"],
                index=raw["index"],
                block=block,
                entry_hash=raw["entry_hash"],
                leader_sig=raw.get("leader_sig", "")
            )

            # Record signed header for equivocation gossip detection
            if entry.leader_sig:
                header = SignedHeader(
                    term=entry.term,
                    index=entry.index,
                    entry_hash=entry.entry_hash,
                    leader_sig=entry.leader_sig,
                    proposer=leader_id
                )
                proof = self.byzantine.record_signed_header(header)
                if proof:
                    self.emit_event("equivocation_detected", {"offender": proof.offender, "index": proof.index})
                    self._broadcast_proof(proof)

                # Gossip header to peers to uncover equivocation rapidly
                self._gossip_header(header)

                # Hardened mode: broadcast Echo
                if self.consensus_mode == "hardened":
                    echo = self.byzantine.create_echo(entry.term, entry.index, entry.entry_hash, entry.leader_sig)
                    self._broadcast_echo(echo)

            # Replace or append log entry
            if entry.index < len(self.log):
                self.log[entry.index] = entry
            else:
                self.log.append(entry)

        # Update commit index and apply to state machine
        if leader_commit > self.commit_index:
            target_commit = min(leader_commit, self.log[-1].index)
            self._apply_entries(target_commit)

        reply_data = {"success": True, "match_index": self.log[-1].index, "send_ts": send_ts}
        reply = RPCMessage(type="AppendEntriesReply", term=self.current_term, src=self.node_id, dst=leader_id, data=reply_data)
        self.network.send(self.node_id, leader_id, reply, self._on_packet_delivered)

    def handle_append_reply(self, msg: RPCMessage) -> None:
        """Leader processes reply from follower."""
        if self.role != NodeRole.LEADER:
            return

        follower_id = msg.src
        success = msg.data.get("success", False)
        match_idx = msg.data.get("match_index", 0)
        send_ts = msg.data.get("send_ts", self.clock.t)

        # Update RTT estimate for follower
        rtt_ms = max(0.5, (self.clock.t - send_ts) * 1000.0)
        self.adaptive.record_ack_rtt(follower_id, rtt_ms)

        if success:
            self.next_index[follower_id] = match_idx + 1
            self.match_index[follower_id] = match_idx
            self._check_leader_commit()
        else:
            self.next_index[follower_id] = max(1, self.next_index.get(follower_id, 2) - 1)
            # Resend immediately
            self.send_append_entries_all()

    def _check_leader_commit(self) -> None:
        """
        Check if any higher entry index has achieved required quorum.
        CFT Mode: Majority (3 of 5).
        Hardened Mode: 4 of 5 matching Echoes (Leader counts as 1).
        """
        last_idx = self.log[-1].index
        for n in range(last_idx, self.commit_index, -1):
            if self.log[n].term == self.current_term:
                if self.consensus_mode == "hardened":
                    # Hardened quorum check: 4 of 5 echoes
                    echo_count = self.byzantine.get_echo_count(self.current_term, n, self.log[n].entry_hash) + 1  # +1 for leader
                    if echo_count >= 4:
                        self._apply_entries(n)
                        break
                else:
                    # CFT Majority check: 3 of 5
                    count = 1  # Self
                    for peer in self.peers:
                        if self.match_index.get(peer, 0) >= n:
                            count += 1
                    if count >= (len(self.peers) + 1) // 2 + 1:
                        self._apply_entries(n)
                        break

    def _apply_entries(self, new_commit: int) -> None:
        """Apply newly committed log entries to the TokenLedger state machine."""
        while self.last_applied < new_commit:
            self.last_applied += 1
            entry = self.log[self.last_applied]
            success, reason = self.ledger.apply_block(entry.block)
            self.commit_index = self.last_applied
            self.emit_event("block_committed", {
                "height": entry.block.height,
                "hash": entry.block.hash[:12],
                "state_root": self.ledger.compute_state_root()[:12]
            })

    # ---------------------------------------------------------
    # Byzantine Gossip & Echo Helpers
    # ---------------------------------------------------------
    def _gossip_header(self, header: SignedHeader) -> None:
        for peer in self.peers:
            msg = RPCMessage(type="Gossip", term=header.term, src=self.node_id, dst=peer, data=header.to_dict())
            self.network.send(self.node_id, peer, msg, self._on_packet_delivered)

    def _broadcast_proof(self, proof: EquivProof) -> None:
        for peer in self.peers:
            msg = RPCMessage(type="EquivProof", term=proof.term, src=self.node_id, dst=peer, data=proof.to_dict())
            self.network.send(self.node_id, peer, msg, self._on_packet_delivered)

    def _broadcast_echo(self, echo: EchoMessage) -> None:
        for peer in self.peers:
            msg = RPCMessage(type="Echo", term=echo.term, src=self.node_id, dst=peer, data=echo.to_dict())
            self.network.send(self.node_id, peer, msg, self._on_packet_delivered)

    def handle_gossip(self, msg: RPCMessage) -> None:
        header = SignedHeader(
            term=msg.data["term"],
            index=msg.data["index"],
            entry_hash=msg.data["entry_hash"],
            leader_sig=msg.data["leader_sig"],
            proposer=msg.data["proposer"]
        )
        proof = self.byzantine.record_signed_header(header)
        if proof:
            self.emit_event("equivocation_detected", {"offender": proof.offender, "index": proof.index})
            self._broadcast_proof(proof)

    def handle_echo(self, msg: RPCMessage) -> None:
        echo = EchoMessage(
            term=msg.data["term"],
            index=msg.data["index"],
            entry_hash=msg.data["entry_hash"],
            leader_sig=msg.data["leader_sig"],
            sender=msg.data["sender"],
            echo_sig=msg.data["echo_sig"]
        )
        self.byzantine.record_echo(echo)
        if self.role == NodeRole.LEADER:
            self._check_leader_commit()

    def handle_equiv_proof(self, msg: RPCMessage) -> None:
        proof = EquivProof(
            offender=msg.data["offender"],
            term=msg.data["term"],
            index=msg.data["index"],
            hash_a=msg.data["hash_a"],
            sig_a=msg.data["sig_a"],
            hash_b=msg.data["hash_b"],
            sig_b=msg.data["sig_b"]
        )
        if self.byzantine.handle_proof(proof):
            self.emit_event("peer_quarantined", {"offender": proof.offender})
            # If current leader is the offender, initiate election immediately!
            if self.role != NodeRole.LEADER:
                self.reset_election_timer()
