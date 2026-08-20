# Client Invoice Upload — Plan & Roadmap

## 1. Goal

Enable **clients** (the customers of an organization) to upload invoices themselves,
so the organization can process them.

- Today: `OWNER`/`STAFF` users create invoices and upload files inside the web app.
- Tomorrow: a client logs in (web app now, mobile app later) and uploads an invoice file.
  The invoice is created `PENDING` + file attached, unassigned. `OWNER` sees it in the
  queue and assigns it to `STAFF` (existing workflow).
- **Out of scope now:** the mobile app. We only build the backend API (which the mobile
  app will reuse later) and a client-facing web app.

## 2. Current state (what already exists)

- Multi-tenant model: `Organization -> Users (OWNER/STAFF)`, `Clients`, `Invoices`.
- `User` (`app/models/user.py`) has `role` (`OWNER`, `STAFF`), `is_active`,
  `organization_id`, email/password auth (`app/modules/auth/`).
- `Client` (`app/models/client.py`) is a **data record only** (name, email, phone,
  address, notes, `is_active`) — no login, no user account.
- Invoices (`app/models/invoice.py`) belong to a `Client`, carry `items`, `files`,
  `status`, `assigned_to_id`.
- Roles already gate APIs:
  - `OWNER`: everything (clients, staff, audit logs, reports, delete, assignment).
  - `STAFF`: only invoices assigned to them; cannot assign, cannot delete, no reports.
- Upload today is `POST /invoices/{id}/files` — requires an invoice to exist first.

## 3. Target architecture

```
                   ┌──────────────────────────────────────────┐
                   │              Backend API (FastAPI)       │
                   │  /auth (login)                            │
                   │  /clients/me/invoices (own invoices)      │
                   │  /clients/me/invoices/upload (create+file)│
                   │  ... existing OWNER/STAFF endpoints       │
                   └──────────────────────────────────────────┘
                       ▲                    ▲
          web app      │                    │
    /ui/...xhtml  ─────┘                    └───── mobile app (FUTURE,
    (OWNER/STAFF/CLIENT pages)                    same API, not built now)
```

One backend, one API. The mobile app later consumes the exact same endpoints the
client web app uses today.

## 4. Data model changes

1. **New role** `CLIENT` in `UserRole` (`app/models/enums.py`).
2. **Link client user ↔ client record.** Options:
   - `clients.user_id` (nullable FK to `users.id`) — one login per client record.
   - `users.client_id` (nullable FK to `clients.id`) — allows a client record to
     have multiple logins (multiple people at the client company).
   - Recommended: **`users.client_id` (nullable)**, `CLIENT` users get a
     `client_id`; `OWNER`/`STAFF` users keep `client_id = NULL`. Keeps `users`
     as the single account table (auth, tokens, audit already key off it) and
     allows future multiple logins per client.
   - Add a unique constraint on `(client_id)` per user is NOT needed; keep it flexible.
3. **Migration**: new Alembic migration adding `clients.user_id` OR `users.client_id`,
   plus unique index `(organization_id, client_id)` on `users` if using `users.client_id`
   (allows only one account per client to start — relax later if needed).

## 5. Backend API design

### 5.1 Auth
- `/api/v1/auth/login`, `/logout`, `/me` already work for any role — `CLIENT` just works.

### 5.2 Owner-side (invite / manage client accounts)
- Extend `POST /clients` (`app/modules/clients/`) or add `POST /clients/{id}/invite`:
  payload `{ email, password }` (or auto-generated temp password).
  Creates a `User` with `role=CLIENT`, `client_id=<id>`, `organization_id` = owner's org.
  Audit: `client.invited`.
- `GET /clients/{id}` returns `has_account` / `account_email` so the UI can show invite state.
- Deactivating a client (`PATCH /clients/{id} {is_active:false}`) also deactivates the linked
  `CLIENT` user account (or vice-versa). Keep both flags in sync.

### 5.3 Client-side (the core new API, mobile-ready)
- `GET /clients/me/invoices` — list of the client's own invoices (all fields needed by
  web + mobile): number, status, date, total, currency, created_at, files.
