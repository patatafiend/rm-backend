# rm-backend — RM API

---

## 1. Overview

The API (internally named `RM API`, app name `RequirementsMonitoringApp`)
powers three logical systems, each with its own set of endpoints but sharing
one auth/RBAC layer:

| System | Purpose | Key routers |
|---|---|---|
| **RM / ERMP** (Requirements Monitoring) | Track onboarding document completeness for employees pulled from an external HR feed | `employee_requirements`, `users`, `roles`, `permissions`, `companies`, `clients` |
| **AP** (Analytics Portal) | ETL + hiring-funnel analytics over an external HR pipeline feed | `analytics` |
| **PAM** (Performance Appraisal Management) | 3rd/5th/6th-month probationary appraisal workflow with automatic fail-safes | `appraisals`, `notifications` |

All three are reachable from the frontend under one Next.js app; this backend
routes external, unauthenticated callers into the right system via a single
SSO-style endpoint (`GET /api/v1/auth/authorize`, see [§5](#5-authentication--authorization)).

---

## 2. Tech stack

| Concern | Library |
|---|---|
| Web framework | FastAPI 0.115 (Starlette, Uvicorn) |
| ORM / migrations | SQLAlchemy 2.0 + Alembic |
| DB drivers | `psycopg2-binary` (Postgres), `PyMySQL` (MySQL), `asyncpg` present |
| Auth | `PyJWT`, `passlib[bcrypt]`, `pyotp` (TOTP/MFA) |
| Object storage | `boto3` (S3 presigned upload/download URLs) |
| Scheduling | `APScheduler` (in-process background cron) |
| Data/ETL | `pandas` |
| HTTP client (outbound) | `httpx` |
| Config | `pydantic-settings` (`.env` file) |

Full pinned list: [`requirements.txt`](./requirements.txt).

---

## 3. Project structure

```
app/
├── main.py                 # FastAPI app, CORS, lifespan, APScheduler wiring
├── api/v1/
│   ├── router.py            # mounts all endpoint routers under /api/v1
│   └── endpoints/
│       ├── auth.py          # register/login/refresh/MFA/forgot-reset + /authorize SSO
│       ├── users.py         # self-service + admin user CRUD, devices, signin history
│       ├── roles.py         # role CRUD + role↔permission assignment
│       ├── permissions.py   # permission CRUD + permission↔account_type assignment
│       ├── companies.py     # company CRUD (tenant root)
│       ├── clients.py       # client CRUD (tenant child of company)
│       ├── employee_requirements.py  # ERMP: missing-document computation
│       ├── analytics.py     # AP: funnel/status/time-metrics/weekly-trend
│       ├── appraisals.py    # PAM: appraisal records, decisions, file URLs
│       └── notifications.py # PAM: BU/role-scoped notification feed
├── core/
│   ├── config.py             # Settings (env-driven)
│   ├── dependencies.py       # get_current_user / get_current_caller / require_* guards
│   ├── security.py           # JWT issuing/decoding, password hashing
│   ├── s3.py                 # boto3 S3 client factory
│   ├── bu_permissions.py     # business-unit permission/group maps for /authorize
│   └── requirements.py       # universal + company-specific onboarding document lists
├── db/
│   ├── session.py            # engine, SessionLocal, get_db dependency
│   └── base.py                # declarative Base + ToDictMixin, imports all models
├── models/                   # SQLAlchemy ORM models (user.py, appraisal.py)
├── schemas/                  # Pydantic request/response models
└── services/                 # business logic (auth, user, role, company, appraisal)
migrations/                  # Alembic environment + versions
scripts/                     # run_cycle.py, debug_appraisal_cycle.py (manual cycle runners)
tests/                       # pytest unit tests (appraisal cycle, analytics ETL)
migrate.sh                    # wrapper around `alembic revision --autogenerate` + upgrade
```

---

## 4. Getting started

### Prerequisites
- Python 3.11+
- A Postgres or MySQL database
- An AWS S3 bucket (for appraisal file uploads)

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure environment

Create a `.env` file in the project root. All of the following are
**required** (no default) unless noted:

```bash
# App
ENV=DEV                              # optional, default "DEV"
FRONTEND_URL=http://localhost:3000    # used for CORS + /authorize redirects

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# JWT
JWT_SECRET_KEY=change-me
JWT_REFRESH_SECRET_KEY=change-me
JWT_PASSWORD_RESET_SECRET_KEY=change-me
JWT_MFA_SECRET_KEY=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=480       # optional, default 480 (8h)
REFRESH_TOKEN_EXPIRE_DAYS=7           # optional, default 7
ALGORITHM=HS256                       # optional, default HS256

# AWS S3 (appraisal file uploads/downloads)
AWS_REGION=ap-southeast-1             # optional, default ap-southeast-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=...
S3_PRESIGNED_URL_EXPIRY=300           # optional, default 300 seconds
```

> **Note:** `app/core/config.py` declares the canonical schema (`Settings`
> class) — treat it as the source of truth if this list drifts.
>
> **Note:** `app/db/session.py` also reads `DATABASE_URL` directly via
> `os.getenv` (independent of the `pydantic-settings` loader in
> `config.py`), so it must be present in the environment either way.

### Run migrations

```bash
alembic upgrade head
```

To create a new migration, use the provided wrapper (it guards against
duplicate/similarly-named migration files and rolls back on failure):

```bash
./migrate.sh -m "add appraisal extension table"
```

### Run the dev server

```bash
uvicorn app.main:app --reload
```

The API is served at `http://localhost:8000`, with interactive docs at
`/docs` (Swagger UI) and `/redoc`. All application routes are mounted under
`/api/v1` (see `API_V1_STR` in `config.py`).

### Run tests

```bash
pytest
```

Tests use an in-memory SQLite database and stub out the external HR feed
functions, so no network access or real database is required.

---

## 5. Authentication & authorization

There are **two caller types**, both represented as JWTs validated in
`app/core/security.py` / `app/core/dependencies.py`:

### 5.1 Internal users (`UserModel`)
Standard email/password accounts stored in the `users` table.

- `POST /api/v1/auth/register` — create account
- `POST /api/v1/auth/login` — returns `access_token` + `refresh_token`, or
  `{mfa_required: true, mfa_token}` if MFA is enabled
- `POST /api/v1/auth/mfa/verify` — exchange `mfa_token` + TOTP code for tokens
- `POST /api/v1/auth/mfa/setup` / `mfa/verify-setup` / `mfa/disable` — TOTP
  (Google Authenticator-style) enrollment, via `pyotp`
- `POST /api/v1/auth/refresh-token` — rotates the refresh token (old one is
  deleted, new one stored against the device)
- `POST /api/v1/auth/logout` — revokes the current device's refresh token
- `POST /api/v1/auth/forgot-password` / `reset-password` — 1-hour reset token
  flow (email delivery is a `TODO` in `AuthService.forgot_password`)

Account types (`RoleModel.account_type` enum): `company_account`,
`admin_account`, `client_account`, `super_admin_account`.

Access tokens carry `{"sub": user_id, "type": "access", ...}`; refresh tokens
carry `{"sub": user_id, "type": "refresh"}`, signed with separate secrets
conceptually (single `JWT_SECRET_KEY` is currently used for signing, but
distinct `JWT_REFRESH_SECRET_KEY` / `JWT_PASSWORD_RESET_SECRET_KEY` /
`JWT_MFA_SECRET_KEY` settings exist for future separation).

### 5.2 External callers (`ExternalCaller`) — cross-portal SSO

`GET /api/v1/auth/authorize` is a **redirect-based SSO entry point** used by
another internal system (an "OneHR" host app) to hand a user off into one of
the three portals without a login screen. It:

1. Validates `bu_group` (comma-separated) against a permission map — either
   `BU_GROUP_MAP` (RM/Analytics) or `APPRAISALS_BU_GROUP_MAP` (Appraisals),
   selected by the `system` query param (`rm` | `analytics` | `appraisals`).
2. Optionally validates `category` (`staff` / `non_staff`) — **appraisals
   only** — against `APPRAISALS_CATEGORY_MAP`.
3. Mints a short-lived JWT (`type: "external"`) embedding `sub=employee_id`,
   `allowed_bus`, and `allowed_categories`.
4. 302-redirects to `{FRONTEND_URL}/external?redirect={portal_path}&token={jwt}`.

The frontend's `/external` page (see `rm-frontend` docs) picks up `token`,
stores it as the access token, and forwards to the target portal. External
tokens have **no refresh token** and **no user record** — they're scoped
entirely by the `allowed_bus` / `allowed_categories` claims baked in at
mint time.

`app/core/bu_permissions.py` documents *why* two different BU maps exist:
the ERMP/Analytics external feed still reports granular business units
(`delivery`, `met`, `see`, `security`), while the newer two-feed data PAM
consumes only ever bundles employees into `Security` or `MWFL`.

### 5.3 Dependency guards (`app/core/dependencies.py`)

| Dependency | Use |
|---|---|
| `get_current_user` | Internal users only (401 if external/invalid) |
| `get_current_caller` | Internal users **or** external callers — used by most PAM/Analytics/ERMP read endpoints |
| `require_admin` | `role_id` must be an admin role |
| `require_super_admin` | `account_type == "super_admin_account"` |
| `require_internal_caller` | Rejects `ExternalCaller` — for write endpoints external tokens must never reach |
| `resolve_allowed_bus` / `resolve_allowed_categories` | Returns `None` (unrestricted) for internal callers, or the claim list for external callers |

---

## 6. Data model

### Identity & RBAC (`app/models/user.py`)

- **`UserModel`** — account, optional `role_id`, optional `company_id` /
  `client_id` (tenant scoping)
- **`RoleModel`** — scoped to a company **or** a client **or** neither
  (global/super-admin roles); enforced by a `CheckConstraint`
- **`PermissionModel`** — `(resource, action)` pairs, e.g.
  `("Recruitment - Delivery", "read")`
- **`RolePermissionModel`** / **`PermissionAccountTypeModel`** — join tables
- **`UserDeviceModel`**, **`UserSigninModel`**, **`UserSignupModel`** —
  device fingerprinting and sign-in/up audit trail
- **`UserTokenModel`** — one active refresh token per device (unique on
  `device_id`)
- **`ResetTokenModel`**, **`MfaTokenModel`** — short-lived flow tokens
- **`Company`** → **`Client`** (1‑to‑many) — the tenancy hierarchy
- **`AuthorizedDomainModel`** — allow-listed email domains (referenced by
  `auth.py` imports; used for domain-gated signup/SSO)

### Appraisals (`app/models/appraisal.py`)

- **`PerformanceAppraisalModel`** — one row per employee's probationary
  appraisal cycle: 3rd-month due date/decision, 5th-month due date/decision,
  6th-month failsafe check date, overall `appraisal_status`, and resolution
  fields for manual overrides.
- **`ExtensionRecordModel`** — append-only sequence of extension grants per
  appraisal (an appraisal can be extended more than once).
- **`NotificationModel`** — targeted at either a `BU_GROUP` or a `ROLE`
  (e.g. `HRBP`), consumed by the notifications endpoint.
- **`ActivityLogModel`** — append-only audit log of every decision/upload
  action, capturing actor type (`INTERNAL`/`EXTERNAL`), outcome, and a JSON
  `detail` blob.

---

## 7. API reference

Base path: `/api/v1`. Interactive schema: `GET /docs`.

### Auth — `/auth`
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/register` | — | |
| POST | `/login` | — | may return MFA challenge instead of tokens |
| POST | `/refresh-token` | — (refresh token in body) | rotates token |
| POST | `/logout` | user | |
| POST | `/forgot-password` | — | always 202, doesn't leak account existence |
| POST | `/reset-password` | — | |
| POST | `/mfa/setup` | user | |
| POST | `/mfa/verify-setup` | user | |
| POST | `/mfa/verify` | — (mfa_token in body) | |
| POST | `/mfa/disable` | user | |
| GET | `/authorize` | — | SSO redirect, see [§5.2](#52-external-callers-externalcaller--cross-portal-sso) |

### Users — `/users`
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/me` | user | |
| PUT | `/me` | user | |
| PUT | `/me/password` | user | |
| GET | `/` | admin | paginated, filters: `account_type`, `is_blocked`, `search` |
| POST | `/` | admin | admin-create user |
| GET/PUT/DELETE | `/{user_id}` | admin | |
| PATCH | `/{user_id}/block` | admin | toggle block |
| GET | `/{user_id}/devices` | user (self) or admin | |
| DELETE | `/{user_id}/devices/{device_id}` | user (self) or admin | |
| GET | `/{user_id}/signin-history` | user (self) or admin | paginated |

### Roles — `/roles`, Permissions — `/permissions`
Standard admin/super-admin-gated CRUD, plus:
- `GET/POST /roles/{role_id}/permissions`, `DELETE /roles/{role_id}/permissions/{permission_id}` — assign/revoke
- `GET/POST /permissions/{permission_id}/account-types`, `DELETE .../{account_type}` — link a permission to an account type

### Companies — `/companies`, Clients — `/clients`
Tenant CRUD (`super_admin` for delete/create at company level; `admin` for
most reads/updates). Nested listing:
- `GET /companies/{company_id}/users`, `/companies/{company_id}/clients`
- `GET /clients/{client_id}/users`

### Employee Requirements — `/employee-requirements` (ERMP)
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/employee-requirements` | `get_current_caller` | BU-filtered list from the external onboarding feed; supports `limit`/`offset` |
| GET | `/employee-requirements/missing-major` | none | **internal service-to-service** — employees missing SSS/Pag-IBIG/PhilHealth |
| GET | `/employee-requirements/missing-minor` | none | **internal service-to-service** — employees missing universal/company-specific docs; PII-sanitized output |

Source data comes from `https://cmiitdept.com/hr/api_onboarded_minor.php`.
"Major" documents are SSS/Pag-IBIG/PhilHealth numbers; "minor" documents are
the list in `app/core/requirements.py` (universal + per-company overrides).

### Analytics — `/analytics` (AP)
All endpoints accept `refresh=false` (bypass the 5-minute in-memory cache)
and `bu` (filter by business unit). Source:
`https://cmiitdept.com/hr/api_analytics_main_pooling`.

| Method | Path | Description |
|---|---|---|
| GET | `/status-counts` | Counts per `rm_job_status` |
| GET | `/funnel` | Ordered funnel (Applicant → For Medical → For Onboarding → Onboarded) with stage-to-stage and cumulative conversion rates |
| GET | `/time-metrics` | Mean/median/min/max days from encode to onboarded |
| GET | `/weekly-trend?weeks=12` | Encoded-count per ISO week |
| GET | `/raw?limit=&offset=&bu=&company=&status=` | Paginated raw rows |
| GET | `/bu-list` | Distinct business units seen in the feed |

Every response includes a `meta` block with `data_quality_flags` (missing
encode dates, missing contract dates on "Onboarded" rows, duplicate
`rm_tran_no` counts).

### Appraisals — `/appraisals` (PAM)
| Method | Path | Notes |
|---|---|---|
| GET | `/for-regularization` | Records with `appraisal_status = REGULARIZED` |
| GET | `/` | List, optional `?status=` filter |
| GET | `/{employee_id}` | Single record, enriched with live employee data |
| POST | `/{employee_id}/third-month` | Submit 3rd-month decision (`PROCEED_5TH` / `NON_REGULARIZATION` / `NO_APPRAISAL`) |
| POST | `/{employee_id}/fifth-month` | Submit 5th-month decision (`REGULARIZATION` / `NON_REGULARIZATION` / `NO_APPRAISAL` / `EXTENSION`) |
| POST | `/{employee_id}/extension-decision` | Resolve (or re-extend) an active extension |
| POST | `/{employee_id}/upload-url` | Presigned S3 `PUT` URL for the appraisal file (`application/pdf`, `image/jpeg`, `image/png` only) |
| GET | `/{employee_id}/files/{file_key}/download-url` | Presigned S3 `GET` URL |

All decision/upload endpoints write an `ActivityLogModel` entry (success or
failure) and are BU/category-scoped for external callers via
`resolve_allowed_bus` / `resolve_allowed_categories` and the
`_filter_by_category` helper.

### Notifications — `/notifications` (PAM)
`GET /notifications?unread=false` — returns notifications scoped to the
caller: external callers see `BU_GROUP` notifications matching their
`allowed_bus`; internal super admins see everything; other internal users
see `ROLE` notifications matching their role name.

---

## 8. The appraisal cycle (background job)

`app/main.py` starts an `APScheduler` `BackgroundScheduler` in the FastAPI
`lifespan` context, running `run_appraisal_cycle_job` (from
`app/services/appraisal.py`) **once daily at 00:00 server time**.

Each run, per eligible (`PROBATIONARY`) employee from the external feed:

1. Creates the `PerformanceAppraisalModel` row if it doesn't exist yet.
2. At **3 calendar months** since `contract_sdate`: sets the 3rd-month due
   date and fires a `3RD_MONTH_APPRAISAL_DUE` notification.
3. At **5 months**, if no 3rd-month decision was ever made: auto-sets
   `NO_APPRAISAL` and fires `NON_COMPLIANCE_NO_3RD_MONTH_APPRAISAL`
   notifications (to the BU group and the `HRBP` role).
4. At **5 months**: sets the 5th-month due date and fires
   `5TH_MONTH_APPRAISAL_DUE`.
5. If an extension's window has elapsed with no final decision: auto-forces
   the record back to `FOR_REGULARIZATION` and fires
   `NON_COMPLIANCE_EXTENSION_UNRESOLVED_AUTO_REGULARIZED`.
6. At **6 months**, if still `PENDING` with no 5th-month decision: the
   **fail-safe** triggers — auto-regularizes the employee
   (`appraisal_status = REGULARIZED`) and fires
   `NON_COMPLIANCE_AUTO_REGULARIZED`.
7. Finally, `reconcile_resolved_employees` sweeps all `PENDING` /
   `FOR_REGULARIZATION` records: if the employee is now `REGULAR` in the
   source feed, the record is confirmed as `FOR_REGULARIZATION`; if the
   employee has left the feed entirely or moved to a non-eligible status,
   the record is flagged `NEEDS_REVIEW` for manual handling.

You can trigger this manually for debugging via `scripts/run_cycle.py` or
`scripts/debug_appraisal_cycle.py` rather than waiting for the cron.

---

## 9. External integrations

| Integration | Used by | Purpose |
|---|---|---|
| `cmiitdept.com/hr/api_onboarded_minor.php` | ERMP | Onboarding/document-completeness feed |
| `cmiitdept.com/hr/api_analytics_main_pooling` | Analytics | Hiring pipeline feed |
| `cmiitdept.com/clea_sec/api_probi_emp_sec.php` + `cmiitdept.com/clea/api_probi_emp_nonsec.php` | Appraisals | Two-feed (security / non-security) probationary employee roster; **both must succeed** or the cycle aborts |
| AWS S3 | Appraisals | Presigned upload/download URLs for appraisal PDFs/images |

All outbound calls use `httpx` with explicit timeouts and are wrapped to
raise `HTTPException(502, ...)` (API endpoints) or `RuntimeError` (service
layer, used by the scheduled job) on failure, non-200 responses, invalid
JSON, or an unexpected response shape.

---

## 10. Deployment notes

- CORS is restricted to a single origin, `settings.FRONTEND_URL`.
- The scheduler runs **in-process** — if you run multiple API instances/
  workers behind a load balancer, the appraisal cycle job will fire once per
  instance unless this is changed to a single dedicated worker or an
  external scheduler.
- `S3_PRESIGNED_URL_EXPIRY` (default 300s) controls how long upload/download
  links remain valid.