"""
Trinetra Workload Generator
Generates realistic signed token transfer transactions at configurable TPS
across synthetic accounts, with an intentional fraction of malformed
transactions to test state-machine rejection integrity.
"""
import random
from typing import List, Dict, Tuple, Optional, Callable, Any
from core.crypto import KeyPair, sha256_hash
from core.ledger import Transaction


class WorkloadGenerator:
    def __init__(
        self,
        clock: Any,
        account_count: int = 20,
        initial_balance: int = 50_000,
        rng_seed: int = 42
    ):
        self.clock = clock
        self.rng = random.Random(rng_seed)
        self.account_count = account_count
        self.initial_balance = initial_balance

        # Generate deterministic synthetic accounts
        self.keypairs: List[KeyPair] = []
        self.genesis_balances: Dict[str, int] = {}
        self.account_nonces: Dict[str, int] = {}

        for i in range(account_count):
            seed_bytes = f"trinetra_synthetic_account_seed_{i}".encode('utf-8')
            kp = KeyPair(seed_bytes)
            self.keypairs.append(kp)
            self.genesis_balances[kp.public_key_hex] = initial_balance
            self.account_nonces[kp.public_key_hex] = 0

        # Workload state
        self.is_running: bool = False
        self.target_tps: float = 100.0
        self.invalid_pct: float = 2.0  # 2% invalid transactions
        self.submit_callback: Optional[Callable[[List[Transaction]], None]] = None
        self.timer_handle: Optional[int] = None

        # Statistics
        self.txs_generated: int = 0
        self.invalid_txs_injected: int = 0

    def start(self, target_tps: float = 100.0, invalid_pct: float = 2.0) -> None:
        """Start paced transaction generation."""
        self.target_tps = max(1.0, target_tps)
        self.invalid_pct = max(0.0, min(100.0, invalid_pct))
        self.is_running = True
        self._schedule_next_batch()

    def stop(self) -> None:
        """Stop workload generator."""
        self.is_running = False
        if self.timer_handle is not None:
            self.clock.cancel(self.timer_handle)
            self.timer_handle = None

    def _schedule_next_batch(self) -> None:
        if not self.is_running:
            return

        # Pacing: Generate batches every 50ms (20 times per second)
        interval_sec = 0.050
        batch_size = max(1, int(self.target_tps * interval_sec))

        batch = self.generate_batch(batch_size)
        if self.submit_callback and batch:
            self.submit_callback(batch)

        self.timer_handle = self.clock.call_later(interval_sec, self._schedule_next_batch)

    def generate_batch(self, count: int) -> List[Transaction]:
        """Generate a batch of signed transactions."""
        batch: List[Transaction] = []
        for _ in range(count):
            tx = self._create_single_tx()
            batch.append(tx)
            self.txs_generated += 1
        return batch

    def _create_single_tx(self) -> Transaction:
        # Pick random sender and distinct recipient
        sender_idx = self.rng.randint(0, self.account_count - 1)
        recipient_idx = (sender_idx + self.rng.randint(1, self.account_count - 1)) % self.account_count

        sender_kp = self.keypairs[sender_idx]
        recipient_kp = self.keypairs[recipient_idx]
        sender_pubkey = sender_kp.public_key_hex
        recipient_pubkey = recipient_kp.public_key_hex

        # Nonce tracking
        self.account_nonces[sender_pubkey] += 1
        nonce = self.account_nonces[sender_pubkey]
        amount = self.rng.randint(10, 250)

        tx = Transaction(
            sender=sender_pubkey,
            recipient=recipient_pubkey,
            amount=amount,
            nonce=nonce,
            timestamp=self.clock.t
        )

        # Deliberate invalid transaction injection
        is_invalid = (self.rng.random() * 100.0) < self.invalid_pct
        if is_invalid:
            self.invalid_txs_injected += 1
            corruption_type = self.rng.choice(["bad_sig", "bad_nonce", "overdraft"])
            if corruption_type == "bad_sig":
                tx.sign(sender_kp)
                tx.sig = "0" * 128  # Corrupted signature
            elif corruption_type == "bad_nonce":
                tx.nonce = max(1, nonce - 5)  # Replay or old nonce
                tx.sign(sender_kp)
            elif corruption_type == "overdraft":
                tx.amount = 999_999_999  # Exceeds balance
                tx.sign(sender_kp)
        else:
            tx.sign(sender_kp)

        return tx
