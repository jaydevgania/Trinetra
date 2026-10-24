"""
Trinetra Simulated Network (SimNetwork)
Models realistic latency, jitter, packet loss, duplicate packets, and partitions.
Supports Datacenter, Regional, and Global WAN presets.
"""
import random
from typing import Dict, Tuple, List, Set, Optional, Callable, Any
from dataclasses import dataclass, field


@dataclass
class LinkConfig:
    src: int
    dst: int
    base_latency_ms: float = 2.0
    jitter_ms: float = 0.5
    drop_prob: float = 0.0
    duplicate_prob: float = 0.0
    blocked: bool = False


@dataclass
class PacketTrace:
    id: int
    src: int
    dst: int
    msg_type: str
    term: int
    scheduled_at: float
    deliver_at: float
    status: str  # "in_flight", "delivered", "dropped", "duplicated"
    reason: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)


class SimNetwork:
    # Geo Presets (in milliseconds)
    PRESETS = {
        "dc": {
            "name": "Single Datacenter (Local LAN)",
            "default_latency_ms": 1.5,
            "jitter_ms": 0.3,
            "matrix": None  # Uniform
        },
        "regional": {
            "name": "Regional WAN (Mumbai, Pune, Hyderabad)",
            "default_latency_ms": 20.0,
            "jitter_ms": 4.0,
            "matrix": {
                # 0: Mumbai-1, 1: Mumbai-2, 2: Pune, 3: Hyderabad-1, 4: Hyderabad-2
                (0, 1): 2.0, (1, 0): 2.0,
                (0, 2): 15.0, (2, 0): 15.0,
                (1, 2): 16.0, (2, 1): 16.0,
                (0, 3): 26.0, (3, 0): 26.0,
                (1, 3): 27.0, (3, 1): 27.0,
                (2, 3): 22.0, (3, 2): 22.0,
                (0, 4): 28.0, (4, 0): 28.0,
                (1, 4): 29.0, (4, 1): 29.0,
                (2, 4): 24.0, (4, 2): 24.0,
                (3, 4): 3.0, (4, 3): 3.0,
            }
        },
        "global": {
            "name": "Global WAN (Mumbai, Frankfurt, Virginia)",
            "default_latency_ms": 120.0,
            "jitter_ms": 15.0,
            "matrix": {
                # 0: Mumbai, 1: Frankfurt, 2: Virginia, 3: Frankfurt-2, 4: Virginia-2
                (0, 1): 110.0, (1, 0): 110.0,
                (0, 3): 112.0, (3, 0): 112.0,
                (1, 3): 4.0, (3, 1): 4.0,
                (1, 2): 85.0, (2, 1): 85.0,
                (1, 4): 87.0, (4, 1): 87.0,
                (3, 2): 86.0, (2, 3): 86.0,
                (3, 4): 88.0, (4, 3): 88.0,
                (2, 4): 3.0, (4, 2): 3.0,
                (0, 2): 195.0, (2, 0): 195.0,
                (0, 4): 198.0, (4, 0): 198.0,
            }
        }
    }

    def __init__(self, clock: Any, node_ids: List[int], rng: Optional[random.Random] = None):
        self.clock = clock
        self.node_ids = list(node_ids)
        self.rng = rng or random.Random(42)
        self.links: Dict[Tuple[int, int], LinkConfig] = {}
        self.active_preset: str = "dc"
        self.active_partitions: List[List[int]] = []

        # Statistics
        self.messages_sent: int = 0
        self.messages_delivered: int = 0
        self.messages_dropped: int = 0
        self.total_bytes: int = 0

        # Handlers
        self.packet_counter: int = 0
        self.listeners: List[Callable[[PacketTrace], None]] = []
        self.node_handlers: Dict[int, Callable[[Any], None]] = {}

        self._init_links()

    def register_node(self, node_id: int, handler: Callable[[Any], None]) -> None:
        """Register delivery handler for destination node."""
        self.node_handlers[node_id] = handler

    def _init_links(self) -> None:
        """Initialize all pairwise links with the default preset."""
        self.apply_preset("dc")

    def apply_preset(self, preset_name: str) -> None:
        """Apply a geo-latency preset to all links."""
        if preset_name not in self.PRESETS:
            preset_name = "dc"
        self.active_preset = preset_name
        preset = self.PRESETS[preset_name]
        default_latency = preset["default_latency_ms"]
        jitter = preset["jitter_ms"]
        matrix = preset.get("matrix") or {}

        for src in self.node_ids:
            for dst in self.node_ids:
                if src == dst:
                    continue
                pair = (src, dst)
                latency = matrix.get(pair, default_latency)
                if pair in self.links:
                    self.links[pair].base_latency_ms = latency
                    self.links[pair].jitter_ms = jitter
                else:
                    self.links[pair] = LinkConfig(
                        src=src,
                        dst=dst,
                        base_latency_ms=latency,
                        jitter_ms=jitter,
                        drop_prob=0.0,
                        duplicate_prob=0.0,
                        blocked=False
                    )

    def set_link(self, src: int, dst: int, base_latency_ms: Optional[float] = None,
                 jitter_ms: Optional[float] = None, drop_prob: Optional[float] = None,
                 duplicate_prob: Optional[float] = None, blocked: Optional[bool] = None) -> None:
        pair = (src, dst)
        if pair not in self.links:
            self.links[pair] = LinkConfig(src=src, dst=dst)
        cfg = self.links[pair]
        if base_latency_ms is not None:
            cfg.base_latency_ms = max(0.1, base_latency_ms)
        if jitter_ms is not None:
            cfg.jitter_ms = max(0.0, jitter_ms)
        if drop_prob is not None:
            cfg.drop_prob = max(0.0, min(1.0, drop_prob))
        if duplicate_prob is not None:
            cfg.duplicate_prob = max(0.0, min(1.0, duplicate_prob))
        if blocked is not None:
            cfg.blocked = blocked

    def set_all_links(self, drop_prob: Optional[float] = None,
                      delay_ms: Optional[float] = None,
                      jitter_ms: Optional[float] = None) -> None:
        """Apply global netem degradation across all links."""
        for cfg in self.links.values():
            if drop_prob is not None:
                cfg.drop_prob = max(0.0, min(1.0, drop_prob))
            if delay_ms is not None:
                cfg.base_latency_ms = max(0.1, delay_ms)
            if jitter_ms is not None:
                cfg.jitter_ms = max(0.0, jitter_ms)

    def partition(self, groups: List[List[int]]) -> None:
        """
        Partition network into disconnected groups of nodes.
        Nodes within the same group can talk; nodes in different groups are blocked.
        """
        self.active_partitions = [list(g) for g in groups]
        group_map = {}
        for g_idx, group in enumerate(groups):
            for node_id in group:
                group_map[node_id] = g_idx

        for (src, dst), cfg in self.links.items():
            if src in group_map and dst in group_map:
                cfg.blocked = (group_map[src] != group_map[dst])
            else:
                cfg.blocked = False

    def heal(self) -> None:
        """Remove all active network partitions."""
        self.active_partitions.clear()
        for cfg in self.links.values():
            cfg.blocked = False

    def add_trace_listener(self, listener: Callable[[PacketTrace], None]) -> None:
        self.listeners.append(listener)

    def _emit_trace(self, trace: PacketTrace) -> None:
        for listener in self.listeners:
            try:
                listener(trace)
            except Exception:
                pass

    def send(self, src: int, dst: int, msg: Any, deliver_callback: Optional[Callable[[int, Any], None]] = None) -> None:
        """
        Send a message from src to dst.
        Delivers to dst node handler after calculated delay,
        respecting packet drop, duplication, and partition blocks.
        """
        self.messages_sent += 1
        self.packet_counter += 1
        pkt_id = self.packet_counter

        # Extract message metadata
        msg_type = getattr(msg, "type", type(msg).__name__)
        term = getattr(msg, "term", 0)
        payload_summary = getattr(msg, "to_dict", lambda: {"type": msg_type})()

        link = self.links.get((src, dst))
        if link is None:
            link = LinkConfig(src=src, dst=dst)
            self.links[(src, dst)] = link

        # 1. Partition Check
        if link.blocked:
            self.messages_dropped += 1
            trace = PacketTrace(
                id=pkt_id,
                src=src,
                dst=dst,
                msg_type=msg_type,
                term=term,
                scheduled_at=self.clock.t,
                deliver_at=self.clock.t,
                status="dropped",
                reason="partition",
                payload=payload_summary
            )
            self._emit_trace(trace)
            return

        # 2. Packet Drop Check
        if link.drop_prob > 0.0 and self.rng.random() < link.drop_prob:
            self.messages_dropped += 1
            trace = PacketTrace(
                id=pkt_id,
                src=src,
                dst=dst,
                msg_type=msg_type,
                term=term,
                scheduled_at=self.clock.t,
                deliver_at=self.clock.t + (link.base_latency_ms / 2000.0),
                status="dropped",
                reason="packet_loss",
                payload=payload_summary
            )
            self._emit_trace(trace)
            return

        # 3. Calculate latency (ms -> seconds)
        jitter = self.rng.uniform(-link.jitter_ms, link.jitter_ms) if link.jitter_ms > 0 else 0.0
        latency_ms = max(0.1, link.base_latency_ms + jitter)
        delay_sec = latency_ms / 1000.0
        deliver_time = self.clock.t + delay_sec

        trace = PacketTrace(
            id=pkt_id,
            src=src,
            dst=dst,
            msg_type=msg_type,
            term=term,
            scheduled_at=self.clock.t,
            deliver_at=deliver_time,
            status="in_flight",
            payload=payload_summary
        )
        self._emit_trace(trace)

        def _deliver():
            self.messages_delivered += 1
            trace.status = "delivered"
            self._emit_trace(trace)
            if dst in self.node_handlers:
                self.node_handlers[dst](msg)
            elif deliver_callback:
                deliver_callback(dst, msg)

        self.clock.call_later(delay_sec, _deliver)

        # 4. Duplicate packet injection (if configured)
        if link.duplicate_prob > 0.0 and self.rng.random() < link.duplicate_prob:
            dup_delay = delay_sec + (self.rng.uniform(2.0, 10.0) / 1000.0)
            self.messages_sent += 1

            def _deliver_dup():
                self.messages_delivered += 1
                dup_trace = PacketTrace(
                    id=pkt_id * 1000,
                    src=src,
                    dst=dst,
                    msg_type=msg_type,
                    term=term,
                    scheduled_at=self.clock.t,
                    deliver_at=self.clock.t + dup_delay,
                    status="delivered",
                    reason="duplicate",
                    payload=payload_summary
                )
                self._emit_trace(dup_trace)
                if dst in self.node_handlers:
                    self.node_handlers[dst](msg)
                elif deliver_callback:
                    deliver_callback(dst, msg)

            self.clock.call_later(dup_delay, _deliver_dup)
