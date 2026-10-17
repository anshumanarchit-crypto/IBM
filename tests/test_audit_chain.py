import json
from pathlib import Path

from governance.audit_chain import (
    AuditChainWriter,
    verify_chain,
)
from schemas.contracts import AuditRecord

TEST_KEY = b"signal-gate-test-key-" + b"x" * 40


def make_record(record_id: str, p: float) -> AuditRecord:
    return AuditRecord(
        id=record_id,
        p=p,
        u=0.08,
        u_method="test",
        action="MANUAL_REVIEW",
        reason="R3_MODEL_DISAGREEMENT",
        cfg_hash="a" * 64,
        split_hash="b" * 64,
    )


def test_new_chain_verifies(tmp_path: Path):
    path = tmp_path / "audit.jsonl"

    writer = AuditChainWriter(path, TEST_KEY)

    first = writer.append(make_record("case-1", 0.2))
    second = writer.append(make_record("case-2", 0.7))

    assert first.seq == 1
    assert second.seq == 2
    assert second.prev_hash == first.record_hash

    result = verify_chain(path, TEST_KEY)

    assert result.ok
    assert result.record_count == 2
    assert result.errors == ()


def test_modified_record_is_detected(tmp_path: Path):
    path = tmp_path / "audit.jsonl"

    writer = AuditChainWriter(path, TEST_KEY)
    writer.append(make_record("case-1", 0.2))
    writer.append(make_record("case-2", 0.7))

    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])

    # Simulate a post-write modification.
    first["p"] = 0.9

    lines[0] = json.dumps(
        first,
        separators=(",", ":"),
    )

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    result = verify_chain(path, TEST_KEY)

    assert not result.ok
    assert any(
        "hash mismatch" in error.lower()
        or "hmac verification failed" in error.lower()
        for error in result.errors
    )


def test_wrong_key_fails_verification(tmp_path: Path):
    path = tmp_path / "audit.jsonl"

    writer = AuditChainWriter(path, TEST_KEY)
    writer.append(make_record("case-1", 0.4))

    wrong_key = b"wrong-key-" + b"z" * 40

    result = verify_chain(path, wrong_key)

    assert not result.ok
    assert any(
        "hmac verification failed" in error.lower()
        for error in result.errors
    )


def test_writer_refuses_damaged_existing_chain(tmp_path: Path):
    path = tmp_path / "audit.jsonl"

    writer = AuditChainWriter(path, TEST_KEY)
    writer.append(make_record("case-1", 0.4))

    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '"p":0.4', '"p":0.8'
        ),
        encoding="utf-8",
    )

    try:
        AuditChainWriter(path, TEST_KEY)
    except ValueError as exc:
        assert "invalid audit chain" in str(exc).lower()
    else:
        raise AssertionError(
            "An invalid existing chain must not be accepted"
        )
