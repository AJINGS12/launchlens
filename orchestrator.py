import asyncio
import os
import sys
from typing import Tuple, Optional, Callable
from agents import Runner
from schemas import (
    MarketReport,
    CompetitionReport,
    RiskReport,
    LaunchMemo,
    HumanReviewRecord,
)
from agents_registry import (
    market_analyst,
    competition_analyst,
    risk_analyst,
    launch_synthesizer,
)


class AdversarialGateError(Exception):
    """Raised when hard automated quality rules are violated."""
    pass


def evaluate_adversarial_quality_gate(memo: LaunchMemo, risk_rep: RiskReport) -> None:
    """Hard automated checks to intercept invalid or contradictory recommendations."""
    # Rule 1: No automated 'go' if risk is critical or high
    if memo.decision == "go" and risk_rep.overall_risk_level in ["critical", "high"]:
        raise AdversarialGateError(
            f"Automated Gate Failure: Memo attempted 'go' while risk is '{risk_rep.overall_risk_level}'."
        )

    # Rule 2: Confidence score minimum for 'go'
    if memo.decision == "go" and memo.confidence_score < 0.70:
        raise AdversarialGateError(
            f"Automated Gate Failure: 'go' decision requires >= 0.70 confidence (got {memo.confidence_score})."
        )

    # Rule 3: Must specify mitigations for positive trajectories
    if memo.decision in ["go", "pilot"] and len(memo.mandatory_mitigations) == 0:
        raise AdversarialGateError(
            f"Automated Gate Failure: Decision '{memo.decision}' has 0 mandatory mitigations."
        )


def check_hitl_required(memo: LaunchMemo, risk_rep: RiskReport) -> bool:
    """Evaluates if high risk or agent tension warrants human escalation."""
    if memo.decision == "pilot" and risk_rep.overall_risk_level in ["medium", "high"]:
        return True
    if len(memo.dissenting_concerns) > 0:
        return True
    if memo.confidence_score < 0.80 and memo.decision != "no_go":
        return True
    return False


def terminal_human_reviewer_prompt(memo: LaunchMemo, risk_rep: RiskReport) -> HumanReviewRecord:
    """CLI handler prompting a human reviewer for input and sign-off."""
    print("\n" + "=" * 60)
    print("🚨 HUMAN-IN-THE-LOOP INTERVENTION TRIGGERED")
    print("=" * 60)
    print(f"Synthesized Decision : {memo.decision.upper()}")
    print(f"Model Confidence     : {memo.confidence_score * 100:.1f}%")
    print(f"Assessed Risk Level  : {risk_rep.overall_risk_level.upper()}")
    print("\nIdentified Critical Risks:")
    for r in risk_rep.critical_risks:
        print(f"  • {r}")
    print("\nDissenting Specialist Concerns:")
    for d in memo.dissenting_concerns:
        print(f"  • {d}")
    print("-" * 60)

    print("Choose action:")
    print(" [1] Approve decision as proposed")
    print(" [2] Override to PILOT (isolated sandbox)")
    print(" [3] Override to NO_GO (terminate initiative)")

    choice = input("Enter choice (1/2/3) [default: 1]: ").strip() or "1"
    reviewer_name = input("Enter your Name/Role [e.g., Head of Risk]: ").strip() or "Reviewing Lead"
    notes = input("Enter rationale: ").strip() or "Approved in accordance with compliance baseline."
    stipulation = input("Enter mandatory human stipulation (or press Enter to skip): ").strip()

    action_map = {
        "1": "approved",
        "2": "overridden_to_pilot",
        "3": "overridden_to_no_go"
    }

    return HumanReviewRecord(
        reviewed_by=reviewer_name,
        action_taken=action_map.get(choice, "approved"),
        reviewer_notes=notes,
        additional_stipulations=[stipulation] if stipulation else []
    )


