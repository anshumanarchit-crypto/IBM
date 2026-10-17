"""Hash-chained, HMAC-authenticated JSONL audit log.

HMAC uses a shared secret. Keep that secret outside source control. This
single-process writer is not a distributed logging service, and a privileged
attacker with access to both log and secret could rewrite the chain.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from schemas.contracts import AuditRecord, ZERO_HASH


def _canonical_json(payload: dict) -> bytes:
    """Return stable JSON bytes for hashing."""
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return text.encode("utf-8")


def _record_hash(record: AuditRecord) -> str:
    """Hash the unsigned record payload, including prev_hash and seq."""
    payload = record.model_dump(
        mode="json",
        exclude={"record_hash", "signature"},
    )
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _signature(record_hash: str, key: bytes) -> str:
    return hmac.new(key, record_hash.encode("ascii"), hashlib.sha256).hexdigest()


def signing_key_from_env() -> bytes:
    """Load the audit key without storing it in source code."""
    value = os.environ.get("SIGNALGATE_AUDIT_HMAC_KEY")
    if not value:
        raise RuntimeError("Set SIGNALGATE_AUDIT_HMAC_KEY before writing a real audit log")
    key = value.encode("utf-8")
    if len(key) < 32:
        raise ValueError("The audit key must contain at least 32 bytes")
    return key


@dataclass(frozen=True)
class VerificationResult:
    """Detailed verification outcome with backwards-compatible boolean behavior."""

    ok: bool
    record_count: int
    errors: tuple[str, ...]
    final_hash: str

    def __bool__(self) -> bool:
        """Allow verify_chain(...) to be evaluated directly as a boolean."""
        return self.ok


def verify_chain(path: str | Path, key: bytes) -> VerificationResult:
    """Verify JSON syntax, sequence, previous hashes, hashes and HMACs."""
    audit_path = Path(path)
    if not isinstance(key, bytes) or not key:
        return VerificationResult(
            ok=False,
            record_count=0,
            errors=("Invalid or empty HMAC signing key",),
            final_hash=ZERO_HASH,
        )

    if not audit_path.exists():
        return VerificationResult(
            ok=True,
            record_count=0,
            errors=(),
            final_hash=ZERO_HASH,
        )

    errors: list[str] = []
    expected_seq = 1
    expected_prev_hash = ZERO_HASH
    record_count = 0

    try:
        raw_lines = audit_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return VerificationResult(
            ok=False,
            record_count=0,
            errors=(f"Failed to read audit file: {exc}",),
            final_hash=ZERO_HASH,
        )

    for line_number, line in enumerate(raw_lines, start=1):
        if not line.strip():
            errors.append(f"Line {line_number}: empty lines are not permitted")
            break

        try:
            record = AuditRecord.model_validate_json(line)
        except Exception as exc:
            errors.append(f"Line {line_number}: invalid audit record ({type(exc).__name__})")
            break

        record_count += 1

        if record.seq != expected_seq:
            errors.append(f"Line {line_number}: unexpected sequence number (expected {expected_seq}, got {record.seq})")

        if record.prev_hash != expected_prev_hash:
            errors.append(f"Line {line_number}: previous hash mismatch")

        computed_hash = _record_hash(record)
        if not record.record_hash:
            errors.append(f"Line {line_number}: missing record hash")
        elif not hmac.compare_digest(computed_hash, record.record_hash):
            errors.append(f"Line {line_number}: record hash mismatch")

        expected_sig = _signature(computed_hash, key)
        if not record.signature:
            errors.append(f"Line {line_number}: missing HMAC signature")
        elif not hmac.compare_digest(expected_sig, record.signature):
            errors.append(f"Line {line_number}: HMAC verification failed")

        expected_prev_hash = record.record_hash or ZERO_HASH
        expected_seq += 1

    return VerificationResult(
        ok=(len(errors) == 0),
        record_count=record_count,
        errors=tuple(errors),
        final_hash=expected_prev_hash,
    )


class AuditChainWriter:
    """Append decisions in order and reject an invalid existing chain."""

    def __init__(self, path: str | Path, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("The audit key must contain at least 32 bytes")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.key = key
        self._lock = threading.Lock()

        if self.path.exists() and self.path.stat().st_size > 0:
            result = verify_chain(self.path, self.key)
            if not result.ok:
                raise ValueError("Refusing to append to an invalid audit chain: " + "; ".join(result.errors))

    def append(self, record: AuditRecord) -> AuditRecord:
        """Finalise sequence/hash/signature, then append one JSONL line."""
        if not isinstance(record, AuditRecord):
            raise TypeError("append requires an AuditRecord")

        with self._lock:
            # Re-verify disk before each append to prevent appending onto tampered logs
            if self.path.exists() and self.path.stat().st_size > 0:
                result = verify_chain(self.path, self.key)
                if not result.ok:
                    raise ValueError("Refusing to append to an invalid audit chain: " + "; ".join(result.errors))
                last_line = self.path.read_text(encoding="utf-8").splitlines()[-1]
                last_record = AuditRecord.model_validate_json(last_line)
                sequence = last_record.seq + 1
                previous_hash = last_record.record_hash or ZERO_HASH
            else:
                sequence = 1
                previous_hash = ZERO_HASH

            payload = record.model_dump(mode="python")
            payload.update(
                seq=sequence,
                prev_hash=previous_hash,
                record_hash=ZERO_HASH,
                signature="",
            )
            unsigned = AuditRecord.model_validate(payload)
            record_hash = _record_hash(unsigned)
            sig = _signature(record_hash, self.key)
            signed = unsigned.model_copy(
                update={"record_hash": record_hash, "signature": sig}
            )

            line = json.dumps(signed.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())

            return signed
