"""
Trinetra Message Tracer (Wireshark-Style RPC Inspector)
Maintains a rolling ring buffer of packet captures with metadata,
latency profiling, filtering, and payload introspection.
"""
from typing import List, Dict, Any, Optional
from core.network import PacketTrace


class MessageTracer:
    def __init__(self, max_capacity: int = 1000):
        self.max_capacity = max_capacity
        self.packets: List[PacketTrace] = []

    def record_packet(self, trace: PacketTrace) -> None:
        """Add or update packet trace in ring buffer."""
        # Check if already present to update status (in_flight -> delivered/dropped)
        for i in range(len(self.packets) - 1, max(-1, len(self.packets) - 50), -1):
            if self.packets[i].id == trace.id:
                self.packets[i] = trace
                return

        self.packets.append(trace)
        if len(self.packets) > self.max_capacity:
            self.packets.pop(0)

    def get_packets(
        self,
        src: Optional[int] = None,
        dst: Optional[int] = None,
        msg_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Return filtered slice of recorded packets."""
        results = []
        for p in reversed(self.packets):
            if src is not None and p.src != src:
                continue
            if dst is not None and p.dst != dst:
                continue
            if msg_type is not None and msg_type.lower() not in p.msg_type.lower():
                continue
            if status is not None and p.status != status:
                continue

            results.append({
                "id": p.id,
                "src": p.src,
                "dst": p.dst,
                "msg_type": p.msg_type,
                "term": p.term,
                "scheduled_at": round(p.scheduled_at, 4),
                "deliver_at": round(p.deliver_at, 4),
                "latency_ms": round(max(0.1, (p.deliver_at - p.scheduled_at) * 1000.0), 2),
                "status": p.status,
                "reason": p.reason,
                "payload": p.payload
            })
            if len(results) >= limit:
                break
        return results

    def clear(self) -> None:
        self.packets.clear()
