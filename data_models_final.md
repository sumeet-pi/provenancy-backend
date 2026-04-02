# Provenancy — Data Models v2.0

> **Version:** 2.0.0 · **Stack:** FastAPI · PostgreSQL (Supabase) · SQLAlchemy · Pydantic

---

## What Changed from v1.0

| # | Problem in v1.0 | Fix in v2.0 |
|---|---|---|
| 1 | Verification was a field update on `engagements` | `verification_requests` is now a first-class workflow |
| 2 | `engagements` mixed context + content + verification | Split into `engagements` (context) + `engagement_records` (content) |
| 3 | `skills` was a flat counter (LinkedIn-level) | `engagement_skills` creates a real skill provenance graph |
| 4 | No trust classification for supervisors | `trust_tier` + `email_domain` on `supervisor_profiles` |
| 5 | No domain authentication enforcement | `verification_type` on `engagements` |
| 6 | Immutability mentioned but not enforced | `is_locked` on `engagement_records` |
| 7 | No audit history | `verification_logs` captures every state change |

---

## Architecture

### Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Primary Keys | **UUID** | Safe for public IDs; prevents enumeration attacks |
| Auth design | **Separate `users` table** | Auth data isolated from profile data |
| Profiles | **Separate `student_profiles` / `supervisor_profiles`** | Clean separation; no null-heavy fat table |
| Passwords | **bcrypt hash** | Plaintext never stored |
| Ledger IDs | **Auto-generated strings** | Human-readable IDs (`PRV-2026-XXXX`) for the UI |
| Verification | **First-class `verification_requests` table** | Makes verification an intentional, auditable workflow — not a field flip |
| Records | **`engagement_records` separate from `engagements`** | Enables versioning, draft → revision → final; separates identity from content |
| Skills | **Relational `engagement_skills`** | Real skill provenance graph; computable from verified engagements only |
| Trust | **`trust_tier` on supervisor profile** | Core credibility engine — institutional vs. independent authority |

### Table Hierarchy

```
users                                     ← Auth: email, password, role, ledger_id
├── student_profiles                      ← Student identity & bio (1-to-1)
│   ├── skills                            ← Skill definitions (1-to-many)
│   └── engagements                       ← Work context shell (1-to-many)
│       ├── engagement_records            ← Versioned content layer (1-to-many)
│       │   ├── engagement_highlights     ← Bullet points (1-to-many)
│       │   ├── engagement_evidence       ← Supporting docs/links (1-to-many)
│       │   └── engagement_skills         ← Skill usage (many-to-many bridge)
│       ├── verification_requests         ← Verification workflow (1-to-many)
│       └── verification_logs             ← Full audit trail (1-to-many)
│
└── supervisor_profiles                   ← Supervisor identity & trust (1-to-1)
    └── supervisor_domains                ← Verification domains (1-to-many)
```

---

## Tables

### `users`
> Central auth table. One row per registered account regardless of role.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | Internal primary key |
| `email` | `VARCHAR(255)` | UNIQUE · NOT NULL · indexed | Login identifier |
| `hashed_password` | `VARCHAR(255)` | NOT NULL | bcrypt hash — never returned in API responses |
| `role` | `ENUM` | NOT NULL | `student` or `supervisor` — set at signup, immutable |
| `ledger_id` | `VARCHAR(50)` | UNIQUE · NOT NULL | Auto-generated public ID (see Auto-generated Fields) |
| `is_active` | `BOOLEAN` | NOT NULL · default `true` | Soft-disable without deletion |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | Account creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL · auto-updated | Last modification timestamp |

---

### `student_profiles`
> Extended identity for students. Created automatically on signup.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | Internal primary key |
| `user_id` | `UUID` | FK → `users.id` · UNIQUE · NOT NULL | One-to-one link to auth user |
| `full_name` | `VARCHAR(255)` | NOT NULL | Pre-filled from signup; editable in Profile page |
| `title` | `VARCHAR(255)` | nullable | e.g. "Graduate Research Assistant" |
| `bio` | `TEXT` | nullable | Professional / academic summary |
| `linkedin_url` | `VARCHAR(512)` | nullable | Public LinkedIn URL |
| `institution` | `VARCHAR(255)` | nullable | Shown as "Linked Oracle" on public profile |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL · auto-updated | |

---

