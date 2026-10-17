from governance.audit_chain import AuditChainWriter
from schemas.agent_view import AgentCaseView, AgentView
from schemas.contracts import AuditRecord

TEST_KEY = b"signal-gate-test-key-" + b"x" * 40


def test_agent_view_contains_only_approved_fields(tmp_path):
    path = tmp_path / "audit.jsonl"
    writer = AuditChainWriter(path, TEST_KEY)

    record = writer.append(
        AuditRecord(
            id="case-1",
            p=0.75,
            u=0.12,
            u2=0.03,
            n=0.5,
            action="MANUAL_REVIEW",
            reason="R3_MODEL_DISAGREEMENT",
            cfg_hash="a" * 64,
            split_hash="b" * 64,
        )
    )

    case_view = AgentCaseView.from_audit_record(record)

    allowed = {
        "record_id",
        "p",
        "u",
        "u2",
        "n",
        "action",
        "reason",
        "record_hash",
        "cfg_hash",
        "split_hash",
    }

    assert set(type(case_view).model_fields) == allowed
    assert not hasattr(case_view, "isFraud")
    assert not hasattr(case_view, "TransactionAmt")

    view = AgentView.from_audit_records([record])

    assert len(view.records) == 1
    assert view.records[0].record_id == "case-1"


def test_agent_view_rejects_unknown_fields():
    try:
        AgentCaseView(
            record_id="case-1",
            action="ROUTINE",
            reason="R5_LOW_RISK_RELIABLE",
            record_hash="a" * 64,
            cfg_hash="b" * 64,
            split_hash="c" * 64,
            isFraud=1,
        )
    except Exception:
        pass
    else:
        raise AssertionError(
            "AgentCaseView must reject unapproved fields"
        )
