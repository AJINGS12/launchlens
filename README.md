# LaunchLens: Multi-Agent AI Product Launch Due Diligence

LaunchLens evaluates early-stage AI product launches across customer demand, competition, and risk before issuing an executive recommendation[cite: 1, 6, 7].

---

## 1. Problem & Multi-Agent Rationale
A single LLM prompt fails due to[cite: 1]:
* **Sycophancy:** Anchoring on optimistic founder assumptions[cite: 1].
* **Context Dilution:** Mixing legal risks, market claims, and technical moats weakens risk detection[cite: 1].
* **Lack of Adversarial Checks:** Fails to self-critique, leading to unbacked "go" recommendations[cite: 1, 2].

LaunchLens separates concerns across specialized agents and synthesizes findings into an audited decision[cite: 2, 6, 9].

---

## 2. Agents
* **`MarketAnalyst`**: Evaluates customer pain, urgency (1–10), ICP, and adoption blockers[cite: 6].
* **`CompetitionAnalyst`**: Maps alternatives, switching costs, moats, and platform kill-shot risks[cite: 7].
* **`RiskAnalyst`**: Audits compliance (HIPAA/GDPR), privacy leakage, operational dependencies, and hallucination liability[cite: 7].
* **`LaunchDecisionSynthesizer`**: Reconciles specialist reports into a single `LaunchMemo` (`go`, `pilot`, or `no_go`)[cite: 6, 7, 8].

---

## 3. Design Patterns
* **Parallel Fan-Out:** Domain specialists run concurrently via `asyncio.gather`[cite: 8].
* **Typed Structured Outputs:** Pydantic schemas enforce report validation[cite: 9, 13].
* **Reducer / Synthesis:** A dedicated agent resolves conflicting findings[cite: 9].
* **Adversarial Quality Gate:** Programmatic logic rejects unbacked `go` outcomes if risk is high/critical[cite: 10].
* **Human-in-the-Loop (HITL):** Halts on high-risk conditions or agent dissents for human override and binding stipulations[cite: 10, 11, 12].
* **Offline Demo Mode:** Deterministic fixtures run locally without API keys or token spend[cite: 13, 14].

---

## 4. Setup & Testing

### Installation
```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt


Run Automated Tests
Bash
pytest -v test_launchlens.py


Run Offline Demo (Zero API Cost)
Bash
python orchestrator.py --demo



Run Live with OpenAI API
Bash
# Windows PowerShell:
$env:OPENAI_API_KEY="sk-..."
python orchestrator.py

# macOS / Linux:
export OPENAI_API_KEY="sk-..."
python orchestrator.py