# Phase 9 Technical Interview Preparation: Specialist Agents

## 1. High-Level Concepts & Multi-Agent Architecture

### Q1: What was the primary objective of Phase 9, and why did you transition from a single monolithic agent to a team of specialist agents?
**Answer:**
A single monolithic prompt suffers from **cognitive overload**, high token cost, prompt-tuning fragility, and hallucination risk when attempting to parse documents, audit regulatory compliance, query historical memories, draft formal communications, and evaluate security threats simultaneously.
In Phase 9, we applied the **Single Responsibility Principle (SRP)** to autonomous AI by implementing a modular team of 6 specialist agents:
1. **`SupervisorAgent`:** Evaluates high-level goals and decomposes them into ordered specialist subtasks.
2. **`DocumentAnalysisAgent`:** Ingests unstructured agreements, extracting structured entities, terms, and risk clauses.
3. **`ComplianceAgent`:** Audits proposed transactions against corporate policies and approval thresholds ($100k limits).
4. **`KnowledgeRetrievalAgent`:** Searches multi-source knowledge bases and enterprise memories for grounded citations.
5. **`ResponseDraftingAgent`:** Generates professional communications strictly grounded in verified facts.
6. **`EscalationHandoffAgent`:** Analyzes operational threats and formats human handoff packets and incident tickets.

---

### Q2: How do specialist agents communicate with each other? What prevents schema drift?
**Answer:**
Specialist agents communicate strictly via **typed Pydantic schemas**:
- Every agent invocation requires an `AgentTask` payload specifying `role`, `instruction`, `context`, and `parameters`.
- Every agent execution returns a standardized `AgentResult` containing `status`, `output_data` (validated against a specific Pydantic model such as `ComplianceResult` or `DocumentAnalysisResult`), `confidence_score`, `citations`, and execution `metrics`.
- If an underlying model returns an unexpected key or missing required attribute, Pydantic's `model_validate()` fails fast at the agent boundary, preventing corrupted data from entering downstream workflow nodes or database tables.

---

## 2. Technical Implementation & Design Patterns

### Q3: How is the `BaseSpecialistAgent[T]` structured, and what design patterns does it use?
**Answer:**
`BaseSpecialistAgent[T]` employs the **Template Method Pattern** and Python Generics:
```python
class BaseSpecialistAgent(Generic[T]):
    role: AgentRole
    output_schema: Type[T]

    def build_prompt(self, task: AgentTask) -> str:
        # Standardizes role headers, instructions, context, and parameters
        ...

    def run(self, task: AgentTask) -> AgentResult:
        # Measures latency
        # Dispatches prompt to FakeLLMHarness or live LLM
        # Validates output with output_schema.model_validate(raw_output)
        # Extracts citations and confidence scores
        # Returns standard AgentResult
```
**Benefits:**
- **Code Reuse:** Metrics collection, prompt formatting, schema validation, and error trapping are written once in the base class.
- **Type Safety:** Subclasses only declare their `role` and `output_schema` (e.g. `ComplianceAgent(BaseSpecialistAgent[ComplianceResult])`).

---

### Q4: What is the purpose of the `FakeLLMHarness`, and how does it support offline testing?
**Answer:**
Calling commercial LLMs (OpenAI, Anthropic) during CI/CD builds or unit testing causes severe drawbacks: high API costs, rate limiting, network latency, and non-deterministic assertions.
The `FakeLLMHarness`:
1. Acts as a deterministic test double.
2. Generates schema-valid responses tailored to each `AgentRole` (e.g., realistic contract extraction for `DOCUMENT_ANALYST`, threshold checks for `COMPLIANCE`).
3. Supports custom keyword overrides via `register_response(trigger_phrase, custom_dict)`.
4. Allows simulating latency and error rates to test resilience.
5. Executes our entire 15-test suite in **0.70 seconds** 100% offline with zero external network access.

---

### Q5: How does the Compliance Agent enforce financial limits and policies?
**Answer:**
The `ComplianceAgent`:
- Inspects the transaction payload (e.g. `amount`, `vendor`).
- Evaluates corporate policies (such as single-approver financial threshold of \$100,000).
- If the amount $\ge \$100,000$, it marks `is_compliant = False`, sets `risk_level = "CRITICAL"`, appends a `ComplianceViolation(rule_id="POL-FIN-100K", severity="CRITICAL")`, and specifies `recommendation = "Halt automated action. Route to Executive Board."`
- Otherwise, it returns `is_compliant = True` with `risk_level = "LOW"`.

---

## 3. Evaluation & Quality Assurance

### Q6: How does the Benchmark Evaluation Dataset (`P9-8`) work?
**Answer:**
We implemented `BENCHMARK_SCENARIOS` in `eval_dataset.py`:
- Contains structured enterprise test cases covering all 6 agent roles (e.g. procurement contract extraction, routine purchases, threshold breaches, grounded fact retrieval, and security incident handoffs).
- `evaluate_scenario(agent, scenario)` executes the agent against the scenario and validates key assertions (e.g. `is_compliant`, `violations_count`, `citations_min`, `requires_human`, `target_role`).
- The evaluation can be run directly from the CLI via `python -m lakenterprises agent eval`, reporting per-scenario status, latency, and a summary score (e.g. `6/6 passed`).

---

### Q7: How does Phase 9 lay the groundwork for Phase 10 (Workflow Graph & Tracing)?
**Answer:**
In Phase 10, the platform will implement a LangGraph `StateGraph` checkpointer and runtime tracer. Because Phase 9 established:
1. Distinct specialist agents with pure input $\rightarrow$ output contracts,
2. Validated Pydantic output schemas,
3. A standardized supervisor planner,
...the LangGraph nodes in Phase 10 can simply wrap these specialist agents as graph nodes, using the schemas as graph state transitions without needing to rewrite agent logic.
