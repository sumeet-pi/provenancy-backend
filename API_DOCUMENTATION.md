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
7. [Routes — Student (`/student`)](#routes--student-student)
   - [GET /student/me](#get-studentme)
   - [PUT /student/me](#put-studentme)
   - [GET /student/{student_id}/public](#get-studentstudent_idpublic)
8. [Routes — Supervisor (`/supervisor`)](#routes--supervisor-supervisor)
   - [GET /supervisor/me](#get-supervisorme)
   - [PUT /supervisor/me](#put-supervisorme)
   - [GET /supervisor/{supervisor_id}/public](#get-supervisorsupervisor_idpublic)
9. [Routes — Student Engagements (`/engagements`)](#routes--student-engagements-engagements)
   - [POST /engagements](#post-engagements)
   - [GET /engagements](#get-engagements)
   - [GET /engagements/:id](#get-engagementsid)
   - [PUT /engagements/:id](#put-engagementsid)
   - [DELETE /engagements/:id](#delete-engagementsid)
   - [POST /engagements/:id/submit](#post-engagementsidsubmit)
10. [Routes — Supervisor Engagements (`/supervisor/engagements`)](#routes--supervisor-engagements-supervisorengagements)
    - [GET /supervisor/engagements/requests](#get-supervisorengagementsrequests)
    - [POST /engagements/:id/approve](#post-engagementsidapprove)
    - [POST /engagements/:id/reject](#post-engagementsidreject)
    - [POST /engagements/:id/request-edit](#post-engagementsidrequested-edit)
11. [Routes — Skills (`/skills`)](#routes--skills-skills)
    - [GET /skills/search](#get-skillssearch)
    - [GET /skills](#get-skills)
    - [POST /skills](#post-skills)
    - [DELETE /skills/{skill_id}](#delete-skillsskill_id)
12. [Data Schemas Reference](#data-schemas-reference)
13. [Auto-Generated Fields](#auto-generated-fields)
14. [Trust Tier Logic](#trust-tier-logic)
15. [Frontend Integration Notes](#frontend-integration-notes)
16. [CORS Configuration](#cors-configuration)
17. [Environment Variables](#environment-variables)

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

### `EngagementStatus`

| Value              | Description                                                                 |
| ------------------ | --------------------------------------------------------------------------- |
| `"draft"`          | Created by student, not yet submitted for verification                      |
| `"pending"`        | Submitted — awaiting supervisor action                                      |
| `"verified"`       | Approved and cryptographically signed by supervisor; **immutable**          |
| `"rejected"`       | Rejected by supervisor; student cannot resubmit                             |
| `"edit_requested"` | Supervisor requested changes; student must update and resubmit              |

**Status flow:**

```
draft → pending → verified
               ↘ rejected
               ↘ edit_requested → pending (on resubmit)
```

### `VerificationType`

| Value             | Description                                                                 |
| ----------------- | --------------------------------------------------------------------------- |
| `"institutional"` | Supervisor's email domain matches the engagement organisation               |
| `"independent"`   | Supervisor's email domain does not match the engagement organisation        |

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

## Routes — Student (`/student`)

All routes in this section are prefixed with `/student`.

> **Role guard:** All `/student/me` endpoints require the authenticated user to have `role = "student"`. A supervisor token will receive `403 Forbidden`.

---

### `GET /student/me`

Get the current student's private profile — includes the embedded `UserResponse` block and a `profile_complete` flag. Use this to hydrate the student dashboard.

**Authentication:** Required — Bearer Token (`role = "student"` only)

**Request:** No body required.

```
Authorization: Bearer <access_token>
```

**Response `200 OK`:**

```json
{
  "message": "Profile retrieved successfully",
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
  },
  "profile_complete": true,
  "ledger_id": "PRV-2026-0001"
}
```

#### Response Fields

| Field              | Type      | Description                                                   |
| ------------------ | --------- | ------------------------------------------------------------- |
| `message`          | `string`  | Always `"Profile retrieved successfully"`                     |
| `profile`          | `object`  | Full `StudentProfileResponse` object (see schema below)       |
| `profile_complete` | `boolean` | `true` if `profile.institution` is set                        |
| `ledger_id`        | `string`  | User's public identifier (e.g. `PRV-2026-0001`)               |

#### Possible Errors

| Status | `detail` value                          | When it occurs                          | Frontend action                                 |
| ------ | --------------------------------------- | --------------------------------------- | ----------------------------------------------- |
| `401`  | `"Invalid authentication credentials"` | Token missing, malformed, or expired    | Clear token, redirect to login                  |
| `401`  | `"User not found"`                      | Token valid but user deleted from DB    | Clear token, redirect to login                  |
| `403`  | `"User account is inactive"`            | Account deactivated                     | Toast: "Account deactivated", redirect to login |
| `403`  | `"Supervisor access required"`          | Supervisor token used on student route  | Redirect to correct dashboard                   |
| `404`  | `"Student profile not found"`           | DB integrity issue — profile row missing | Toast: "Profile error, contact support"        |

---

### `PUT /student/me`

Update the current student's profile fields. All fields are optional — send only the ones you want to change. At least one non-empty field must be provided.

**Authentication:** Required — Bearer Token (`role = "student"` only)

**Request Body:** `application/json`

```json
{
  "full_name": "Alex Carter",
  "title": "Software Engineering Intern",
  "bio": "Final year CS student interested in distributed systems.",
  "linkedin_url": "https://linkedin.com/in/alexcarter",
  "institution": "MIT"
}
```

#### Request Fields

| Field          | Type     | Required    | Validation                                          |
| -------------- | -------- | ----------- | --------------------------------------------------- |
| `full_name`    | `string` | ❌ Optional | Trimmed; max 150 chars                              |
| `title`        | `string` | ❌ Optional | Trimmed whitespace                                  |
| `bio`          | `string` | ❌ Optional | Trimmed whitespace                                  |
| `linkedin_url` | `string` | ❌ Optional | Must start with `http(s)://` and contain `linkedin.com` |
| `institution`  | `string` | ❌ Optional | Setting this makes `profile_complete = true`        |

> **Note:** At least one field with a non-empty value must be provided, otherwise a `400` is returned.

**Response `200 OK`:**

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
    "updated_at": "2026-04-01T11:45:00Z"
  },
  "profile_complete": true
}
```

> **Note:** The `PUT /student/me` response does **not** include `ledger_id` (unlike `GET /student/me`).

#### Possible Errors

| Status | `detail` value                          | When it occurs                               | Frontend action                                 |
| ------ | --------------------------------------- | -------------------------------------------- | ----------------------------------------------- |
| `400`  | `"No fields provided for update"`       | All fields are `null` or empty strings       | Toast: "Please fill in at least one field"      |
| `401`  | `"Invalid authentication credentials"` | Token missing, malformed, or expired         | Clear token, redirect to login                  |
| `401`  | `"User not found"`                      | Token valid but user deleted from DB         | Clear token, redirect to login                  |
| `403`  | `"User account is inactive"`            | Account deactivated                          | Toast: "Account deactivated", redirect to login |
| `403`  | `"Supervisor access required"`          | Supervisor token used on student route       | Redirect to correct dashboard                   |
| `404`  | `"Student profile not found"`           | DB integrity issue — profile row missing     | Toast: "Profile error, contact support"         |
| `422`  | `"Validation error"` + `errors[]`       | Wrong field types or invalid `linkedin_url`  | Map `errors[].field` to form field messages     |

---

### `GET /student/{student_id}/public`

Get a student's public-facing profile by their **profile UUID** (`StudentProfile.id`). Includes only verified engagements. No authentication required — suitable for public portfolio links.

**Authentication:** None required

**Path Parameter:**

| Parameter    | Type            | Description                                  |
| ------------ | --------------- | -------------------------------------------- |
| `student_id` | `string` (UUID) | The student's profile UUID (`StudentProfile.id`) |

**Request:** No body required.

**Response `200 OK`:**

```json
{
  "id": "7f6c1d20-a4b3-4c5e-8f9d-1a2b3c4d5e6f",
  "ledger_id": "PRV-2026-0001",
  "full_name": "Alex Carter",
  "title": "Software Engineering Intern",
  "bio": "Final year CS student interested in distributed systems.",
  "linkedin_url": "https://linkedin.com/in/alexcarter",
  "institution": "MIT",
  "created_at": "2026-04-01T10:30:00Z",
  "verified_engagements": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "organization_name": "Acme Corp",
      "role": "Backend Engineer Intern",
      "start_date": "2025-06-01T00:00:00Z",
      "end_date": "2025-08-31T00:00:00Z",
      "verification_type": "institutional",
      "verified_at": "2025-09-02T14:22:00Z"
    }
  ],
  "skills": {
    "declared": [
      {
        "id": "e4c1f211-54b9-4d43-a65c-6b3281cda885",
        "name": "python"
      }
    ],
    "verified": [
      {
        "name": "javascript",
        "count": 2
      }
    ]
  }
}
```

#### Response Fields

| Field                  | Type              | Description                                               |
| ---------------------- | ----------------- | --------------------------------------------------------- |
| `id`                   | `string` (UUID)   | Student profile UUID                                      |
| `ledger_id`            | `string`          | Public ledger ID (e.g. `PRV-2026-0001`)                   |
| `full_name`            | `string`          | Student's display name                                    |
| `title`                | `string` \| `null` | Current role/title (optional)                            |
| `bio`                  | `string` \| `null` | Short bio (optional)                                     |
| `linkedin_url`         | `string` \| `null` | LinkedIn URL (optional)                                  |
| `institution`          | `string` \| `null` | Affiliated institution (optional)                        |
| `created_at`           | `string` (ISO 8601 UTC) | Profile creation date                               |
| `verified_engagements` | `array`           | List of verified engagements only (empty array if none)   |
| `skills`               | `object` \| `null`| Grouped skills containing `declared` and `verified` lists |

#### `verified_engagements[]` Item Fields

| Field               | Type                                          | Description                                  |
| ------------------- | --------------------------------------------- | -------------------------------------------- |
| `id`                | `string` (UUID)                               | Engagement UUID                              |
| `organization_name` | `string`                                      | Name of the organisation                     |
| `role`              | `string`                                      | Role held during the engagement              |
| `start_date`        | `string` (ISO 8601 UTC)                       | Engagement start date                        |
| `end_date`          | `string` (ISO 8601 UTC) \| `null`             | Engagement end date (null if ongoing)        |
| `verification_type` | `"institutional"` \| `"independent"` \| `null` | Supervisor's trust tier at time of verification |
| `verified_at`       | `string` (ISO 8601 UTC) \| `null`             | When the engagement was verified             |

#### `skills` Object Fields

| Field        | Type    | Description                                            |
| ------------ | ------- | ------------------------------------------------------ |
| `declared`   | `array` | List of self-declared skills (see fields below)        |
| `verified`   | `array` | List of verified skills with counts (see fields below) |

**`skills.declared[]` Item Fields:**
- `id` (`string`, UUID): Unique skill ID
- `name` (`string`): Skill name

**`skills.verified[]` Item Fields:**
- `name` (`string`): Verified skill name
- `count` (`integer`): Number of verified engagements backing this skill

#### Possible Errors

| Status | `detail` value                    | When it occurs                                                      | Frontend action                        |
| ------ | --------------------------------- | ------------------------------------------------------------------- | -------------------------------------- |
| `400`  | `"Invalid student ID format"`     | `student_id` path param is not a valid UUID                         | Show 404 page                          |
| `404`  | `"Student profile not found"`     | No active student profile with that UUID, or account is deactivated | Show 404 page                          |

---

## Routes — Supervisor (`/supervisor`)

All routes in this section are prefixed with `/supervisor`.

> **Role guard:** All `/supervisor/me` endpoints require the authenticated user to have `role = "supervisor"`. A student token will receive `403 Forbidden`.

---

### `GET /supervisor/me`

Get the current supervisor's private profile — includes the full profile object, `profile_complete` flag, and `ledger_id`. Use this to hydrate the supervisor dashboard.

**Authentication:** Required — Bearer Token (`role = "supervisor"` only)

**Request:** No body required.

```
Authorization: Bearer <access_token>
```

**Response `200 OK`:**

```json
{
  "message": "Profile retrieved successfully",
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
  },
  "profile_complete": true,
  "ledger_id": "PRV-SUP-8821"
}
```

#### Response Fields

| Field              | Type      | Description                                                    |
| ------------------ | --------- | -------------------------------------------------------------- |
| `message`          | `string`  | Always `"Profile retrieved successfully"`                      |
| `profile`          | `object`  | Full `SupervisorProfileResponse` object (see schema below)     |
| `profile_complete` | `boolean` | `true` if `profile.organization` is set                        |
| `ledger_id`        | `string`  | User's public identifier (e.g. `PRV-SUP-8821`)                 |

#### Possible Errors

| Status | `detail` value                          | When it occurs                           | Frontend action                                  |
| ------ | --------------------------------------- | ---------------------------------------- | ------------------------------------------------ |
| `401`  | `"Invalid authentication credentials"` | Token missing, malformed, or expired     | Clear token, redirect to login                   |
| `401`  | `"User not found"`                      | Token valid but user deleted from DB     | Clear token, redirect to login                   |
| `403`  | `"User account is inactive"`            | Account deactivated                      | Toast: "Account deactivated", redirect to login  |
| `403`  | `"Supervisor access required"`          | Student token used on supervisor route   | Redirect to correct dashboard                    |
| `404`  | `"Supervisor profile not found"`        | DB integrity issue — profile row missing | Toast: "Profile error, contact support"          |

---

### `PUT /supervisor/me`

Update the current supervisor's profile fields. All fields are optional — send only the ones you want to change. At least one non-empty field must be provided.

**Authentication:** Required — Bearer Token (`role = "supervisor"` only)

**Request Body:** `application/json`

```json
{
  "full_name": "James Vance",
  "designation": "Associate Professor",
  "organization": "Stanford University",
  "bio": "Researcher in AI safety and interpretability.",
  "linkedin_url": "https://linkedin.com/in/jvance"
}
```

#### Request Fields

| Field          | Type     | Required    | Validation                                              |
| -------------- | -------- | ----------- | ------------------------------------------------------- |
| `full_name`    | `string` | ❌ Optional | Trimmed; max 150 chars                                  |
| `designation`  | `string` | ❌ Optional | Trimmed whitespace                                      |
| `organization` | `string` | ❌ Optional | Trimmed; setting this triggers trust tier re-evaluation |
| `bio`          | `string` | ❌ Optional | Trimmed whitespace                                      |
| `linkedin_url` | `string` | ❌ Optional | Must start with `http(s)://` and contain `linkedin.com` |

> **Note:** At least one field with a non-empty value must be provided, otherwise a `400` is returned.

> **Trust tier:** Updating `organization` automatically re-evaluates `trust_tier`. See [Trust Tier Logic](#trust-tier-logic).

**Response `200 OK`:**

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
    "updated_at": "2026-04-01T11:45:00Z"
  },
  "profile_complete": true
}
```

> **Note:** The `PUT /supervisor/me` response does **not** include `ledger_id` (unlike `GET /supervisor/me`).

#### Possible Errors

| Status | `detail` value                          | When it occurs                               | Frontend action                                  |
| ------ | --------------------------------------- | -------------------------------------------- | ------------------------------------------------ |
| `400`  | `"No fields provided for update"`       | All fields are `null` or empty strings       | Toast: "Please fill in at least one field"       |
| `401`  | `"Invalid authentication credentials"` | Token missing, malformed, or expired         | Clear token, redirect to login                   |
| `401`  | `"User not found"`                      | Token valid but user deleted from DB         | Clear token, redirect to login                   |
| `403`  | `"User account is inactive"`            | Account deactivated                          | Toast: "Account deactivated", redirect to login  |
| `403`  | `"Supervisor access required"`          | Student token used on supervisor route       | Redirect to correct dashboard                    |
| `404`  | `"Supervisor profile not found"`        | DB integrity issue — profile row missing     | Toast: "Profile error, contact support"          |
| `422`  | `"Validation error"` + `errors[]`       | Wrong field types or invalid `linkedin_url`  | Map `errors[].field` to form field messages      |

---

### `GET /supervisor/{supervisor_id}/public`

Get a supervisor's public-facing profile by their **profile UUID** (`SupervisorProfile.id`). Includes only verified engagements they have verified. No authentication required.

**Authentication:** None required

**Path Parameter:**

| Parameter       | Type            | Description                                       |
| --------------- | --------------- | ------------------------------------------------- |
| `supervisor_id` | `string` (UUID) | The supervisor's profile UUID (`SupervisorProfile.id`) |

**Request:** No body required.

**Response `200 OK`:**

```json
{
  "id": "8g7d2e30-b5c4-5d6f-9g0e-2b3c4d5e6f7a",
  "ledger_id": "PRV-SUP-8821",
  "full_name": "James Vance",
  "designation": "Associate Professor",
  "organization": "Stanford University",
  "bio": "Researcher in AI safety and interpretability.",
  "linkedin_url": "https://linkedin.com/in/jvance",
  "trust_tier": "institutional",
  "created_at": "2026-03-15T08:00:00Z",
  "verified_engagements": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "student_full_name": "Alex Carter",
      "organization_name": "Acme Corp",
      "role": "Backend Engineer Intern",
      "start_date": "2025-06-01T00:00:00Z",
      "end_date": "2025-08-31T00:00:00Z",
      "verification_type": "institutional",
      "verified_at": "2025-09-02T14:22:00Z"
    }
  ]
}
```

#### Response Fields

| Field                  | Type                              | Description                                              |
| ---------------------- | --------------------------------- | -------------------------------------------------------- |
| `id`                   | `string` (UUID)                   | Supervisor profile UUID                                  |
| `ledger_id`            | `string`                          | Public ledger ID (e.g. `PRV-SUP-8821`)                   |
| `full_name`            | `string`                          | Supervisor's display name                                |
| `designation`          | `string` \| `null`                | Job title/designation (optional)                         |
| `organization`         | `string` \| `null`                | Organisation name (optional)                             |
| `bio`                  | `string` \| `null`                | Short bio (optional)                                     |
| `linkedin_url`         | `string` \| `null`                | LinkedIn URL (optional)                                  |
| `trust_tier`           | `"institutional"` \| `"independent"` | Auto-resolved trust tier                             |
| `created_at`           | `string` (ISO 8601 UTC)           | Profile creation date                                    |
| `verified_engagements` | `array`                           | Engagements this supervisor has verified (empty if none) |

#### `verified_engagements[]` Item Fields

| Field               | Type                                          | Description                                        |
| ------------------- | --------------------------------------------- | -------------------------------------------------- |
| `id`                | `string` (UUID)                               | Engagement UUID                                    |
| `student_full_name` | `string`                                      | Name of the student whose engagement was verified  |
| `organization_name` | `string`                                      | Organisation for the engagement                    |
| `role`              | `string`                                      | Role held during the engagement                    |
| `start_date`        | `string` (ISO 8601 UTC)                       | Engagement start date                              |
| `end_date`          | `string` (ISO 8601 UTC) \| `null`             | Engagement end date                                |
| `verification_type` | `"institutional"` \| `"independent"` \| `null` | Supervisor's trust tier at time of verification    |
| `verified_at`       | `string` (ISO 8601 UTC) \| `null`             | When the engagement was verified                   |

#### Possible Errors

| Status | `detail` value                       | When it occurs                                                          | Frontend action |
| ------ | ------------------------------------ | ----------------------------------------------------------------------- | --------------- |
| `400`  | `"Invalid supervisor ID format"`     | `supervisor_id` path param is not a valid UUID                          | Show 404 page   |
| `404`  | `"Supervisor profile not found"`     | No active supervisor profile with that UUID, or account is deactivated  | Show 404 page   |

---

## Routes — Student Engagements (`/engagements`)

All student engagement routes are prefixed with `/engagements`.

> **Role guard:** `POST`, `PUT`, `DELETE`, and `POST /:id/submit` require `role = "student"`. `GET /engagements` and `GET /engagements/:id` accept both roles (response content is role-aware). A supervisor token will receive `403 Forbidden` on student-only endpoints.

> **Profile guard:** `POST /engagements` (create) additionally requires `profile_complete = true`. An incomplete profile returns `403 Forbidden`.

---

### `POST /engagements`

Create a new engagement record. Created engagements start in `draft` status and are not visible to the assigned supervisor until submitted.

**Authentication:** Required — Bearer Token (`role = "student"` + `profile_complete = true`)

**Request Body:** `application/json`

```json
{
  "organization_name": "Acme Corp",
  "role": "Backend Engineer Intern",
  "start_date": "2025-06-01T00:00:00Z",
  "end_date": "2025-08-31T00:00:00Z",
  "summary": "Worked on the payments microservice team.",
  "highlights": ["Reduced API latency by 40%", "Shipped 3 features to production"],
  "links": ["https://github.com/alexcarter/payments-poc"],
  "supervisor_ref": "PRV-SUP-8821",
  "skills": ["Python", "FastAPI", "Docker"]
}
```

#### Request Fields

| Field               | Type                    | Required    | Notes                                                                 |
| ------------------- | ----------------------- | ----------- | --------------------------------------------------------------------- |
| `organization_name` | `string`                | ✅ Yes      | Name of the company/institution                                       |
| `role`              | `string`                | ✅ Yes      | Role/position held during the engagement                              |
| `start_date`        | `string` (ISO 8601 UTC) | ✅ Yes      | Engagement start date                                                 |
| `end_date`          | `string` (ISO 8601 UTC) | ❌ Optional | Engagement end date; `null` if ongoing                                |
| `summary`           | `string`                | ❌ Optional | Short description of the engagement                                   |
| `highlights`        | `array` of `string`     | ❌ Optional | Notable achievements or bullet points                                 |
| `links`             | `array` of `string`     | ❌ Optional | Supporting URLs (e.g. GitHub, portfolio)                              |
| `supervisor_ref`    | `string`                | ❌ Optional | Supervisor's ledger ID (e.g. `PRV-SUP-8821`) or registered email; required at submit time |
| `skills`            | `array` of `string`     | ❌ Optional | Skill names to associate; created or reused per student profile       |

**Response `201 Created`:** Returns a full `EngagementResponse` object (see [Data Schemas Reference](#data-schemas-reference)).

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "student_profile_id": "7f6c1d20-a4b3-4c5e-8f9d-1a2b3c4d5e6f",
  "supervisor_profile_id": null,
  "supervisor_ref": "PRV-SUP-8821",
  "organization_name": "Acme Corp",
  "role": "Backend Engineer Intern",
  "start_date": "2025-06-01T00:00:00Z",
  "end_date": "2025-08-31T00:00:00Z",
  "summary": "Worked on the payments microservice team.",
  "highlights": ["Reduced API latency by 40%", "Shipped 3 features to production"],
  "links": ["https://github.com/alexcarter/payments-poc"],
  "status": "draft",
  "rejection_reason": null,
  "verified_at": null,
  "block_hash": null,
  "verification_type": null,
  "created_at": "2026-04-10T08:00:00Z",
  "updated_at": "2026-04-10T08:00:00Z",
  "skills": [
    { "id": "a1b2c3d4-...", "name": "python" },
    { "id": "b2c3d4e5-...", "name": "fastapi" },
    { "id": "c3d4e5f6-...", "name": "docker" }
  ]
}
```

#### Possible Errors

| Status | `detail` value                                                              | When it occurs                                             | Frontend action                                       |
| ------ | --------------------------------------------------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------- |
| `400`  | `"Duplicate engagement: similar engagement already exists..."`              | Same org + role + non-rejected engagement already exists   | Toast: "A similar engagement already exists"          |
| `401`  | `"Invalid authentication credentials"`                                      | Token missing, malformed, or expired                       | Clear token, redirect to login                        |
| `403`  | `"User account is inactive"`                                                | Account deactivated                                        | Toast: "Account deactivated", redirect to login       |
| `403`  | `"Student access required"`                                                 | Supervisor token used on student-only endpoint             | Redirect to correct dashboard                         |
| `403`  | `"Complete your profile before creating engagements"`                       | Profile is incomplete (`institution` not set)              | Redirect to profile completion page                   |
| `404`  | `"Student profile not found"`                                               | DB integrity issue                                         | Toast: "Profile error, contact support"               |
| `422`  | `"Validation error"` + `errors[]`                                           | Missing required fields or wrong types                     | Map `errors[].field` to form field messages           |

---

### `GET /engagements`

List engagements for the current user. Results are role-aware — students see their own engagements; supervisors see engagements assigned to them.

**Authentication:** Required — Bearer Token (both roles)

**Query Parameters:**

| Parameter | Type     | Required    | Description                                                                         |
| --------- | -------- | ----------- | ----------------------------------------------------------------------------------- |
| `status`  | `string` | ❌ Optional | Filter by status. Omit or use `all` for no filter. See allowed values per role below |

**Allowed `status` values by role:**

| Role         | Allowed values                                              |
| ------------ | ----------------------------------------------------------- |
| `student`    | `all` · `draft` · `pending` · `verified` · `rejected` · `edit_requested` |
| `supervisor` | `all` · `pending` · `verified` · `rejected` · `edit_requested` |

**Response `200 OK`:** Returns an array of `EngagementListResponse` objects.

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "organization_name": "Acme Corp",
    "role": "Backend Engineer Intern",
    "start_date": "2025-06-01T00:00:00Z",
    "end_date": "2025-08-31T00:00:00Z",
    "status": "pending",
    "verified_at": null
  }
]
```

#### Response Fields (`EngagementListResponse` item)

| Field               | Type                                    | Description                                   |
| ------------------- | --------------------------------------- | --------------------------------------------- |
| `id`                | `string` (UUID)                         | Engagement UUID                               |
| `organization_name` | `string`                                | Company/institution name                      |
| `role`              | `string`                                | Role held                                     |
| `start_date`        | `string` (ISO 8601 UTC)                 | Engagement start date                         |
| `end_date`          | `string` (ISO 8601 UTC) \| `null`       | Engagement end date                           |
| `status`            | `EngagementStatus`                      | Current status                                |
| `verified_at`       | `string` (ISO 8601 UTC) \| `null`       | Verification timestamp (`null` if not verified) |

> **Note:** Returns an empty array `[]` if no engagements exist. Never returns `404`.

#### Possible Errors

| Status | `detail` value                                    | When it occurs                                | Frontend action                  |
| ------ | ------------------------------------------------- | --------------------------------------------- | -------------------------------- |
| `400`  | `"Invalid status. Allowed values: ..."`           | `status` query param is not in allowed list   | Show filter error / reset filter |
| `401`  | `"Invalid authentication credentials"`            | Token missing, malformed, or expired          | Clear token, redirect to login   |
| `403`  | `"User account is inactive"`                      | Account deactivated                           | Toast + redirect to login        |

---

### `GET /engagements/:id`

Get full details of a single engagement. Accessible by the **owner student** and the **assigned supervisor**.

**Authentication:** Required — Bearer Token (both roles)

**Path Parameter:**

| Parameter       | Type            | Description         |
| --------------- | --------------- | ------------------- |
| `engagement_id` | `string` (UUID) | The engagement UUID |

**Response `200 OK`:** Returns a full `EngagementResponse` object.

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "student_profile_id": "7f6c1d20-a4b3-4c5e-8f9d-1a2b3c4d5e6f",
  "supervisor_profile_id": "8g7d2e30-b5c4-5d6f-9g0e-2b3c4d5e6f7a",
  "supervisor_ref": "PRV-SUP-8821",
  "organization_name": "Acme Corp",
  "role": "Backend Engineer Intern",
  "start_date": "2025-06-01T00:00:00Z",
  "end_date": "2025-08-31T00:00:00Z",
  "summary": "Worked on the payments microservice team.",
  "highlights": ["Reduced API latency by 40%"],
  "links": ["https://github.com/alexcarter/payments-poc"],
  "status": "verified",
  "rejection_reason": null,
  "verified_at": "2025-09-02T14:22:00Z",
  "block_hash": "0xabcdef...1234",
  "verification_type": "institutional",
  "created_at": "2026-04-10T08:00:00Z",
  "updated_at": "2026-04-10T09:00:00Z",
  "skills": [
    { "id": "a1b2c3d4-...", "name": "python" }
  ]
}
```

> **Role note:** This endpoint is shared. The frontend should use the JWT `role` claim to decide whether to show supervisor action buttons (approve / reject / request-edit).

#### Possible Errors

| Status | `detail` value                            | When it occurs                                                      | Frontend action                  |
| ------ | ----------------------------------------- | ------------------------------------------------------------------- | -------------------------------- |
| `401`  | `"Invalid authentication credentials"`   | Token missing, malformed, or expired                                | Clear token, redirect to login   |
| `403`  | `"You don't have access to this engagement"` | Student accessing another student's engagement, or supervisor not assigned | Show 403 page             |
| `404`  | `"Engagement not found"`                  | No engagement with that UUID                                        | Show 404 page                    |

---

### `PUT /engagements/:id`

Update an existing engagement. Only allowed when status is `draft` or `edit_requested`.

**Authentication:** Required — Bearer Token (`role = "student"` only)

**Path Parameter:**

| Parameter       | Type            | Description         |
| --------------- | --------------- | ------------------- |
| `engagement_id` | `string` (UUID) | The engagement UUID |

**Request Body:** `application/json` — all fields are optional; send only what you want to change.

```json
{
  "organization_name": "Acme Corp",
  "role": "Backend Engineer Intern",
  "start_date": "2025-06-01T00:00:00Z",
  "end_date": "2025-08-31T00:00:00Z",
  "summary": "Updated summary.",
  "highlights": ["Led backend refactor"],
  "links": ["https://github.com/alexcarter/payments-poc"],
  "supervisor_ref": "PRV-SUP-8821",
  "skills": ["Python", "FastAPI"]
}
```

#### Request Fields

| Field               | Type                    | Required    | Notes                                                      |
| ------------------- | ----------------------- | ----------- | ---------------------------------------------------------- |
| `organization_name` | `string`                | ❌ Optional | Trimmed whitespace                                         |
| `role`              | `string`                | ❌ Optional | Trimmed whitespace                                         |
| `start_date`        | `string` (ISO 8601 UTC) | ❌ Optional |                                                            |
| `end_date`          | `string` (ISO 8601 UTC) | ❌ Optional | Set to `null` if ongoing                                   |
| `summary`           | `string`                | ❌ Optional |                                                            |
| `highlights`        | `array` of `string`     | ❌ Optional | **Replaces** existing highlights                           |
| `links`             | `array` of `string`     | ❌ Optional | **Replaces** existing links                                |
| `supervisor_ref`    | `string`                | ❌ Optional | Supervisor ledger ID or email                              |
| `skills`            | `array` of `string`     | ❌ Optional | **Replaces** all existing skill associations               |

**Response `200 OK`:** Returns the updated `EngagementResponse` object.

#### Possible Errors

| Status | `detail` value                                                                   | When it occurs                                       | Frontend action                                   |
| ------ | -------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------- |
| `400`  | `"Duplicate engagement: similar engagement already exists"`                       | Edited fields collide with another engagement        | Toast: "A similar engagement already exists"      |
| `401`  | `"Invalid authentication credentials"`                                            | Token missing, malformed, or expired                 | Clear token, redirect to login                    |
| `403`  | `"You don't have access to this engagement"`                                      | Student does not own this engagement                 | Show 403 page                                     |
| `403`  | `"Cannot update engagement. Verified engagements are immutable."`                 | Attempted to edit a `verified` engagement            | Disable edit UI for verified engagements          |
| `403`  | `"Cannot update engagement. Only draft or edit_requested engagements can be updated."` | Attempted to edit a `pending` or `rejected` engagement | Disable edit on non-editable statuses        |
| `404`  | `"Engagement not found"`                                                          | No engagement with that UUID                         | Show 404 page                                     |
| `422`  | `"Validation error"` + `errors[]`                                                 | Wrong field types                                    | Map `errors[].field` to form field messages       |

---

### `DELETE /engagements/:id`

Permanently delete an engagement. **Not** allowed if status is `verified` (verified records are immutable).

**Authentication:** Required — Bearer Token (`role = "student"` only)

**Path Parameter:**

| Parameter       | Type            | Description         |
| --------------- | --------------- | ------------------- |
| `engagement_id` | `string` (UUID) | The engagement UUID |

**Response `200 OK`:**

```json
{ "message": "Engagement deleted successfully" }
```

#### Possible Errors

| Status | `detail` value                                                    | When it occurs                                | Frontend action                            |
| ------ | ----------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------ |
| `401`  | `"Invalid authentication credentials"`                            | Token missing, malformed, or expired          | Clear token, redirect to login             |
| `403`  | `"You don't have access to this engagement"`                      | Student does not own this engagement          | Show 403 page                              |
| `403`  | `"Cannot delete engagement. Verified engagements are immutable."` | Attempted to delete a `verified` engagement   | Disable delete for verified engagements    |
| `404`  | `"Engagement not found"`                                          | No engagement with that UUID                  | Show 404 page                              |

---

### `POST /engagements/:id/submit`

Submit a `draft` engagement for supervisor verification. Transitions status `draft → pending`. The supervisor is resolved from `supervisor_ref` (ledger ID or email) and linked to the engagement at submit time.

**Authentication:** Required — Bearer Token (`role = "student"` only)

**Path Parameter:**

| Parameter       | Type            | Description         |
| --------------- | --------------- | ------------------- |
| `engagement_id` | `string` (UUID) | The engagement UUID |

**Request:** No body required.

**Response `200 OK`:** Returns the updated `EngagementResponse` with `status: "pending"` and `supervisor_profile_id` now populated.

#### Possible Errors

| Status | `detail` value                                                                        | When it occurs                                         | Frontend action                                  |
| ------ | ------------------------------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------ |
| `400`  | `"Cannot submit engagement with status '...'"` | Engagement is not in `draft` status                                  | Prevent submit button on non-draft engagements   |
| `400`  | `"Organization name, role, start date, and end date are required to submit"`          | Engagement has missing required fields                 | Prompt user to fill in missing fields            |
| `400`  | `"Supervisor reference is required to submit"`                                        | `supervisor_ref` is not set                            | Prompt user to add a supervisor reference        |
| `400`  | `"Invalid supervisor reference"`                                                      | `supervisor_ref` does not match any supervisor account | Toast: "Supervisor not found"                    |
| `401`  | `"Invalid authentication credentials"`                                                | Token missing, malformed, or expired                   | Clear token, redirect to login                   |
| `403`  | `"You don't have access to this engagement"`                                          | Student does not own this engagement                   | Show 403 page                                    |
| `404`  | `"Engagement not found"`                                                              | No engagement with that UUID                           | Show 404 page                                    |

---

## Routes — Supervisor Engagements (`/supervisor/engagements`)

> **Role guard:** All endpoints in this section require `role = "supervisor"`. A student token will receive `403 Forbidden`.

---

### `GET /supervisor/engagements/requests`

Get all engagements assigned to the current supervisor, optionally filtered by status.

**Authentication:** Required — Bearer Token (`role = "supervisor"` only)

**Query Parameters:**

| Parameter | Type     | Required    | Description                                                    |
| --------- | -------- | ----------- | -------------------------------------------------------------- |
| `status`  | `string` | ❌ Optional | Filter by status. Allowed: `all` · `pending` · `verified` · `rejected` · `edit_requested` |

**Response `200 OK`:** Returns an array of `EngagementListResponse` objects.

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "organization_name": "Acme Corp",
    "role": "Backend Engineer Intern",
    "start_date": "2025-06-01T00:00:00Z",
    "end_date": "2025-08-31T00:00:00Z",
    "status": "pending",
    "verified_at": null
  }
]
```

> **Note:** Returns an empty array `[]` if no engagements are assigned. Never returns `404`.

#### Possible Errors

| Status | `detail` value                                    | When it occurs                                | Frontend action                  |
| ------ | ------------------------------------------------- | --------------------------------------------- | -------------------------------- |
| `400`  | `"Invalid status. Allowed values: ..."`           | `status` query param not in allowed list      | Reset filter                     |
| `401`  | `"Invalid authentication credentials"`            | Token missing, malformed, or expired          | Clear token, redirect to login   |
| `403`  | `"Student access required"`                       | Student token used on supervisor route        | Redirect to correct dashboard    |

---

### `POST /engagements/:id/approve`

Approve an engagement and mark it as `verified`. Transitions `pending → verified`. Generates a `block_hash` as an immutable proof of verification and endorses all linked skills.

**Authentication:** Required — Bearer Token (`role = "supervisor"` only)

**Path Parameter:**

| Parameter       | Type            | Description         |
| --------------- | --------------- | ------------------- |
| `engagement_id` | `string` (UUID) | The engagement UUID |

**Request:** No body required.

**Response `200 OK`:** Returns the updated `EngagementResponse` with `status: "verified"`, `verified_at`, `block_hash`, and `verification_type` populated.

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "verified",
  "verified_at": "2025-09-02T14:22:00Z",
  "block_hash": "0xabcdef...1234",
  "verification_type": "institutional",
  "...": "..."
}
```

#### Side Effects on Approval

1. `status` set to `"verified"`
2. `verified_at` set to the current UTC timestamp
3. `block_hash` generated: `SHA-256(engagement_id:student_profile_id:supervisor_profile_id:verified_at)` — truncated to `0x{first6}...{last4}`
4. `verification_type` resolved: `"institutional"` if supervisor's email domain matches the organisation name, otherwise `"independent"`
5. All skills linked to this engagement are marked `is_verified = true`
6. `rejection_reason` cleared to `null`

#### Possible Errors

| Status | `detail` value                                                                                 | When it occurs                                  | Frontend action                              |
| ------ | ---------------------------------------------------------------------------------------------- | ----------------------------------------------- | -------------------------------------------- |
| `400`  | `"Cannot approve engagement with status '...'. Only pending engagements can be approved."`     | Engagement is not `pending`                     | Disable approve button on non-pending items  |
| `401`  | `"Invalid authentication credentials"`                                                          | Token missing, malformed, or expired            | Clear token, redirect to login               |
| `403`  | `"You are not assigned to this engagement"`                                                     | Supervisor is not the assigned reviewer         | Show 403 page                                |
| `404`  | `"Engagement not found"`                                                                        | No engagement with that UUID                    | Show 404 page                                |
| `404`  | `"Supervisor profile not found"`                                                                | DB integrity issue                              | Toast: "Profile error, contact support"      |

---

### `POST /engagements/:id/reject`

Reject an engagement with a required reason. Transitions `pending → rejected`.

**Authentication:** Required — Bearer Token (`role = "supervisor"` only)

**Path Parameter:**

| Parameter       | Type            | Description         |
| --------------- | --------------- | ------------------- |
| `engagement_id` | `string` (UUID) | The engagement UUID |

**Request Body:** `application/json`

```json
{ "reason": "The dates provided do not match our records." }
```

#### Request Fields

| Field    | Type     | Required | Notes                                          |
| -------- | -------- | -------- | ---------------------------------------------- |
| `reason` | `string` | ✅ Yes   | Human-readable rejection reason for the student |

**Response `200 OK`:** Returns the updated `EngagementResponse` with `status: "rejected"` and `rejection_reason` set.

#### Possible Errors

| Status | `detail` value                                                                                  | When it occurs                                  | Frontend action                              |
| ------ | ----------------------------------------------------------------------------------------------- | ----------------------------------------------- | -------------------------------------------- |
| `400`  | `"Cannot reject engagement with status '...'. Only pending engagements can be rejected."`       | Engagement is not `pending`                     | Disable reject button on non-pending items   |
| `401`  | `"Invalid authentication credentials"`                                                           | Token missing, malformed, or expired            | Clear token, redirect to login               |
| `403`  | `"You are not assigned to this engagement"`                                                      | Supervisor is not the assigned reviewer         | Show 403 page                                |
| `404`  | `"Engagement not found"`                                                                         | No engagement with that UUID                    | Show 404 page                                |
| `422`  | `"Validation error"` + `errors[]`                                                                | `reason` missing or wrong type                  | Require reason field before submission       |

---

### `POST /engagements/:id/request-edit`

Request changes from the student. Transitions `pending → edit_requested`. The student will see the attached reason and can update + resubmit.

**Authentication:** Required — Bearer Token (`role = "supervisor"` only)

**Path Parameter:**

| Parameter       | Type            | Description         |
| --------------- | --------------- | ------------------- |
| `engagement_id` | `string` (UUID) | The engagement UUID |

**Request Body:** `application/json`

```json
{ "reason": "Please add a more detailed summary of your responsibilities." }
```

#### Request Fields

| Field    | Type     | Required | Notes                                              |
| -------- | -------- | -------- | -------------------------------------------------- |
| `reason` | `string` | ✅ Yes   | Explanation of what the student needs to change    |

**Response `200 OK`:** Returns the updated `EngagementResponse` with `status: "edit_requested"` and `rejection_reason` set to the provided reason.

> **Note:** The `rejection_reason` field doubles as the edit-request message. Display it to the student as edit feedback, not a rejection.

#### Possible Errors

| Status | `detail` value                                                                                                    | When it occurs                                  | Frontend action                              |
| ------ | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | -------------------------------------------- |
| `400`  | `"Cannot request edits on engagement with status '...'. Only pending engagements can be requested for edits."`    | Engagement is not `pending`                     | Disable request-edit button on non-pending   |
| `401`  | `"Invalid authentication credentials"`                                                                             | Token missing, malformed, or expired            | Clear token, redirect to login               |
| `403`  | `"You are not assigned to this engagement"`                                                                        | Supervisor is not the assigned reviewer         | Show 403 page                                |
| `404`  | `"Engagement not found"`                                                                                           | No engagement with that UUID                    | Show 404 page                                |
| `422`  | `"Validation error"` + `errors[]`                                                                                  | `reason` missing or wrong type                  | Require reason field before submission       |

---

## Routes — Skills (`/skills`)

All routes in this section are prefixed with `/skills`.

---

### `GET /skills/search`

Search the global skill master table for autocomplete suggestions. This is an open endpoint (no authentication required) and returns up to 10 matching skills, sorted by exact match, prefix match, then substring match.

**Authentication:** None required

**Query Parameters:**

| Parameter | Type     | Required    | Description                                      |
| --------- | -------- | ----------- | ------------------------------------------------ |
| `q`       | `string` | ✅ Required | Search string (minimum 1 character required)     |

**Request:** No body required.

```http
GET /skills/search?q=react
```

**Response `200 OK`:**

```json
[
  {
    "id": "1a2b3c4d-...",
    "name": "React"
  },
  {
    "id": "5e6f7g8h-...",
    "name": "React Native"
  }
]
```

#### Response Fields (Array of objects)

| Field  | Type     | Description                             |
| ------ | -------- | --------------------------------------- |
| `id`   | `string` | UUID of the master skill                |
| `name` | `string` | The skill name (e.g. "React", "Python") |

#### Possible Errors

| Status | `detail` value                                    | When it occurs                    | Frontend action                  |
| ------ | ------------------------------------------------- | --------------------------------- | -------------------------------- |
| `422`  | `"Validation error"`                              | `q` parameter is missing or empty | Don't send empty search requests |

---

### `GET /skills`

Get all declared and verified skills for the currently authenticated user.

**Authentication:** Required — Bearer Token

**Request:** No body required.

```http
GET /skills
Authorization: Bearer <access_token>
```

**Response `200 OK`:**

```json
{
  "declared": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "react"
    }
  ],
  "verified": [
    {
      "name": "python",
      "count": 2
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `declared` | `array` | List of skills declared by the user but not yet verified |
| `verified` | `array` | List of verified skills and their occurrence counts |

#### Possible Errors

| Status | `detail` value | When it occurs | Frontend action |
| --- | --- | --- | --- |
| `401` | `"Invalid authentication credentials"` | Missing or invalid token | Redirect to login |

---

### `POST /skills`

Add one or multiple declared skills to the current user's profile. Up to 10 skills can be added at once. Duplicates (even different cases) are automatically skipped.

**Authentication:** Required — Bearer Token

**Request Body:** `application/json`

```json
{
  "skills": ["Python", "React", "Docker"]
}
```

#### Request Fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `skills` | `array` of `string` | ✅ Yes | 1 to 10 skill names. Length 1-100 characters per skill. |

**Response `201 Created`:**

```json
{
  "created": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "python"
    },
    {
      "id": "123e4567-e89b-12d3-a456-426614174001",
      "name": "docker"
    }
  ],
  "skipped": ["react"]
}
```

#### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `created` | `array` | Details of successfully added skills |
| `skipped` | `array` of `string` | Skills that were not added because they already exist |

#### Possible Errors

| Status | `detail` value | When it occurs | Frontend action |
| --- | --- | --- | --- |
| `400` | `"Student profile not found"` | Missing profile | Toast error |
| `401` | `"Invalid authentication credentials"` | Invalid token | Redirect to login |
| `422` | `"Validation error"` + `errors[]` | Array size > 10, empty skill string, etc. | Handle validation error |

---

### `DELETE /skills/{skill_id}`

Remove a declared skill from the user's profile. Note: Verified skills cannot be deleted.

**Authentication:** Required — Bearer Token

**Path Parameter:**

| Parameter | Type | Description |
| --- | --- | --- |
| `skill_id` | `string` (UUID) | The ID of the skill to delete |

**Request:** No body required.

**Response `200 OK`:**

```json
{
  "message": "Skill removed"
}
```

#### Possible Errors

| Status | `detail` value | When it occurs | Frontend action |
| --- | --- | --- | --- |
| `401` | `"Invalid authentication credentials"` | Invalid token | Redirect to login |
| `403` | `"Verified skills cannot be deleted"` | Attempting to delete a verified skill | Show error stating it can't be deleted |
| `404` | `"Skill not found"` | Skill doesn't exist or doesn't belong to the user | Treat as local state update anyway |

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

### `EngagementCreate` (sent to `POST /engagements`)

```typescript
{
  organization_name: string;
  role: string;
  start_date: string;                // ISO 8601 UTC
  end_date?: string | null;          // ISO 8601 UTC
  summary?: string | null;
  highlights?: string[] | null;
  links?: string[] | null;
  supervisor_ref?: string | null;    // supervisor ledger_id or email
  skills?: string[] | null;          // skill names
}
```

### `EngagementUpdate` (sent to `PUT /engagements/:id`)

```typescript
// All fields optional — send only what changes
{
  organization_name?: string;
  role?: string;
  start_date?: string;
  end_date?: string | null;
  summary?: string | null;
  highlights?: string[] | null;
  links?: string[] | null;
  supervisor_ref?: string | null;
  skills?: string[] | null;          // replaces all existing skill associations
}
```

### `EngagementResponse` (returned by all engagement detail endpoints)

```typescript
{
  id: string;                          // UUID
  student_profile_id: string;          // UUID
  supervisor_profile_id: string | null; // UUID — null until submitted
  supervisor_ref: string | null;       // ledger_id or email used at submit time
  organization_name: string;
  role: string;
  start_date: string;                  // ISO 8601 UTC
  end_date: string | null;             // ISO 8601 UTC
  summary: string | null;
  highlights: string[] | null;
  links: string[] | null;
  status: "draft" | "pending" | "verified" | "rejected" | "edit_requested";
  rejection_reason: string | null;     // set on reject or request-edit
  verified_at: string | null;          // ISO 8601 UTC — set on approve
  block_hash: string | null;           // e.g. "0xabcdef...1234" — set on approve
  verification_type: "institutional" | "independent" | null; // set on approve
  created_at: string;                  // ISO 8601 UTC
  updated_at: string;                  // ISO 8601 UTC
  skills: SkillResponse[];             // associated skills
}
```

### `EngagementListResponse` (returned by list endpoints)

```typescript
{
  id: string;                          // UUID
  organization_name: string;
  role: string;
  start_date: string;                  // ISO 8601 UTC
  end_date: string | null;             // ISO 8601 UTC
  status: "draft" | "pending" | "verified" | "rejected" | "edit_requested";
  verified_at: string | null;          // ISO 8601 UTC
}
```

### `RejectEngagementRequest` (sent to `POST /engagements/:id/reject`)

```typescript
{ reason: string; }
```

### `RequestEditEngagementRequest` (sent to `POST /engagements/:id/request-edit`)

```typescript
{ reason: string; }
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
