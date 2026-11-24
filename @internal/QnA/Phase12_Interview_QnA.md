# Phase 12 — Interview Questions & Answers

## Core Concepts & Technical Architecture

### Q1: Why build a dedicated Next.js Console UI shell instead of relying on FastAPI's Swagger UI or CLI?
**Answer:**
While Swagger UI (`/docs`) and CLI tools are excellent for developers and API diagnostics, real-world enterprise agentic platforms require non-technical operators (such as operations managers, compliance auditors, and executive decision-makers) to monitor live state machines, inspect risk evaluations, and approve or reject escalations. A dedicated Next.js UI provides:
1. **Interactive Governance:** 1-click approvals for high-dollar disputes with explicit visual context.
2. **Real-Time Visibility:** Live KPI dashboards tracking active state machines, open queues, and SLA deadlines.
3. **Seamless RBAC Personas:** Ability to switch between Viewer, Analyst, and Administrator roles with real-time UI permission gating.

---

### Q2: How does the typed API client communicate with the FastAPI backend and handle authentication?
**Answer:**
The `LakApiClient` is built using modern TypeScript fetch APIs:
- **Bearer Token Management:** It stores the JWT token in `localStorage` upon login and automatically appends `Authorization: Bearer <token>` to all subsequent HTTP requests.
- **Correlation ID Tracking:** Every client request automatically generates and attaches an `X-Request-ID` header. When received by FastAPI's `AuditMiddleware`, the request ID is attached to audit log records and returned in the HTTP response headers, ensuring full end-to-end traceability from the browser to database operations.
- **Type Safety:** All responses and payloads adhere to strict TypeScript interfaces (`ProcessInstance`, `ApprovalRequest`, `UserProfile`, `WorkflowState`), ensuring compile-time safety and preventing schema drift.

---

### Q3: How is Role-Based Access Control (RBAC) enforced between the Frontend and Backend?
**Answer:**
RBAC follows defense-in-depth principles:
- **Frontend Layer:** The React `AuthProvider` maintains the user's roles and permissions, conditionally rendering sensitive actions (such as the "Approve" / "Reject" buttons in `/approvals`, which require `analyst` or `admin` roles).
- **Backend Layer (Source of Truth):** The backend never relies on client-side claims. Every endpoint validates the JWT cryptographic signature and checks user role membership using FastAPI dependency injection (`Depends(require_role(...))`). If a `viewer` attempts to call `POST /api/v1/approvals/{id}/decide`, the backend responds with `403 Forbidden`.

---

### Q4: How does Next.js handle API requests to avoid CORS issues in development and production?
**Answer:**
In `next.config.js`, we configure route rewrites:
```javascript
async rewrites() {
  return [
    {
      source: '/api/v1/:path*',
      destination: (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8001') + '/api/v1/:path*',
    },
  ];
}
```
This proxies `/api/v1/*` requests directly through the Next.js server to the FastAPI backend, allowing the frontend to make same-origin requests (`/api/v1/...`) without triggering browser CORS restrictions, while backend `CORSMiddleware` provides a second layer of defense.

---

### Q5: How is the Next.js frontend integrated into the project's developer tooling and CLI?
**Answer:**
We integrated the UI lifecycle directly into `lakenterprises`:
- Running `lakenterprises ui --port 3001` or `python -m lakenterprises ui` automatically launches the Next.js console shell.
- The repository structure maintains clear separation of concerns: `/frontend` holds the Next.js application, while `/src/lakenterprises/ui.py` provides Python integration hooks and test harnesses.