def _get_offline_reports() -> Tuple[MarketReport, CompetitionReport, RiskReport, LaunchMemo]:
    """Deterministic offline data fixtures allowing local tests without API keys."""
    market = MarketReport(
        core_pain_point="Manual compliance workflows in clinical research trials take 35 hours weekly.",
        urgency_score=8,
        target_buyer="Clinical Operations VP",
        adoption_blockers=["Integration with legacy EDC software", "Hospital IRB approval delays"]
    )
    competition = CompetitionReport(
        direct_competitors=["Veeva Systems", "Deep6 AI"],
        switching_cost_rating="high",
        moat_defensibility="Proprietary workflow integration with local hospital EMRs.",
        kill_shot_risk="Moderate: Veeva could bundle a lighter version into its existing clinical suite."
    )
    risk = RiskReport(
        critical_risks=["HIPAA patient identification leakage through prompt context"],
        data_privacy_concerns=["Cross-border model inference processing sensitive health information"],
        operational_fragility="High latency from multi-step recursive retrieval over complex clinical PDFs",
        overall_risk_level="high"
    )
    memo = LaunchMemo(
        decision="pilot",
        confidence_score=0.76,
        executive_summary="Strong market demand, but HIPAA and integration risks require a sandboxed pilot before general launch.",
        mandatory_mitigations=[
            "Deploy on-premise de-identification proxy before forwarding data to LLM APIs",
            "Establish Business Associate Agreements (BAAs) with all model providers"
        ],
        dissenting_concerns=["Risk analyst warns against multi-tenant cloud hosting for clinical trial data"]
    )
    return market, competition, risk, memo


async def run_launchlens(
    pitch: str,
    offline: bool = False,
    human_review_handler: Optional[Callable[[LaunchMemo, RiskReport], HumanReviewRecord]] = None
) -> LaunchMemo:
    """Executes the complete LaunchLens pipeline."""

    # Phase 1: Fan-out & Execution
    if offline or not os.getenv("OPENAI_API_KEY"):
        print("[LaunchLens] Running in OFFLINE mode (deterministic fixtures)...")
        market_rep, comp_rep, risk_rep, memo = _get_offline_reports()
    else:
        print("[LaunchLens] Phase 1: Fan-out - running specialist agents in parallel...")
        market_res, comp_res, risk_res = await asyncio.gather(
            Runner.run(market_analyst, pitch),
            Runner.run(competition_analyst, pitch),
            Runner.run(risk_analyst, pitch)
        )
        market_rep: MarketReport = market_res.final_output
        comp_rep: CompetitionReport = comp_res.final_output
        risk_rep: RiskReport = risk_res.final_output

        print("[LaunchLens] Phase 2: Reducer - synthesizing specialist reports...")
        synthesis_input = (
            f"Product Pitch: {pitch}\n\n"
            f"--- Market Report ---\n{market_rep.model_dump_json(indent=2)}\n\n"
            f"--- Competition Report ---\n{comp_rep.model_dump_json(indent=2)}\n\n"
            f"--- Risk Report ---\n{risk_rep.model_dump_json(indent=2)}\n"
        )
        synth_res = await Runner.run(launch_synthesizer, synthesis_input)
        memo: LaunchMemo = synth_res.final_output

    # Phase 2: Automated Quality Gate
    print("[LaunchLens] Phase 3: Validating adversarial quality gate...")
    evaluate_adversarial_quality_gate(memo, risk_rep)

    # Phase 3: Human-in-the-Loop Review Gate
    if check_hitl_required(memo, risk_rep):
        print("[LaunchLens] HITL Required: Escalating to human reviewer...")
        handler = human_review_handler or terminal_human_reviewer_prompt
        review_record = handler(memo, risk_rep)

        memo.human_review = review_record
        if review_record.action_taken == "overridden_to_pilot":
            memo.decision = "pilot"
        elif review_record.action_taken == "overridden_to_no_go":
            memo.decision = "no_go"

        if review_record.additional_stipulations:
            memo.mandatory_mitigations.extend(review_record.additional_stipulations)
    else:
        print("[LaunchLens] HITL Bypass: All metrics fall within automated approval thresholds.")

    return memo


if __name__ == "__main__":
    sample_pitch = (
        "MedScribe: An autonomous agent for oncology clinical trial investigators that reads patient records, "
        "auto-populates trial eligibility forms, and drafts regulatory submissions."
    )
    is_offline = "--demo" in sys.argv or not bool(os.getenv("OPENAI_API_KEY"))
    result = asyncio.run(run_launchlens(sample_pitch, offline=is_offline))
    print("\n" + "=" * 60)
    print("📋 FINAL CERTIFIED LAUNCH MEMO")
    print("=" * 60)
    print(f"Final Decision:      {result.decision.upper()}")
    print(f"Model Confidence:    {result.confidence_score * 100:.1f}%")
    print(f"Executive Summary:   {result.executive_summary}")
    print(f"Mitigations:         {result.mandatory_mitigations}")
    if result.human_review:
        print(f"Reviewed By:         {result.human_review.reviewed_by} ({result.human_review.action_taken})")
        print(f"Reviewer Notes:      {result.human_review.reviewer_notes}")