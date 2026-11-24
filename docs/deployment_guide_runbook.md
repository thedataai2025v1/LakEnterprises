# LakEnterprises — Production Deployment Guide & Operations Runbook

## Overview
This runbook guides DevOps, SRE, and platform engineers through configuring, building, testing, deploying, and operating the LakEnterprises platform in production environments.

---

## 1. Architecture & Port Map

| Component | Port | Technology | Purpose |
|---|---|---|---|
| **Next.js Console UI** | `3001` | Next.js 15, React 19, Tailwind | Business user mission control cockpit |
| **FastAPI Backend Engine** | `8001` | Python 3.12, Uvicorn, LangGraph | Multi-agent reasoning, workflows, REST APIs |
| **PostgreSQL Database** | `5432` | Postgres 16 | Relational entities, audit trail, checkpoints |
| **Redis Cache** | `6379` | Redis 7 | Rate limiting, session memory, sliding windows |
| **Qdrant Vector DB** | `6333` | Qdrant 1.12 | Vector search & document chunk embeddings |

---

## 2. Environment Variables & Secret Configuration

Copy `.env.example` to `.env` and configure appropriate production credentials:

```bash
# Core Environment
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=YOUR_ENTERPRISE_CRYPTO_SECRET_KEY_MIN_32_CHARS

# Database (PostgreSQL)
POSTGRES_USER=lak_user
POSTGRES_PASSWORD=YOUR_STRONG_PASSWORD
POSTGRES_DB=lakenterprises_prod
DATABASE_URL=postgresql+psycopg2://lak_user:YOUR_STRONG_PASSWORD@localhost:5432/lakenterprises_prod

# Cache & Vector Store
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333

# Rate Limiting & Security
RATE_LIMIT_PER_MINUTE=120
ALLOWED_ORIGINS=https://console.lakenterprises.com,http://localhost:3001

# LLM Provider Configuration
LLM_PROVIDER=openai # Or: fake, anthropic, azure, ollama
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

---

## 3. Deployment Options

### Option A: Local / Stage Multi-Container Stack (Docker Compose)
Run the full production-like environment with one command:

```bash
# Build and start all 5 services in detached mode
docker compose up -d --build

# Verify running containers
docker compose ps

# Tail backend and frontend logs
docker compose logs -f backend frontend
```

### Option B: Bare-Metal / Virtual Machine Deployment
```bash
# 1. Install Python 3.12 and uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Sync locked production dependencies
uv sync --frozen --no-dev

# 3. Start Uvicorn Backend with multiple worker processes
uv run uvicorn lakenterprises.app:app --host 0.0.0.0 --port 8001 --workers 4

# 4. Start Next.js Console UI Shell
cd frontend && npm install && npm run build && npm start
```

---

## 4. Health Checks & Synthetic Probes

- **Liveness Probe:** `GET /health/live`  
  Checks if the Python Uvicorn process is responding (Returns `200 OK`).
- **Readiness Probe:** `GET /health/ready`  
  Checks database and cache connectivity before routing traffic.
- **API Spec & Docs:**  
  - OpenAPI Spec: `GET /openapi.json`
  - Swagger UI: `GET /docs`
  - Redoc Documentation: `GET /redoc`

---

## 5. Operations & Incident Response Runbook

### Scenario 1: High SLA Breach Alerts
- **Symptom:** Operations board flags `SLA BREACHED` on workflow queues.
- **Diagnosis:** Run `lakenterprises workflow --id <id> trace` or check `/processes/<id>` in the Console UI.
- **Resolution:** Contact designated tier executive (Tier 4: Executive CFO/VP) or submit an authorized override approval via `POST /api/v1/workflow/<id>/decide`.

### Scenario 2: Rate Limit Throttling (HTTP 429)
- **Symptom:** Clients receiving `429 Too Many Requests`.
- **Diagnosis:** Inspect Redis sliding window key counts: `redis-cli keys "rate_limit:*"`
- **Resolution:** Increase `RATE_LIMIT_PER_MINUTE` in `.env` or adjust client concurrency backoff.

### Scenario 3: Database Connection Pool Exhaustion
- **Symptom:** Readiness probe returns `status: degraded` and `database: disconnected`.
- **Resolution:** Check PostgreSQL connection count:
  ```sql
  SELECT count(*) FROM pg_stat_activity WHERE datname = 'lakenterprises_prod';
  ```
  Adjust `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` in `lakenterprises/config.py`.
