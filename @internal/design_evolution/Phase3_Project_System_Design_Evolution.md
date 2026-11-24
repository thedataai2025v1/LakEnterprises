# Phase 3 — System Design Evolution: Identity and Access Control

> **Scope:** Architectural journey and design evolution of the security, authorization, rate limiting, and auditing infrastructure in LakEnterprises.

---

## 1. Executive Summary & Design Goals

In an enterprise-grade AI and knowledge research platform, security cannot be an afterthought bolted onto endpoints. It must be an integral architectural layer that guarantees:
- **Zero-Trust Identity Verification:** Every API call is authenticated and authorized statelessly using industry-standard JSON Web Tokens (JWT).
- **Least-Privilege Role-Based Access Control (RBAC):** Granular separation of concerns across 6 distinct roles (`admin`, `manager`, `analyst`, `viewer`, `auditor`, `system`) and 25 operational permissions.
- **DDoS and Brute-Force Resilience:** Distributed sliding-window rate limiting backed by Redis sorted sets with zero-overhead in-memory fallback.
- **Non-Repudiation & Auditability:** Transparent ASGI request interception recording execution duration, user identity, IP address, and status codes.

---

## 2. Architectural Evolution Across Phase 3

### Stage 1: Initial Baseline Design (Pre-Phase 3)

At the onset of Phase 3, the backend only supported basic database entities without an HTTP authorization gateway, token generation, rate limiting, or request tracking.

```mermaid
flowchart TD
    Client[HTTP Client] -->|Unauthenticated Requests| Router[Direct Router / Endpoints]
    Router -->|Direct Query| DB[(Database / Repository)]
    
    style Client fill:#f9f9f9,stroke:#333
    style Router fill:#ffdddd,stroke:#f00
    style DB fill:#e1f5fe,stroke:#0288d1
```

**Limitations of Baseline Design:**
- Endpoints were unprotected; any client could trigger expensive retrieval queries or administrative mutations.
- No session tracking or revocation mechanisms.
- Vulnerable to volumetric abuse, brute-force password guessing, and API scrapers.
- No audit trails for security investigations or regulatory compliance.

---

### Stage 2: Subtasks P3-1 & P3-2 — Cryptographic JWT & Granular RBAC

In Subtask P3-1 and P3-2, we implemented the identity core:
1. **Password Hashing:** PBKDF2-HMAC-SHA256 with 100,000 iterations and per-user unique 32-byte cryptographically secure salts.
2. **Dual-Token Architecture:**
   - **Access Token:** Short-lived (60 minutes) containing signed claims (`sub`, `roles`, `permissions`, `exp`, `jti`).
   - **Refresh Token:** Long-lived (7 days) stored with hashed lookup and atomic revocation semantics.
3. **Role & Permission Matrix:** Pre-seeded with 6 enterprise roles and 25 fine-grained permissions.

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Client
    participant AuthRoute as /api/v1/auth/login
    participant Service as AuthService
    participant Repo as UserRepository
    participant DB as SQLite / PostgreSQL

    User->>AuthRoute: POST Credentials (username, password)
    AuthRoute->>Service: authenticate_user(username, password)
    Service->>Repo: get_by_username_or_email(username)
    Repo->>DB: SELECT * FROM users WHERE ...
    DB-->>Repo: User entity (with password_hash)
    Repo-->>Service: User Record
    Service->>Service: Verify PBKDF2/Bcrypt hash
    Service->>Service: create_access_token() + create_refresh_token()
    Service->>DB: Persist AuthToken record
    Service-->>AuthRoute: TokenResponse (access_token, refresh_token, roles, perms)
    AuthRoute-->>User: 200 OK + JWT Tokens