### `supervisor_profiles`
> Extended identity for supervisors. Includes trust classification for the credibility engine.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | Internal primary key |
| `user_id` | `UUID` | FK → `users.id` · UNIQUE · NOT NULL | One-to-one link to auth user |
| `full_name` | `VARCHAR(255)` | NOT NULL | Pre-filled from signup; editable in Profile page |
| `designation` | `VARCHAR(255)` | nullable | e.g. "Dean of Students", "Senior Research Lead" |
| `organization` | `VARCHAR(255)` | nullable | e.g. "Stanford University" |
| `bio` | `TEXT` | nullable | Administrative / academic background |
| `linkedin_url` | `VARCHAR(512)` | nullable | Public LinkedIn URL |
| `email_domain` | `VARCHAR(255)` | nullable | Extracted from signup email e.g. `stanford.edu` |
| `trust_tier` | `ENUM` | NOT NULL · default `'independent'` | `institutional` or `independent` (see logic below) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL · auto-updated | |

> [!NOTE]
> **Trust Tier Logic:** If the supervisor's email domain matches `organization` (e.g. `jvance@stanford.edu` → `stanford.edu` matches `Stanford University`), `trust_tier` is set to `institutional`. Otherwise it defaults to `independent`. This is the foundation of the credibility engine.

---

### `skills`
> Skill definitions owned by a student. Endorsement count is computed from verified engagements.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | |
| `student_profile_id` | `UUID` | FK → `student_profiles.id` · NOT NULL · indexed | Owning student |
| `name` | `VARCHAR(100)` | NOT NULL | e.g. "Python", "Machine Learning" |
| `endorsement_count` | `INTEGER` | NOT NULL · default `0` | Count of verified engagements that used this skill via `engagement_skills` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |

> [!NOTE]
> `endorsement_count` is not manually set — it is derived by counting rows in `engagement_skills` where the linked `engagement_record` belongs to a `verified` verification request. Updated via app logic on each verification approval.

---

### `supervisor_domains`
> Areas of expertise a supervisor is authorized to verify engagements in.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | |
| `supervisor_profile_id` | `UUID` | FK → `supervisor_profiles.id` · NOT NULL · indexed | Owning supervisor |
| `name` | `VARCHAR(100)` | NOT NULL | e.g. "Computer Science", "Quantum Physics" |
| `verification_count` | `INTEGER` | NOT NULL · default `0` | Total approved verification requests in this domain |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |

---

### `engagements`
> The context shell of a work experience. Holds identity and metadata. Does NOT hold content — that lives in `engagement_records`.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | |
| `student_profile_id` | `UUID` | FK → `student_profiles.id` · NOT NULL · indexed | The student who owns this shell |
| `supervisor_profile_id` | `UUID` | FK → `supervisor_profiles.id` · nullable · indexed | Resolved after supervisor lookup |
| `supervisor_ref` | `VARCHAR(255)` | nullable | Raw input (email or ledger_id) before resolution |
| `organization_name` | `VARCHAR(255)` | NOT NULL | e.g. "Node.js Foundation" |
| `role` | `VARCHAR(255)` | NOT NULL | e.g. "Open Source Contributor" |
| `start_date` | `DATE` | NOT NULL | |
| `end_date` | `DATE` | nullable | `null` = ongoing |
| `verification_type` | `ENUM` | nullable | `institutional` or `independent` — mirrors supervisor's trust tier at time of submission |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL · auto-updated | |

> [!NOTE]
> `verification_type` is snapshotted from `supervisor_profiles.trust_tier` at the moment the verification request is created. This prevents retroactive trust reclassification from affecting existing records.

---

### `engagement_records`
> The versioned content layer of an engagement. A new record is created on each revision attempt. Only one record per engagement can ever be `is_locked = true`.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | |
| `engagement_id` | `UUID` | FK → `engagements.id` · NOT NULL · indexed | Owning engagement shell |
| `version` | `SMALLINT` | NOT NULL · default `1` | Incremented on each revision |
| `summary` | `TEXT` | nullable | Comprehensive work description |
| `status` | `ENUM` | NOT NULL · default `'draft'` | `draft` · `submitted` · `approved` · `rejected` |
| `block_hash` | `VARCHAR(255)` | nullable | Set upon supervisor approval |
| `verified_at` | `TIMESTAMPTZ` | nullable | Timestamp of approval |
| `is_locked` | `BOOLEAN` | NOT NULL · default `false` | `true` = immutable; no updates permitted |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |

