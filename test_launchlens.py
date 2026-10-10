import pytest
from schemas import LaunchMemo, RiskReport, HumanReviewRecord
from orchestrator import (
    evaluate_adversarial_quality_gate,
    check_hitl_required,
    run_launchlens,
    AdversarialGateError,
)


def test_adversarial_gate_rejects_go_on_high_risk():
    """Verify quality gate blocks 'go' recommendations when risk is critical or high."""
    risky_report = RiskReport(
        critical_risks=["Model outputs hallucinated regulatory filings"],
        data_privacy_concerns=["Raw patient identifiers logged to unencrypted storage"],
        operational_fragility="High rate of model downtime during peak hospital hours",
        overall_risk_level="critical",
    )
    unbacked_go_memo = LaunchMemo(
        decision="go",
        confidence_score=0.95,
        executive_summary="Everything looks promising from the initial analysis.",
        mandatory_mitigations=["Monitor error logs"],
        dissenting_concerns=[],
    )

    with pytest.raises(AdversarialGateError, match="Automated Gate Failure: Memo attempted 'go'"):
        evaluate_adversarial_quality_gate(unbacked_go_memo, risky_report)


def test_adversarial_gate_rejects_pilot_without_mitigations():
    """Verify 'pilot' decision fails if no mitigations are specified."""
    safe_risk_report = RiskReport(
        critical_risks=[],
        data_privacy_concerns=[],
        operational_fragility="Low",
        overall_risk_level="low",
    )
    invalid_memo = LaunchMemo(
        decision="pilot",
        confidence_score=0.85,
        executive_summary="Proceeding with initial cohort test.",
        mandatory_mitigations=[],  # Empty list must trigger gate error
        dissenting_concerns=[],
    )

    with pytest.raises(AdversarialGateError, match="has 0 mandatory mitigations"):
        evaluate_adversarial_quality_gate(invalid_memo, safe_risk_report)


def test_hitl_trigger_conditions():
    """Verify HITL activates when risk is high and dissenting views exist."""
    risk = RiskReport(
        critical_risks=["Data sovereignty violation under EU AI Act"],
        data_privacy_concerns=["GDPR non-compliance in secondary data sharing"],
        operational_fragility="Medium API latency",
        overall_risk_level="high",
    )
    memo = LaunchMemo(
        decision="pilot",
        confidence_score=0.75,
        executive_summary="Proceeding with sandboxed testing cohort.",
        mandatory_mitigations=["Run inside sandboxed VPC"],
        dissenting_concerns=["Risk analyst dissents on HIPAA boundary safeguards"],
    )
    assert check_hitl_required(memo, risk) is True


def test_hitl_bypass_on_safe_evaluation():
    """Verify HITL is safely bypassed when metrics meet auto-approval criteria."""
    safe_risk = RiskReport(
        critical_risks=[],
        data_privacy_concerns=[],
        operational_fragility="Low",
        overall_risk_level="low",
    )
    clear_memo = LaunchMemo(
        decision="go",
        confidence_score=0.92,
        executive_summary="Internal developer tooling with minimal external risk footprint.",
        mandatory_mitigations=["Weekly token spend alerts"],
        dissenting_concerns=[],
    )
    assert check_hitl_required(clear_memo, safe_risk) is False


@pytest.mark.asyncio
async def test_hitl_human_override_flow():
    """Verify that a human reviewer can override an initial decision and attach stipulations."""

    def mock_human_override(m: LaunchMemo, r: RiskReport) -> HumanReviewRecord:
        return HumanReviewRecord(
            reviewed_by="Chief Compliance Officer",
            action_taken="overridden_to_no_go",
            reviewer_notes="Cannot proceed without SOC2 Type II certification and verified BAA agreements.",
            additional_stipulations=["Complete SOC2 audit before reopening launch review."],
        )

    memo = await run_launchlens(
        pitch="MedScribe: Autonomous agent for oncology clinical trial investigators.",
        offline=True,
        human_review_handler=mock_human_override,
    )

    assert memo.decision == "no_go"
    assert memo.human_review is not None
    assert memo.human_review.reviewed_by == "Chief Compliance Officer"
    assert "Complete SOC2 audit before reopening launch review." in memo.mandatory_mitigations


@pytest.mark.asyncio
async def test_offline_orchestrator_execution():
    """Verifies complete pipeline runs end-to-end in offline mode without crashing."""

    def mock_auto_approve(m: LaunchMemo, r: RiskReport) -> HumanReviewRecord:
        return HumanReviewRecord(
            reviewed_by="Automated Test Runner",
            action_taken="approved",
            reviewer_notes="Automated test fixture validation.",
            additional_stipulations=[],
        )

    pitch = "AI-powered contract parsing tool for local real estate brokers."
    memo = await run_launchlens(pitch, offline=True, human_review_handler=mock_auto_approve)

    assert memo.decision in ["go", "pilot", "no_go"]
    assert 0.0 <= memo.confidence_score <= 1.0
    assert len(memo.executive_summary) > 20