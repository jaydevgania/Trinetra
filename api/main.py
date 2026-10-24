"""
Trinetra Chaos Console - Main FastAPI Application
Provides REST endpoints, 10Hz WebSocket state streaming,
Prometheus /metrics exporter, and serves the dark-mode dashboard.
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from core.cluster import ClusterController
from core.monkey import MonkeyFuzzer
from core.crypto import KeyPair, MerkleTree
from bench.run_bench import compare_static_vs_adaptive
from bench.report import generate_html_report
from api.models import (
    WorkloadRequest, TransactionRequest, NodeActionRequest,
    PartitionRequest, NetemRequest, MaliciousActionRequest,
    ModeRequest, GeoPresetRequest, SpeedControlRequest,
    ScenarioRunRequest, BenchmarkRunRequest, MonkeyRunRequest,
    SlowLeaderRequest, PlannedTransferRequest, ManualTxRequest,
    CustomScenarioRequest
)
from api.ws import ConnectionManager
from api.prometheus import format_prometheus_metrics

# Global Cluster Singleton
cluster = ClusterController(node_count=5, seed=42)
ws_manager = ConnectionManager()
runner_task: Optional[asyncio.Task] = None


async def live_cluster_loop():
    """
    Background worker that paces the discrete-event simulation
    against wall-clock time and broadcasts state to WebSocket clients at 10Hz.
    """
    tick_interval = 0.100  # 10 Hz (100ms)
    while True:
        try:
            if not cluster.clock.is_paused:
                # Step clock according to speed multiplier
                dt = tick_interval * cluster.clock.speed
                cluster.step(dt=dt)

            snapshot = cluster.get_snapshot()
            await ws_manager.broadcast_json(snapshot)
        except Exception as e:
            # Prevent background loop crash
            pass
        await asyncio.sleep(tick_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start cluster and live runner
    cluster.start()
    # Start gentle initial workload so dashboard is alive on load
    cluster.start_workload(tps=80.0, invalid_pct=2.0)
    global runner_task
    runner_task = asyncio.create_task(live_cluster_loop())
    yield
    # Shutdown
    if runner_task:
        runner_task.cancel()
        try:
            await runner_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Trinetra Chaos Console API",
    version="2.0.0",
    description="Chaos-testing console for permissioned blockchains and adaptive consensus",
    lifespan=lifespan
)


# -------------------------------------------------------------
# REST API Endpoints
# -------------------------------------------------------------

@app.get("/state")
def get_state() -> Dict[str, Any]:
    """Retrieve complete instantaneous snapshot of cluster state."""
    return cluster.get_snapshot()


@app.post("/workload")
def set_workload(req: WorkloadRequest) -> Dict[str, Any]:
    """Start or adjust transaction generation rate."""
    cluster.start_workload(tps=req.tps, invalid_pct=req.invalid_pct)
    return {"status": "ok", "tps": req.tps, "invalid_pct": req.invalid_pct}


@app.post("/workload/stop")
def stop_workload() -> Dict[str, Any]:
    """Halt transaction generation."""
    cluster.stop_workload()
    return {"status": "ok", "running": False}


@app.post("/chaos/crash")
def crash_node(req: NodeActionRequest) -> Dict[str, Any]:
    """Crash a specific validator node."""
    cluster.crash_node(req.node)
    return {"status": "ok", "action": "crash", "node": req.node}


@app.post("/chaos/recover")
def recover_node(req: NodeActionRequest) -> Dict[str, Any]:
    """Reboot a crashed validator node."""
    cluster.recover_node(req.node)
    return {"status": "ok", "action": "recover", "node": req.node}


@app.post("/chaos/partition")
def partition_network(req: PartitionRequest) -> Dict[str, Any]:
    """Sever network links between defined node groups."""
    cluster.partition_network(req.groups)
    return {"status": "ok", "partitions": req.groups}


@app.post("/chaos/heal")
def heal_network() -> Dict[str, Any]:
    """Restore all severed network partitions."""
    cluster.heal_partitions()
    return {"status": "ok", "healed": True}


@app.post("/chaos/netem")
def netem(req: NetemRequest) -> Dict[str, Any]:
    """Inject latency, packet loss, or jitter across all links."""
    cluster.inject_netem(drop_prob=req.drop_prob, delay_ms=req.delay_ms, jitter_ms=req.jitter_ms)
    return {"status": "ok", "drop_prob": req.drop_prob, "delay_ms": req.delay_ms, "jitter_ms": req.jitter_ms}


@app.post("/chaos/malicious")
def inject_malicious(req: MaliciousActionRequest) -> Dict[str, Any]:
    """Arm validator to perform Byzantine dual-proposal equivocation."""
    cluster.inject_malicious_equivocation(req.node)
    return {"status": "ok", "malicious_node": req.node, "behavior": req.behavior}


@app.post("/chaos/slow_leader")
def slow_leader(req: SlowLeaderRequest) -> Dict[str, Any]:
    """Inject Gray Failure: delay leader outbound heartbeats by specified milliseconds."""
    cluster.set_slow_leader(req.node, slow=req.slow, delay_ms=req.delay_ms)
    return {"status": "ok", "node": req.node, "slow": req.slow, "delay_ms": req.delay_ms}


@app.post("/chaos/transfer_leadership")
def transfer_leadership(req: PlannedTransferRequest) -> Dict[str, Any]:
    """Trigger planned leader transfer via TimeoutNow."""
    cluster.transfer_leadership(req.target)
    return {"status": "ok", "target": req.target}


@app.post("/tx/submit")
def submit_manual_tx(req: ManualTxRequest) -> Dict[str, Any]:
    """Submit a client transaction from the Interactive Transaction Studio."""
    result = cluster.submit_client_tx(req.sender_idx, req.recipient_idx, req.amount)
    return result


@app.post("/scenario/custom")
def run_custom_scenario(req: CustomScenarioRequest) -> Dict[str, Any]:
    """Execute a custom chaos timeline composed in the Visual Scenario Composer."""
    cluster.run_custom_scenario(req.events)
    return {"status": "ok", "name": req.name, "events_scheduled": len(req.events)}


@app.post("/mode")
def set_mode(req: ModeRequest) -> Dict[str, Any]:
    """Configure timers (static/adaptive), pre-vote, and consensus mode (cft/hardened)."""
    cluster.set_mode(timers=req.timers, prevote=req.prevote, consensus=req.consensus)
    return {
        "status": "ok",
        "timers": cluster.timers_mode,
        "prevote": cluster.prevote_enabled,
        "consensus": cluster.consensus_mode
    }


@app.post("/geo")
def set_geo(req: GeoPresetRequest) -> Dict[str, Any]:
    """Apply latency matrix preset (dc, regional, global)."""
    cluster.apply_geo_preset(req.preset)
    return {"status": "ok", "preset": req.preset}


# Playback & Discrete Step Controls (Feature A4)
@app.post("/control/pause")
def pause_cluster() -> Dict[str, Any]:
    cluster.clock.is_paused = True
    return {"status": "ok", "is_paused": True}


@app.post("/control/resume")
def resume_cluster() -> Dict[str, Any]:
    cluster.clock.is_paused = False
    return {"status": "ok", "is_paused": False}


@app.post("/control/step")
def step_cluster() -> Dict[str, Any]:
    """Advance simulation by 1 discrete step (50ms)."""
    cluster.step(dt=0.050)
    return {"status": "ok", "t": cluster.clock.t}


@app.post("/control/speed")
def set_speed(req: SpeedControlRequest) -> Dict[str, Any]:
    cluster.clock.speed = req.speed
    return {"status": "ok", "speed": req.speed}


# Autopilot Demo Controls (Feature A2)
@app.post("/autopilot/start")
def autopilot_start() -> Dict[str, Any]:
    cluster.autopilot.start()
    return {"status": "ok", "autopilot": cluster.autopilot.get_status()}


@app.post("/autopilot/stop")
def autopilot_stop() -> Dict[str, Any]:
    cluster.autopilot.stop()
    return {"status": "ok", "autopilot": cluster.autopilot.get_status()}


@app.post("/autopilot/next")
def autopilot_next() -> Dict[str, Any]:
    cluster.autopilot.next_chapter()
    return {"status": "ok", "autopilot": cluster.autopilot.get_status()}


@app.post("/autopilot/prev")
def autopilot_prev() -> Dict[str, Any]:
    cluster.autopilot.prev_chapter()
    return {"status": "ok", "autopilot": cluster.autopilot.get_status()}


# Benchmark Harness (Static vs Adaptive)
@app.post("/benchmark/run")
def run_benchmark(req: BenchmarkRunRequest) -> Dict[str, Any]:
    """Execute comparative benchmark of Static vs Adaptive timers over N seeds."""
    results = compare_static_vs_adaptive(scenario=req.scenario, runs=req.runs)
    return results


# Monkey Mode Fuzzing (Feature A8)
@app.post("/monkey/run")
def run_monkey(req: MonkeyRunRequest) -> Dict[str, Any]:
    """Execute Jepsen-style random chaos fuzz schedules in pure virtual time."""
    fuzzer = MonkeyFuzzer(node_count=5)
    result = fuzzer.run_fuzz_campaign(schedules_count=req.schedules, seed=req.seed)
    return result


# Ledger & Cryptographic Merkle Proof Inspection (Feature A6)
@app.get("/ledger/{node}")
def get_ledger(node: int) -> Dict[str, Any]:
    """Return committed block chain for the specified node."""
    if not (0 <= node < cluster.node_count):
        raise HTTPException(status_code=404, detail="Node index out of range")
    chain = cluster.nodes[node].ledger.chain
    return {
        "node_id": node,
        "height": len(chain) - 1,
        "blocks": [b.to_dict() for b in chain]
    }


@app.get("/ledger/{node}/proof/{height}/{tx_id}")
def get_merkle_proof(node: int, height: int, tx_id: str) -> Dict[str, Any]:
    """Generate and verify cryptographic Merkle inclusion proof for a transaction."""
    if not (0 <= node < cluster.node_count):
        raise HTTPException(status_code=404, detail="Node index out of range")
    chain = cluster.nodes[node].ledger.chain
    if height < 0 or height >= len(chain):
        raise HTTPException(status_code=404, detail="Block height not found")

    block = chain[height]
    tx_hashes = [tx.tx_id if tx.tx_id else tx.compute_hash() for tx in block.txs]
    if tx_id not in tx_hashes:
        raise HTTPException(status_code=404, detail="Transaction ID not in block")

    tx_idx = tx_hashes.index(tx_id)
    tree = MerkleTree(tx_hashes)
    proof = tree.get_proof(tx_idx)
    verified = MerkleTree.verify_proof(tx_id, proof, block.merkle_root)

    return {
        "node_id": node,
        "height": height,
        "tx_id": tx_id,
        "tx_index": tx_idx,
        "merkle_root": block.merkle_root,
        "proof_path": proof,
        "is_verified": verified
    }


# Message Tracer RPC Inspector (Feature A7)
@app.get("/trace")
def get_trace(
    src: Optional[int] = None,
    dst: Optional[int] = None,
    msg_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """Return captured RPC packet traces."""
    packets = cluster.tracer.get_packets(src=src, dst=dst, msg_type=msg_type, status=status, limit=limit)
    return {"total": len(packets), "packets": packets}


@app.get("/consistency")
def get_consistency() -> Dict[str, Any]:
    """Run and return invariant audit."""
    return cluster.run_invariant_check()


# Resilience Audit Report (Feature A3)
@app.get("/report")
def get_report(format: str = "html") -> Any:
    """Download certified Resilience Report as HTML or JSON."""
    snapshot = cluster.get_snapshot()
    if format.lower() == "json":
        return snapshot
    html_content = generate_html_report(snapshot)
    return HTMLResponse(content=html_content, status_code=200)


# Prometheus Exporter (Feature A9)
@app.get("/metrics")
def get_prometheus_metrics() -> Response:
    """Prometheus telemetry exposition endpoint."""
    snapshot = cluster.get_snapshot()
    text = format_prometheus_metrics(snapshot)
    return Response(content=text, media_type="text/plain; version=0.0.4; charset=utf-8")


# -------------------------------------------------------------
# WebSocket Live Stream (10 Hz)
# -------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    # Immediately send initial snapshot
    await websocket.send_json(cluster.get_snapshot())
    try:
        while True:
            # Client can send control commands over WS
            data = await websocket.receive_json()
            cmd = data.get("action")
            if cmd == "pause":
                cluster.clock.is_paused = True
            elif cmd == "resume":
                cluster.clock.is_paused = False
            elif cmd == "step":
                cluster.step(dt=0.050)
            elif cmd == "crash":
                cluster.crash_node(int(data.get("node", 0)))
            elif cmd == "recover":
                cluster.recover_node(int(data.get("node", 0)))
            elif cmd == "heal":
                cluster.heal_partitions()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# Serve Static Web UI Files
web_dir = Path(__file__).resolve().parent.parent / "web"
app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.get("/")
def serve_index():
    index_file = web_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>Trinetra Chaos Console</h1><p>Dashboard UI loading...</p>")
