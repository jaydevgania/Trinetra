"""
Unit Tests for Trinetra Ledger, Cryptography, and Token State Machine
"""
import pytest
from core.crypto import KeyPair, sha256_hash, MerkleTree
from core.ledger import Transaction, Block, TokenLedger


def test_keypair_signing_and_verification():
    kp = KeyPair(b"test_seed_keypair_123")
    msg = "trinetra_test_message"
    sig = kp.sign(msg)
    assert KeyPair.verify(kp.public_key_hex, msg, sig) is True
    # Tampered message should fail
    assert KeyPair.verify(kp.public_key_hex, "tampered_message", sig) is False


def test_merkle_tree_inclusion_proof():
    leaves = [sha256_hash(f"tx_data_{i}") for i in range(8)]
    tree = MerkleTree(leaves)

    for idx in range(len(leaves)):
        proof = tree.get_proof(idx)
        assert len(proof) == 3  # log2(8) = 3
        verified = MerkleTree.verify_proof(leaves[idx], proof, tree.root)
        assert verified is True

    # Tampered leaf should fail verification
    proof_0 = tree.get_proof(0)
    assert MerkleTree.verify_proof("fake_hash", proof_0, tree.root) is False


def test_ledger_valid_transactions():
    alice = KeyPair(b"alice_seed")
    bob = KeyPair(b"bob_seed")
    ledger = TokenLedger(genesis_accounts={alice.public_key_hex: 1000, bob.public_key_hex: 500})

    tx = Transaction(
        sender=alice.public_key_hex,
        recipient=bob.public_key_hex,
        amount=200,
        nonce=1,
        timestamp=1.0
    )
    tx.sign(alice)

    valid, reason = ledger.validate_tx(tx)
    assert valid is True
    assert ledger.apply_tx(tx) is True
    assert ledger.balances[alice.public_key_hex] == 800
    assert ledger.balances[bob.public_key_hex] == 700
    assert ledger.nonces[alice.public_key_hex] == 1


def test_ledger_rejection_overdraft():
    alice = KeyPair(b"alice_seed_2")
    bob = KeyPair(b"bob_seed_2")
    ledger = TokenLedger(genesis_accounts={alice.public_key_hex: 100})

    tx = Transaction(
        sender=alice.public_key_hex,
        recipient=bob.public_key_hex,
        amount=500,  # Overdraft
        nonce=1
    )
    tx.sign(alice)

    valid, reason = ledger.validate_tx(tx)
    assert valid is False
    assert "Overdraft" in reason


def test_ledger_rejection_replay_nonce():
    alice = KeyPair(b"alice_seed_3")
    bob = KeyPair(b"bob_seed_3")
    ledger = TokenLedger(genesis_accounts={alice.public_key_hex: 1000})

    # Apply tx 1
    tx1 = Transaction(sender=alice.public_key_hex, recipient=bob.public_key_hex, amount=100, nonce=1)
    tx1.sign(alice)
    ledger.apply_tx(tx1)

    # Replay tx 1
    valid, reason = ledger.validate_tx(tx1)
    assert valid is False
    assert "Bad nonce" in reason


def test_ledger_rejection_corrupted_signature():
    alice = KeyPair(b"alice_seed_4")
    bob = KeyPair(b"bob_seed_4")
    ledger = TokenLedger(genesis_accounts={alice.public_key_hex: 1000})

    tx = Transaction(sender=alice.public_key_hex, recipient=bob.public_key_hex, amount=100, nonce=1)
    tx.sign(alice)
    tx.sig = "0" * 128  # Invalidate signature

    valid, reason = ledger.validate_tx(tx)
    assert valid is False
    assert "Invalid cryptographic signature" in reason
