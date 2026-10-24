"""
Trinetra Discrete-Event Simulation Clock
Enables 100% deterministic, reproducible consensus execution,
instant CPU-bound benchmarks, and wall-clock paced live playback.
"""
from heapq import heappush, heappop
from typing import Callable, Any, Optional, Set, List, Tuple
import time
import asyncio


class SimClock:
    def __init__(self, start_time: float = 0.0):
        self.t: float = start_time
        self.q: List[Tuple[float, int, Callable, tuple, dict]] = []
        self.seq: int = 0
        self.cancelled: Set[int] = set()
        self.is_paused: bool = False
        self.speed: float = 1.0  # Multiplier for live pacing

    def reset(self, start_time: float = 0.0) -> None:
        """Reset clock state for replay or fresh scenario run."""
        self.t = start_time
        self.q.clear()
        self.seq = 0
        self.cancelled.clear()
        self.is_paused = False

    def call_later(self, delay: float, fn: Callable, *args: Any, **kwargs: Any) -> int:
        """Schedule a callback to be executed after `delay` simulated seconds."""
        if delay < 0:
            delay = 0.0
        self.seq += 1
        handle = self.seq
        heappush(self.q, (self.t + delay, self.seq, fn, args, kwargs))
        return handle

    def call_at(self, target_time: float, fn: Callable, *args: Any, **kwargs: Any) -> int:
        """Schedule a callback at an absolute simulated timestamp."""
        delay = max(0.0, target_time - self.t)
        return self.call_later(delay, fn, *args, **kwargs)

    def cancel(self, handle: Optional[int]) -> None:
        """Cancel a pending scheduled callback handle."""
        if handle is not None:
            self.cancelled.add(handle)

    def has_pending(self) -> bool:
        """Check if any events remain in the queue."""
        return len(self.q) > 0

    def next_event_time(self) -> Optional[float]:
        """Peek at the timestamp of the next event in the queue."""
        while self.q and self.q[0][1] in self.cancelled:
            heappop(self.q)
        return self.q[0][0] if self.q else None

    def step(self) -> bool:
        """
        Execute the single next valid event in the queue.
        Returns True if an event was popped and executed, False if queue is empty.
        """
        while self.q:
            exec_time, handle, fn, args, kwargs = heappop(self.q)
            if handle in self.cancelled:
                self.cancelled.remove(handle)
                continue
            self.t = exec_time
            fn(*args, **kwargs)
            return True
        return False

    def step_dt(self, dt: float) -> int:
        """
        Advance simulated time by `dt` seconds, running all events up to `t + dt`.
        Returns number of events executed.
        """
        target_time = self.t + dt
        return self.run_until(target_time)

    def run_until(self, t_end: float) -> int:
        """
        Run all events until simulated time reaches `t_end`.
        Returns number of events executed.
        """
        executed = 0
        while self.q:
            # Peek at next event
            if self.q[0][0] > t_end:
                break
            exec_time, handle, fn, args, kwargs = heappop(self.q)
            if handle in self.cancelled:
                self.cancelled.remove(handle)
                continue
            self.t = exec_time
            fn(*args, **kwargs)
            executed += 1
        self.t = max(self.t, t_end)
        return executed

    def run_for(self, duration: float) -> int:
        """Run simulated time for `duration` seconds."""
        return self.run_until(self.t + duration)
