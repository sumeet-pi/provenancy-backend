# Provenancy API — Documentation

> **Version:** 1.0.0 · **Framework:** FastAPI · **Database:** PostgreSQL (Supabase) · **Auth:** JWT (HS256)
> **Base URL (dev):** `http://localhost:8000`
> **Interactive Docs:** `http://localhost:8000/docs` · `http://localhost:8000/redoc`

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication Model](#authentication-model)
3. [Global Error Conventions](#global-error-conventions)
4. [Enums & Constants](#enums--constants)
5. [Routes — System](#routes--system)
   - [GET /](#get-)
   - [GET /health](#get-health)
6. [Routes — Authentication (`/auth`)](#routes--authentication-auth)
   - [POST /auth/register](#post-authregister)
   - [POST /auth/login](#post-authlogin)
   - [GET /auth/me](#get-authme)
   - [PUT /auth/complete-profile](#put-authcomplete-profile)
   - [POST /auth/logout](#post-authlogout)
7. [Data Schemas Reference](#data-schemas-reference)
8. [Auto-Generated Fields](#auto-generated-fields)
9. [Trust Tier Logic](#trust-tier-logic)
10. [Frontend Integration Notes](#frontend-integration-notes)
11. [CORS Configuration](#cors-configuration)
12. [Environment Variables](#environment-variables)

---

## Overview

**Provenancy** is a credential verification platform where students log work engagements and supervisors cryptographically verify them. This document covers the backend API used by the frontend.

### Stack Summary

| Concern     | Technology                          |
| ----------- | ----------------------------------- |
| Framework   | FastAPI (Python)                    |
| Database    | PostgreSQL via Supabase             |
| ORM         | SQLAlchemy                          |
| Validation  | Pydantic v2                         |
| Auth        | JWT (HS256) via `python-jose`       |
| Passwords   | bcrypt                              |

---

## Authentication Model

All protected endpoints require a **Bearer Token** in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

### JWT Token Payload (decoded)

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "student",
  "ledger_id": "PRV-2026-0001",
  "exp": 1743619200
}
```

| Claim       | Type                  | Description                                         |
| ----------- | --------------------- | --------------------------------------------------- |
| `user_id`   | `string` (UUID)       | The user's internal UUID                            |
| `role`      | `string`              | `"student"` or `"supervisor"`                       |
| `ledger_id` | `string`              | Human-readable public identifier                    |
| `exp`       | `number` (Unix epoch) | Token expiry — default **60 minutes** from issue    |

### Token Lifecycle

- Tokens expire after **60 minutes** (env: `ACCESS_TOKEN_EXPIRE_MINUTES`)
- No refresh token in v1 — client must re-login on expiry (`401` will be returned)
- Inactive accounts (`is_active = false`) are rejected even with a valid token (`403`)
- **Client responsibility:** store the token in memory or `localStorage`, include it in every protected request, and clear it on logout

---

## Global Error Conventions

All errors follow this shape:

```json
{
  "detail": "Human-readable error message"
}
```

Validation errors (`422`) have a richer shape (see below).

### HTTP Status Code Reference

| Code  | Meaning                 | When it occurs                                                  |
| ----- | ----------------------- | --------------------------------------------------------------- |
| `200` | OK                      | Successful GET / POST requests                                  |
| `201` | Created                 | Successful resource creation (register)                         |
| `400` | Bad Request             | Business logic error — duplicate email, missing required field  |
| `401` | Unauthorized            | Missing / expired / invalid JWT, or wrong credentials           |
| `403` | Forbidden               | Valid token but account is inactive, or wrong role              |
| `404` | Not Found               | Profile row missing (data integrity issue)                      |
| `422` | Unprocessable Entity    | Pydantic schema validation failure (wrong types, missing fields)|
| `500` | Internal Server Error   | Unhandled exception on the server                               |

### `422` Validation Error Shape

The API customises 422 errors to a flat list of field-level messages:

```json
{
  "detail": "Validation error",
  "errors": [
    {
      "field": "email",
      "message": "value is not a valid email address"
    },
    {
      "field": "role",
      "message": "Input should be 'student' or 'supervisor'"
    }
  ]
}
```

> **Frontend tip:** Iterate `errors[]` and map each `field` to the corresponding form input to show inline validation messages.

---

## Enums & Constants

### `UserRole`

| Value          | Description                                                       |
| -------------- | ----------------------------------------------------------------- |
| `"student"`    | A candidate who creates and submits engagement records            |
| `"supervisor"` | An institutional authority who verifies engagement records        |

> Role is set at registration and is **immutable** — it cannot be changed after account creation.

### `TrustTier` _(Supervisors only)_

| Value             | When Applied                                                      |
| ----------------- | ----------------------------------------------------------------- |
| `"institutional"` | Supervisor's email domain matches their provided organization     |
| `"independent"`   | Email domain does not match organisation (default at signup)      |

---

## Routes — System

### `GET /`

Root endpoint — returns basic API metadata.

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

Health-check endpoint. Verifies API is running and the database is reachable.

**Authentication:** None required

**Response `200 OK` — Healthy:**

```json
{
  "status": "ok",
  "database": "healthy",
  "version": "1.0.0"
}
```

**Response `200 OK` — DB unreachable (Degraded):**

```json
{
  "status": "degraded",
  "database": "unhealthy",
  "version": "1.0.0"
}
```

> **Note:** This endpoint always returns HTTP `200`. You must check the `status` field to determine actual health. A degraded state means auth/profile endpoints will likely fail.

---

## Routes — Authentication (`/auth`)

All routes in this section are prefixed with `/auth`.

---

### `POST /auth/register`

Register a new user account and create their role-specific profile. Returns a JWT access token immediately — the user is logged in after registration.

> **Deprecated alias:** `POST /auth/signup` points to the same handler but is hidden from docs.

**Authentication:** None required

**Request Body:** `application/json`

```json
{
  "full_name": "Alex Carter",
  "email": "alex@university.edu",
  "password": "securepassword123",
  "role": "student"
}
```

#### Request Fields

| Field       | Type                          | Required | Notes                                               |
| ----------- | ----------------------------- | -------- | --------------------------------------------------- |
| `full_name` | `string`                      | ✅ Yes   | Stored in the profile, not the users table          |
| `email`     | `string` (valid email format) | ✅ Yes   | Login identifier; must be unique across all users   |
| `password`  | `string`                      | ✅ Yes   | Plain text — bcrypt-hashed before storage           |
| `role`      | `"student"` \| `"supervisor"` | ✅ Yes   | Determines which profile type is created; immutable |

> **Note:** `institution` and `organization` are **not** sent at registration. They are set via [PUT /auth/complete-profile](#put-authcomplete-profile) after login.

**Response `201 Created`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role": "student",
  "ledger_id": "PRV-2026-0001"
}
```

#### Response Fields

| Field          | Type     | Description                                           |
| -------------- | -------- | ----------------------------------------------------- |
| `access_token` | `string` | JWT to include in `Authorization: Bearer` header      |
| `token_type`   | `string` | Always `"bearer"`                                     |
| `role`         | `string` | `"student"` or `"supervisor"` — useful for routing    |
| `ledger_id`    | `string` | Auto-generated public ID (e.g. `PRV-2026-0001`)       |

#### Possible Errors

| Status | `detail` value                              | When it occurs                                     | Frontend action                              |
| ------ | ------------------------------------------- | -------------------------------------------------- | -------------------------------------------- |
| `400`  | `"Email already registered"`               | Another account is using this email                | Show error on email field / toast error      |
| `422`  | `"Validation error"` + `errors[]`           | Missing fields, invalid email format, bad role     | Map `errors[].field` to form field messages  |
| `500`  | `"Internal server error"`                   | Unhandled server exception                         | Generic toast: "Something went wrong"        |

#### Side Effects on Success

1. New row inserted into `users` table
2. Ledger ID auto-generated:
   - Student → `PRV-{YEAR}-{4-digit sequence}` e.g. `PRV-2026-0001`
   - Supervisor → `PRV-SUP-{4-digit random}` e.g. `PRV-SUP-8821`
3. Role-specific profile created (with `institution = null` / `organization = null`):
   - Student → row in `student_profiles`
   - Supervisor → row in `supervisor_profiles` (`trust_tier` defaults to `"independent"`)
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

| Field      | Type                          | Required | Notes                        |
| ---------- | ----------------------------- | -------- | ---------------------------- |
| `email`    | `string` (valid email format) | ✅ Yes   | Registered email address     |
| `password` | `string`                      | ✅ Yes   | Plain text password to verify|

**Response `200 OK`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role": "student",
  "ledger_id": "PRV-2026-0001"
}
```

#### Response Fields

| Field          | Type     | Description                                        |
| -------------- | -------- | -------------------------------------------------- |
| `access_token` | `string` | JWT for subsequent authenticated requests          |
| `token_type`   | `string` | Always `"bearer"`                                  |
| `role`         | `string` | Use to redirect to the correct dashboard on login  |
| `ledger_id`    | `string` | User's public identifier                           |

#### Possible Errors

| Status | `detail` value                 | When it occurs                                     | Frontend action                                   |
| ------ | ------------------------------ | -------------------------------------------------- | ------------------------------------------------- |
| `401`  | `"Invalid email or password"`  | Email not found **or** password mismatch           | Toast: "Invalid email or password" (don't specify which) |
| `403`  | `"User account is inactive"`   | Account is deactivated (`is_active = false`)       | Toast: "Your account has been deactivated"        |
| `422`  | `"Validation error"` + `errors[]` | Missing fields, invalid email format            | Map `errors[].field` to form field messages       |
| `500`  | `"Internal server error"`      | Unhandled server exception                         | Generic toast: "Something went wrong"             |

> **Security note:** The same `"Invalid email or password"` message is intentionally returned for both unknown email and wrong password to prevent user enumeration attacks.

---

### `GET /auth/me`

Retrieve the current authenticated user's full data including their role-specific profile. Used to hydrate the app state on load or after token refresh.

**Authentication:** Required — Bearer Token

**Request:** No body required.

```
Authorization: Bearer <access_token>
```

**Response `200 OK` — Student (`role = "student"`):**

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
    "institution": null,
    "created_at": "2026-04-01T10:30:00Z",
    "updated_at": "2026-04-01T10:30:00Z"
  },
  "profile_complete": false
}
```

**Response `200 OK` — Supervisor (`role = "supervisor"`):**

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
    "organization": null,
    "bio": null,
    "linkedin_url": null,
    "email_domain": "stanford.edu",
    "trust_tier": "independent",
    "created_at": "2026-03-15T08:00:00Z",
    "updated_at": "2026-03-15T08:00:00Z"
  },
  "profile_complete": false
}
```

#### `user` Object Fields

| Field        | Type                          | Description                          |
| ------------ | ----------------------------- | ------------------------------------ |
| `id`         | `string` (UUID)               | Internal user ID                     |
| `email`      | `string`                      | Registered email                     |
| `role`       | `"student"` \| `"supervisor"` | Account role                         |
| `ledger_id`  | `string`                      | Human-readable public ID             |
| `is_active`  | `boolean`                     | Account status                       |
| `created_at` | `string` (ISO 8601 UTC)       | Account creation time                |
| `updated_at` | `string` (ISO 8601 UTC)       | Last update time                     |

#### `profile` Object Fields — Student

| Field         | Type              | Description                           |
| ------------- | ----------------- | ------------------------------------- |
| `id`          | `string` (UUID)   | Profile record ID                     |
| `user_id`     | `string` (UUID)   | FK to `users.id`                      |
| `full_name`   | `string`          | Name set at registration              |
| `title`       | `string` \| `null` | Job/internship title (optional)       |
| `bio`         | `string` \| `null` | Professional/academic bio (optional)  |
| `linkedin_url`| `string` \| `null` | LinkedIn profile URL (optional)       |
| `institution` | `string` \| `null` | **Required** to mark profile complete |
| `created_at`  | `string`          | Profile creation time                 |
| `updated_at`  | `string`          | Last update time                      |

#### `profile` Object Fields — Supervisor

| Field          | Type                              | Description                                             |
| -------------- | --------------------------------- | ------------------------------------------------------- |
| `id`           | `string` (UUID)                   | Profile record ID                                       |
| `user_id`      | `string` (UUID)                   | FK to `users.id`                                        |
| `full_name`    | `string`                          | Name set at registration                                |
| `designation`  | `string` \| `null`                | Job designation e.g. "Dean of Faculty" (optional)       |
| `organization` | `string` \| `null`                | **Required** to mark profile complete                   |
| `bio`          | `string` \| `null`                | Background summary (optional)                           |
| `linkedin_url` | `string` \| `null`                | LinkedIn profile URL (optional)                         |
| `email_domain` | `string`                          | Extracted from signup email, e.g. `"stanford.edu"`      |
| `trust_tier`   | `"institutional"` \| `"independent"` | Auto-resolved; updated when `organization` is set    |
| `created_at`   | `string`                          | Profile creation time                                   |
| `updated_at`   | `string`                          | Last update time                                        |

#### `profile_complete` Flag

| Value   | Student meaning                  | Supervisor meaning               |
| ------- | -------------------------------- | -------------------------------- |
| `false` | `profile.institution` is `null`  | `profile.organization` is `null` |
| `true`  | `profile.institution` is set     | `profile.organization` is set    |

> **Frontend tip:** After login, call `GET /auth/me` and check `profile_complete`. If `false`, redirect the user to a profile completion screen before allowing access to the main app.

#### Possible Errors

| Status | `detail` value                          | When it occurs                                        | Frontend action                                  |
| ------ | --------------------------------------- | ----------------------------------------------------- | ------------------------------------------------ |
| `401`  | `"Invalid authentication credentials"` | Token missing, malformed, or expired                  | Clear token, redirect to login                   |
| `401`  | `"Invalid authentication credentials"` | `user_id` claim missing from token payload            | Clear token, redirect to login                   |
| `401`  | `"User not found"`                      | Token valid but user deleted from DB                  | Clear token, redirect to login                   |
| `403`  | `"User account is inactive"`            | Account has been deactivated                          | Toast: "Account deactivated", redirect to login  |
| `404`  | `"Student profile not found"`           | DB integrity issue — profile row missing              | Toast: "Profile error, contact support"          |
| `404`  | `"Supervisor profile not found"`        | DB integrity issue — profile row missing              | Toast: "Profile error, contact support"          |

---

### `PUT /auth/complete-profile`

Complete or update a user's profile. This endpoint is role-aware — it only accepts fields valid for the current user's role. Called after registration when `profile_complete = false`.

**Authentication:** Required — Bearer Token

**Request Body:** `application/json`

**For Students:**

```json
{
  "institution": "MIT",
  "title": "Software Engineering Intern",
  "bio": "Final year CS student interested in distributed systems.",
  "linkedin_url": "https://linkedin.com/in/alexcarter"
}
```

**For Supervisors:**

```json
{
  "organization": "Stanford University",
  "designation": "Associate Professor",
  "bio": "Researcher in AI safety and interpretability.",
  "linkedin_url": "https://linkedin.com/in/jvance"
}
```

#### Request Fields — Student

| Field          | Type     | Required                | Notes                                            |
| -------------- | -------- | ----------------------- | ------------------------------------------------ |
| `institution`  | `string` | ✅ **Yes** (must send)  | Makes `profile_complete = true`                  |
| `title`        | `string` | ❌ Optional             | Job/internship title                             |
| `bio`          | `string` | ❌ Optional             | Short bio (max ~1000 chars)                      |
| `linkedin_url` | `string` | ❌ Optional             | Full LinkedIn URL                                |

> **Student note:** Sending `organization` or `designation` fields will result in a `400` error — these fields are forbidden for students.

#### Request Fields — Supervisor

| Field          | Type     | Required                | Notes                                            |
| -------------- | -------- | ----------------------- | ------------------------------------------------ |
| `organization` | `string` | ✅ **Yes** (must send)  | Makes `profile_complete = true`; triggers trust tier re-evaluation |
| `designation`  | `string` | ❌ Optional             | Job title/designation                            |
| `bio`          | `string` | ❌ Optional             | Short bio (max ~1000 chars)                      |
| `linkedin_url` | `string` | ❌ Optional             | Full LinkedIn URL                                |

> **Supervisor note:** Sending `institution` or `title` fields will result in a `400` error — these fields are forbidden for supervisors.

**Response `200 OK` — Student:**

```json
{
  "message": "Profile updated successfully",
  "profile": {
    "id": "7f6c1d20-a4b3-4c5e-8f9d-1a2b3c4d5e6f",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "full_name": "Alex Carter",
    "title": "Software Engineering Intern",
    "bio": "Final year CS student interested in distributed systems.",
    "linkedin_url": "https://linkedin.com/in/alexcarter",
    "institution": "MIT",
    "created_at": "2026-04-01T10:30:00Z",
    "updated_at": "2026-04-01T11:00:00Z"
  }
}
```

**Response `200 OK` — Supervisor:**

```json
{
  "message": "Profile updated successfully",
  "profile": {
    "id": "8g7d2e30-b5c4-5d6f-9g0e-2b3c4d5e6f7a",
    "user_id": "660f9500-f30c-52e5-b827-557766551111",
    "full_name": "James Vance",
    "designation": "Associate Professor",
    "organization": "Stanford University",
    "bio": "Researcher in AI safety and interpretability.",
    "linkedin_url": "https://linkedin.com/in/jvance",
    "email_domain": "stanford.edu",
    "trust_tier": "institutional",
    "created_at": "2026-03-15T08:00:00Z",
    "updated_at": "2026-04-01T11:00:00Z"
  }
}
```

#### Possible Errors

| Status | `detail` value                                              | When it occurs                                                   | Frontend action                                      |
| ------ | ----------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------- |
| `400`  | `"No fields provided for update"`                           | Empty request body or all fields are `null`                      | Toast: "Please fill in at least one field"           |
| `400`  | `"institution is required to complete student profile"`     | Student sent request but omitted `institution`                   | Highlight institution field as required              |
| `400`  | `"organization is required to complete supervisor profile"` | Supervisor sent request but omitted `organization`               | Highlight organization field as required             |
| `400`  | `"Student cannot update fields: organization, designation"` | Student sent supervisor-only fields                              | Frontend shouldn't send these; log as a bug          |
| `400`  | `"Supervisor cannot update fields: institution, title"`     | Supervisor sent student-only fields                              | Frontend shouldn't send these; log as a bug          |
| `401`  | `"Invalid authentication credentials"`                      | Token missing, malformed, or expired                             | Clear token, redirect to login                       |
| `401`  | `"User not found"`                                          | Token valid but user deleted from DB                             | Clear token, redirect to login                       |
| `403`  | `"User account is inactive"`                                | Account has been deactivated                                     | Toast: "Account deactivated", redirect to login      |
| `404`  | `"Student profile not found"`                               | DB integrity issue — profile row missing                         | Toast: "Profile error, contact support"              |
| `404`  | `"Supervisor profile not found"`                            | DB integrity issue — profile row missing                         | Toast: "Profile error, contact support"              |
| `422`  | `"Validation error"` + `errors[]`                           | Wrong field types in the body                                    | Map `errors[].field` to form field messages          |

---

### `POST /auth/logout`

Logout the current user. Since JWT is stateless, the server-side operation here is a no-op — it validates your token and returns a success message.

**The real logout action is client-side**: delete the stored token.

**Authentication:** Required — Bearer Token

**Request:** No body required.

```
Authorization: Bearer <access_token>
```

**Response `200 OK`:**

```json
{
  "message": "Logged out successfully"
}
```

#### Possible Errors

| Status | `detail` value                          | When it occurs                            | Frontend action                       |
| ------ | --------------------------------------- | ----------------------------------------- | ------------------------------------- |
| `401`  | `"Invalid authentication credentials"` | Token missing, malformed, or expired       | Clear token anyway, redirect to login |
| `401`  | `"User not found"`                      | Token valid but user deleted from DB      | Clear token, redirect to login        |
| `403`  | `"User account is inactive"`            | Account has been deactivated              | Clear token, redirect to login        |

> **Frontend tip:** Even if this call fails (e.g. expired token), always clear the local token and redirect to login. Do not block logout on a server error.

---

## Data Schemas Reference

These TypeScript-style type definitions mirror the Pydantic schemas exactly.

### `UserSignupRequest` (sent to `POST /auth/register`)

```typescript
{
  full_name: string;
  email: string;           // must be a valid email
  password: string;
  role: "student" | "supervisor";
}
```

### `UserLoginRequest` (sent to `POST /auth/login`)

```typescript
{
  email: string;
  password: string;
}
```

### `TokenResponse` (returned by register & login)

```typescript
{
  access_token: string;    // JWT string
  token_type: "bearer";
  role: "student" | "supervisor";
  ledger_id: string;       // e.g. "PRV-2026-0001" or "PRV-SUP-8821"
}
```

### `UserResponse` (nested inside `/auth/me`)

```typescript
{
  id: string;              // UUID
  email: string;
  role: "student" | "supervisor";
  ledger_id: string;
  is_active: boolean;
  created_at: string;      // ISO 8601 UTC
  updated_at: string;      // ISO 8601 UTC
}
```

### `StudentProfileResponse`

```typescript
{
  id: string;              // UUID
  user_id: string;         // UUID
  full_name: string;
  title: string | null;
  bio: string | null;
  linkedin_url: string | null;
  institution: string | null;
  created_at: string;
  updated_at: string;
}
```

### `SupervisorProfileResponse`

```typescript
{
  id: string;              // UUID
  user_id: string;         // UUID
  full_name: string;
  designation: string | null;
  organization: string | null;
  bio: string | null;
  linkedin_url: string | null;
  email_domain: string;    // e.g. "stanford.edu"
  trust_tier: "institutional" | "independent";
  created_at: string;
  updated_at: string;
}
```

### `StudentCompleteResponse` (returned by `GET /auth/me` for students)

```typescript
{
  user: UserResponse;
  profile: StudentProfileResponse;
  profile_complete: boolean;
}
```

### `SupervisorCompleteResponse` (returned by `GET /auth/me` for supervisors)

```typescript
{
  user: UserResponse;
  profile: SupervisorProfileResponse;
  profile_complete: boolean;
}
```

### `CompleteProfileRequest` (sent to `PUT /auth/complete-profile`)

```typescript
// Send only the fields relevant to the user's role
{
  // Student fields
  institution?: string;
  title?: string;
  bio?: string;
  linkedin_url?: string;

  // Supervisor fields
  organization?: string;
  designation?: string;
}
```

### `CompleteProfileResponse` (returned by `PUT /auth/complete-profile`)

```typescript
{
  message: string;         // "Profile updated successfully"
  profile: StudentProfileResponse | SupervisorProfileResponse;
}
```

### `LogoutResponse`

```typescript
{
  message: string;         // "Logged out successfully"
}
```

---

## Auto-Generated Fields

These fields are **never provided by the client** — the server creates them automatically.

### Ledger IDs

Generated at registration. Format depends on role:

| Role       | Format                                  | Example          |
| ---------- | --------------------------------------- | ---------------- |
| Student    | `PRV-{YEAR}-{4-digit padded sequence}`  | `PRV-2026-0001`  |
| Supervisor | `PRV-SUP-{4-digit random}`              | `PRV-SUP-8821`   |

- **Student:** Sequential per calendar year. First student in 2026 = `PRV-2026-0001`. Resets per year.
- **Supervisor:** Random 4-digit suffix. Server retries until unique.

### `email_domain` (Supervisors only)

Extracted from the supervisor's signup email:

```
"jvance@stanford.edu"  →  email_domain = "stanford.edu"
```

### `trust_tier` (Supervisors only)

Auto-resolved. See [Trust Tier Logic](#trust-tier-logic) below.

---

## Trust Tier Logic

Resolved automatically when a supervisor sets their `organization` via `PUT /auth/complete-profile`. Never manually set by the client.

**Resolution logic:**

```
email_domain = supervisor_email.split("@")[1].lower()
org_slug     = organization.lower().strip()
             # strips: "university", "college", "institute", "school", "ltd", "inc", "corp"

if (email_domain in org_slug) OR (org_slug in email_domain):
    trust_tier = "institutional"
else:
    trust_tier = "independent"
```

**Examples:**

| Email                  | Organization         | `trust_tier`      |
| ---------------------- | -------------------- | ----------------- |
| `jvance@stanford.edu`  | `Stanford University`| `institutional`   |
| `alice@gmail.com`      | `Stanford University`| `independent`     |
| `bob@acme.com`         | `Acme Corp`          | `institutional`   |
| `charlie@gmail.com`    | _(none / null)_      | `independent`     |

> **Why it matters:** Verification from an `institutional` supervisor carries more credibility weight on a student's public profile than from an `independent` supervisor.

---

## Frontend Integration Notes

### Typical Auth Flow

```
1. User hits Register form
   └─ POST /auth/register
       └─ On success: store { access_token, role, ledger_id }
                      redirect to → complete-profile page

2. Complete Profile page
   └─ PUT /auth/complete-profile
       └─ On success: redirect to → dashboard (role-based)

3. On every app load / hard refresh
   └─ GET /auth/me
       ├─ 401 → clear token, redirect to login
       └─ 200 → hydrate app state
                check profile_complete
                  └─ false → redirect to complete-profile
                  └─ true  → proceed to dashboard

4. User hits Login form
   └─ POST /auth/login
       └─ On success: store { access_token, role, ledger_id }
                      GET /auth/me to hydrate state
                      check profile_complete → route accordingly

5. User logs out
   └─ POST /auth/logout  (fire and forget — ignore errors)
       └─ Always: clear token, clear state, redirect to login
```

### Token Storage

Store `access_token` in `localStorage` or a cookies store (pick one and be consistent). Include it in every authenticated request:

```javascript
headers: {
  "Authorization": `Bearer ${access_token}`,
  "Content-Type": "application/json"
}
```

### Role-Based Routing

After login/register, use the `role` field from the token response (or from `GET /auth/me`) to route users:

- `"student"` → `/student/dashboard`
- `"supervisor"` → `/supervisor/dashboard`

### Error Handling Pattern

```javascript
try {
  const res = await api.post("/auth/login", { email, password });
  // success
} catch (err) {
  if (err.status === 401) showToast("Invalid email or password");
  else if (err.status === 403) showToast("Your account has been deactivated");
  else if (err.status === 422) mapFieldErrors(err.data.errors);
  else showToast("Something went wrong. Please try again.");
}
```

---

## CORS Configuration

Current development config (all origins allowed):

```python
allow_origins=["*"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

> **Production:** Replace `["*"]` with the exact frontend origin (e.g. `["https://provenancy.app"]`) before deploying.

---

## Environment Variables

Required in `backend/.env`:

| Variable                      | Description                                  | Default                              |
| ----------------------------- | -------------------------------------------- | ------------------------------------ |
| `user`                        | PostgreSQL username                          | —                                    |
| `password`                    | PostgreSQL password                          | —                                    |
| `host`                        | PostgreSQL host                              | —                                    |
| `port`                        | PostgreSQL port                              | —                                    |
| `dbname`                      | PostgreSQL database name                     | —                                    |
| `SECRET_KEY`                  | JWT signing secret                           | `"your-secret-key-change-in-production"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime in minutes                | `60`                                 |
| `DEBUG`                       | Enable debug logging                         | `False`                              |

> **Production:** Always override `SECRET_KEY` with a strong random secret. Never commit `.env` to version control.
