# Trinetra 5-Minute Winning Demo Script

> **Time Target**: 5 minutes pitch + 2 minutes spare for 3 minutes Q&A.  
> **Backup Plan**: Use the 1-Click Autopilot button if you want hands-free delivery.

---

## Act 1: The Hook (0:00 - 0:30)
* **Talk Track**:  
  *"Judges, consortium blockchains fail in ways nobody tests until they hit production. A bank in Frankfurt and a validator in Mumbai experience unexpected WAN jitter, and the entire payment corridor stalls from leader churn.  
  Trinetra solves this: it is the chaos-engineering and resilience certification console for permissioned blockchains. We break validator networks on purpose, observe consensus live, and certify resilience before going live."*
* **Visual**: Show Obsidian Eye dashboard running steady state with 5 nodes, blue heartbeat particles flowing, and TPS at ~150.

---

## Act 2: Normal Operation & Geography (0:30 - 1:15)
* **Talk Track**:  
  *"We start with 5 validators across regions. Notice the Live Narrator explaining events in plain English. Each block contains Ed25519-signed token transactions and binary Merkle tree roots. All 5 nodes have identical state roots."*
* **Action**: Switch Geo preset from `DC (1ms)` to `Regional (20ms)` to `Global (120ms)`.
* **Key Point to Mention**: *"With global delays, traditional static 150-300ms timers fail. Our Jacobson/Karels adaptive RTT estimators measure propagation dynamically."*

---

## Act 3: Leader Crash & Failover (1:15 - 2:00)
* **Talk Track**:  
  *"Let's disrupt the system. I will crash our active leader right now."*
* **Action**: Click `N0` (or active leader) crash button.
* **Visual**:
  * Leader halo turns gray/red (`DOWN`).
  * Narrator: *"Node N0 was forcefully halted. Heartbeat stream terminated."*
  * Randomized timer fires, candidate starts Pre-Vote, quorum is formed, and leader crown moves to the new leader.
  * Point to MTTR: **< 400 ms failover!**
* **Action**: Click `Recover All` to show the old leader seamlessly rejoining as a Follower and catching up on the log without disrupting consensus.

---

## Act 4: Network Partition & Pre-Vote Safety (2:00 - 2:45)
* **Talk Track**:  
  *"Now we simulate an asymmetric network split: {N0, N1} vs {N2, N3, N4}."*
* **Action**: Click `Split [2 | 3]`.
* **Visual**:
  * Topology canvas displays dashed red cut line with scissor glyphs.
  * Minority {N0, N1} pauses commits safely. Majority {N2, N3, N4} maintains quorum (3 of 5) and continues committing.
* **Talk Track**:  
  *"Watch what happens when we heal the partition. In plain Raft, isolated nodes inflate their term counter and disrupt the healthy leader upon reconnection. With Trinetra Pre-Vote enabled, zero disruptions occur!"*
* **Action**: Click `Heal Network`. Notice zero leader step-down!

---

## Act 5: Byzantine Equivocation & Hardened Mode (2:45 - 3:45)
* **Talk Track**:  
  *"Now let's test malicious validators. Problem Statement 3 describes validators proposing conflicting blocks. That is equivocation."*
* **Action**: Switch to CFT Raft, click `Inject Malicious Equivocation`.
* **Visual**:
  * Red Alert Banner pops up: **"CRITICAL SAFETY VIOLATION: Ledger Fork!"**
  * Ledger Heat Grid reveals a vivid color split at the same height.
  * Narrator logs: *"Two conflicting leader signatures uncovered. Offender quarantined."*
* **Action**: Switch to `Hardened Mode` (4-of-5 Echo Quorum).
* **Talk Track**:  
  *"Under Trinetra Hardened Mode, followers must collect 4-of-5 signed echoes before committing. Because an honest node echoes only once, conflicting blocks can never reach 4 echoes. Zero forks occur!"*

---

## Act 6: Resilience Certification & Benchmark (3:45 - 4:45)
* **Action**: Click `Run 10-Seed Comparative Benchmark`.
* **Visual**:
  * Table renders: Static mode churn = ~600 elections/min vs Adaptive mode churn = ~3 elections/min!
* **Action**: Click `📥 View / Download HTML Report`.
* **Talk Track**:  
  *"Finally, consortium operators download this audit report. Notice our published mathematical formula: 0.45 availability + 0.25 recovery + 0.20 stability + 0.10 efficiency. Safety violations gate to Grade F. Today, our cluster earns Grade A!"*

---

## Act 7: Close & Business Model (4:45 - 5:00)
* **Talk Track**:  
  *"Trinetra is packaged as a SaaS resilience testing suite and a CI/CD GitHub Action that automatically fails PRs if consensus resilience drops below 80.  
  Thank you, we are now ready for your questions!"*

---

## Judge Q&A Cheat Sheet
1. **Q: Is Raft Byzantine fault tolerant?**  
   *A: Plain Raft tolerates crash faults (CFT) with $2f+1$ nodes. We demonstrate this limitation honestly, provide cryptographic equivocation detection, and introduce Hardened Mode with a 4-of-5 echo quorum for $f=1$. Full BFT (PBFT/HotStuff) is on our roadmap.*
2. **Q: Why discrete-event simulation instead of real Docker containers?**  
   *A: The problem statement requested simulation. Discrete-event simulation guarantees 100% deterministic reproducibility with fixed random seeds, sub-second 20-seed benchmarking, and millisecond-accurate latency profiling that container network namespaces cannot match.*
3. **Q: How do you prevent replay attacks on transactions?**  
   *A: Every account maintains an incrementing nonce signed with Ed25519. The leader pre-validates $nonce == last\_nonce + 1$ and followers re-validate on commit.*
