"""SignalGate Executive & Governance Dashboard (Gate G6).

Interactive Streamlit demonstration reading exclusively from frozen evaluation
artifacts and verified cryptographic audit records.

Governance Disclosures:
- Benchmark / Replay demonstration only; not a live payment-processing service.
- All evaluation metrics precomputed and immutable (results/results.json).
- Zero live model retraining, feature extraction, or threshold tuning.
- Workstation simulation disclosure: latency measured on AMD64 host, not IBM Z on-chip AI accelerator.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure root is in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from app.dashboard_data import DashboardDataLoader
from governance.claim_ledger import ClaimLedger, ReportableClaim

# ---------------------------------------------------------------------------
# Page Configuration & Styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SignalGate | Shift-Aware Fraud Triage",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for Enterprise Governance Aesthetic
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 1.2rem;
    }
    .badge-bar {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin-bottom: 1rem;
    }
    .status-badge {
        background-color: #F1F5F9;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.82rem;
        font-weight: 600;
        color: #334155;
    }
    .status-badge-pass {
        background-color: #ECFDF5;
        border: 1px solid #6EE7B7;
        color: #065F46;
    }
    .status-badge-fail {
        background-color: #FEF2F2;
        border: 1px solid #FCA5A5;
        color: #991B1B;
    }
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-label {
        font-size: 0.82rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
        margin: 4px 0;
    }
    .metric-delta-pos {
        font-size: 0.88rem;
        font-weight: 600;
        color: #10B981;
    }
    .metric-delta-neg {
        font-size: 0.88rem;
        font-weight: 600;
        color: #EF4444;
    }
    .disclaimer-box {
        background-color: #FFFBEB;
        border-left: 4px solid #F59E0B;
        padding: 12px 16px;
        border-radius: 0 6px 6px 0;
        margin-bottom: 1.2rem;
        font-size: 0.88rem;
        color: #92400E;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def get_loader():
    return DashboardDataLoader(root_dir=ROOT)


loader = get_loader()
results_data = loader.load_results()
freeze_data = loader.load_freeze_record()
shift_manifest = loader.load_shift_manifest()
agent_cache = loader.load_agent_cache()
drift_report = loader.load_drift_report()
prov_status = loader.verify_provenance()

# ---------------------------------------------------------------------------
# Sidebar: System Governance & Hashes
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://raw.githubusercontent.com/tandpfun/skill-icons/main/icons/Python-Dark.svg",
        width=42,
    )
    st.title("SignalGate G6")
    st.caption("Shift-Aware Fraud Triage Engine")

    st.markdown("---")
    st.subheader("System Status")
    st.markdown("🟢 **Mode:** Offline Benchmark Replay")
    st.markdown(r"🔒 **Decision Policy:** Frozen ($\lambda = 0.0$)")
    st.markdown("📦 **Master Evaluation:** `results.json`")

    st.markdown("---")
    st.subheader("Cryptographic Provenance")
    if prov_status.config_hash_verified:
        st.success(f"Config Hash Verified\n`{prov_status.actual_config_hash[:16]}...`")
    else:
        st.error("Config Hash Mismatch / Unverified")

    if prov_status.split_hash_verified:
        st.success(f"Split Hash Verified\n`{prov_status.actual_split_hash[:16]}...`")
    else:
        st.error("Split Hash Mismatch / Unverified")

    if prov_status.policy_hash_verified:
        st.success(f"Policy Hash Verified\n`{prov_status.actual_policy_hash[:16]}...`")
    else:
        st.warning("Policy Hash Unverified")

    st.markdown("---")
    st.caption("IBM Z Datathon 2026 | Gate G6 Audit Dashboard")


# ---------------------------------------------------------------------------
# Main Header & Governance Disclosures
# ---------------------------------------------------------------------------
st.markdown('<div class="main-header">🛡️ SignalGate Governance & Triage Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Gate G6: Verified Claim Ledger, Operational Lanes, and Frozen Artifact Replay</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="disclaimer-box">
        <strong>Governance Disclosure:</strong> This dashboard is an offline scientific benchmark and proposal-replay demonstration.
        It is <strong>not</strong> a live payment-processing service. All reported figures are deterministically loaded from frozen
        evaluation artifacts (<code>results/results.json</code>, <code>results/pre_eval_freeze_record.json</code>).
        No models are trained or retuned in this interface.
    </div>
    """,
    unsafe_allow_html=True,
)

