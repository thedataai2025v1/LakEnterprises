# Phase 14 — Interview Questions & Answers

## Core Concepts & Technical Architecture

### Q1: What constitutes "production hardening" in an enterprise AI platform?
**Answer:**
Production hardening transforms an experimental or developer prototype into a resilient, secure, and observable enterprise product. Key hardening facets include:
1. **Security & Perimeter Defense:** Enforcing OWASP headers (`nosniff`, `X-Frame-Options: DENY`, `HSTS`, `CSP`), PII sanitization, and explicit origin CORS policies.
2. **Deterministic Containerization:** Packaging services into minimal, multi-stage Docker images running under non-root user accounts with reproducible lockfiles (`uv.lock`).
3. **High Availability & Health Checks:** Implementing decoupled liveness (`/health/live`) and readiness (`/health/ready`) probes for zero-downtime rolling updates.
4. **Comprehensive Documentation:** Exposing standardized OpenAPI schemas (`/openapi.json`), interactive Swagger UI (`/docs`), and Redoc references (`/redoc`).
5. **Synthetic End-to-End Smoke Testing:** Automated validation of critical user journeys before deploying into production.

---

### Q2: Why are liveness and readiness probes separated, and how do they work in this architecture?
**Answer:**
In modern container orchestrators (like Kubernetes or Docker Compose):
- **Liveness Probe (`/health/live`):** Verifies that the application process is alive and responsive. If it fails (e.g., deadlock or unhandled process crash), the orchestrator immediately restarts the container.
- **Readiness Probe (`/health/ready`):** Verifies that downstream dependencies (PostgreSQL database, Redis cache) are reachable and healthy. If the database is under maintenance, readiness fails and traffic is temporarily paused without needlessly restarting the healthy Python process.

---

### Q3: What security headers were implemented and what specific attacks do they prevent?
**Answer:**
Via `SecurityHeadersMiddleware`, we inject:
- `X-Frame-Options: DENY`: Completely mitigates Clickjacking attacks where attackers attempt to iframe the console shell inside an invisible layer on a malicious site.
- `X-Content-Type-Options: nosniff`: Prevents MIME-confusion attacks and malicious script execution disguised as images.
- `Strict-Transport-Security (HSTS)`: Instructs browsers to enforce HTTPS exclusively for 1 year (`max-age=31536000; includeSubDomains`), eliminating SSL-stripping man-in-the-middle attacks.
- `Content-Security-Policy (CSP)`: Restricts trusted script, stylesheet, and font origins, preventing Cross-Site Scripting (XSS) and arbitrary JavaScript injection.
- `Referrer-Policy: strict-origin-when-cross-origin`: Protects sensitive URL paths and query parameters from leaking to external domains.

---

### Q4: How does the Docker Compose setup guarantee deterministic, failure-free startups?
**Answer:**
We use Docker Compose service dependency conditions:
```yaml
backend:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    qdrant:
      condition: service_healthy
```
Instead of merely waiting for the Postgres container process to spawn, Docker holds the backend container until the database's `pg_isready` check returns `0`. This eliminates startup race conditions and database connection timeouts during deployment.

---

### Q5: What is the purpose of the end-to-end smoke test suite (`test_e2e_smoke.py`)?
**Answer:**
While unit tests verify isolated functions with mocks, synthetic smoke tests validate the entire system integration against production middleware:
1. Validates that security headers and CSP are attached to live responses.
2. Verifies that OpenAPI and Redoc documentation render valid specs.
3. Simulates a complete user journey: authenticating as an analyst, ingesting a regulatory agreement, triggering a high-value multi-agent workflow ($175,000), verifying the 1-hour SLA tier, and submitting an approved human decision that successfully resolves the ticket.
