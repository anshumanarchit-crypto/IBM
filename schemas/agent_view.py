"""Allowlisted, sanitised views that may be passed to agents.

Never pass a source DataFrame, raw transaction columns, or true labels to an
agent. Construct views only from verified audit records.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

from schemas.contracts import Action, AuditRecord, ReasonCode, SHA256_PATTERN


class AgentCaseView(BaseModel):
    """The explicitly permitted information for one case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1)
    p: float | None = Field(default=None, ge=0.0, le=1.0)
    u: float | None = Field(default=None, ge=0.0)
    u2: float | None = Field(default=None, ge=0.0)
    n: float | None = Field(default=None, ge=0.0)
    action: Action
    reason: ReasonCode
    record_hash: str = Field(pattern=SHA256_PATTERN)
    cfg_hash: str = Field(pattern=SHA256_PATTERN)
    split_hash: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def from_audit_record(cls, record: AuditRecord) -> "AgentCaseView":
        """Build an allowlisted view; do not copy arbitrary record fields."""
        if not isinstance(record, AuditRecord):
            raise TypeError("from_audit_record requires an AuditRecord")
        return cls(
            record_id=record.id,
            p=record.p,
            u=record.u,
            u2=record.u2,
            n=record.n,
            action=record.action,
            reason=record.reason,
            record_hash=record.record_hash,
            cfg_hash=record.cfg_hash,
            split_hash=record.split_hash,
        )


class AgentView(BaseModel):
    """Container for sanitised agent case views."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cases: tuple[AgentCaseView, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _support_records_kwarg(cls, data: Any) -> Any:
        if isinstance(data, dict) and "records" in data and "cases" not in data:
            data = dict(data)
            data["cases"] = data.pop("records")
        return data

    @property
    def records(self) -> tuple[AgentCaseView, ...]:
        """Alias for cases to support both records and cases interfaces."""
        return self.cases

    @classmethod
    def from_audit_records(cls, records: list[AuditRecord]) -> "AgentView":
        return cls(cases=tuple(AgentCaseView.from_audit_record(r) for r in records))
