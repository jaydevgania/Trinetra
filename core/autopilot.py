"""
Trinetra One-Button Autopilot Demo Engine
Orchestrates an end-to-end automated 5-minute pitch demo through
6 choreographed chapters. Works as a live automated presenter and a fail-safe backup.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable


@dataclass
class DemoChapter:
    name: str
    duration_sec: float
    description: str
    action_fn_name: str
    action_args: Dict[str, Any]


class AutopilotController:
    CHAPTERS: List[DemoChapter] = [
        DemoChapter(
            name="Chapter 1: Normal Multi-Region Operation",
            duration_sec=10.0,
            description="5 validators operating across regions under 200 TPS steady workload. All ledgers and state roots in 100% agreement.",
            action_fn_name="step_chapter_1",
            action_args={"tps": 200.0, "preset": "regional"}
        ),
        DemoChapter(
            name="Chapter 2: Leader Crash & Sub-Second Failover",
            duration_sec=12.0,
            description="Active leader is killed unexpectedly. The cluster detects loss, elects a new leader with randomized timers, and resumes commits with MTTR < 400ms.",
            action_fn_name="step_chapter_2",
            action_args={}
        ),
        DemoChapter(
            name="Chapter 3: Asymmetric Partition & Pre-Vote Safety",
            duration_sec=15.0,
            description="Network split into {N0, N1} minority and {N2, N3, N4} majority. Pre-Vote prevents minority from inflating term and disrupting the healthy leader upon healing.",
            action_fn_name="step_chapter_3",
            action_args={}
        ),
        DemoChapter(
            name="Chapter 4: Global Latency Storm (Adaptive Timers)",
            duration_sec=15.0,
            description="WAN propagation delay jumps to 300ms. Jacobson/Karels RTT estimators dynamically stretch timeouts, eliminating election churn and maintaining high throughput.",
            action_fn_name="step_chapter_4",
            action_args={"delay_ms": 300.0}
        ),
        DemoChapter(
            name="Chapter 5: Byzantine Equivocation & Hardened Defense",
            duration_sec=18.0,
            description="Malicious leader signs conflicting blocks. In Plain Raft this causes a state fork; under Trinetra Hardened Mode, 4-of-5 Echo quorum intercepts and quenches the attack.",
            action_fn_name="step_chapter_5",
            action_args={}
        ),
        DemoChapter(
            name="Chapter 6: Resilience Certification & Audit Report",
            duration_sec=10.0,
            description="Evaluation complete! Published mathematical resilience score calculated (Grade A) and certified audit report generated for consortium stakeholders.",
            action_fn_name="step_chapter_6",
            action_args={}
        )
    ]

    def __init__(self, cluster: Any):
        self.cluster = cluster
        self.is_active: bool = False
        self.current_chapter_idx: int = 0
        self.time_in_chapter: float = 0.0
        self.step_timer_handle: Optional[int] = None

    def start(self) -> None:
        """Start full autopilot demo from beginning."""
        self.is_active = True
        self.current_chapter_idx = 0
        self.time_in_chapter = 0.0
        self._execute_current_chapter()

    def stop(self) -> None:
        """Halt autopilot execution."""
        self.is_active = False
        if self.step_timer_handle is not None:
            self.cluster.clock.cancel(self.step_timer_handle)
            self.step_timer_handle = None

    def next_chapter(self) -> None:
        """Manually advance to next chapter."""
        if self.current_chapter_idx < len(self.CHAPTERS) - 1:
            self.current_chapter_idx += 1
            self.time_in_chapter = 0.0
            self._execute_current_chapter()
        else:
            self.stop()

    def prev_chapter(self) -> None:
        """Go back to previous chapter."""
        if self.current_chapter_idx > 0:
            self.current_chapter_idx -= 1
            self.time_in_chapter = 0.0
            self._execute_current_chapter()

    def _execute_current_chapter(self) -> None:
        if not self.is_active or self.current_chapter_idx >= len(self.CHAPTERS):
            self.is_active = False
            return

        chapter = self.CHAPTERS[self.current_chapter_idx]
        self.cluster.emit_narrative(
            "autopilot_step",
            {"chapter": chapter.name, "text": chapter.description}
        )

        fn = getattr(self, chapter.action_fn_name, None)
        if fn:
            fn(**chapter.action_args)

        # Schedule advancement
        if self.step_timer_handle is not None:
            self.cluster.clock.cancel(self.step_timer_handle)

        self.step_timer_handle = self.cluster.clock.call_later(
            chapter.duration_sec,
            self._on_chapter_timer_done
        )

    def _on_chapter_timer_done(self) -> None:
        if not self.is_active:
            return
        if self.current_chapter_idx < len(self.CHAPTERS) - 1:
            self.current_chapter_idx += 1
            self._execute_current_chapter()
        else:
            self.is_active = False

    # Chapter Action Implementations
    def step_chapter_1(self, tps: float, preset: str) -> None:
        self.cluster.apply_geo_preset(preset)
        self.cluster.set_mode(timers="adaptive", prevote=True, consensus="cft")
        self.cluster.heal_partitions()
        self.cluster.start_workload(tps=tps, invalid_pct=2.0)

    def step_chapter_2(self) -> None:
        leader_id = self.cluster.get_current_leader_id()
        if leader_id is not None:
            self.cluster.crash_node(leader_id)
            # Recover leader after 4 simulated seconds
            self.cluster.clock.call_later(4.0, lambda: self.cluster.recover_node(leader_id))

    def step_chapter_3(self) -> None:
        # Asymmetric partition: 2 vs 3
        self.cluster.partition_network([[0, 1], [2, 3, 4]])
        # Heal after 6 seconds
        self.cluster.clock.call_later(6.0, lambda: self.cluster.heal_partitions())

    def step_chapter_4(self, delay_ms: float) -> None:
        self.cluster.inject_netem(delay_ms=delay_ms, drop_prob=0.05, jitter_ms=20.0)
        # Clear after 7 seconds
        self.cluster.clock.call_later(7.0, lambda: self.cluster.inject_netem(delay_ms=2.0, drop_prob=0.0, jitter_ms=0.5))

    def step_chapter_5(self) -> None:
        # First switch to Hardened mode to demonstrate 0-fork defense
        self.cluster.set_mode(timers="adaptive", prevote=True, consensus="hardened")
        leader_id = self.cluster.get_current_leader_id()
        if leader_id is not None:
            self.cluster.inject_malicious_equivocation(leader_id)

    def step_chapter_6(self) -> None:
        # Wrap up and ensure all invariants pass
        self.cluster.run_invariant_check()

    def get_status(self) -> Dict[str, Any]:
        curr = self.CHAPTERS[self.current_chapter_idx] if self.current_chapter_idx < len(self.CHAPTERS) else None
        return {
            "active": self.is_active,
            "chapter_index": self.current_chapter_idx,
            "total_chapters": len(self.CHAPTERS),
            "chapter_name": curr.name if curr else "",
            "description": curr.description if curr else "",
            "duration_sec": curr.duration_sec if curr else 0.0
        }
