# Phase 3 — Interview Questions & Answers: Identity, Access Control & Architecture

> **Focus Area:** Technical and architectural interview preparation covering Authentication, Authorization, Cryptography, Distributed Rate Limiting, ASGI Middleware, and Observability.

---

## 1. Authentication & Cryptography

### Q1: Why do we use PBKDF2/Bcrypt instead of standard cryptographic hashes like SHA-256 or MD5 for passwords?
**Answer:**
Standard hash functions (like MD5, SHA-1, SHA-256) are designed for speed and data integrity—they can compute billions of hashes per second on modern GPUs, making them trivial to brute-force using rainbow tables or dictionary attacks.  
Key derivation functions like **PBKDF2**, **Bcrypt**, or **Argon2** are computationally expensive and incorporate a **work factor** (e.g., 100,000 iterations in PBKDF2). This deliberate slowdown makes brute-force attacks economically and computationally infeasible. Additionally, every password is combined with a unique, cryptographically generated **salt** (32 random bytes), ensuring two users with identical passwords never produce the same stored hash, defeating precomputed rainbow table attacks.

---

### Q2: How does the Dual-Token (Access + Refresh) pattern improve security and user experience?
**Answer:**
1. **Minimizes Vulnerability Window:** Access tokens are short-lived (e.g., 60 minutes) and transmitted in authorization headers with every API call. If an access token is intercepted over an insecure channel, the attacker's window of opportunity is limited to the remaining expiration time.
2. **Stateless Scalability:** Access tokens contain cryptographically signed claims (`sub`, `roles`, `permissions`), enabling microservices to validate requests without querying the database on every HTTP request.
3. **Controlled Re-Authentication:** Refresh tokens are long-lived (e.g., 7 days) and stored securely in the database with their hashes. They are only sent over the wire when obtaining a new access token at `/api/v1/auth/refresh`. When a user logs out or is flagged, revoking the refresh token in the database immediately stops new access tokens from being generated.

---

### Q3: How do you handle JWT revocation in a stateless architecture?
**Answer:**
Because standard JWTs are stateless and verified by signature, they remain valid until expiration unless explicitly checked. In LakEnterprises, we handle revocation through a hybrid approach:
- **Short Expiration Time:** Access tokens expire automatically after 60 minutes.
- **Fast Token Blacklist:** When a user logs out (`/logout`), the token's unique identifier (`jti`) or token hash is added to an in-memory blacklist (or Redis with a TTL matching the token's remaining lifespan).
- **Database Revocation for Refresh Tokens:** Refresh tokens are persisted in the database; setting `is_revoked = True` ensures they cannot be used to refresh sessions.

---

## 2. Authorization & RBAC

### Q4: How is Role-Based Access Control (RBAC) implemented in this codebase?
**Answer:**
Our RBAC system operates at two levels:
1. **Data Model:** Users have a many-to-many relationship with `Role` entities, and `Role` entities have a many-to-many relationship with granular `Permission` entities (25 permissions spanning user management, document CRUD, session management, and auditing).
2. **FastAPI Dependency Injection (`require_role`):** Endpoints declare required roles or permissions using FastAPI dependencies:
   ```python
   @router.get("/admin", dependencies=[Depends(require_role("admin"))])
   def admin_endpoint(current_user: User = Depends(get_current_user)):
       return {"message": "Admin access granted"}
   ```
   The dependency extracts the JWT, verifies its signature, checks whether the user's assigned roles satisfy the requirement, and raises an `HTTPException(403, "Forbidden")` if unauthorized.

---

### Q5: What is the difference between RBAC and ABAC, and when would you transition to ABAC?
**Answer:**
- **RBAC (Role-Based Access Control):** Permissions are tied directly to user roles (e.g., `analyst` can run searches, `admin` can delete users). It is simple, fast, and satisfies 90% of enterprise requirements.
- **ABAC (Attribute-Based Access Control):** Permissions are evaluated dynamically using contextual attributes: subject (user department, clearance), resource (document classification level, owner), and environment (time of day, client IP, geographical location).
- **When to transition:** When business logic requires dynamic rules such as *"Analysts can only view documents within their own regional branch, during business hours, and only if the document sensitivity is below Confidential."*

---

## 3. Distributed Rate Limiting