- `GET /clients/me/invoices/{id}` — detail incl. status + files.
- `POST /clients/me/invoices/upload` — **multipart** upload:
  - Body: `file` (required), optional `notes`.
  - Backend: creates `Invoice` (status `PENDING`, `client_id` = the caller's `client_id`,
    `invoice_number` auto-generated, `total_amount` = 0, no items) **and** uploads the
    file to MinIO + registers `InvoiceFile` in one request.
  - Returns the created invoice detail (same shape as detail response).
  - Validation: caller must be `CLIENT` with a `client_id`; file size ≤ 25 MB (reuse
    `MAX_UPLOAD_BYTES`); empty file → 400.
- `POST /clients/me/invoices/{id}/files` — upload **additional** files to own invoice.
- `GET /clients/me/invoices/{id}/files/{file_id}/download` — download own invoice file.
- **Permissions**: `CLIENT` users can only ever see/act on invoices where
  `client_id = their client_id`. Enforce in a dependency, mirroring how STAFF
  access is scoped today (`_require_staff_access`).

### 5.4 Permission matrix (add CLIENT column)

| Action                      | OWNER | STAFF | CLIENT |
|-----------------------------|:-----:|:-----:|:------:|
| Login / view own profile    |  ✔    |  ✔    |   ✔    |
| Upload invoices (self)      |  n/a  |  n/a  |   ✔    |
| View own invoices + files   |  n/a  |  n/a  |   ✔    |
| Invite/manage client users  |  ✔    |   ✘   |   ✘    |
| Assign invoices to staff    |  ✔    |   ✘   |   ✘    |
| Process/update any invoice  |  ✔    | own only | ✘   |
| Delete invoices             |  ✔    |   ✘   |   ✘    |
| Reports / staff / audit     |  ✔    |   ✘   |   ✘    |
| List org clients            |  ✔    |   ✘   |   ✘    |

### 5.5 Existing endpoints — no changes
- Invoice processing/assignment/delete stay exactly as-is for OWNER/STAFF.
- `CLIENT` users are simply blocked from those endpoints (new dependency).

## 6. Client web app (this project, same UI pattern)

Reuse the existing `initShell`/`app.js` pattern. Add a `CLIENT` nav + pages:

- `login.xhtml` already works for any role.
- **Client dashboard** (`client-dashboard.xhtml`): "Upload invoice" card + status
  summary (pending/processing/completed counts) + recent own invoices.
- **Client invoices** (`client-invoices.xhtml`): table of own invoices (number,
  status badge, date, total, files), link to detail.
- **Client invoice detail** (`client-invoice-detail.xhtml`): status, notes, files
  (upload more, download), no edit/assign/delete controls.
- **Owner clients page**: show invite status per client + "Invite" button
  (modal: email + password), "Resend"/reset password.

Nav (`app.js`):
- `OWNER`: Dashboard, Invoices, Clients, Staff, Audit Logs, Organization.
- `STAFF`: Dashboard, Invoices.
- `CLIENT`: Client Dashboard, My Invoices.

## 7. Mobile readiness (no code now)

- The mobile app will call the same REST API in §5.3 — JSON, bearer tokens,
  multipart upload. No separate mobile backend needed.
- Keep the upload endpoint contract stable (document response shapes).
- CORS already configured; mobile doesn't need it.

## 8. Implementation phases

1. **Model + migration** — `UserRole.CLIENT`, `users.client_id` FK + index.
2. **Auth** — nothing to change; verify `login`/`me` work for `CLIENT`.
3. **Backend client upload API** — §5.3 endpoints + scoping dependency + tests.
4. **Owner invite API** — extend clients module (§5.2) + tests.
5. **Client web app** — §6 pages + nav wiring.
6. **Owner UI** — invite button + status on clients page.
7. **Full test pass** — unit/API tests for every permission in §5.4; ruff + mypy.

## 9. Open decisions to confirm later

- Single vs multiple logins per client record (starts with one).
- Temp password shown to owner vs emailed to client (no email infra yet).
- Whether client-uploaded invoices may also carry line items in the future
  (OCR/parse) — API can extend `upload` later.
- Client visible statuses only, or also a "rejected/review" note flow.
