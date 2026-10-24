"""
Trinetra Adaptive Consensus Module
Implements Jacobson/Karels RTT estimation for leader heartbeats,
EWMA inter-arrival jitter tracking for followers, and Pre-Vote phase.
Prevents leader churn and election storms during WAN latency spikes.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import random


@dataclass
class RttEstimator:
    """Jacobson/Karels RTT Estimator (used by Leader per follower)."""
    srtt: float = 20.0       # Smoothed RTT (ms)
    rttvar: float = 5.0      # RTT Variance (ms)
    rto: float = 40.0        # Retransmission Timeout (ms)
    samples: int = 0

    def update(self, sample_rtt: float) -> float:
        """Update RTT metrics using Jacobson/Karels formula."""
        sample_rtt = max(0.1, sample_rtt)
        if self.samples == 0:
            self.srtt = sample_rtt
            self.rttvar = sample_rtt / 2.0
        else:
            self.rttvar = 0.75 * self.rttvar + 0.25 * abs(self.srtt - sample_rtt)
            self.srtt = 0.875 * self.srtt + 0.125 * sample_rtt

        self.rto = self.srtt + 4.0 * self.rttvar
        self.samples += 1
        return self.rto


@dataclass
class FollowerHeartbeatTracker:
    """Follower tracking of leader heartbeat inter-arrival jitter."""
    last_arrival_time: Optional[float] = None
    mu: float = 50.0         # EWMA mean inter-arrival time (ms)
    dev: float = 10.0        # EWMA deviation (ms)
    samples: int = 0

    def record_arrival(self, current_time_sec: float) -> Tuple[float, float]:
        """Record arrival of leader heartbeat and update EWMA statistics."""
        current_time_ms = current_time_sec * 1000.0
        if self.last_arrival_time is not None:
            delta_ms = max(1.0, current_time_ms - self.last_arrival_time)
            if self.samples == 0:
                self.mu = delta_ms
                self.dev = delta_ms / 4.0
            else:
                self.dev = 0.75 * self.dev + 0.25 * abs(self.mu - delta_ms)
                self.mu = 0.875 * self.mu + 0.125 * delta_ms
            self.samples += 1
        self.last_arrival_time = current_time_ms
        return self.mu, self.dev

    def calculate_election_timeout_range(self, adaptive: bool = True) -> Tuple[float, float]:
        """
        Calculate min and max election timeout in seconds.
        If adaptive=False (Static baseline): [150ms, 300ms].
        If adaptive=True: base = clamp(mu + 6*dev, 150ms, 3000ms), range [base, 2*base].
        """
        if not adaptive:
            return 0.150, 0.300

        base_ms = max(150.0, min(3000.0, self.mu + 6.0 * self.dev))
        return (base_ms / 1000.0), (2.0 * base_ms / 1000.0)


class AdaptiveController:
    """Coordinates adaptive timeouts and pre-vote decisions for a node."""
    def __init__(self, node_id: int, peers: list[int]):
        self.node_id = node_id
        self.peers = peers
        self.rtt_estimators: Dict[int, RttEstimator] = {p: RttEstimator() for p in peers}
        self.heartbeat_tracker = FollowerHeartbeatTracker()
        self.mode: str = "adaptive"  # "static" or "adaptive"
        self.prevote_enabled: bool = True

    def record_ack_rtt(self, follower_id: int, rtt_ms: float) -> None:
        if follower_id in self.rtt_estimators:
            self.rtt_estimators[follower_id].update(rtt_ms)

    def get_leader_heartbeat_interval(self) -> float:
        """
        Calculate heartbeat interval in seconds.
        Static: 50ms.
        Adaptive: clamp(max(rto over followers), 50ms, 1000ms).
        """
        if self.mode == "static":
            return 0.050

        if not self.rtt_estimators:
            return 0.050

        max_rto = max(est.rto for est in self.rtt_estimators.values())
        clamped_ms = max(50.0, min(1000.0, max_rto))
        return clamped_ms / 1000.0

    def record_heartbeat(self, current_time_sec: float) -> None:
        self.heartbeat_tracker.record_arrival(current_time_sec)

    def sample_election_timeout(self, rng: random.Random) -> float:
        """Draw randomized election timeout in seconds."""
        is_adaptive = (self.mode == "adaptive")
        t_min, t_max = self.heartbeat_tracker.calculate_election_timeout_range(is_adaptive)
        return rng.uniform(t_min, t_max)
