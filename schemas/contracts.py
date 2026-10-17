"""Validated data contracts for SignalGate.

These models define the interface between deterministic routing, audit
records, and optional agents. Raw transaction features and fraud labels do
not belong in agent-facing contracts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ZERO_HASH = "0" * 64
SHA256_PATTERN = r"^[0-9a-f]{64}$"

Action = Literal["ROUTINE", "FRAUD_ALERT", "MANUAL_REVIEW", "HELD", "DEFERRED"]
ReasonCode = Literal[
    "R0_SIGNAL_UNAVAILABLE",
    "R1_HIGH_RISK",
    "R2_INTERMEDIATE_RISK",
    "R3_MODEL_DISAGREEMENT",
    "R4_UNFAMILIAR_INPUT",
    "R5_LOW_RISK_RELIABLE",
    "R6_QUEUE_CAPACITY",
]


class AuditRecord(BaseModel):
    """One deterministic routing decision, suitable for an audit JSONL log."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    seq: int = Field(default=0, ge=0)
    prev_hash: str = Field(default=ZERO_HASH, pattern=SHA256_PATTERN)
    p: float | None = Field(default=None, ge=0.0, le=1.0)
    u: float | None = Field(default=None, ge=0.0)
    u2: float | None = Field(default=None, ge=0.0)
    n: float | None = Field(default=None, ge=0.0)
    u_method: str | None = None
    action: Action
    reason: ReasonCode
    cfg_hash: str = Field(pattern=SHA256_PATTERN)
    split_hash: str = Field(pattern=SHA256_PATTERN)
    record_hash: str = Field(default=ZERO_HASH, pattern=SHA256_PATTERN)
    signature: str = ""

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class Claim(BaseModel):
    """A structured claim that must be verified before it is displayed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(min_length=1)
    operator: Literal["eq", "ne", "lt", "lte", "gt", "gte", "in"]
    value: Any
    template_id: str = Field(min_length=1)


class AgentRecord(BaseModel):
    """An agent output with status and basic provenance metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_id: str = Field(min_length=1)
    record_id: str = Field(min_length=1)
    status: Literal["ok", "unavailable", "failed", "timed_out"]
    claims: list[Claim] = Field(default_factory=list)
    input_hash: str = Field(pattern=SHA256_PATTERN)
    cfg_hash: str = Field(pattern=SHA256_PATTERN)
    output_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class Proposal(BaseModel):
    """Advisory policy-change proposal; never an applied policy change."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(min_length=1)
    base_cfg_hash: str = Field(pattern=SHA256_PATTERN)
    changes: dict[str, Any]
    rationale: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("created_at")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return value
