"""
Trinetra Live Narrator Engine
Generates human-readable, plain-English captions of consensus events,
fault transitions, and Byzantine defenses in real time without external LLM dependencies.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time


@dataclass
class NarrativeItem:
    timestamp: float
    category: str
    headline: str
    text: str
    severity: str  # "info", "success", "warning", "danger"


class LiveNarrator:
    def __init__(self):
        self.history: List[NarrativeItem] = []
        self.latest_item: Optional[NarrativeItem] = None

    def narrate(self, event_type: str, data: Dict[str, Any], sim_time: float) -> NarrativeItem:
        """Translate event into structured human narrative."""
        headline = "Consensus Event"
        text = ""
        severity = "info"
        category = "general"

        match event_type:
            case "cluster_started":
                headline = "Consensus Network Initialized"
                text = f"5 validator nodes online across configured geography. Genesis block 0 sealed and verified."
                severity = "info"
                category = "lifecycle"

            case "leader_elected":
                nid = data.get("node_id")
                term = data.get("term")
                headline = f"Leader Elected: Node N{nid}"
                text = f"Node N{nid} collected a quorum of votes and established leadership for Term {term}. Commits proceeding."
                severity = "success"
                category = "election"

            case "prevote_started":
                nid = data.get("node_id")
                term = data.get("target_term")
                headline = f"Pre-Vote Phase: Node N{nid}"
                text = f"Node N{nid} noticed leader silence and started Pre-Vote for Term {term} to test peer quorum without inflating term counter."
                severity = "info"
                category = "prevote"

            case "election_started":
                nid = data.get("node_id")
                term = data.get("new_term")
                headline = f"Election Underway: Term {term}"
                text = f"Node N{nid} stepped up as candidate for Term {term} and broadcast vote solicitations."
                severity = "warning"
                category = "election"

            case "leader_stepped_down":
                nid = data.get("node_id")
                headline = f"Leader Step Down: Node N{nid}"
                text = f"Leader N{nid} observed a higher term broadcast from a peer and safely stepped down to Follower."
                severity = "info"
                category = "election"

            case "node_crashed":
                nid = data.get("node_id")
                headline = f"Fault Injected: Node N{nid} Crashed"
                text = f"Node N{nid} was forcibly halted. Volatile timers stopped and network socket dropped."
                severity = "danger"
                category = "chaos"

            case "node_recovered":
                nid = data.get("node_id")
                headline = f"Recovery: Node N{nid} Restored"
                text = f"Node N{nid} rebooted, reloaded persisted ledger state from disk, and rejoined as Follower."
                severity = "success"
                category = "chaos"

            case "partition_active":
                groups = data.get("groups", [])
                headline = "Network Split: Active Partition"
                text = f"Network severed into disjoint clusters: {groups}. Cross-partition messages are blocked."
                severity = "danger"
                category = "chaos"

            case "partition_healed":
                headline = "Network Healed"
                text = "Partition healed! Full peer-to-peer mesh connectivity restored across all 5 nodes."
                severity = "success"
                category = "chaos"

            case "latency_storm_started":
                delay = data.get("delay_ms", 300)
                headline = f"Latency Storm: {delay}ms Injected"
                text = f"Link delays surged to {delay}ms across all peers. Evaluating adaptive RTT timers vs static timeouts."
                severity = "warning"
                category = "chaos"

            case "latency_storm_cleared":
                headline = "Latency Storm Resolved"
                text = "Network propagation delays returned to baseline levels."
                severity = "success"
                category = "chaos"

            case "block_committed":
                h = data.get("height")
                b_hash = data.get("hash", "")
                headline = f"Block #{h} Committed"
                text = f"Consensus reached on Block #{h} (hash {b_hash}..). Transactions applied to token state machine."
                severity = "info"
                category = "consensus"

            case "equivocation_injected":
                nid = data.get("node_id")
                h = data.get("height")
                headline = f"Byzantine Attack: Malicious Equivocation"
                text = f"Malicious leader N{nid} signed TWO conflicting blocks for Height {h} and sent them to separate halves of the cluster!"
                severity = "danger"
                category = "byzantine"

            case "equivocation_detected":
                offender = data.get("offender")
                idx = data.get("index")
                headline = f"Equivocation Caught: Node N{offender}"
                text = f"Cryptographic EquivProof generated! Two conflicting leader signatures uncovered for slot {idx}."
                severity = "warning"
                category = "byzantine"

            case "peer_quarantined":
                offender = data.get("offender")
                headline = f"Offender Quarantined: Node N{offender}"
                text = f"Node N{offender} has been permanently blacklisted. All messages dropped. Honest nodes electing new leader."
                severity = "danger"
                category = "byzantine"

            case "hardened_defense_success":
                headline = "Hardened Echo Quorum Defended State"
                text = "Echo threshold 4-of-5 prevented conflicting block from committing. Fork avoided entirely (0 forks)."
                severity = "success"
                category = "byzantine"

            case "fork_detected":
                details = data.get("details", "")
                headline = "CRITICAL SAFETY VIOLATION: Ledger Fork!"
                text = f"Plain Raft permitted conflicting blocks to commit: {details}. Resilience score plunged to 0 (Grade F)."
                severity = "danger"
                category = "safety"

            case "autopilot_step":
                headline = f"Autopilot: {data.get('chapter', 'Demo Step')}"
                text = data.get("text", "")
                severity = "info"
                category = "autopilot"

            case _:
                headline = event_type.replace("_", " ").title()
                text = str(data)

        item = NarrativeItem(
            timestamp=sim_time,
            category=category,
            headline=headline,
            text=text,
            severity=severity
        )
        self.latest_item = item
        self.history.append(item)
        if len(self.history) > 100:
            self.history.pop(0)

        return item

    def get_latest(self) -> Optional[Dict[str, Any]]:
        if not self.latest_item:
            return None
        return {
            "timestamp": round(self.latest_item.timestamp, 2),
            "category": self.latest_item.category,
            "headline": self.latest_item.headline,
            "text": self.latest_item.text,
            "severity": self.latest_item.severity
        }

    def get_recent(self, limit: int = 15) -> List[Dict[str, Any]]:
        return [
            {
                "timestamp": round(it.timestamp, 2),
                "category": it.category,
                "headline": it.headline,
                "text": it.text,
                "severity": it.severity
            }
            for it in reversed(self.history[-limit:])
        ]
