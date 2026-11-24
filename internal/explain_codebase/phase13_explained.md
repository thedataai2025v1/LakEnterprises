# Phase 13 — Process Workflow Screen Explained (Layman's Guide)

## Overview: The Interactive "Flight Deck" for Agentic Workflows

In Phase 12, we created the shell of the console UI: the navigation bar, basic tables, and user login. 

In **Phase 13**, we built the heart of the operational platform: the **Process Workflow Screen** (`/processes/[id]`). 

Think of this like an interactive mission-control glass cockpit used in NASA launches. When an autonomous AI process starts investigating an enterprise issue (like a $150,000 corporate vendor dispute or compliance violation), operations managers and executives do not have to guess what the AI is thinking or wait in the dark. 

The **Process Workflow Screen** provides:
1. **Live Step-by-Step Visualization:** A live 13-node graph stepper showing exactly which agent is running, which steps have passed, and where the workflow is currently evaluating.
2. **Real-Time Polling & Telemetry:** Updates every 3 seconds automatically without reloading the page, streaming duration metrics and node payloads.
3. **Interactive Human Governance Gate:** When high-risk actions halt the workflow, a clean decision panel displays the dispute amount, calculated risk, and 1-click **Approve**, **Reject**, or **Escalate** controls.
4. **Permanent Audit Timeline:** An event stream displaying each milestone, timestamps, and tool execution payloads for SOX or regulatory verification.

---

## 1. How Does It Work in Plain English?

```
[ Operator in Browser (:3001) ]
       │
       │  (Auto-polls /api/v1/workflow/{id}/state & /events every 3s)
       ▼
┌────────────────────────────────────────────────────────┐
│ Process Detail Screen (/processes/[id])                │
│                                                        │
│  [ Left Column: Steps Panel ]                          │
│   1. Orchestrator Intake         (Passed ✅)           │
│   2. Document Analyst            (Passed ✅)           │
│   3. Compliance Verification     (Passed ✅)           │
│   ...                                                  │
│   9. Human Approval Gate         (AWAITING PAUSE ⚠️)   │
│                                                        │
│  [ Right Column: Decision & Timeline ]                 │
│   - Dispute: $150,000.00 | Risk: CRITICAL | SLA: 1 hr  │
│   - Actions: [ Approve & Resume ] [ Reject ] [Escalate]│
│   - Live Timeline: Step duration (ms), JSON payloads   │
└────────────────────────────────────────────────────────┘
       │
       │ (Manager clicks "Approve & Resume")
       ▼
[ FastAPI Backend / LangGraph ] ──► [ Resumes saved checkpoint & executes resolution ]
```

### The 4 Real-World Parts of the Workflow Screen:
1. **The 13-Node Graph Engine Panel (`workflow-steps-panel.tsx`):**
   Displays the canonical LangGraph sequence from Intake to Final Output Guard. Green badges indicate completed steps, pulsing blue shows live execution, and glowing amber highlights human pause gates.
2. **SLA Countdown & Breach Monitor:**
   Calculates corporate SLA windows based on the transaction amount tier (Tier 1 Analyst = 24h, Tier 4 Executive = 1h). The UI warns operators in real time if an SLA is at risk of breach.
3. **Human Approval Action Bar (`process-actions.tsx`):**
   Allows authorized personnel to review audit justification notes and click **Approve & Resume** (which unfreezes the checkpoint and triggers tool actions), **Reject & Halt** (closing the case), or **Escalate to Senior** (transferring to a higher seniority tier).
4. **Event Stream Timeline (`process-timeline.tsx`):**
   Visualizes the internal trace events recorded by the `WorkflowTracer`, capturing millisecond durations, error alerts, and tool inputs.

---

## 2. Key Components Created in Phase 13

| Component | Metaphor | What it Does in Code |
|---|---|---|
| **`ProcessDetailPage` (`/processes/[id]`)** | **The Pilot's Display** | Master screen coordinating state polling, breadcrumbs, SLA indicators, and layout split. |
| **`WorkflowStepsPanel`** | **The Checklist** | Visual representation of all 13 LangGraph nodes with current node highlights and status tags. |
| **`ProcessActions`** | **The Control Yoke** | Interactive buttons with audit justification modals to decide approvals and resume paused state machines. |
| **`ProcessTimeline`** | **The Flight Data Recorder** | Chronological event trace with step durations, node payloads, and error indicators. |
| **API Client Extensions** | **The Telemetry Link** | Added `getWorkflowEvents`, `getWorkflowCheckpoints`, `getWorkflowSLA`, and `decideWorkflowApproval` to `LakApiClient`. |

---

## 3. Why This Matters to Recruiters & Non-Technical Stakeholders

- **Complete Transparency:** Eliminates the "black box" stigma of enterprise AI. Every decision, LLM call, and tool interaction is visible in real time.
- **Fail-Safe Governance:** The system cannot disburse money or alter critical CRM/ERP data without an authorized human submitting an approved decision through this screen.
- **Audit-Ready Compliance:** Everything displayed on the timeline is backed by immutable database checkpoints and audit logs, ready for compliance inspection.
