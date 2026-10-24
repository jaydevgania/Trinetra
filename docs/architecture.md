# Trinetra Chaos Console: System Architecture & Engineering Blueprint

> **Team Sentinel Ark | Innovise 2026 Round 2 | Blockchain PS3: Adaptive Consensus Under Network Failures and Malicious Validators**

---

## 1. Executive Summary & One-Line Pitch

> **"Trinetra is a chaos-testing and resilience certification console for permissioned blockchains. Consortium operators (banks, supply-chain networks, CBDC pilots) break their validator network on purpose, observe consensus react in real time, and export a cryptographically certified resilience report before deploying to production."**

The platform is named **Trinetra** ("Three Eyes"):
1. **Observe (Live Monitoring)**: 10 Hz real-time state streaming, animated packet topology, and plain-English live narration.
2. **Disrupt (Failure Injection)**: Dynamic crash failover, WAN latency storms, packet drops, asymmetric network splits, and Byzantine equivocation.
3. **Verify (Safety & Integrity Auditing)**: Continuous checking of election safety, log matching, chain link integrity, fork detection, and state-root agreement.

---

## 2. Core Architecture & Component Diagram

```
+--------------------------------------------------------------------------+
|                     Browser Dashboard (web/)                             |
|  Network View | Chaos Deck | Charts | Ledger Heat Grid | Narrator | Trace|
+-----------------------------------^--------------------------------------+
                                    | REST (JSON) + WebSocket (10 Hz)
+-----------------------------------v--------------------------------------+
|                     API Layer (FastAPI, api/)                            |
|  /workload  /chaos/*  /mode  /geo  /benchmark/run  /monkey/run  /metrics |
+-----------------------------------^--------------------------------------+
|                     Cluster Controller (core/cluster.py)                 |
|  Orchestrates clock, network, 5 validators, workload, invariants, metrics|
+---------+------------+-------------+--------------+--------------+-------+
|  Clock  | SimNetwork | Validator x5| Invariants / |   Metrics    | Tracer|
| (pynacl | latency,   | Raft state  | Consistency  |   Engine     | wire- |
| discrete| drop, dup, | machine +   | checker      | tps, p50/p95 | shark |
| events) | partitions | byzantine   | (fork, root) | score (A-F)  | ring  |
+---------+------------+------+------+--------------+--------------+-------+
                              |
               Ledger (hash chain) + Ed25519 signatures
                 + Binary Merkle Trees + Token Ledger
```

---

## 3. Mathematical Foundations

### 3.1 Adaptive Consensus Timers (Jacobson/Karels)
During WAN latency storms or cross-regional network jitter, static timers (150–300 ms) trigger spurious elections, causing throughput collapse and severe leader churn.

Trinetra implements adaptive timers:
1. **Leader RTT Tracking**: From `AppendEntries` acknowledgments:
   $$\text{SRTT} = 0.875 \times \text{SRTT} + 0.125 \times \text{RTT}$$
   $$\text{RTTVAR} = 0.75 \times \text{RTTVAR} + 0.25 \times |\text{SRTT} - \text{RTT}|$$
   $$\text{RTO} = \text{SRTT} + 4 \times \text{RTTVAR}$$
   $$\text{Leader Heartbeat} = \text{clamp}(\text{RTO}, 50\text{ ms}, 1000\text{ ms})$$

2. **Follower Inter-Arrival Jitter Tracking**:
   $$\mu = 0.875 \times \mu + 0.125 \times \Delta t$$
   $$\text{dev} = 0.75 \times \text{dev} + 0.25 \times |\mu - \Delta t|$$
   $$\text{Election Base} = \text{clamp}(\mu + 6 \times \text{dev}, 150\text{ ms}, 3000\text{ ms})$$
   $$\text{Timeout} \in [\text{base}, 2 \times \text{base}]$$

### 3.2 Published Transparent Resilience Score Formula
To eliminate black-box ambiguity, the platform publishes and enforces this formula:
* **Safety Gate**: Any state fork or state-root mismatch immediately forces:
  $$\text{Score} = 0, \quad \text{Grade} = \text{"F"}$$
* **Otherwise**:
  $$\text{Score} = 100 \times (0.45 \times \text{Availability} + 0.25 \times \text{Recovery} + 0.20 \times \text{Stability} + 0.10 \times \text{Efficiency})$$
  * $\text{Availability} \in [0, 1]$: Share of 500 ms windows with at least 1 commit.
  * $\text{Recovery} = \text{clamp}(1 - \text{MTTR}/5.0\text{s}, 0, 1)$.
  * $\text{Stability} = 1 - \min(1, \text{elections\_per\_minute}/10.0)$.
  * $\text{Efficiency} = \text{clamp}(\text{baseline\_msgs\_per\_tx}/\text{actual\_msgs\_per\_tx}, 0, 1)$.
* **Grades**: A (90+), B (80+), C (65+), D (50+), F (<50).

---

## 4. Byzantine Fault Handling: Equivocation Defense

### Attack Vector
A malicious leader signs Block $A$ for followers $\{N1, N2\}$ and Block $B$ for $\{N3, N4\}$ at the same height $H$. In plain Raft, both groups reach a majority (3 of 5) $\implies$ **Ledger Fork**.

### Tier 2: Cryptographic Detection & Quarantine
* Leader signs every block header $(term, index, entry\_hash)$.
* Followers gossip signed headers to all peers.
* On detecting two distinct hashes signed for $(term, index)$, honest followers form an `EquivProof(offender, term, index, hash_a, sig_a, hash_b, sig_b)`.
* Proof is broadcast; offender is quarantined (trust score 0, messages dropped).

### Tier 3: Hardened Mode (Zero-Fork Echo Quorum)
* Followers broadcast signed `Echo(term, index, hash, leader_sig)`.
* Commit requires support from at least **4 of 5** distinct signers.
* Since honest nodes echo only 1 block per slot, neither Block $A$ nor Block $B$ can gather 4 echoes (each receives at most 3).
* **Result**: Conflicting proposals stall before commit; proof is gathered; leader is quarantined; **0 state forks occur**.
