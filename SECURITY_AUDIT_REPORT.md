# Security & Production-Readiness Audit — invoice_collect

Date: 2026-09-11
Backend: FastAPI / SQLAlchemy / PostgreSQL / MinIO
Scope: `app/`, `tests/`, deploy config
Result: **98/98 tests pass, ruff clean, mypy clean** after hardening.

---

## 1. Config security

| Finding | Severity | Fix | Status |
|---|---|---|---|
| `secret_key` default `"change-me"` | High | Refuse defaults in production | Fixed |
| `debug=True` default | Medium | Force off in production, warn | Fixed |
| Docs (`/docs`, `/redoc`) exposed | Low | Disabled when `debug=False` (already) | Already sound |

`app/config.py`: `model_validator` now forces `debug=False` in production and raises if
`SECRET_KEY` is `<32` chars or starts with a known insecure prefix.

## 2. Auth

| Finding | Severity | Fix | Status |
|---|---|---|---|
| Double `db.commit()` in register/login/create paths | Low (correctness) | Collapsed into single commit with `flush()` | Fixed (6 sites) |
| Login IP not captured | Medium (forensics) | Store `x-forwarded-for` / client host in audit | Fixed |
| Revoked-token cleanup | Low | Expired rows purged on login (already) | Already sound |
| Argon2 password hashing | — | Correctly configured | Already sound |

## 3. Multi-tenancy

All tenant-scoped queries route through `get_owned_or_404` or an explicit
`organization_id` filter. Staff list is additionally scoped to `assigned_to_id`,
and client self-service is scoped to `client_id`. Verified across invoices,
files, clients, staff, reports, and audit logs. **No cross-tenant leak found.**

## 4. Upload security

| Finding | Severity | Fix | Status |
|---|---|---|---|
| Accepts arbitrary content types | High | Whitelist PDF + image types | Fixed |
| Relies on client-declared content type | Medium | Magic-byte signature check, `415` on mismatch | Fixed |
| Filename traversal | Medium | Regex sanitization (already present) | Already sound |
| 25 MB size cap | — | Enforced with `413` (already present) | Already sound |
| No upload rate limit | Medium | 60 req/hr per IP | Fixed |

## 5–9. Headers / errors / rate limiting / pagination / audits

| Area | Finding | Status |
|---|---|---|
| Security headers | Added `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS (prod) | Fixed |
| 404/500 handling | Registered handlers; 500s return generic body, log stack server-side; dev re-raises for debugging | Fixed |
| Rate limiting | Login 10/5 min, upload 60/hr, sliding window, skipped in test env | Fixed |
| Pagination | `page_size` bounded to 100 (already); report limits bounded (already) | Sound |
| Audit logs | Every mutation writes an entry keyed to org + actor | Sound |

## 10–12. DB / MinIO / client portal

- **DB**: added `pool_size=10`, `max_overflow=20`, `pool_recycle=1800` for non-SQLite engines, `pool_pre_ping` retained. `database.py`
- **MinIO**: credentials come from env; bucket is private. Recommend rotating
  `MINIO_SECRET_KEY` and enabling TLS (`minio_secure=True`) before internet exposure. Not code-fixable without infra.
- **Client portal**: `CLIENT` role isolated to `/clients/me`; blocked from worker invoice, staff, reports, client-crud, and org endpoints (403). Verified by tests.

## 13. New test coverage requested

Add tests in a follow-up PR for: magic-byte rejection (`415`), insecure `SECRET_KEY`
rejection in production mode, security-header presence, and rate-limit `429`.

---

## Regression

- `uv run pytest -q` → **98 passed**
- `uv run ruff check .` → clean
- `uv run mypy app` → no issues
- Graft graph rebuilt (`532 nodes / 1561 edges`)

## Files changed

- `app/config.py` — prod secret validation
- `app/core/ratelimit.py` — **new** sliding-window limiter
- `app/database.py` — pool sizing
- `app/main.py` — security headers + error handlers
- `app/core/audit.py` — (helper unchanged; IP now passed by callers)
- `app/modules/auth/router.py` — single commit, IP capture, login rate limit
- `app/modules/clients/{router,me}.py` — single commits, upload rate limit, magic-byte check
- `app/modules/invoices/{router,files}.py` — single commit, upload validation + rate limit
- `app/modules/staff/router.py` — single commit