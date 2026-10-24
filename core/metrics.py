"""
Trinetra Metrics Engine & Resilience Score Calculator
Computes real-time confirmation latency (p50, p95), 1s sliding window TPS,
MTTR, election churn, availability, network message efficiency,
and the certified 0-100 Resilience Score with published transparent formula.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import time
import math


@dataclass
class LatencyRecord:
    submit_time: float
    commit_time: float
    duration_ms: float


class MetricsEngine:
    def __init__(self, clock: Any, baseline_msgs_per_tx: float = 12.0):
        self.clock = clock
        self.baseline_msgs_per_tx = baseline_msgs_per_tx

        # Latency samples (ms)
        self.latency_samples: List[float] = []

        # Commit timeline for throughput (list of timestamps)
        self.commit_timestamps: List[float] = []

        # Fault tracking for MTTR
        self.last_fault_time: Optional[float] = None
        self.recovery_times: List[float] = []  # In seconds

        # Election tracking
        self.election_starts: List[float] = []
        self.election_durations: List[float] = []
        self._current_election_start: Optional[float] = None

        # Workload and availability tracking
        self.workload_active: bool = False
        self.workload_start_time: float = 0.0
        self.total_committed_txs: int = 0
        self.total_messages_sent: int = 0

        # Pre-calculated 500ms windows
        self.window_size_sec: float = 0.5
        self.active_500ms_windows: int = 0
        self.successful_500ms_windows: int = 0
        self._last_window_idx: int = -1

    def record_fault_injected(self) -> None:
        """Mark start of a failure injection (crash, partition, netem)."""
        self.last_fault_time = self.clock.t

    def record_election_started(self) -> None:
        """Track start of an election for churn and election duration."""
        self.election_starts.append(self.clock.t)
        self._current_election_start = self.clock.t

    def record_leader_elected(self) -> None:
        """Track completion of election."""
        if self._current_election_start is not None:
            duration = max(0.001, self.clock.t - self._current_election_start)
            self.election_durations.append(duration)
            self._current_election_start = None

    def record_commit(self, tx_count: int, client_submit_timestamps: Optional[List[float]] = None) -> None:
        """Record committed block with transaction count and confirmation latencies."""
        now = self.clock.t
        self.total_committed_txs += tx_count

        for _ in range(tx_count):
            self.commit_timestamps.append(now)

        if client_submit_timestamps:
            for submit_t in client_submit_timestamps:
                latency_ms = max(0.5, (now - submit_t) * 1000.0)
                self.latency_samples.append(latency_ms)

        # MTTR tracking
        if self.last_fault_time is not None:
            recovery_sec = max(0.01, now - self.last_fault_time)
            self.recovery_times.append(recovery_sec)
            self.last_fault_time = None

        # Availability 500ms bucket update
        if self.workload_active:
            window_idx = int(now / self.window_size_sec)
            if window_idx > self._last_window_idx:
                self._last_window_idx = window_idx
                self.successful_500ms_windows += 1

    def update_workload_state(self, active: bool, messages_sent: int) -> None:
        self.workload_active = active
        self.total_messages_sent = messages_sent
        now = self.clock.t
        if active and self.workload_start_time == 0.0:
            self.workload_start_time = now

        if active:
            total_elapsed = max(0.1, now - self.workload_start_time)
            self.active_500ms_windows = max(1, int(total_elapsed / self.window_size_sec))

    def get_throughput_1s(self) -> float:
        """Committed transactions in sliding 1-second window."""
        now = self.clock.t
        threshold = now - 1.0
        # Prune older than 5 seconds
        while self.commit_timestamps and self.commit_timestamps[0] < (now - 5.0):
            self.commit_timestamps.pop(0)

        recent = sum(1 for t in self.commit_timestamps if t >= threshold)
        return float(recent)

    def get_latencies(self) -> Tuple[float, float]:
        """Compute (p50, p95) confirmation latency in milliseconds."""
        if not self.latency_samples:
            return 24.0, 48.0  # Default initial baseline
        # Keep last 500 samples
        samples = sorted(self.latency_samples[-500:])
        n = len(samples)
        p50 = samples[int(n * 0.50)]
        p95 = samples[min(n - 1, int(n * 0.95))]
        return p50, p95

    def get_mttr_ms(self) -> float:
        """Mean Time to Recover in milliseconds."""
        if not self.recovery_times:
            return 350.0  # Healthy default
        avg_sec = sum(self.recovery_times) / len(self.recovery_times)
        return avg_sec * 1000.0

    def get_election_time_ms(self) -> float:
        """Average election duration in milliseconds."""
        if not self.election_durations:
            return 120.0
        return (sum(self.election_durations) / len(self.election_durations)) * 1000.0

    def get_churn_per_min(self) -> float:
        """Elections started per minute."""
        now = self.clock.t
        one_min_ago = now - 60.0
        recent = sum(1 for t in self.election_starts if t >= one_min_ago)
        elapsed_min = max(0.1, now / 60.0)
        return float(recent) if now >= 60.0 else float(recent / elapsed_min)

    def get_availability_ratio(self) -> float:
        """Share of 500ms time windows with at least 1 commit."""
        if self.active_500ms_windows <= 0:
            return 1.0
        ratio = self.successful_500ms_windows / max(1, self.active_500ms_windows)
        return max(0.0, min(1.0, ratio))

    def get_message_cost(self) -> float:
        """Messages sent per committed transaction."""
        if self.total_committed_txs <= 0:
            return self.baseline_msgs_per_tx
        return self.total_messages_sent / self.total_committed_txs

    def compute_resilience_score(self, has_safety_violation: bool) -> Dict[str, Any]:
        """
        Published Transparent Formula:
        Safety gate: any fork or state-root mismatch gives score 0 and grade F.
        score = 100 * (0.45*availability + 0.25*recovery + 0.20*stability + 0.10*efficiency)
        """
        if has_safety_violation:
            return {
                "score": 0.0,
                "grade": "F",
                "gate_passed": False,
                "components": {
                    "availability": 0.0,
                    "recovery": 0.0,
                    "stability": 0.0,
                    "efficiency": 0.0
                },
                "formula": "SAFETY_GATE_TRIGGERED: State split or fork detected. Resilience zeroed out."
            }

        # 1. Availability component [0, 1]
        availability = self.get_availability_ratio()

        # 2. Recovery component: clamp(1 - MTTR/5s, 0, 1)
        mttr_sec = self.get_mttr_ms() / 1000.0
        recovery = max(0.0, min(1.0, 1.0 - (mttr_sec / 5.0)))

        # 3. Stability component: 1 - min(1, elections_per_min / 10.0)
        churn = self.get_churn_per_min()
        stability = max(0.0, min(1.0, 1.0 - (churn / 10.0)))

        # 4. Efficiency component: clamp(baseline / actual, 0, 1)
        msgs_per_tx = self.get_message_cost()
        efficiency = max(0.0, min(1.0, self.baseline_msgs_per_tx / max(1.0, msgs_per_tx)))

        raw_score = 100.0 * (
            0.45 * availability +
            0.25 * recovery +
            0.20 * stability +
            0.10 * efficiency
        )
        score = round(max(0.0, min(100.0, raw_score)), 1)

        if score >= 90.0:
            grade = "A"
        elif score >= 80.0:
            grade = "B"
        elif score >= 65.0:
            grade = "C"
        elif score >= 50.0:
            grade = "D"
        else:
            grade = "F"

        return {
            "score": score,
            "grade": grade,
            "gate_passed": True,
            "components": {
                "availability": round(availability, 3),
                "recovery": round(recovery, 3),
                "stability": round(stability, 3),
                "efficiency": round(efficiency, 3)
            },
            "formula": "Score = 100 * (0.45*Avail + 0.25*Recov + 0.20*Stab + 0.10*Eff)"
        }

    def get_snapshot(self, has_safety_violation: bool) -> Dict[str, Any]:
        """Produce full metrics dictionary for WebSocket and REST."""
        p50, p95 = self.get_latencies()
        score_data = self.compute_resilience_score(has_safety_violation)
        return {
            "tps": round(self.get_throughput_1s(), 1),
            "p50_ms": round(p50, 1),
            "p95_ms": round(p95, 1),
            "mttr_ms": round(self.get_mttr_ms(), 1),
            "election_time_ms": round(self.get_election_time_ms(), 1),
            "churn_per_min": round(self.get_churn_per_min(), 1),
            "availability_pct": round(self.get_availability_ratio() * 100.0, 1),
            "msgs_per_tx": round(self.get_message_cost(), 2),
            "total_commits": self.total_committed_txs,
            "resilience": score_data
        }
