"""
Trinetra API Pydantic Request & Response Models
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class WorkloadRequest(BaseModel):
    tps: float = Field(default=150.0, ge=1.0, le=1000.0)
    invalid_pct: float = Field(default=2.0, ge=0.0, le=100.0)


class TransactionRequest(BaseModel):
    sender: str
    recipient: str
    amount: int = Field(gt=0)
    nonce: int = Field(gt=0)
    sig: Optional[str] = None


class NodeActionRequest(BaseModel):
    node: int = Field(ge=0, le=4)


class PartitionRequest(BaseModel):
    groups: List[List[int]]


class NetemRequest(BaseModel):
    drop_prob: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    delay_ms: Optional[float] = Field(default=None, ge=0.1)
    jitter_ms: Optional[float] = Field(default=None, ge=0.0)


class MaliciousActionRequest(BaseModel):
    node: int = Field(ge=0, le=4)
    behavior: str = "equivocate"  # "equivocate" or "mute"


class ModeRequest(BaseModel):
    timers: Optional[str] = None      # "static" or "adaptive"
    prevote: Optional[bool] = None
    consensus: Optional[str] = None    # "cft" or "hardened"


class GeoPresetRequest(BaseModel):
    preset: str = "dc"  # "dc", "regional", "global"


class SpeedControlRequest(BaseModel):
    speed: float = Field(default=1.0, ge=0.1, le=10.0)


class ScenarioRunRequest(BaseModel):
    name: str = "baseline"
    seed: int = 42


class BenchmarkRunRequest(BaseModel):
    scenario: str = "latency_storm"
    runs: int = 5


class MonkeyRunRequest(BaseModel):
    schedules: int = 100
    seed: int = 1337
