"""
Trinetra Scenario Library & Automated Timeline Runner
Houses pre-programmed chaos test suites specified in the Trinetra Blueprint.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional


@dataclass
class ScenarioEvent:
    time_offset_sec: float
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    narration: str = ""


@dataclass
class ScenarioDefinition:
    id: str
    name: str
    description: str
    duration_sec: float
    events: List[ScenarioEvent]


SCENARIO_LIBRARY: Dict[str, ScenarioDefinition] = {
    "baseline": ScenarioDefinition(
        id="baseline",
        name="Baseline Steady State",
        description="30 seconds steady transaction workload under standard network conditions. Verifies zero election churn and 100% agreement.",
        duration_sec=30.0,
        events=[
            ScenarioEvent(0.5, "start_workload", {"tps": 150.0}, "Initiating baseline transaction throughput."),
            ScenarioEvent(30.0, "stop_workload", {}, "Baseline run complete.")
        ]
    ),
    "leader_crash": ScenarioDefinition(
        id="leader_crash",
        name="Leader Crash & Recovery",
        description="Crashes active leader at t=10s, observes sub-second failover to new leader, restarts crashed node at t=20s to observe log sync.",
        duration_sec=25.0,
        events=[
            ScenarioEvent(0.5, "start_workload", {"tps": 150.0}, "Steady load started."),
            ScenarioEvent(5.0, "crash_leader", {}, "CRASH: Leader forcefully terminated!"),
            ScenarioEvent(12.0, "recover_crashed", {}, "RECOVER: Restarting former leader as Follower."),
            ScenarioEvent(25.0, "stop_workload", {}, "Leader crash test complete.")
        ]
    ),
    "follower_crash": ScenarioDefinition(
        id="follower_crash",
        name="Quorum Degradation (2 Crashed Followers)",
        description="Terminates 2 out of 5 validators simultaneously. Proves system maintains quorum (3 of 5) and continues committing safely.",
        duration_sec=20.0,
        events=[
            ScenarioEvent(0.5, "start_workload", {"tps": 120.0}, "Workload started."),
            ScenarioEvent(4.0, "crash_nodes", {"nodes": [3, 4]}, "Simultaneous crash of Node N3 and N4."),
            ScenarioEvent(14.0, "recover_nodes", {"nodes": [3, 4]}, "Rebooting Nodes N3 and N4."),
            ScenarioEvent(20.0, "stop_workload", {}, "Quorum recovery verified.")
        ]
    ),
    "minority_partition": ScenarioDefinition(
        id="minority_partition",
        name="Minority Partition ({0,1} vs {2,3,4})",
        description="Isolates 2 nodes for 10 seconds. Proves minority partition safely pauses without false commits, and pre-vote prevents disruption upon heal.",
        duration_sec=25.0,
        events=[
            ScenarioEvent(0.5, "start_workload", {"tps": 150.0}, "Load started."),
            ScenarioEvent(5.0, "partition", {"groups": [[0, 1], [2, 3, 4]]}, "Partition active: {N0,N1} isolated from {N2,N3,N4}."),
            ScenarioEvent(15.0, "heal", {}, "Partition healed! Full mesh restored."),
            ScenarioEvent(25.0, "stop_workload", {}, "Minority partition test concluded.")
        ]
    ),
    "no_quorum": ScenarioDefinition(
        id="no_quorum",
        name="Loss of Quorum (3 Nodes Down)",
        description="Crashes 3 validators, leaving only 2 active nodes. Validates that commits safely halt (liveness loss) without safety violations.",
        duration_sec=20.0,
        events=[
            ScenarioEvent(0.5, "start_workload", {"tps": 100.0}, "Load active."),
            ScenarioEvent(4.0, "crash_nodes", {"nodes": [2, 3, 4]}, "CRITICAL: 3 nodes down. Quorum lost!"),
            ScenarioEvent(12.0, "recover_nodes", {"nodes": [2, 3]}, "Quorum restored (4 active nodes). Commits resume."),
            ScenarioEvent(20.0, "stop_workload", {}, "No-quorum safety test passed.")
        ]
    ),
    "latency_storm": ScenarioDefinition(
        id="latency_storm",
        name="Latency Storm (300ms Delay Surge)",
        description="Injects 300ms propagation delay across all links for 15s. Compares static vs adaptive timer stability.",
        duration_sec=25.0,
        events=[
            ScenarioEvent(0.5, "start_workload", {"tps": 120.0}, "Load running."),
            ScenarioEvent(4.0, "netem", {"delay_ms": 300.0, "jitter_ms": 25.0, "drop_prob": 0.05}, "STORM INJECTED: 300ms WAN delay spike."),
            ScenarioEvent(18.0, "netem", {"delay_ms": 2.0, "jitter_ms": 0.5, "drop_prob": 0.0}, "Storm cleared. Normal latency restored."),
            ScenarioEvent(25.0, "stop_workload", {}, "Latency storm benchmark concluded.")
        ]
    ),
    "equivocation": ScenarioDefinition(
        id="equivocation",
        name="Byzantine Equivocating Leader Attack",
        description="Malicious leader signs conflicting blocks at same height. In Plain CFT Raft this produces a state fork; in Hardened mode it is intercepted with 0 forks.",
        duration_sec=20.0,
        events=[
            ScenarioEvent(0.5, "start_workload", {"tps": 100.0}, "Normal consensus under load."),
            ScenarioEvent(5.0, "malicious_equivocation", {}, "ATTACK: Malicious leader attempts dual-signature equivocation!"),
            ScenarioEvent(20.0, "stop_workload", {}, "Equivocation defense evaluated.")
        ]
    ),
    "slow_leader": ScenarioDefinition(
        id="slow_leader",
        name="Gray Failure (Slow-but-Alive Leader Transfer)",
        description="Leader experiences 250ms internal outbound delay. Followers detect heartbeat jitter degradation and trigger planned leader transfer before throughput collapses.",
        duration_sec=20.0,
        events=[
            ScenarioEvent(0.5, "start_workload", {"tps": 120.0}, "Baseline workload running."),
            ScenarioEvent(4.0, "slow_leader", {"delay_ms": 250.0}, "GRAY FAILURE: Leader outbound delayed by 250ms."),
            ScenarioEvent(12.0, "clear_slow_leader", {}, "Leader recovered."),
            ScenarioEvent(20.0, "stop_workload", {}, "Gray failure test concluded.")
        ]
    )
}
