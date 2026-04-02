# Provenancy API — Backend Documentation

> **Version:** 1.0.0 · **Framework:** FastAPI · **Database:** PostgreSQL (Supabase) · **Auth:** JWT (HS256)  
> **Base URL:** `http://localhost:8000`  
> **Interactive Docs:** `http://localhost:8000/docs` (Swagger UI) · `http://localhost:8000/redoc`

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication-model)
3. [Global Error Conventions](#global-error-conventions)
4. [Enums & Constants](#enums--constants)
5. [Routes — System](#routes--system)
   - [GET /](#get-)
   - [GET /health](#get-health)
6. [Routes — Authentication (`/auth`)](#routes--authentication-auth)
   - [POST /auth/signup](#post-authsignup)
   - [POST /auth/login](#post-authlogin)
   - [GET /auth/me](#get-authme)
7. [Routes — Users (`/users`) _(Internal/Example)_](#routes--users-users)
   - [POST /users/](#post-users)
   - [GET /users/](#get-users)
   - [GET /users/{user_id}](#get-usersuser_id)
   - [PUT /users/{user_id}](#put-usersuser_id)
   - [DELETE /users/{user_id}](#delete-usersuser_id)
8. [Data Schemas Reference](#data-schemas-reference)
9. [Auto-Generated Fields](#auto-generated-fields)
10. [Trust Tier Logic](#trust-tier-logic)
11. [CORS Configuration](#cors-configuration)

---

## Overview

**Provenancy** is a credential verification platform where students log work engagements and supervisors cryptographically verify them. This API is the backend service that handles:

- User registration and authentication (JWT-based)
- Role-based profile management (student vs. supervisor)
- User account CRUD operations

### Stack Summary

| Concern | Technology |
|---|---|
| Framework | FastAPI (Python) |
| Database | PostgreSQL via Supabase |
| ORM | SQLAlchemy |
| Validation | Pydantic v2 |
| Auth | JWT (HS256) via `python-jose` |
| Passwords | bcrypt |
| Migrations | SQLAlchemy `Base.metadata.create_all` |

---

## Authentication Model

All protected endpoints require a **Bearer Token** in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

### JWT Token Payload

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "student",
  "ledger_id": "PRV-2026-0001",
  "exp": 1743619200
}
```

| Claim | Type | Description |
|---|---|---|
| `user_id` | `UUID` string | The user's internal UUID |
| `role` | `string` | `"student"` or `"supervisor"` |
| `ledger_id` | `string` | Human-readable public ID |
| `exp` | `number` (Unix timestamp) | Token expiry — default 60 minutes from issue |

### Token Lifecycle

- Tokens expire after **60 minutes** (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` env var)
- There is no refresh token mechanism (v1); clients must re-login after expiry
- Inactive user accounts (`is_active = false`) are rejected even with a valid token

---

## Global Error Conventions

All errors follow FastAPI's standard response model:

```json
{
  "detail": "Human-readable error message"
}
```

### Common HTTP Status Codes

| Code | Meaning | When It Occurs |
|---|---|---|
| `200 OK` | Success | GET requests succeed |
| `201 Created` | Resource created | POST requests that create a resource |
| `204 No Content` | Deleted | DELETE requests succeed |
| `400 Bad Request` | Validation / business logic error | Invalid input, duplicate email, invalid role |
| `401 Unauthorized` | Authentication failed | Missing/invalid/expired token, wrong credentials |
| `403 Forbidden` | Authorization failed | Valid token but account is inactive |
| `404 Not Found` | Resource missing | User/profile not found |
| `422 Unprocessable Entity` | Schema validation error | Missing required fields, wrong field types |
| `500 Internal Server Error` | Server fault | Unhandled exceptions |

### 422 Pydantic Validation Error Shape

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "email"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

---

## Enums & Constants

### `UserRole`

| Value | Description |
|---|---|
| `"student"` | A candidate who creates and submits engagement records |
| `"supervisor"` | An institutional authority who verifies engagement records |

> Role is set at signup and is **immutable** — it cannot be changed after account creation.

### `TrustTier` _(Supervisors only)_

| Value | When Applied |
|---|---|
| `"institutional"` | Supervisor's email domain matches their provided organization |
| `"independent"` | Email domain does not match organization (default) |

---

## Routes — System

### `GET /`

Root endpoint. Returns basic API metadata.

**Authentication:** None required

**Response `200 OK`:**

```json
{
  "name": "Provenancy API",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health"
}
```

---

### `GET /health`

Health check endpoint. Verifies API is running and database is reachable.

**Authentication:** None required

**Response `200 OK` — Healthy:**

```json
{
  "status": "ok",
  "database": "healthy",
  "version": "1.0.0"
}
```

**Response `200 OK` — Degraded (DB unreachable):**

```json
{
  "status": "degraded",
  "database": "unhealthy",
  "version": "1.0.0"
}
```

> **Note:** Even when the database is unreachable, this endpoint returns HTTP `200` (not `503`). Check the `status` field in the body to determine actual health.

---

## Routes — Authentication (`/auth`)

All routes in this section are prefixed with `/auth`.

---

### `POST /auth/signup`

Register a new user account and automatically create their role-specific profile. Returns a JWT access token on success.

**Authentication:** None required

**Request Body:** `application/json`

```json
{
  "full_name": "Alex Carter",
  "email": "alex@university.edu",
  "password": "securepassword123",
  "role": "student",
  "institution": "MIT",
  "organization": null
}
```

#### Request Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `full_name` | `string` | Yes | User's full name — stored in the profile |
| `email` | `string` (email format) | Yes | Login identifier; must be unique across all users |
| `password` | `string` | Yes | Plain text password — bcrypt-hashed before storage |
| `role` | `"student"` or `"supervisor"` | Yes | Determines which profile type is created |
| `institution` | `string` or `null` | Optional | For **students** only — educational institution name |
| `organization` | `string` or `null` | Optional | For **supervisors** only — used for trust tier resolution |

> **Role-specific fields:**
> - If `role = "student"` → `institution` is used; `organization` is ignored
> - If `role = "supervisor"` → `organization` is used; `institution` is ignored

**Response `201 Created`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Errors

| Status | `detail` message | Cause |
|---|---|---|
| `400` | `"Email already registered"` | Another user account already uses this email |
| `400` | `"Invalid role. Must be 'student' or 'supervisor'"` | `role` field is not one of the allowed enum values |
| `422` | Pydantic validation error | Missing required fields, invalid email format, etc. |

#### Side Effects on Success

1. New row inserted into `users` table
2. A ledger ID is auto-generated:
   - Student: `PRV-{YEAR}-{4-digit sequence}` e.g. `PRV-2026-0001`
   - Supervisor: `PRV-SUP-{4-digit random}` e.g. `PRV-SUP-8821`
3. Role-specific profile row created:
   - Student → row in `student_profiles`
   - Supervisor → row in `supervisor_profiles` (with `trust_tier` auto-resolved)
4. JWT token generated and returned

---

### `POST /auth/login`

Authenticate an existing user with email and password. Returns a JWT access token.

**Authentication:** None required

**Request Body:** `application/json`

```json
{
  "email": "alex@university.edu",
  "password": "securepassword123"
}
```

#### Request Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `email` | `string` (email format) | Yes | Registered email address |
| `password` | `string` | Yes | Plain text password to verify |

**Response `200 OK`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Errors

| Status | `detail` message | Cause |
|---|---|---|
| `401` | `"Invalid email or password"` | No user with that email exists |
| `401` | `"Invalid email or password"` | Password does not match stored hash |
| `403` | `"User account is inactive"` | User account has `is_active = false` |
| `422` | Pydantic validation error | Missing fields, invalid email format |

> **Security Note:** The same error message `"Invalid email or password"` is returned for both unknown email and wrong password. This is intentional to prevent user enumeration attacks.

---

### `GET /auth/me`

Retrieve the current authenticated user's full profile. The response shape differs based on the user's role.

**Authentication:** Required — Bearer Token

**Request:** No body. Token provided in header:

```
Authorization: Bearer <access_token>
```

**Response `200 OK` — Student:**

```json
{
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "alex@university.edu",
    "role": "student",
    "ledger_id": "PRV-2026-0001",
    "is_active": true,
    "created_at": "2026-04-01T10:30:00Z",
    "updated_at": "2026-04-01T10:30:00Z"
  },
  "profile": {
    "id": "7f6c1d20-a4b3-4c5e-8f9d-1a2b3c4d5e6f",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "full_name": "Alex Carter",
    "title": null,
    "bio": null,
    "linkedin_url": null,
    "institution": "MIT",
    "created_at": "2026-04-01T10:30:00Z",
    "updated_at": "2026-04-01T10:30:00Z"
  }
}
```

**Response `200 OK` — Supervisor:**

```json
{
  "user": {
    "id": "660f9500-f30c-52e5-b827-557766551111",
    "email": "jvance@stanford.edu",
    "role": "supervisor",
    "ledger_id": "PRV-SUP-8821",
    "is_active": true,
    "created_at": "2026-03-15T08:00:00Z",
    "updated_at": "2026-03-15T08:00:00Z"
  },
  "profile": {
    "id": "8g7d2e30-b5c4-5d6f-9g0e-2b3c4d5e6f7a",
    "user_id": "660f9500-f30c-52e5-b827-557766551111",
    "full_name": "James Vance",
    "designation": null,
    "organization": "Stanford University",
    "bio": null,
    "linkedin_url": null,
    "email_domain": "stanford.edu",
    "trust_tier": "institutional",
    "created_at": "2026-03-15T08:00:00Z",
    "updated_at": "2026-03-15T08:00:00Z"
  }
}
```

#### User Object Fields

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | Internal user ID |
| `email` | `string` | Registered email |
| `role` | `"student"` or `"supervisor"` | Account role |
| `ledger_id` | `string` | Human-readable public ID |
| `is_active` | `boolean` | Account status |
| `created_at` | `datetime` (ISO 8601, UTC) | Account creation timestamp |
| `updated_at` | `datetime` (ISO 8601, UTC) | Last update timestamp |

#### Student Profile Fields

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | Profile ID |
| `user_id` | `UUID` | FK to `users.id` |
| `full_name` | `string` | Full name from signup |
| `title` | `string` or `null` | Job/internship title |
| `bio` | `string` or `null` | Professional/academic summary |
| `linkedin_url` | `string` or `null` | LinkedIn profile URL |
| `institution` | `string` or `null` | Educational institution |
| `created_at` | `datetime` | Profile creation timestamp |
| `updated_at` | `datetime` | Last update timestamp |

#### Supervisor Profile Fields

| Field | Type | Description |
|---|---|---|
| `id` | `UUID` | Profile ID |
| `user_id` | `UUID` | FK to `users.id` |
| `full_name` | `string` | Full name from signup |
| `designation` | `string` or `null` | Job designation e.g. "Dean of Students" |
| `organization` | `string` or `null` | Organization name |
| `bio` | `string` or `null` | Background summary |
| `linkedin_url` | `string` or `null` | LinkedIn profile URL |
| `email_domain` | `string` | Extracted from signup email e.g. `stanford.edu` |
| `trust_tier` | `"institutional"` or `"independent"` | Auto-resolved credibility tier |
| `created_at` | `datetime` | Profile creation timestamp |
| `updated_at` | `datetime` | Last update timestamp |

#### Errors

| Status | `detail` message | Cause |
|---|---|---|
| `401` | `"Invalid authentication credentials"` | Token missing, malformed, or expired |
| `401` | `"Invalid authentication credentials"` | `user_id` claim not found in token payload |
| `401` | `"User not found"` | Token valid but the user record no longer exists in DB |
| `403` | `"User account is inactive"` | Account has been deactivated |
| `404` | `"Student profile not found"` | Student profile row is missing (data integrity issue) |
| `404` | `"Supervisor profile not found"` | Supervisor profile row is missing (data integrity issue) |

---

## Routes — Users (`/users`)

> **Note:** This router (`routes/example.py`) is a CRUD scaffold. It is **not currently mounted** in `main.py` and is therefore **not accessible** in the running application. It serves as a reference implementation pattern for future resource routers.

All routes are prefixed with `/users`.

---

### `POST /users/`

Create a new user (simple CRUD — distinct from `/auth/signup`).

**Authentication:** None required _(route not active)_

**Request Body:** `application/json`

```json
{
  "name": "Alex Carter",
  "email": "alex@example.com"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | Yes | User display name |
| `email` | `string` (email) | Yes | Must be unique |

**Response `201 Created`:**

```json
{
  "id": 1,
  "name": "Alex Carter",
  "email": "alex@example.com",
  "created_at": "2026-04-01T10:30:00Z"
}
```

#### Errors

| Status | `detail` | Cause |
|---|---|---|
| `400` | `"Email already exists"` | Duplicate email in DB |
| `422` | Pydantic validation error | Missing/invalid fields |

---

### `GET /users/`

Retrieve a paginated list of all users.

**Authentication:** None required _(route not active)_

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `skip` | `integer` | `0` | Number of records to skip (for pagination) |
| `limit` | `integer` | `100` | Maximum number of records to return |

**Request Example:**

```
GET /users/?skip=0&limit=10
```

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "name": "Alex Carter",
    "email": "alex@example.com",
    "created_at": "2026-04-01T10:30:00Z"
  }
]
```

---

### `GET /users/{user_id}`

Retrieve a single user by their integer ID.

**Authentication:** None required _(route not active)_

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `user_id` | `integer` | The user's unique numeric ID |

**Response `200 OK`:**

```json
{
  "id": 1,
  "name": "Alex Carter",
  "email": "alex@example.com",
  "created_at": "2026-04-01T10:30:00Z"
}
```

#### Errors

| Status | `detail` | Cause |
|---|---|---|
| `404` | `"User with ID {user_id} not found"` | No user exists with that ID |

---

### `PUT /users/{user_id}`

Update an existing user's name and/or email.

**Authentication:** None required _(route not active)_

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `user_id` | `integer` | The user's numeric ID to update |

**Request Body:** `application/json`

```json
{
  "name": "Alexander Carter",
  "email": "new-email@example.com"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` or `null` | Optional | New display name |
| `email` | `string` or `null` | Optional | New email (must be unique) |

**Response `200 OK`:**

```json
{
  "id": 1,
  "name": "Alexander Carter",
  "email": "new-email@example.com",
  "created_at": "2026-04-01T10:30:00Z"
}
```

#### Errors

| Status | `detail` | Cause |
|---|---|---|
| `404` | `"User with ID {user_id} not found"` | No user exists with that ID |
| `400` | `"Email already in use"` | The new email is taken by another user |

---

### `DELETE /users/{user_id}`

Delete a user by their ID. Permanently removes the record.

**Authentication:** None required _(route not active)_

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `user_id` | `integer` | The user's numeric ID to delete |

**Response `204 No Content`:** _(empty body)_

#### Errors

| Status | `detail` | Cause |
|---|---|---|
| `404` | `"User with ID {user_id} not found"` | No user exists with that ID |

---

## Data Schemas Reference

### `UserSignupRequest`

```typescript
{
  full_name: string
  email: string            // valid email format
  password: string
  role: "student" | "supervisor"
  institution?: string     // optional, for students
  organization?: string    // optional, for supervisors
}
```

### `UserLoginRequest`

```typescript
{
  email: string
  password: string
}
```

### `TokenResponse`

```typescript
{
  access_token: string  // JWT string
  token_type: "bearer"
}
```

### `UserResponse`

```typescript
{
  id: string           // UUID
  email: string
  role: "student" | "supervisor"
  ledger_id: string    // e.g. "PRV-2026-0001"
  is_active: boolean
  created_at: string   // ISO 8601 datetime
  updated_at: string   // ISO 8601 datetime
}
```

### `StudentProfileResponse`

```typescript
{
  id: string
  user_id: string
  full_name: string
  title: string | null
  bio: string | null
  linkedin_url: string | null
  institution: string | null
  created_at: string
  updated_at: string
}
```

### `SupervisorProfileResponse`

```typescript
{
  id: string
  user_id: string
  full_name: string
  designation: string | null
  organization: string | null
  bio: string | null
  linkedin_url: string | null
  email_domain: string
  trust_tier: "institutional" | "independent"
  created_at: string
  updated_at: string
}
```

### `StudentCompleteResponse`

```typescript
{
  user: UserResponse
  profile: StudentProfileResponse
}
```

### `SupervisorCompleteResponse`

```typescript
{
  user: UserResponse
  profile: SupervisorProfileResponse
}
```

### `HealthResponse`

```typescript
{
  status: "ok" | "degraded"
  database: "healthy" | "unhealthy"
  version: string
}
```

---

## Auto-Generated Fields

### Ledger IDs

Generated automatically on signup. Never user-provided.

| Role | Format | Example |
|---|---|---|
| Student | `PRV-{YEAR}-{4-digit padded sequence}` | `PRV-2026-0089` |
| Supervisor | `PRV-SUP-{4-digit random}` | `PRV-SUP-8821` |

**Student:** Sequences are incremental per calendar year. The first student in 2026 is `PRV-2026-0001`. Sequence restarts each new year.

**Supervisor:** Random 4-digit suffix. Uniqueness enforced by retry-on-collision loop.

---

## Trust Tier Logic

Resolved automatically on supervisor signup — never manually set.

**Logic:**

```
email_domain = supervisor_email.split("@")[1].lower()
org_slug     = organization.lower().strip()
             (stripped of suffixes: "university", "college", "institute", "school", "ltd", "inc", "corp")

if email_domain in org_slug OR org_slug in email_domain:
    trust_tier = "institutional"
else:
    trust_tier = "independent"
```

**Examples:**

| Email | Organization | `email_domain` | `trust_tier` |
|---|---|---|---|
| `jvance@stanford.edu` | `Stanford University` | `stanford.edu` | `institutional` |
| `alice@gmail.com` | `Stanford University` | `gmail.com` | `independent` |
| `bob@acme.com` | `Acme Corp` | `acme.com` | `institutional` |
| `charlie@gmail.com` | _(none)_ | `gmail.com` | `independent` |

> **Why it matters:** Trust tier drives the credibility engine. Verification from an institutional supervisor carries more weight on a student's public profile than from an independent supervisor.

---

## CORS Configuration

Current configuration (development):

```python
allow_origins=["*"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

> **Production Note:** Replace `allow_origins=["*"]` with the specific frontend origin (e.g. `["https://provenancy.app"]`) before deploying.

---

## Environment Variables

Required in `.env` in the `backend/` directory:

| Variable | Description | Default |
|---|---|---|
| `user` | PostgreSQL username | — |
| `password` | PostgreSQL password | — |
| `host` | PostgreSQL host | — |
| `port` | PostgreSQL port | — |
| `dbname` | PostgreSQL database name | — |
| `SECRET_KEY` | JWT signing secret | `"your-secret-key-change-in-production"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry in minutes | `60` |
| `DEBUG` | Enable debug mode | `false` |

---

## Running the Server

```bash
# From the backend/ directory
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Quick Reference — All Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | No | API info |
| `GET` | `/health` | No | Health check |
| `POST` | `/auth/signup` | No | Register new user |
| `POST` | `/auth/login` | No | Login, get token |
| `GET` | `/auth/me` | Yes (Bearer) | Get current user + profile |
| `POST` | `/users/` | No _(inactive)_ | Create user (CRUD scaffold) |
| `GET` | `/users/` | No _(inactive)_ | List all users with pagination |
| `GET` | `/users/{user_id}` | No _(inactive)_ | Get user by ID |
| `PUT` | `/users/{user_id}` | No _(inactive)_ | Update user |
| `DELETE` | `/users/{user_id}` | No _(inactive)_ | Delete user |
