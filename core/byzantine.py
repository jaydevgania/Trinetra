"""
Trinetra Byzantine Fault & Malicious Equivocation Engine
Handles detection of equivocating leaders (Tier 2) and cryptographic
4-of-5 Echo Quorum defense (Tier 3 Hardened Mode) preventing forks.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any
from core.crypto import KeyPair, canonical_json, sha256_hash


@dataclass
class SignedHeader:
    term: int
    index: int
    entry_hash: str
    leader_sig: str
    proposer: int

    def compute_hash(self) -> str:
        payload = {
            "term": self.term,
            "index": self.index,
            "entry_hash": self.entry_hash,
            "proposer": self.proposer
        }
        return sha256_hash(canonical_json(payload))

    def verify(self, leader_pubkey: str) -> bool:
        header_hash = self.compute_hash()
        return KeyPair.verify(leader_pubkey, header_hash, self.leader_sig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term,
            "index": self.index,
            "entry_hash": self.entry_hash,
            "leader_sig": self.leader_sig,
            "proposer": self.proposer
        }


@dataclass
class EquivProof:
    offender: int
    term: int
    index: int
    hash_a: str
    sig_a: str
    hash_b: str
    sig_b: str

    def verify(self, offender_pubkey: str) -> bool:
        """Verify that offender signed two distinct hashes for the same term and index."""
        if self.hash_a == self.hash_b:
            return False

        header_a = SignedHeader(self.term, self.index, self.hash_a, self.sig_a, self.offender)
        header_b = SignedHeader(self.term, self.index, self.hash_b, self.sig_b, self.offender)

        return header_a.verify(offender_pubkey) and header_b.verify(offender_pubkey)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offender": self.offender,
            "term": self.term,
            "index": self.index,
            "hash_a": self.hash_a,
            "sig_a": self.sig_a,
            "hash_b": self.hash_b,
            "sig_b": self.sig_b
        }


@dataclass
class EchoMessage:
    term: int
    index: int
    entry_hash: str
    leader_sig: str
    sender: int
    echo_sig: str

    def compute_hash(self) -> str:
        payload = {
            "term": self.term,
            "index": self.index,
            "entry_hash": self.entry_hash,
            "leader_sig": self.leader_sig,
            "sender": self.sender
        }
        return sha256_hash(canonical_json(payload))

    def verify(self, sender_pubkey: str) -> bool:
        return KeyPair.verify(sender_pubkey, self.compute_hash(), self.echo_sig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "Echo",
            "term": self.term,
            "index": self.index,
            "entry_hash": self.entry_hash,
            "leader_sig": self.leader_sig,
            "sender": self.sender,
            "echo_sig": self.echo_sig
        }


class ByzantineManager:
    """Manages gossip, equivocation detection, and hardened echo verification per node."""
    def __init__(self, node_id: int, keypair: KeyPair, peer_pubkeys: Dict[int, str]):
        self.node_id = node_id
        self.keypair = keypair
        self.peer_pubkeys = peer_pubkeys  # node_id -> hex public key

        # Quarantine set: nodes proven malicious whose messages must be dropped
        self.quarantine: Set[int] = set()

        # Known leader signed headers: (term, index) -> Dict[entry_hash, SignedHeader]
        self.observed_headers: Dict[Tuple[int, int], Dict[str, SignedHeader]] = {}

        # Proven equivocations: (term, index) -> EquivProof
        self.proofs: Dict[Tuple[int, int], EquivProof] = {}

        # Hardened mode: (term, index, entry_hash) -> Set[signer_node_id]
        self.echo_support: Dict[Tuple[int, int, str], Set[int]] = {}

        # Validator trust scores: node_id -> float (0 to 100)
        self.trust_scores: Dict[int, float] = {nid: 100.0 for nid in peer_pubkeys.keys()}
        self.trust_scores[node_id] = 100.0

    def record_signed_header(self, header: SignedHeader) -> Optional[EquivProof]:
        """
        Record signed header received directly from leader or via gossip.
        If a conflicting header for the same (term, index) is discovered,
        construct and return an EquivProof.
        """
        key = (header.term, header.index)
        if key not in self.observed_headers:
            self.observed_headers[key] = {}

        headers_for_slot = self.observed_headers[key]
        if header.entry_hash not in headers_for_slot:
            headers_for_slot[header.entry_hash] = header

        # Check for equivocation (more than 1 different hash for same term, index)
        if len(headers_for_slot) >= 2 and key not in self.proofs:
            hashes = list(headers_for_slot.keys())
            h_a = headers_for_slot[hashes[0]]
            h_b = headers_for_slot[hashes[1]]
            proof = EquivProof(
                offender=header.proposer,
                term=header.term,
                index=header.index,
                hash_a=h_a.entry_hash,
                sig_a=h_a.leader_sig,
                hash_b=h_b.entry_hash,
                sig_b=h_b.leader_sig
            )
            # Verify and quarantine
            offender_pubkey = self.peer_pubkeys.get(header.proposer)
            if offender_pubkey and proof.verify(offender_pubkey):
                self.proofs[key] = proof
                self.quarantine.add(header.proposer)
                self.trust_scores[header.proposer] = 0.0
                return proof

        return None

    def handle_proof(self, proof: EquivProof) -> bool:
        """Process incoming broadcast EquivProof from peer."""
        offender_pubkey = self.peer_pubkeys.get(proof.offender)
        if not offender_pubkey:
            return False

        if proof.verify(offender_pubkey):
            self.quarantine.add(proof.offender)
            self.trust_scores[proof.offender] = 0.0
            self.proofs[(proof.term, proof.index)] = proof
            return True
        return False

    def create_echo(self, term: int, index: int, entry_hash: str, leader_sig: str) -> EchoMessage:
        """Construct signed Echo message for Hardened Mode."""
        echo = EchoMessage(
            term=term,
            index=index,
            entry_hash=entry_hash,
            leader_sig=leader_sig,
            sender=self.node_id,
            echo_sig=""
        )
        msg_hash = echo.compute_hash()
        echo.echo_sig = self.keypair.sign(msg_hash)
        return echo

    def record_echo(self, echo: EchoMessage) -> int:
        """
        Record validated Echo for Hardened Mode quorum.
        Returns total count of distinct signers supporting this entry.
        """
        sender_pubkey = self.peer_pubkeys.get(echo.sender)
        if not sender_pubkey:
            return 0

        if not echo.verify(sender_pubkey):
            return 0

        key = (echo.term, echo.index, echo.entry_hash)
        if key not in self.echo_support:
            self.echo_support[key] = set()

        self.echo_support[key].add(echo.sender)
        return len(self.echo_support[key])

    def get_echo_count(self, term: int, index: int, entry_hash: str) -> int:
        return len(self.echo_support.get((term, index, entry_hash), set()))

    def update_trust(self, node_id: int, delta: float) -> float:
        if node_id in self.quarantine:
            self.trust_scores[node_id] = 0.0
            return 0.0
        score = max(0.0, min(100.0, self.trust_scores.get(node_id, 100.0) + delta))
        self.trust_scores[node_id] = score
        return score
