"""
Trinetra Cryptographic Primitives & Merkle Trees
Implements Ed25519 digital signatures via PyNaCl, canonical JSON hashing,
and binary Merkle trees with cryptographic inclusion proofs.
"""
import hashlib
import json
from typing import Dict, List, Tuple, Any, Optional
import nacl.signing
import nacl.encoding


def canonical_json(obj: Any) -> str:
    """Serialize dictionary/object to deterministic canonical JSON string."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def sha256_hash(data: str) -> str:
    """Return 64-char hex SHA-256 digest of input UTF-8 string."""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def sha256_combine(left: str, right: str) -> str:
    """Combine two hex hashes deterministically."""
    return hashlib.sha256((left + right).encode('utf-8')).hexdigest()


class KeyPair:
    """Ed25519 KeyPair wrapper for nodes and client accounts."""
    def __init__(self, seed: Optional[bytes] = None):
        if seed:
            # Deterministic 32-byte seed
            if len(seed) < 32:
                seed = hashlib.sha256(seed).digest()
            elif len(seed) > 32:
                seed = seed[:32]
            self._signing_key = nacl.signing.SigningKey(seed)
        else:
            self._signing_key = nacl.signing.SigningKey.generate()
        self._verify_key = self._signing_key.verify_key

    @property
    def public_key_hex(self) -> str:
        return self._verify_key.encode(encoder=nacl.encoding.HexEncoder).decode('utf-8')

    def sign(self, message: str) -> str:
        """Sign a message and return the hex-encoded Ed25519 signature."""
        signed = self._signing_key.sign(message.encode('utf-8'))
        return signed.signature.hex()

    @staticmethod
    def verify(public_key_hex: str, message: str, signature_hex: str) -> bool:
        """Verify an Ed25519 signature against the public key and message."""
        try:
            verify_key = nacl.signing.VerifyKey(public_key_hex, encoder=nacl.encoding.HexEncoder)
            sig_bytes = bytes.fromhex(signature_hex)
            verify_key.verify(message.encode('utf-8'), sig_bytes)
            return True
        except Exception:
            return False


class MerkleTree:
    """
    Binary Merkle Tree for transaction sets.
    Generates cryptographic inclusion proofs that verify in O(log N).
    """
    def __init__(self, tx_hashes: List[str]):
        self.tx_hashes = list(tx_hashes)
        if not self.tx_hashes:
            self.root = sha256_hash("GENESIS_EMPTY_TREE")
            self.layers: List[List[str]] = [[self.root]]
        else:
            self.layers = self._build_tree(self.tx_hashes)
            self.root = self.layers[-1][0]

    def _build_tree(self, leaves: List[str]) -> List[List[str]]:
        layers = [leaves]
        current = leaves
        while len(current) > 1:
            next_layer = []
            for i in range(0, len(current), 2):
                left = current[i]
                if i + 1 < len(current):
                    right = current[i + 1]
                else:
                    right = left  # Duplicate odd leaf as per standard Bitcoin/Ethereum convention
                next_layer.append(sha256_combine(left, right))
            layers.append(next_layer)
            current = next_layer
        return layers

    def get_proof(self, tx_index: int) -> List[Dict[str, str]]:
        """
        Generate inclusion proof for the leaf at `tx_index`.
        Returns list of { "position": "left" | "right", "hash": str }.
        """
        if tx_index < 0 or tx_index >= len(self.tx_hashes):
            return []

        proof: List[Dict[str, str]] = []
        idx = tx_index

        for layer in self.layers[:-1]:
            is_right = (idx % 2 == 1)
            sibling_idx = idx - 1 if is_right else idx + 1
            if sibling_idx < len(layer):
                sibling_hash = layer[sibling_idx]
            else:
                sibling_hash = layer[idx]

            proof.append({
                "position": "left" if is_right else "right",
                "hash": sibling_hash
            })
            idx //= 2

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: List[Dict[str, str]], expected_root: str) -> bool:
        """Verify that leaf_hash leads to expected_root via proof path."""
        current = leaf_hash
        for step in proof:
            sibling = step["hash"]
            pos = step["position"]
            if pos == "left":
                current = sha256_combine(sibling, current)
            else:
                current = sha256_combine(current, sibling)
        return current == expected_root