> [!IMPORTANT]
> Once `is_locked = true`, the application layer must reject all PATCH/PUT attempts on this record. This is the DB-level immutability enforcement.

#### Record Status Lifecycle

```
draft ──► submitted ──► approved (is_locked = true, block_hash set)
              │
              └──► rejected ──► [student creates new record, version++)
                                     │
                                     └──► submitted ──► ...
```

---

### `engagement_highlights`
> Key performance bullet points attached to a specific `engagement_record` version.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | |
| `engagement_record_id` | `UUID` | FK → `engagement_records.id` · NOT NULL · indexed | Owning record version |
| `text` | `VARCHAR(500)` | NOT NULL | The bullet point text |
| `order` | `SMALLINT` | NOT NULL · default `0` | Display order (0, 1, 2…) |

---

### `engagement_evidence`
> Supporting documents or URLs attached to a specific `engagement_record` version.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | |
| `engagement_record_id` | `UUID` | FK → `engagement_records.id` · NOT NULL · indexed | Owning record version |
| `label` | `VARCHAR(255)` | NOT NULL | Display name e.g. "Project Portfolio Repository" |
| `url` | `VARCHAR(2048)` | NOT NULL | External link or file reference |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |

---

### `engagement_skills`
> Many-to-many bridge between `engagement_records` and `skills`. This is the skill provenance graph.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | |
| `engagement_record_id` | `UUID` | FK → `engagement_records.id` · NOT NULL · indexed | The record version this skill was applied in |
| `skill_id` | `UUID` | FK → `skills.id` · NOT NULL · indexed | The skill being referenced |

> [!NOTE]
> **Why this matters:** Verified skill count = `COUNT(engagement_skills JOIN engagement_records WHERE is_locked = true)`. This is computed provenance, not a manually entered number. It powers the trust score on the public student profile.

---

### `verification_requests`
> First-class verification workflow. A new request is created each time a student submits an engagement record for supervisor review. Supports revisions, rejections, and audit trails.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | |
| `engagement_id` | `UUID` | FK → `engagements.id` · NOT NULL · indexed | The engagement being reviewed |
| `engagement_record_id` | `UUID` | FK → `engagement_records.id` · NOT NULL | The specific version submitted |
| `supervisor_profile_id` | `UUID` | FK → `supervisor_profiles.id` · NOT NULL · indexed | The supervisor receiving the request |
| `status` | `ENUM` | NOT NULL · default `'pending'` | `pending` · `approved` · `rejected` · `revision_requested` |
| `feedback` | `TEXT` | nullable | Supervisor notes — shown to student on rejection |
| `requested_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | When the student submitted |
| `reviewed_at` | `TIMESTAMPTZ` | nullable | When the supervisor acted |

#### Verification Request Lifecycle

```
[Student submits engagement_record]
              │
              ▼
    verification_request created (status: pending)
              │
    ┌─────────┼──────────────────┐
    ▼         ▼                  ▼
approved  rejected       revision_requested
    │         │                  │
    │    [no action]    [student edits, new
    │                    record version +
    │                    new request created]
    ▼
engagement_record.is_locked = true
block_hash generated
```

---

### `verification_logs`
> Immutable audit trail. Every state change across the verification lifecycle is recorded here.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | PK, default `uuid4()` | |
| `engagement_id` | `UUID` | FK → `engagements.id` · NOT NULL · indexed | The engagement this log belongs to |
| `actor_id` | `UUID` | FK → `users.id` · NOT NULL | Who performed the action (student or supervisor) |
| `action` | `ENUM` | NOT NULL | `submitted` · `approved` · `rejected` · `revision_requested` · `record_locked` |
| `note` | `TEXT` | nullable | Optional context (e.g. rejection reason snapshot) |
| `timestamp` | `TIMESTAMPTZ` | NOT NULL · default `now()` | When the action occurred |

> [!NOTE]
> Logs are **append-only**. No updates or deletes are permitted on this table. It is the ground truth for dispute resolution.

---

## Full Relationships Diagram

```
users (1) ─────────────────────────────── (1) student_profiles
                                                    │
                              ┌─────────────────────┼──────────────┐
                             (N)                   (N)
                           skills             engagements
                              ▲                    │
                              │         ┌──────────┼──────────────┐
                              │        (N)         │             (N)
                              │  engagement_records │    verification_requests
                              │        │            │
                              │   ┌────┼────┐       │
                              │  (N)  (N)  (N)      │
                              │  highlights evidence engagement_skills
                              │                         │
                              └─────────────────────────┘
                                (many engagement_records reference many skills)

              verification_logs ── (N) → engagements