### Q6: Why did you choose a Sliding Window Counter using Redis Sorted Sets instead of a Fixed Window or Token Bucket algorithm?
**Answer:**
- **Fixed Window Flaw:** In a fixed window (e.g., 100 requests per minute resetting at 12:00, 12:01), an attacker could send 100 requests at 12:00:59 and another 100 requests at 12:01:01, resulting in a burst of 200 requests within 2 seconds without triggering the rate limit.
- **Sliding Window Log / Sorted Set:** In our implementation, every request is recorded in a Redis Sorted Set (`ZSET`) where both the score and member are the epoch timestamp $T$.
  1. `ZREMRANGEBYSCORE key 0 (T - 60)` purges requests older than the 60-second window.
  2. `ZCARD key` returns the exact number of requests made in the rolling 60 seconds.
  3. If count $\ge$ limit, the request is rejected with `429 Too Many Requests`.
  4. Otherwise, `ZADD key T T` records the current request, and `EXPIRE key 60` ensures automated garbage collection.
- This guarantees a smooth, mathematically precise limit across any rolling 60-second slice.

---

### Q7: What happens to rate limiting if Redis crashes or is temporarily unreachable?
**Answer:**
We designed the `SlidingWindowRateLimiter` with **graceful degradation**:
- All Redis operations are wrapped in try-except blocks catching `redis.RedisError`.
- If Redis is unreachable, the system automatically falls back to an in-memory sliding window using Python's `collections.deque`.
- This ensures high availability: an infrastructure outage in the cache cluster will not cascade into a complete service outage for legitimate API consumers.

---

## 4. ASGI Middleware & Framework Concurrency

### Q8: Why did you implement `AuditMiddleware` as a pure ASGI middleware (`__call__(scope, receive, send)`) rather than inheriting from Starlette's `BaseHTTPMiddleware`?
**Answer:**
Starlette's `BaseHTTPMiddleware` wraps request processing in a separate `anyio` task group with internal streaming response buffers. This known architecture has several drawbacks:
1. **Deadlocks in Test Environments:** In test runners (`pytest` with `TestClient`), `BaseHTTPMiddleware` can deadlock when testing concurrent or streamed connections.
2. **Context Leakage & Memory Overhead:** It buffers response bodies in memory, preventing true zero-copy streaming for large file downloads or AI tokens.
3. **Pure ASGI Performance:** A pure ASGI middleware directly wraps `receive` and `send` callables, adding virtually zero overhead, cleanly injecting headers (`X-Request-ID`), and remaining fully compatible with Python 3.12 exception groups and anyio concurrency primitives.

---

### Q9: How does the system handle Python 3.12 ExceptionGroups in FastAPI dependency injection?
**Answer:**
When a dependency is declared as a synchronous function (`def`), FastAPI offloads it to a thread pool via `anyio.to_thread.run_sync()`. In Python 3.12, unhandled exceptions originating inside thread pools are caught and wrapped in an `ExceptionGroup`. If an exception inherits from `BaseException` rather than `Exception`, Starlette's default exception handler fails to catch it, leading to unhandled 500 server errors.  
We solved this by:
1. Ensuring all custom authentication exceptions (`AuthException`, `TokenExpiredError`, etc.) inherit strictly from standard Python `Exception`.
2. Defining security dependencies (`get_current_user`, `require_role`) as `async def`, allowing them to execute directly on the main event loop without thread pool context switching.

---

## 5. Audit Logging & Compliance

### Q10: What compliance requirements (e.g., SOC2, HIPAA) does the Audit service address?
**Answer:**
- **Traceability (`X-Request-ID`):** Every API request receives a unique UUIDv4 that is returned in response headers and logged with every database operation, enabling end-to-end distributed tracing.
- **Non-Repudiation:** The audit log records the exact identity of the actor (`user_id`), target resource, action performed (`LOGIN`, `LOGOUT`, `UPDATE`, `TOKEN_REFRESH`), timestamp, remote IP address, and execution duration.
- **Immutable Persistence:** Logs are persisted in dedicated audit tables with severity levels (`INFO`, `WARNING`, `CRITICAL`), providing the tamper-evident records required for SOC2 Trust Services Criteria and HIPAA Access Monitoring.
