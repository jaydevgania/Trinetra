"""
Trinetra Ledger & Token State Machine
Implements signed transactions, hash-chained blocks with Merkle roots,
and a deterministic account-balance state machine with nonce-replay defense.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
import time
from core.crypto import canonical_json, sha256_hash, KeyPair, MerkleTree


@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: int
    nonce: int
    sig: str = ""
    tx_id: str = ""
    timestamp: float = 0.0

    def compute_hash(self) -> str:
        payload = {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "nonce": self.nonce,
            "timestamp": self.timestamp
        }
        return sha256_hash(canonical_json(payload))

    def sign(self, keypair: KeyPair) -> None:
        self.sender = keypair.public_key_hex
        self.tx_id = self.compute_hash()
        self.sig = keypair.sign(self.tx_id)

    def is_valid_signature(self) -> bool:
        if not self.sig or not self.sender:
            return False
        computed = self.compute_hash()
        return KeyPair.verify(self.sender, computed, self.sig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "nonce": self.nonce,
            "sig": self.sig,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        return cls(
            sender=data.get("sender", ""),
            recipient=data.get("recipient", ""),
            amount=int(data.get("amount", 0)),
            nonce=int(data.get("nonce", 0)),
            sig=data.get("sig", ""),
            tx_id=data.get("tx_id", ""),
            timestamp=float(data.get("timestamp", 0.0))
        )


@dataclass
class Block:
    height: int
    term: int
    prev_hash: str
    txs: List[Transaction]
    proposer: int
    ts: float
    merkle_root: str = ""
    state_root: str = ""
    hash: str = ""
    sig: str = ""

    def compute_merkle_root(self) -> str:
        tx_hashes = [tx.tx_id if tx.tx_id else tx.compute_hash() for tx in self.txs]
        tree = MerkleTree(tx_hashes)
        return tree.root

    def compute_hash(self) -> str:
        payload = {
            "height": self.height,
            "term": self.term,
            "prev_hash": self.prev_hash,
            "txs": [tx.to_dict() for tx in self.txs],
            "proposer": self.proposer,
            "ts": self.ts,
            "merkle_root": self.merkle_root,
            "state_root": self.state_root
        }
        return sha256_hash(canonical_json(payload))

    def finalize(self, keypair: KeyPair, state_root: str) -> None:
        """Compute Merkle root, state root, block hash, and sign block."""
        self.state_root = state_root
        self.merkle_root = self.compute_merkle_root()
        self.hash = self.compute_hash()
        self.sig = keypair.sign(self.hash)

    def verify_integrity(self, proposer_public_key: Optional[str] = None) -> Tuple[bool, str]:
        """Verify Merkle root, hash, and optional leader signature."""
        computed_merkle = self.compute_merkle_root()
        if computed_merkle != self.merkle_root:
            return False, f"Merkle root mismatch: expected {self.merkle_root}, got {computed_merkle}"

        computed_hash = self.compute_hash()
        if computed_hash != self.hash:
            return False, f"Block hash mismatch: expected {self.hash}, got {computed_hash}"

        if proposer_public_key and self.sig:
            if not KeyPair.verify(proposer_public_key, self.hash, self.sig):
                return False, "Invalid block leader signature"

        return True, "OK"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "height": self.height,
            "term": self.term,
            "prev_hash": self.prev_hash,
            "txs": [tx.to_dict() for tx in self.txs],
            "tx_count": len(self.txs),
            "proposer": self.proposer,
            "ts": self.ts,
            "merkle_root": self.merkle_root,
            "state_root": self.state_root,
            "hash": self.hash,
            "sig": self.sig
        }


class TokenLedger:
    """
    Account state machine: balances, nonces, and cryptographic state root.
    Handles transaction validation, nonce monotonicity, and state transitions.
    """
    def __init__(self, genesis_accounts: Optional[Dict[str, int]] = None):
        # account_pubkey -> balance
        self.balances: Dict[str, int] = dict(genesis_accounts or {})
        # account_pubkey -> last processed nonce
        self.nonces: Dict[str, int] = {}
        self.chain: List[Block] = []

    def clone(self) -> "TokenLedger":
        """Create a deep copy of ledger state for rollback or simulation."""
        new_ledger = TokenLedger(genesis_accounts=self.balances.copy())
        new_ledger.nonces = self.nonces.copy()
        new_ledger.chain = list(self.chain)
        return new_ledger

    def compute_state_root(self) -> str:
        """
        Hash of sorted balances and nonces.
        Every honest validator applying identical blocks will compute identical state_root.
        """
        sorted_balances = sorted(self.balances.items())
        sorted_nonces = sorted(self.nonces.items())
        payload = {
            "balances": sorted_balances,
            "nonces": sorted_nonces
        }
        return sha256_hash(canonical_json(payload))

    def validate_tx(self, tx: Transaction) -> Tuple[bool, str]:
        """
        Validate transaction against current state:
        1. Signature check
        2. Nonce monotonicity (nonce == last_nonce + 1)
        3. Sufficient funds (no overdraft)
        """
        if not tx.is_valid_signature():
            return False, "Invalid cryptographic signature"

        current_nonce = self.nonces.get(tx.sender, 0)
        if tx.nonce != current_nonce + 1:
            return False, f"Bad nonce: expected {current_nonce + 1}, got {tx.nonce} (replay/reorder)"

        sender_balance = self.balances.get(tx.sender, 0)
        if tx.amount <= 0:
            return False, "Invalid amount: must be positive"
        if sender_balance < tx.amount:
            return False, f"Overdraft: balance {sender_balance} < transfer amount {tx.amount}"

        return True, "Valid"

    def apply_tx(self, tx: Transaction) -> bool:
        """Apply transaction to balances and nonces if valid."""
        valid, _ = self.validate_tx(tx)
        if not valid:
            return False

        self.balances[tx.sender] -= tx.amount
        self.balances[tx.recipient] = self.balances.get(tx.recipient, 0) + tx.amount
        self.nonces[tx.sender] = tx.nonce
        return True

    def apply_block(self, block: Block) -> Tuple[bool, str]:
        """
        Apply a committed block to the state machine.
        Validates transactions, applies state updates, and verifies state root.
        """
        if self.chain:
            expected_prev = self.chain[-1].hash
            if block.prev_hash != expected_prev:
                return False, f"Broken chain link: expected prev_hash {expected_prev}, got {block.prev_hash}"
            if block.height != self.chain[-1].height + 1:
                return False, f"Height gap: expected {self.chain[-1].height + 1}, got {block.height}"

        # Apply transactions sequentially
        for tx in block.txs:
            # Note: Deliberately invalid synthetic transactions are skipped or rejected
            valid, reason = self.validate_tx(tx)
            if valid:
                self.apply_tx(tx)

        computed_state_root = self.compute_state_root()
        if block.state_root and block.state_root != computed_state_root:
            return False, f"State-root mismatch at height {block.height}: expected {block.state_root}, got {computed_state_root}"

        self.chain.append(block)
        return True, "OK"