users (1) ─────────────────────────────── (1) supervisor_profiles
                                                    │
                                                   (N)
                                          supervisor_domains

engagements.supervisor_profile_id ────────────── supervisor_profiles.id
verification_requests.supervisor_profile_id ──── supervisor_profiles.id
```

---

## Enum Definitions

### `UserRole`
| Value | Description |
|---|---|
| `student` | A candidate who submits engagement records |
| `supervisor` | An institutional authority who verifies records |

### `SupervisorTrustTier`
| Value | When Applied | Weight |
|---|---|---|
| `institutional` | Email domain matches organization domain | Higher credibility score |
| `independent` | Email domain does not match organization | Standard credibility score |

### `EngagementRecordStatus`
| Value | Description |
|---|---|
| `draft` | Created but not yet submitted |
| `submitted` | Under active review via a `verification_request` |
| `approved` | Supervisor approved; `is_locked = true`, `block_hash` set |
| `rejected` | Supervisor declined this version |

### `VerificationRequestStatus`
| Value | Description |
|---|---|
| `pending` | Awaiting supervisor action |
| `approved` | Supervisor accepted; triggers record locking |
| `rejected` | Supervisor declined with optional feedback |
| `revision_requested` | Supervisor flagged for revision before re-submission |

### `VerificationAction` (Logs)
| Value | Description |
|---|---|
| `submitted` | Student submitted an engagement record |
| `approved` | Supervisor approved the record |
| `rejected` | Supervisor rejected the record |
| `revision_requested` | Supervisor requested changes |
| `record_locked` | System locked the record after approval |

### `VerificationType`
| Value | Description |
|---|---|
| `institutional` | Verified by an institutional-tier supervisor |
| `independent` | Verified by an independent-tier supervisor |

---

## Auto-generated Fields

### Ledger IDs

| Role | Format | Example |
|---|---|---|
| Student | `PRV-{YEAR}-{4-digit padded sequence}` | `PRV-2026-0089` |
| Supervisor | `PRV-SUP-{4-digit random}` | `PRV-SUP-8821` |

```python
from datetime import datetime
import random, string

def generate_student_ledger_id(sequence: int) -> str:
    year = datetime.utcnow().year
    return f"PRV-{year}-{str(sequence).zfill(4)}"

def generate_supervisor_ledger_id() -> str:
    suffix = ''.join(random.choices(string.digits, k=4))
    return f"PRV-SUP-{suffix}"
```

### Block Hash (on Engagement Approval)

```python
import hashlib

def generate_block_hash(engagement_id: str, supervisor_id: str, timestamp: str) -> str:
    payload = f"{engagement_id}:{supervisor_id}:{timestamp}"
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return f"0x{digest[:6]}...{digest[-4:]}"
```

### Trust Tier Resolution (on Supervisor Signup)

```python
def resolve_trust_tier(email: str, organization: str) -> str:
    domain = email.split("@")[-1].lower()           # e.g. "stanford.edu"
    org_slug = organization.lower().replace(" ", "")  # e.g. "stanforduniversity"
    if domain.split(".")[0] in org_slug:
        return "institutional"
    return "independent"
```

---

## Auth API Surface (Phase 1)

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/signup` | Create user + auto-create role profile; returns JWT |
| `POST` | `/auth/login` | Verify credentials; returns JWT |
| `GET` | `/auth/me` | Return current user info decoded from JWT |

### Signup Request
```json
{
  "full_name": "Alex Carter",
  "email": "alex@university.edu",
  "password": "securepassword",
  "role": "student"
}
```

### Login Request
```json
{
  "email": "alex@university.edu",
  "password": "securepassword"
}
```

### Token Response
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "role": "student",
  "ledger_id": "PRV-2026-0089"
}
```

> [!IMPORTANT]
> `role` and `ledger_id` are included in the token response so the frontend can immediately redirect to the correct dashboard without a separate `/me` call.