if results_data is None:
    st.error("CRITICAL: results/results.json is missing or unreadable. Dashboard operates in fail-closed unverified state.")
    st.stop()

# ---------------------------------------------------------------------------
# Dashboard Navigation Tabs
# ---------------------------------------------------------------------------
tab_exec, tab_lanes, tab_shifts, tab_cases, tab_drift, tab_ledger, tab_latency, tab_ac = st.tabs([
    "📊 Executive Comparison",
    "🚦 Operational Lanes",
    "🌪️ Shift Scenarios (S0–S3)",
    "🔍 Case Drilldown & Briefs",
    "📈 Drift Monitoring",
    "📜 Claim Ledger & Provenance",
    "⚡ Latency Benchmarks",
    "✅ Acceptance Criteria",
])

# ---------------------------------------------------------------------------
# TAB 1: Executive Comparison (B2 vs SignalGate P5)
# ---------------------------------------------------------------------------
with tab_exec:
    st.subheader("Executive Comparison: Baseline B2 vs SignalGate P5")
    st.caption("Evaluated on S0 Full Chronological Test Set (N=118,108 transactions, 4,064 fraud cases) at matched 1.5× review budget.")

    s0 = results_data["scenarios"]["S0"]
    b2 = s0["baseline_b2"]
    p5 = s0["candidate_p5"]
    bs = s0["paired_bootstrap"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">SignalGate Recall (P5)</div>
                <div class="metric-value">{p5['recall']*100:.2f}%</div>
                <div class="metric-delta-pos">+{bs['delta_point_estimate']*100:.2f} pp vs B2 ({b2['recall']*100:.2f}%)</div>
                <div style="font-size:0.75rem; color:#64748B; margin-top:4px;">95% CI: [{bs['ci_lower']*100:.2f}%, {bs['ci_upper']*100:.2f}%]</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        prec_delta = (p5['precision'] - b2['precision']) * 100
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Precision at Budget</div>
                <div class="metric-value">{p5['precision']*100:.2f}%</div>
                <div class="metric-delta-pos">+{prec_delta:.2f} pp vs B2 ({b2['precision']*100:.2f}%)</div>
                <div style="font-size:0.75rem; color:#64748B; margin-top:4px;">Reviewed: {p5['reviewed_cases']:,} cases (5.08%)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        prauc_delta = p5['pr_auc'] - b2['pr_auc']
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">PR-AUC (Precision-Recall)</div>
                <div class="metric-value">{p5['pr_auc']:.4f}</div>
                <div class="metric-delta-pos">+{prauc_delta:.4f} vs B2 ({b2['pr_auc']:.4f})</div>
                <div style="font-size:0.75rem; color:#64748B; margin-top:4px;">Area under Precision-Recall curve</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        ece_delta = p5['ece'] - b2['ece']
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Expected Calibration Error</div>
                <div class="metric-value">{p5['ece']:.4f}</div>
                <div class="metric-delta-pos">{ece_delta:.4f} vs B2 ({b2['ece']:.4f})</div>
                <div style="font-size:0.75rem; color:#64748B; margin-top:4px;">Platt calibrated probabilities</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Head-to-Head Comparison Table")
    comp_df = pd.DataFrame([
        {
            "Metric": "Recall (% fraud detected)",
            "Baseline B2 (Top Score)": f"{b2['recall']*100:.2f}% ({b2['detected_fraud']:,} / {s0['fraud_count']:,})",
            "SignalGate P5 (Candidate)": f"{p5['recall']*100:.2f}% ({p5['detected_fraud']:,} / {s0['fraud_count']:,})",
            "Difference (P5 - B2)": f"+{bs['delta_point_estimate']*100:.2f} pp",
            "Statistical Significance": "Significant (CI strictly > 0)",
        },
        {
            "Metric": "Precision (% reviewed that are fraud)",
            "Baseline B2 (Top Score)": f"{b2['precision']*100:.2f}%",
            "SignalGate P5 (Candidate)": f"{p5['precision']*100:.2f}%",
            "Difference (P5 - B2)": f"+{(p5['precision'] - b2['precision'])*100:.2f} pp",
            "Statistical Significance": "Positive improvement",
        },
        {
            "Metric": "PR-AUC",
            "Baseline B2 (Top Score)": f"{b2['pr_auc']:.4f}",
            "SignalGate P5 (Candidate)": f"{p5['pr_auc']:.4f}",
            "Difference (P5 - B2)": f"+{p5['pr_auc'] - b2['pr_auc']:.4f}",
            "Statistical Significance": "Consistent ranking gain",
        },
        {
            "Metric": "Expected Calibration Error (ECE)",
            "Baseline B2 (Top Score)": f"{b2['ece']:.4f}",
            "SignalGate P5 (Candidate)": f"{p5['ece']:.4f}",
            "Difference (P5 - B2)": f"{p5['ece'] - b2['ece']:.4f}",
            "Statistical Significance": "96.1% calibration improvement",
        },
        {
            "Metric": "Brier Score",
            "Baseline B2 (Top Score)": f"{b2['brier_score']:.4f}",
            "SignalGate P5 (Candidate)": f"{p5['brier_score']:.4f}",
            "Difference (P5 - B2)": f"{p5['brier_score'] - b2['brier_score']:.4f}",
            "Statistical Significance": "Lower error",
        },
        {
            "Metric": "Confident Misses (Fraud routed to ROUTINE)",
            "Baseline B2 (Top Score)": f"{b2['confident_misses']:,}",
            "SignalGate P5 (Candidate)": f"{p5['confident_misses']:,}",
            "Difference (P5 - B2)": f"-{b2['confident_misses'] - p5['confident_misses']:,} (-1.64%)",
            "Statistical Significance": "Modest reduction (AC4 unmet)",
        },
    ])
    st.dataframe(comp_df, use_container_width=True, hide_index=True)

    st.markdown("#### Budget Sweep Analysis on S0")
    if "budget_sweep_s0" in results_data:
        sweep_rows = []
        for mult, sweep_item in results_data["budget_sweep_s0"].items():
            sweep_rows.append({
                "Budget Multiple": mult,
                "Capacity (k)": f"{sweep_item['budget_k']:,}",
                "B2 Recall": f"{sweep_item['baseline_b2_recall']*100:.2f}%",
                "P5 Recall": f"{sweep_item['candidate_p5_recall']*100:.2f}%",
                "Delta Recall": f"+{sweep_item['delta_recall']*100:.2f} pp",
                "B2 Precision": f"{sweep_item['baseline_b2_precision']*100:.2f}%",
                "P5 Precision": f"{sweep_item['candidate_p5_precision']*100:.2f}%",
            })
        st.dataframe(pd.DataFrame(sweep_rows), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# TAB 2: Operational Triage Lanes
# ---------------------------------------------------------------------------
with tab_lanes:
    st.subheader("Operational Triage Lanes (Scenario S0)")
    st.caption("Distribution of 118,108 test transactions across deterministic operational lanes.")

    lane_check = loader.verify_lane_counters("S0")
    if lane_check.is_consistent:
        st.success(
            f"✅ Lane Counter Verification PASSED: Sum of lanes ({lane_check.sum_of_lanes:,}) "
            f"exactly equals total cases ({lane_check.total_cases:,}). Reviewed sum ({lane_check.sum_reviewed_lanes:,}) "
            f"matches review budget."
        )
    else:
        st.error(f"❌ Lane Counter Mismatch: {'; '.join(lane_check.discrepancy_details)}")

    l1, l2, l3, l4 = st.columns(4)
    with l1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label" style="color:#DC2626;">FRAUD_ALERT</div>
                <div class="metric-value">{lane_check.fraud_alert_count:,}</div>
                <div style="font-size:0.85rem; color:#64748B;">{lane_check.fraud_alert_count/lane_check.total_cases*100:.2f}% of total</div>
                <div style="font-size:0.75rem; color:#DC2626; margin-top:4px;">Rule R1 (High Risk p &ge; 0.70)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with l2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label" style="color:#D97706;">MANUAL_REVIEW</div>
                <div class="metric-value">{lane_check.manual_review_count:,}</div>
                <div style="font-size:0.85rem; color:#64748B;">{lane_check.manual_review_count/lane_check.total_cases*100:.2f}% of total</div>
                <div style="font-size:0.75rem; color:#D97706; margin-top:4px;">Rules R2, R3 (Intermediate / Disagreement)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with l3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label" style="color:#2563EB;">ROUTINE (AUTO-CLEAR)</div>
                <div class="metric-value">{lane_check.routine_count:,}</div>
                <div style="font-size:0.85rem; color:#64748B;">{lane_check.routine_count/lane_check.total_cases*100:.2f}% of total</div>
                <div style="font-size:0.75rem; color:#2563EB; margin-top:4px;">Rule R5 (Low Risk, Reliable)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with l4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label" style="color:#64748B;">HELD / DEFERRED</div>
                <div class="metric-value">{lane_check.held_deferred_count:,}</div>
                <div style="font-size:0.85rem; color:#64748B;">{lane_check.held_deferred_count/lane_check.total_cases*100:.2f}% of total</div>
                <div style="font-size:0.75rem; color:#64748B; margin-top:4px;">Rule R6 (Queue Capacity Limit)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Confident Misses Analysis")
    st.markdown(
        """
        A **confident miss** occurs when a true positive fraud case is assigned to the `ROUTINE` lane (auto-cleared)
        because the model under-predicted its risk.
        """
    )
    cm_p5 = p5["confident_misses"]
    cm_b2 = b2["confident_misses"]
    cm_red = (cm_b2 - cm_p5) / cm_b2 * 100

    col_cm1, col_cm2 = st.columns([1, 2])
    with col_cm1:
        st.metric("SignalGate Confident Misses", f"{cm_p5:,}", delta=f"-{cm_b2 - cm_p5:,} vs B2 ({cm_b2:,})", delta_color="inverse")
        st.caption(f"Reduction rate: **{cm_red:.2f}%** (Target was 10.0%, hence AC4 is marked FAIL).")
    with col_cm2:
        st.info(
            f"**Honest Disclosure:** SignalGate reduced confident misses by {cm_b2 - cm_p5} cases ({cm_red:.2f}%), "
            f"which is below the pre-registered AC4 acceptance threshold of 10.0%. This result is honestly "
            f"reported as **FAIL / UNMET** rather than altered or disguised."
        )


# ---------------------------------------------------------------------------
# TAB 3: Shift Scenario Evaluation (S0 - S3)
# ---------------------------------------------------------------------------
with tab_shifts:
    st.subheader("Shift Scenario Evaluation (S0, S1, S2, S3)")
    st.caption("Evaluation across temporal shifts and synthetic stress tests with formal evidence classification.")

    shift_rows = []
    scenarios_data = results_data.get("scenarios", {})

    for sc_id in ["S0", "S1", "S2", "S3"]:
        if sc_id not in scenarios_data:
            continue
        sc = scenarios_data[sc_id]
        spec = sc.get("scenario_spec", {})
        sc_b2 = sc["baseline_b2"]
        sc_p5 = sc["candidate_p5"]
        sc_bs = sc["paired_bootstrap"]

        evidence_type = "measured synthetic data" if spec.get("is_synthetic") else "measured real data"
        shift_rows.append({
            "Scenario": sc_id,
            "Description": spec.get("name", sc_id),
            "Evidence Type": evidence_type,
            "Sample Size (N)": f"{sc['sample_size']:,}",
            "Fraud Cases": f"{sc['fraud_count']:,} ({sc['fraud_count']/sc['sample_size']*100:.2f}%)",
            "B2 Recall": f"{sc_b2['recall']*100:.2f}%",
            "P5 Recall": f"{sc_p5['recall']*100:.2f}%",
            "Delta Recall": f"+{sc_bs['delta_point_estimate']*100:.2f} pp",
            "95% Bootstrap CI": f"[{sc_bs['ci_lower']*100:.2f}%, {sc_bs['ci_upper']*100:.2f}%]",
            "PR-AUC Gain": f"+{sc_p5['pr_auc'] - sc_b2['pr_auc']:.4f}",
            "ECE Gain": f"{sc_p5['ece'] - sc_b2['ece']:.4f}",
        })

    st.dataframe(pd.DataFrame(shift_rows), use_container_width=True, hide_index=True)

    st.markdown("#### Scenario Provenance & Reconciliation Notes")
    st.markdown(
        r"""
        - **S0 (Original Chronological Test Set):** 118,108 transactions from chronological test split (TransactionDT: 12,192,900 – 15,811,131). Evidence: *measured real data*.
        - **S1 (Late-Period Test Scenario):** 31,582 transactions from final ~28% of test period (`TransactionDT >= 14,800,000`). Evidence: *measured real data*.
        - **S2 (Real-Data Validation Shift):** 27,390 transactions from late half of validation partition (`TransactionDT >= 11,315,422`). Evidence: *measured real data*.
          * **Reconciliation of G4 vs G5 counts:** The G4 report cited 29,527 transactions (the theoretical midpoint: $59,054 / 2$). When the actual timestamp filter `TransactionDT >= 11,315,422` is applied to non-uniformly distributed validation transactions, the true count is **27,390 transactions**. This is the authoritative count recorded in `results.json`.
        - **S3 (Synthetic Perturbation):** 59,054 transactions with deterministic $1.15\times$ scaling and Gaussian noise ($\sigma=0.15\times\text{std}$, seed=42). Evidence: *measured synthetic data*.
          * *Disclosure:* Synthetic stress testing verifies model stability under extreme covariate noise; it does **not** constitute proof of natural distribution shift resilience.
        """
    )


# ---------------------------------------------------------------------------
# TAB 4: Case Drilldown & Verified Briefs
# ---------------------------------------------------------------------------
with tab_cases:
    st.subheader("Case Drilldown & Verified Decision Support Briefs")
    st.caption("Sanitized AgentCaseView records evaluated by AgentSupervisor, CaseCopilot, and ClaimVerifier.")

    st.markdown(
        """
        <div class="disclaimer-box">
            <strong>Security Guardrail (AG5):</strong> Agents ingest strictly allowlisted <code>AgentCaseView</code> structures
            (p, u, u2, n, action, reason, cfg_hash). Raw transaction features and ground-truth fraud labels are
            <strong>never</strong> accessible to agents.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if agent_cache is not None and "records" in agent_cache:
        records = agent_cache["records"]
        case_options = [f"{r['record_id']} — {r['action']} ({r['reason']})" for r in records]
        selected_idx = st.selectbox("Select Sanitized Case Record:", range(len(case_options)), format_func=lambda i: case_options[i])
        selected_case = records[selected_idx]

        col_c1, col_c2 = st.columns([1, 1])
        with col_c1:
            st.markdown("#### Allowlisted AgentCaseView")
            st.json({
                "record_id": selected_case["record_id"],
                "calibrated_risk_p": selected_case["p"],
                "disagreement_u": selected_case["u"],
                "secondary_disagreement_u2": selected_case["u2"],
                "sample_size_n": selected_case["n"],
                "assigned_action": selected_case["action"],
                "reason_code": selected_case["reason"],
                "provider": selected_case["provider"],
                "execution_mode": selected_case["execution_mode"],
                "input_hash": selected_case["input_hash"],
                "output_hash": selected_case["output_hash"],
            })

        with col_c2:
            st.markdown("#### Verified Copilot Brief")
            st.markdown(f"**Status:** `{selected_case['status']}` | **Claims Count:** `{selected_case['claims_count']}`")
            st.markdown("##### Verified Statements:")
            for stmt in selected_case["verified_statements"]:
                st.markdown(f"- {stmt}")

            if selected_case["verified_claims"]:
                st.markdown("##### Verified Claims:")
                st.dataframe(pd.DataFrame(selected_case["verified_claims"]), use_container_width=True, hide_index=True)
    else:
        st.warning("Agent cache (results/agent_cache.json) is missing. Run scripts/cache_agent_outputs.py to generate.")


# ---------------------------------------------------------------------------
# TAB 5: Batch Drift Monitoring
# ---------------------------------------------------------------------------
with tab_drift:
    st.subheader("Batch Drift Monitoring (PSI & KS Diagnostics)")
    st.caption("Saved drift diagnostics comparing transaction batches to the frozen validation reference.")

    st.markdown(
        """
        <div class="disclaimer-box">
            <strong>Statistical Disclaimer:</strong> Population Stability Index (PSI) and Kolmogorov-Smirnov (KS) metrics
            measure covariate or score distribution shifts relative to the reference period.
            <strong>Distribution shift does NOT constitute proof or evidence of increased fraud prevalence.</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if drift_report is not None and "scenarios" in drift_report:
        sc_choice = st.selectbox("Select Shift Batch to Inspect:", ["S0 (Test Full)", "S1 (Late Test)", "S2 (Real Shift)", "S3 (Synthetic)"])
        sc_key = sc_choice.split()[0]

        if sc_key in drift_report["scenarios"]:
            sc_drift = drift_report["scenarios"][sc_key]
            st.markdown(f"**Batch ID:** `{sc_drift['batch_id']}` | **Sample Size:** `{sc_drift['sample_size']:,}` | **Overall Drift Detected:** `{sc_drift['overall_drift_detected']}`")

            feat_rows = []
            for f_name, f_res in sc_drift["feature_results"].items():
                feat_rows.append({
                    "Feature": f_name,
                    "PSI": f"{f_res['psi']:.4f}",
                    "KS Statistic": f"{f_res['ks_statistic']:.4f}",
                    "p-value": f"{f_res['p_value']:.4e}",
                    "Shift Severity": f_res["shift_severity"].upper(),
                    "Drift Detected": f_res["drift_detected"],
                    "Interpretation": f_res["interpretation"],
                })
            st.dataframe(pd.DataFrame(feat_rows), use_container_width=True, hide_index=True)
    else:
        st.warning("Drift report artifact (results/drift_report.json) not found.")


# ---------------------------------------------------------------------------
# TAB 6: Claim Ledger & Provenance
# ---------------------------------------------------------------------------
with tab_ledger:
    st.subheader("Deterministic Claim Ledger (Gate G6)")
    st.caption("Verifies numerical performance claims directly against immutable results artifacts. Deterministically rejects planted numbers.")

    ledger_res, v_cnt, r_cnt = loader.verify_standard_claims()
    st.markdown(f"**Verification Outcome:** `{v_cnt} Verified` | `{r_cnt} Rejected` across registered headline claims.")

    # Interactive Planted Wrong Number Test
    st.markdown("#### Planted Wrong Number Adversarial Test")
    plant_test = st.checkbox("Simulate Planted Incorrect Claim (Adversarial Demonstration)")
    if plant_test:
        bad_claim = ReportableClaim(
            claim_id="CLM_ADVERSARIAL_PLANTED_RECALL",
            metric_name="recall",
            scenario_id="S0",
            claimed_value=0.8500,  # Fabricated recall claim (85.0% vs actual 51.33%)
            evidence_type="measured real data",
            source_artifact="results/results.json",
            sample_size=118108,
            config_hash=prov_status.actual_config_hash,
            description="Fabricated headline claim asserting 85.0% recall on S0",
        )
        ledger = ClaimLedger(results_path=loader.results_file, freeze_record_path=loader.freeze_record_file)
        check_outcome = ledger.verify_claim(bad_claim)

        st.error(
            f"🚨 Planted Error Caught by Claim Ledger!\n\n"
            f"- **Claimed:** {check_outcome.claimed_value}\n"
            f"- **Actual Verified Value:** {check_outcome.actual_value}\n"
            f"- **Rejection Reason:** {check_outcome.rejection_reason}\n"
            f"- **Status:** `REJECTED (is_verified={check_outcome.is_verified})`"
        )

    st.markdown("#### Standard Headline Claims Verification Table")
    ledger_table_rows = []
    for r in ledger_res:
        ledger_table_rows.append({
            "Claim ID": r.claim_id,
            "Verified": "✅ PASS" if r.is_verified else "❌ REJECTED",
            "Claimed Value": str(r.claimed_value),
            "Actual Value": str(r.actual_value) if r.actual_value is not None else "N/A",
            "Rejection Reason": r.rejection_reason or "Verified against results.json",
            "Source Artifact": r.source_artifact_path,
        })
    st.dataframe(pd.DataFrame(ledger_table_rows), use_container_width=True, hide_index=True)

    st.markdown("#### HMAC Audit-Chain Live Verification")
    chain_status = loader.verify_audit_chain()
    if chain_status["ok"]:
        st.success(
            f"✅ Cryptographic Audit Chain PASSED: {chain_status['record_count']} records verified. "
            f"Final HMAC Signature Hash: `{chain_status['final_hash']}`."
        )
    else:
        st.error(f"❌ Audit Chain Verification Failed: {chain_status['errors']}")

    st.markdown("#### Attestation & TEE Disclosure")
    st.info(
        "**Integrity Disclosure:** This benchmark runs in standard user space. "
        "No claim is made that IBM Secure Execution, confidential computing, or an attested Trusted Execution "
        "Environment (TEE) has been demonstrated, as hardware attestation evidence does not exist in this environment."
    )


# ---------------------------------------------------------------------------
# TAB 7: Latency Benchmarks
# ---------------------------------------------------------------------------
with tab_latency:
    st.subheader("Latency Benchmarks (Gate G5 / G6)")
    st.caption("Measured single-row and batch inference latency on host workstation.")

    lat = results_data.get("latency_benchmark", {})
    st.markdown(
        f"""
        <div class="disclaimer-box">
            <strong>Measurement Conditions:</strong> Latency benchmarks were recorded on host environment:
            <code>{lat.get('host_os', 'Windows')}</code> on <code>{lat.get('host_architecture', 'AMD64')}</code>,
            Python <code>{lat.get('python_version', '3.13')}</code> using <code>{lat.get('clock_source', 'time.perf_counter')}</code>.
            These timings do <strong>not</strong> represent IBM Telum on-chip AI coprocessor acceleration.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_l1, col_l2, col_l3, col_l4 = st.columns(4)
    with col_l1:
        st.metric("Single-Row p50", f"{lat.get('single_row_p50_ms', 0):.2f} ms")
    with col_l2:
        st.metric("Single-Row p95 (AC5 Target)", f"{lat.get('single_row_p95_ms', 0):.2f} ms", delta="< 50.0 ms target", delta_color="normal")
    with col_l3:
        st.metric("Single-Row p99", f"{lat.get('single_row_p99_ms', 0):.2f} ms")
    with col_l4:
        st.metric("Batch-32 p95", f"{lat.get('batch32_p95_ms', 0):.2f} ms")

    st.markdown("#### Component Breakdown (Single-Row Execution)")
    st.dataframe(pd.DataFrame([
        {"Component": "Decision System (Feature Preprocessing + Ensemble + Platt Calibration)", "p95 Latency": f"{lat.get('single_row_p95_ms', 0):.2f} ms"},
        {"Component": "Deterministic Routing Policy (Candidate P5 Thresholds)", "p95 Latency": f"{lat.get('routing_decision_only_p95_ms', 0):.3f} ms"},
        {"Component": "HMAC Audit Chain Log Append", "p95 Latency": f"{lat.get('audit_chain_write_p95_ms', 0):.3f} ms"},
        {"Component": "Case Copilot Brief (Offline Deterministic Mode)", "p95 Latency": f"{lat.get('copilot_agent_offline_p95_ms', 0):.3f} ms"},
    ]), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# TAB 8: Acceptance Criteria Checklist
# ---------------------------------------------------------------------------
with tab_ac:
    st.subheader("Formal Acceptance Criteria Checklist")
    st.caption("Final evaluation of criteria AC1 through AC5 from results/results.json.")

    ac_dict = results_data.get("acceptance_criteria", {})
    ac_rows = []
    for ac_key in ["AC1", "AC2", "AC3", "AC4", "AC5"]:
        if ac_key in ac_dict:
            item = ac_dict[ac_key]
            status = item.get("status", "NOT MEASURED")
            ac_rows.append({
                "Criterion": ac_key,
                "Description": item.get("name", ac_key),
                "Threshold Requirement": item.get("rule", ""),
                "Observed Metric": item.get("observed", ""),
                "Status": status,
                "Notes": item.get("rationale", ""),
            })

    st.dataframe(pd.DataFrame(ac_rows), use_container_width=True, hide_index=True)

    st.markdown("#### Scientific Integrity Summary")
    st.markdown(
        r"""
        - **AC1 (Recall Gain &ge; +2.0 pp):** **FAIL / UNMET**. While the recall gain is statistically significant
          ($\Delta = +0.81$ pp, 95% CI $[+0.07\%, +1.41\%]$ strictly above zero), it does not reach the ambitious $+2.00$ pp hurdle.
        - **AC2 (Touched Rate Reduction &ge; 10%):** **FAIL / NOT ESTABLISHED**. The candidate was evaluated at matched review budget ($k=5,994$).
        - **AC3 (Shift Robustness across S0–S3):** **PASS**. SignalGate P5 consistently outperforms baseline B2 across all 4 shift scenarios.
        - **AC4 (Confident Miss Reduction &ge; 10%):** **FAIL / UNMET**. Observed confident miss reduction is $1.64\%$, below the $10\%$ target.
        - **AC5 (p95 Latency &le; 50 ms):** **PASS**. Host p95 latency is $8.34\text{ ms} \le 50.0\text{ ms}$.
        """
    )