```

---

### Stage 3: Subtask P3-3 — Distributed Sliding-Window Rate Limiter

Fixed-window rate limiters suffer from boundary traffic bursts (e.g., doubling the limit at window transitions). To solve this, Phase 3 introduced a **Sliding Window Counter** using **Redis Sorted Sets (ZSET)**.

#### Algorithmic Design:
1. Key structure: `rate_limit:{client_ip}:{window_seconds}`
2. At timestamp $T$:
   - `ZREMRANGEBYSCORE key 0 (T - window_seconds)`: Prune entries older than the rolling window.
   - `ZCARD key`: Count remaining entries in the current window.
   - If count $\ge$ limit: Reject request with HTTP 429 and calculate `Retry-After`.
   - Else: `ZADD key T T` and `EXPIRE key window_seconds`.
3. **Graceful Fallback:** If Redis is down or unavailable, the limiter automatically falls back to an in-memory `collections.deque` with zero downtime.

```mermaid
flowchart TD
    Req[Incoming HTTP Request] --> KeyGen[Generate Rate Limit Key\nrate_limit:client_ip:60]
    KeyGen --> RedisCheck{Redis Available?}
    
    RedisCheck -- Yes --> Zrem[ZREMRANGEBYSCORE: Drop Timestamps < T - 60]
    Zrem --> Zcard[ZCARD: Count Requests in Window]
    Zcard --> LimitCheck{Count >= Limit?}
    
    LimitCheck -- Yes --> Reject[Return HTTP 429 Too Many Requests\nHeaders: Retry-After, X-RateLimit-*]
    LimitCheck -- No --> Zadd[ZADD: Add Current Timestamp T\nEXPIRE: 60s]
    Zadd --> NextMiddleware[Proceed to Next Handler]
    
    RedisCheck -- No --> MemFallback[In-Memory Deque Sliding Window]
    MemFallback --> LimitCheck
```

---

### Stage 4: Subtask P3-4 & Final Integrated System Design

The final system design coordinates ASGI middleware, rate limiting, audit logging, and dependency-injected security guards into a unified, high-performance pipeline.

```mermaid
flowchart TD
    Client([HTTP Client / Frontend]) --> Ingress[Reverse Proxy / Ingress :8001]
    
    subgraph ASGI_Pipeline["FastAPI ASGI Pipeline"]
        Ingress --> CORS[1. CORSMiddleware]
        CORS --> RateLimit[2. RateLimitMiddleware\nSliding Window Redis/Memory]
        RateLimit -->|Exceeded| Res429[429 Too Many Requests]
        
        RateLimit -->|Allowed| AuditMid[3. AuditMiddleware\nGenerates X-Request-ID\nMeasures Latency]
        
        subgraph Routing_Layer["FastAPI Routing & Auth Gateways"]
            AuditMid --> AuthRouter["/api/v1/auth/*\n(Public Endpoints: Login, Refresh, Demo)"]
            AuditMid --> ProtectedRouter["/api/v1/protected/*\n(Guarded Endpoints)"]
            
            ProtectedRouter --> AuthDep["Security Dependency\nget_current_user\nrequire_role('admin' | 'analyst')"]
            AuthDep -->|Invalid/Expired Token| Res401[401 Unauthorized]
            AuthDep -->|Insufficient Role| Res403[403 Forbidden]
            AuthDep -->|Authorized| Controller[Business Logic / Pipeline Controller]
        end
    end
    
    subgraph Data_Layer["Enterprise Services & Persistence"]
        Controller --> Services[Enterprise Services\nSessionService / DocumentService]
        Services --> Repos[Repository Layer]
        Repos --> RelationalDB[(SQL Database\nUsers, Roles, Tokens)]
        RateLimit -.-> RedisStore[(Redis In-Memory Store\nSliding Window ZSETs)]
        AuditMid -.-> AuditService[Audit Logging Service\nPersists Access Logs]
        AuditService -.-> RelationalDB
    end

    Controller --> SuccessResponse[200 OK Response]
    SuccessResponse --> AuditMid
    AuditMid --> OutgoingClient([Client Response with X-Request-ID Header])
```

---

## 3. Security Specifications & Invariants

1. **One-Way Architectural Flow:**
   `app / routes` $\rightarrow$ `services` $\rightarrow$ `repositories` $\rightarrow$ `models`.
2. **Stateless Verification:**
   Core API verification uses HMAC-SHA256 signature checking without requiring synchronous DB queries on every request.
3. **Instant Revocation Support:**
   Critical security actions (e.g., logout, security lockout) flag token identifiers in an in-memory blacklist and database cache.
4. **Resilient Defaults:**
   If Redis or logging stores face temporary latency, the system fails open safely with audit warnings, ensuring core business availability.
