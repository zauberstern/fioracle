"""WebSocket message schemas for brain-to-body communication."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    STATE_DELTA = "state_delta"
    REGIME_EVENT = "regime_event"


class DLinearStateDelta(BaseModel):
    type: Literal["state_delta"] = "state_delta"
    layer: Literal["dlinear"] = "dlinear"
    asset: str
    trend: float
    residual: float
    residual_z: float


class BSADFStateDelta(BaseModel):
    type: Literal["state_delta"] = "state_delta"
    layer: Literal["bsadf"] = "bsadf"
    asset: str
    bsadf_stat: float
    critical_value: float
    bubble_flag: bool


class LPPLSStateDelta(BaseModel):
    type: Literal["state_delta"] = "state_delta"
    layer: Literal["lppls"] = "lppls"
    asset: str
    lpp_confidence: float = Field(..., ge=0, le=1)
    crash_window_start: datetime | None = None
    crash_window_end: datetime | None = None


class SentimentStateDelta(BaseModel):
    type: Literal["state_delta"] = "state_delta"
    layer: Literal["sentiment"] = "sentiment"
    asset: str
    sentiment_velocity: float
    sentiment_level: float = Field(..., ge=-1, le=1)


class RegimeStateDelta(BaseModel):
    type: Literal["state_delta"] = "state_delta"
    layer: Literal["regime"] = "regime"
    asset: str
    regime_state: Literal["normal", "boom", "bust"]
    regime_confidence: float = Field(..., ge=0, le=1)
    boom_probability: float = Field(..., ge=0, le=1)
    bust_probability: float = Field(..., ge=0, le=1)


class MacroStateDelta(BaseModel):
    type: Literal["state_delta"] = "state_delta"
    layer: Literal["macro"] = "macro"
    asset: str
    debt_to_gdp: float
    sustainable_threshold: float
    gap: float


class BubbleConfirmedEvent(BaseModel):
    type: Literal["regime_event"] = "regime_event"
    event: Literal["bubble_confirmed"] = "bubble_confirmed"
    asset: str
    bsadf_stat: float
    critical_value: float
    timestamp: datetime


class CrashWindowEvent(BaseModel):
    type: Literal["regime_event"] = "regime_event"
    event: Literal["crash_window_entered", "crash_window_exited"]
    asset: str
    confidence: float
    timestamp: datetime


class SentimentSpikeEvent(BaseModel):
    type: Literal["regime_event"] = "regime_event"
    event: Literal["sentiment_spike"] = "sentiment_spike"
    asset: str
    velocity: float
    timestamp: datetime


class RegimeFlipEvent(BaseModel):
    type: Literal["regime_event"] = "regime_event"
    event: Literal["regime_flip"] = "regime_flip"
    asset: str
    from_state: Literal["normal", "boom", "bust"]
    to_state: Literal["normal", "boom", "bust"]
    timestamp: datetime


class MacroThresholdEvent(BaseModel):
    type: Literal["regime_event"] = "regime_event"
    event: Literal["threshold_breach"] = "threshold_breach"
    asset: str
    gap: float
    timestamp: datetime
