# 🧿 Trinetra Chaos Console

[![Consensus Tests](https://img.shields.io/badge/tests-15%2F15%20passing-brightgreen)](tests/)
[![Resilience CI](https://img.shields.io/badge/resilience%20score-A%20(87.5%2F100)-blue)](bench/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.115-009688)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **Team Sentinel Ark | Innovise 2026 Round 2 | Blockchain PS3: Adaptive Consensus Under Network Failures and Malicious Validators**

**Trinetra** is a mission-control chaos testing console and resilience certification platform for permissioned blockchains (banking consortia, supply chain tracking, CBDC pilots).

Consortium operators break their validator network on purpose, observe consensus dynamics in real-time at 10 Hz, and export an audited **Resilience Report** with a published mathematical scoring formula before deploying to production.

---

## ⚡ Quickstart

### 1. Local Run (Native)
```bash
# Clone and enter workspace
git clone https://github.com/sentinel-ark/trinetra.git
cd trinetra

# Install dependencies
pip install -r requirements.txt

# Launch FastAPI & WebSocket Server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

### 2. Docker Run
```bash
docker compose up --build
```

---

## 🏆 Advanced Features Built (Top 1 Roadmap)

| Feature | Description | Status |
| :--- | :--- | :---: |
| **A1. Live Narrator** | Real-time plain-English commentary explaining consensus transitions, elections, and failures as they happen. | ✅ Built |
| **A2. Demo Autopilot** | One-button 5-minute automated pitch demo running through 6 choreographed chapters with narration and fail-safe recovery. | ✅ Built |
| **A3. Published Resilience Score** | Transparent mathematical 0–100 score ($A$ to $F$) with strict safety gating (any fork $\to$ Score 0). Exportable as HTML/JSON report. | ✅ Built |
| **A4. Pause, Step & Replay** | Single-step 50ms discrete-event advancement, playback pausing, and variable speed simulation (0.5x to 5x). | ✅ Built |
| **A5. Geo-Latency Presets** | Instant switching between Local DC (1ms), Regional WAN (Mumbai, Pune, Hyderabad: 20ms), and Global WAN (Mumbai, Frankfurt, Virginia: 120ms). | ✅ Built |
| **A6. Merkle Roots & Proofs** | Every block header includes a SHA-256 binary Merkle tree root. Interactive transaction audit proofs verifiable in $O(\log N)$. | ✅ Built |
| **A7. Message Tracer** | Wireshark-style interactive RPC inspector capturing AppendEntries, RequestVote, PreVote, and Echo packets with filters and JSON payload viewing. | ✅ Built |
| **A8. Monkey Mode Fuzzing** | Jepsen-style chaos engine running 1,000 randomized fault schedules in virtual time to prove 0 safety violations. | ✅ Built |
| **A9. Prometheus & Grafana** | Standard `/metrics` exporter endpoint and bundled `docs/grafana_dashboard.json`. | ✅ Built |
| **A10. CI Mode Gate** | Automated CLI runner (`python -m bench.run_bench --scenario latency_storm --fail-under 80`) with bundled GitHub Actions workflow. | ✅ Built |
| **A11. Validator Trust Scores** | Dynamic per-node trust scoring (0–100%) reflecting responsiveness, lag, and equivocation evidence. | ✅ Built |
| **A12. Tier 3 Hardened Defense** | 4-of-5 Echo Quorum mode intercepting Byzantine dual-proposal attacks with **0 forks**. | ✅ Built |

---

## 🔬 Mathematical Formulas

### Published Resilience Score Formula
$$\text{Score} = 100 \times \left(0.45 \times \text{Availability} + 0.25 \times \text{Recovery} + 0.20 \times \text{Stability} + 0.10 \times \text{Efficiency}\right)$$
* **Safety Gate**: If Fork Detected $\implies$ $\text{Score} = 0$, $\text{Grade} = \text{"F"}$.
* $\text{Availability}$: Share of 500ms time windows with committed blocks.
* $\text{Recovery}$: $\text{clamp}(1 - \text{MTTR}/5.0\text{s}, 0, 1)$.
* $\text{Stability}$: $1 - \min(1, \text{elections\_per\_minute}/10.0)$.
* $\text{Efficiency}$: $\text{clamp}(\text{baseline\_msgs\_per\_tx}/\text{actual\_msgs\_per\_tx}, 0, 1)$.

### Jacobson/Karels Adaptive Timers
$$\text{SRTT} = 0.875 \times \text{SRTT} + 0.125 \times \text{RTT}$$
$$\text{RTTVAR} = 0.75 \times \text{RTTVAR} + 0.25 \times |\text{SRTT} - \text{RTT}|$$
$$\text{RTO} = \text{SRTT} + 4 \times \text{RTTVAR}$$
$$\text{Leader Heartbeat} = \text{clamp}(\text{RTO}, 50\text{ ms}, 1000\text{ ms})$$
$$\text{Follower Election Base} = \text{clamp}(\mu + 6 \times \text{dev}, 150\text{ ms}, 3000\text{ ms})$$

---

## 🧪 Testing & Verification

Run the comprehensive unit and integration test suite:
```bash
python -m pytest tests -v
```
All 15 tests verify:
1. `test_election`: Exactly one leader elected; seamless failover on leader crash.
2. `test_replication`: Cluster converges to identical log hashes and state roots.
3. `test_partition`: Minority stalls safely; Pre-Vote eliminates healing disruptions.
4. `test_adaptive`: Dynamic timers eliminate spurious leader churn in latency storms.
5. `test_equivocation`: Plain Raft detects and quarantines; Hardened mode prevents fork (0 forks).
6. `test_ledger`: Ed25519 signature checks, nonce monotonic replay defense, and overdraft protection.
7. `test_monkey`: 1,000 random fault schedules evaluated with zero invariant breaches.

---

## 📈 Benchmark CLI Execution
```bash
python -m bench.run_bench --scenario latency_storm --fail-under 80
```
**Sample Benchmark Output:**
```
=================================================================
TRINETRA BENCHMARK RESULTS (LATENCY_STORM)
=================================================================
Adaptive Mode Score : 87.5 / 100  (Median churn: 3.0/min, p95: 48.0ms)
Static Mode Score   : 57.8 / 100  (Median churn: 618.0/min, p95: 48.0ms)
=================================================================
[PASS] Adaptive resilience score 87.5 meets CI gate (>= 80.0)!
```

---

## 📂 Repository Structure
```
trinetra/
├── core/                  # Core consensus, simulation, and crypto engine
│   ├── clock.py           # Discrete-event simulation clock
│   ├── network.py         # SimNetwork (latency, jitter, netem, partitions)
│   ├── crypto.py          # Ed25519 (PyNaCl), SHA-256, and MerkleTree
│   ├── ledger.py          # Blocks, transactions, and token state machine
│   ├── raft.py            # Raft node state machine (Follower, Candidate, Leader)
│   ├── adaptive.py        # Jacobson/Karels RTT estimator & Pre-Vote controller
│   ├── byzantine.py       # EquivProof detection, gossip, and 4-of-5 Echo Quorum
│   ├── invariants.py      # Consistency checker (election, fork, state-root)
│   ├── metrics.py         # TPS, latency, MTTR, and Resilience Score
│   ├── workload.py        # Synthetic token transfer transaction generator
│   ├── narrator.py        # Real-time plain-English Live Narrator
│   ├── tracer.py          # Wireshark-style RPC packet tracer
│   ├── autopilot.py       # 1-Button 5-minute choreographed demo controller
│   ├── monkey.py          # Jepsen-style random chaos fuzzer
│   └── scenarios.py       # Pre-built chaos scenarios (crash, storm, partition)
├── api/                   # REST & WebSocket API layer
│   ├── main.py            # FastAPI app & static file mounting
│   ├── ws.py              # 10 Hz WebSocket connection manager
│   ├── models.py          # Pydantic request models
│   └── prometheus.py      # Prometheus /metrics exposition formatter
├── web/                   # Dark Obsidian Eye Dashboard UI
│   ├── index.html         # Single-page mission control layout
│   ├── style.css          # Design system CSS tokens and animations
│   ├── app.js             # Canvas topology, Chart.js, and WebSocket client
│   └── vendor/            # Bundled local Chart.js (offline fail-safe)
├── bench/                 # Benchmarking and reporting suite
│   ├── run_bench.py       # Static vs Adaptive comparative CLI
│   └── report.py          # Standalone HTML/JSON certification report
├── tests/                 # Comprehensive pytest test suite
├── docs/                  # Architectural documentation & demo scripts
│   ├── architecture.md    # Detailed mathematical specification
│   ├── demo_script.md     # 5-minute winning pitch script & judge Q&A
│   └── grafana_dashboard.json # Grafana monitoring dashboard JSON
├── .github/workflows/     # CI/CD workflows
│   └── resilience-gate.yml# GitHub Actions resilience gate
├── Dockerfile             # Container definition
├── docker-compose.yml     # Multi-platform deployment
├── Makefile               # Quick developer shortcuts
└── requirements.txt       # Python dependencies
```

---

## 🎯 Innovise 2026 Presentation Highlights
1. **The crown moves**: Watch the golden crown float from crashed leader $N0$ to newly elected leader $N1$ with MTTR $< 400$ ms.
2. **The color split**: In Plain Raft equivocation, the Ledger Heat Grid visually forks into two different colors at height $H$.
3. **The zero-fork defense**: Under Hardened Mode, the 4-of-5 Echo Quorum halts the equivocation before commit, quarantining the offender with **zero forks**.
4. **The proof on paper**: Generate and download the standalone resilience audit report with one click.
