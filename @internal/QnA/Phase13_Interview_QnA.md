# Phase 13 — Interview Questions & Answers

## Core Concepts & Technical Architecture

### Q1: What is the primary purpose of the Process Workflow Screen in an enterprise agentic application?
**Answer:**
Autonomous AI workflows executing multi-step reasoning across finance, CRM, and ERP systems cannot be treated as opaque black boxes. The Process Workflow Screen (`/processes/[id]`) provides:
1. **Live Visual State Transparency:** Renders the 13-node LangGraph execution sequence so business stakeholders can see which specialist agent is executing, which nodes succeeded, and where the workflow paused.
2. **Deterministic Human-in-the-Loop Gate:** Gives managers an interactive decision interface (Approve / Reject / Escalate) when financial or risk thresholds are exceeded.
3. **Trace Telemetry & Audit:** Displays chronological event streams, millisecond execution durations, and step outputs for auditability and SLA tracking.

---

### Q2: Why use client-side polling instead of WebSockets or SSE for this screen?
**Answer:**
In enterprise architectures, standard HTTP polling (e.g., 3-second interval) offers distinct operational advantages:
- **Firewall & Proxy Compatibility:** Corporate firewalls, API gateways, and load balancers often sever or aggressively drop long-lived WebSocket connections, while standard HTTP GET requests pass reliably through standard infrastructure.
- **Stateless & Scalable:** Each poll is a lightweight, stateless query to the in-memory or Redis checkpointer, easily distributed across horizontally scaled FastAPI backend instances without requiring sticky sessions or complex WebSocket connection registries.
- **Fault-Tolerant & Reconnecting:** If network connectivity drops momentarily, the next poll interval automatically recovers state without requiring complex socket reconnection or state-resynchronization protocols.

---

### Q3: How does the UI screen resume execution after a human approves a paused workflow?
**Answer:**
The flow consists of four coordinated steps:
1. When the workflow hits `human_approval_node` and requires authorization, it saves a snapshot into `WorkflowCheckpointer` and enters status `AWAITING_APPROVAL`.
2. The UI screen detects this status and unlocks the **ProcessActions** decision buttons.
3. The reviewer enters audit notes and clicks **Approve & Resume**, which dispatches `POST /api/v1/workflow/{id}/decide` with `{ decision: "APPROVED", notes: "..." }`.
4. The backend loads the exact checkpoint state from storage, marks `approval_status = "approved"`, and resumes execution directly into `execute_resolution_node` (invoking the ERP/CRM write tool), avoiding redundant LLM queries or duplicate agent runs.

---

### Q4: How are SLA timers calculated and monitored in the workflow UI?
**Answer:**
SLA tracking is driven by `EscalationRouter`:
- Transactions are categorized by exposure into four tiers: `TIER_1_ANALYST` (24h limit), `TIER_2_MANAGER` (8h limit), `TIER_3_DIRECTOR` (4h limit), and `TIER_4_EXECUTIVE` (1h limit).
- The endpoint `GET /api/v1/workflow/{id}/sla` calculates elapsed hours from the process start time against the tier's maximum allowed duration.
- The UI's `WorkflowStepsPanel` renders an SLA status badge (`ON SCHEDULE` vs `SLA BREACHED`) and displays an active countdown of hours remaining.

---

### Q5: How is Role-Based Access Control (RBAC) enforced on the workflow screen?
**Answer:**
We enforce security at both the presentation and API layer:
- **Presentation Layer:** The `ProcessActions` component uses `useAuth()` to inspect the operator's active role. If a user is logged in as `viewer`, the Approve, Reject, and Escalate buttons are disabled, accompanied by an explicit warning banner.
- **Backend API Layer:** Even if a malicious user bypasses the UI and issues a raw `POST /api/v1/workflow/{id}/decide` request, FastAPI dependency injection checks role membership. Only `analyst` and `admin` roles possess authorization, returning `403 Forbidden` to unauthorized users.
