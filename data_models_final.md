# Provenancy — Data Models

> **Version:** 3.0.0 · **Stack:** FastAPI · PostgreSQL (Supabase) · SQLAlchemy · Pydantic

---

## Architecture

### Design Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Primary Keys | **UUID** | Safe for public IDs; prevents enumeration attacks |
| Auth design | **Separate `users` table** | Auth data isolated from profile data |
| Profiles | **Separate `student_profiles` / `supervisor_profiles`** | Clean separation; no null-heavy fat table |
| Passwords | **bcrypt hash** | Plaintext never stored |
| Ledger IDs | **Auto-generated strings** | Human-readable IDs (`PRV-2026-XXXX`) for the UI |
| Engagements | **Single flat table** | All context, content, and status in one place; matches API behavior |
| Skills | **Relational `engagement_skills`** | Skill provenance graph; endorsement count computed from verified engagements |
| Trust | **`trust_tier` on supervisor profile** | Credibility engine — institutional vs. independent authority |

### Table Hierarchy

```text
users                              ← Auth: email, password, role, ledger_id
├── student_profiles               ← Student identity & bio (1-to-1)
│   └── skills                     ← Per-student owned skills (1-to-many)
│   └── engagements                ← Work records (1-to-many)
│       └── engagement_skills      ← Skill usage bridge (many-to-many)
│
└── supervisor_profiles            ← Supervisor identity & trust (1-to-1)
    └── supervisor_domains         ← Verification domains (1-to-many)
```

---

## Tables

### `users`

> Central auth table. One row per registered account regardless of role.

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
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
| --- | --- | --- | --- |
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
| --- | --- | --- | --- |
| `id` | `UUID` | PK, default `uuid4()` | Internal primary key |
| `user_id` | `UUID` | FK → `users.id` · UNIQUE · NOT NULL | One-to-one link to auth user |
| `full_name` | `VARCHAR(255)` | NOT NULL | Pre-filled from signup; editable in Profile page |
| `designation` | `VARCHAR(255)` | nullable | e.g. "Dean of Students", "Senior Research Lead" |
| `organization` | `VARCHAR(255)` | nullable | e.g. "Stanford University" |
| `bio` | `TEXT` | nullable | Administrative / academic background |
| `linkedin_url` | `VARCHAR(512)` | nullable | Public LinkedIn URL |
| `email_domain` | `VARCHAR(255)` | nullable | Extracted from signup email e.g. `stanford.edu` |
| `trust_tier` | `ENUM` | NOT NULL · default `'independent'` | `institutional` or `independent` (see Trust Tier Logic) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL · auto-updated | |

> [!NOTE]
> **Trust Tier Logic:** If the supervisor's email domain matches the organization (e.g. `jvance@stanford.edu` → `stanford.edu` matches `Stanford University`), `trust_tier` is set to `institutional`. Otherwise defaults to `independent`.

---

### `supervisor_domains`

> Areas of expertise a supervisor is authorized to verify engagements in.

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | `UUID` | PK, default `uuid4()` | |
| `supervisor_profile_id` | `UUID` | FK → `supervisor_profiles.id` · NOT NULL · indexed | Owning supervisor |
| `name` | `VARCHAR(100)` | NOT NULL | e.g. "Computer Science", "Quantum Physics" |
| `verification_count` | `INTEGER` | NOT NULL · default `0` | Total approved engagements in this domain |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |

---

### `engagements`

> Complete record of a student's professional or academic experience. Holds all context, content, and verification state in a single row.

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | `UUID` | PK, default `uuid4()` | |
| `student_profile_id` | `UUID` | FK → `student_profiles.id` · NOT NULL · indexed | The student who owns this record |
| `supervisor_profile_id` | `UUID` | FK → `supervisor_profiles.id` · nullable · indexed | Resolved after supervisor lookup |
| `supervisor_ref` | `VARCHAR(255)` | nullable | Raw input from student (email or ledger_id) before resolution |
| `organization_name` | `VARCHAR(255)` | NOT NULL | e.g. "Node.js Foundation" |
| `role` | `VARCHAR(255)` | NOT NULL | e.g. "Open Source Contributor" |
| `start_date` | `DATE` | NOT NULL | |
| `end_date` | `DATE` | nullable | `null` = ongoing |
| `summary` | `TEXT` | nullable | Free-text description of the work |
| `highlights` | `JSON` | nullable | Array of key performance bullet points |
| `links` | `JSON` | nullable | Array of supporting URLs / evidence links |
| `status` | `ENUM` | NOT NULL · default `'draft'` | `draft` · `pending` · `verified` · `rejected` · `edit_requested` |
| `rejection_reason` | `TEXT` | nullable | Populated when status is `rejected` or `edit_requested` |
| `verification_type` | `ENUM` | nullable | `institutional` or `independent` — snapshotted from supervisor trust tier at submission |
| `block_hash` | `VARCHAR(255)` | nullable | Set upon supervisor approval |
| `verified_at` | `TIMESTAMPTZ` | nullable | Timestamp of supervisor approval |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL · auto-updated | |

#### Status Flow

```text
draft → pending → verified
                ↘ rejected
                ↘ edit_requested → pending (on student resubmit)
```

> [!IMPORTANT]
> **Immutability Rule:** Once `engagement.status = 'verified'`, the following fields become read-only and must be rejected by the application layer on any PUT/PATCH attempt:
>
> - `summary`
> - `highlights`
> - `links`
> - skills linked via `engagement_skills`
>
> `verification_type` is snapshotted at submission time and cannot be retroactively changed by reclassifying the supervisor.

---

### `skills`

> Per-student skill registry. Each skill is owned by a specific student.

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | `UUID` | PK, default `uuid4()` | |
| `student_profile_id` | `UUID` | FK → `student_profiles.id` · NOT NULL · indexed | Owning student |
| `name` | `VARCHAR(100)` | NOT NULL | e.g. "Python", "Machine Learning" |
| `endorsement_count` | `INTEGER` | NOT NULL · default `0` | Incremented when a linked engagement transitions to `verified` |
| `created_at` | `TIMESTAMPTZ` | NOT NULL · default `now()` | |

**Unique constraint:** `(student_profile_id, name)` — same student cannot declare the same skill twice.

**Verified vs. Declared:**
- `endorsement_count = 0` → skill is **declared** (added to profile but not yet verified by any engagement)
- `endorsement_count >= 1` → skill is **verified** (at least one engagement using this skill is verified)

`endorsement_count` increments via app logic each time an engagement referencing this skill via `engagement_skills` moves to `status = 'verified'`.

---

### `engagement_skills`

> Many-to-many bridge between `engagements` and `skills`. This is the skill provenance graph.

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | `UUID` | PK, default `uuid4()` | |
| `engagement_id` | `UUID` | FK → `engagements.id` · NOT NULL · indexed | The engagement this skill was applied in |
| `skill_id` | `UUID` | FK → `skills.id` · NOT NULL · indexed | The skill being referenced |

> [!NOTE]
> **Verified skill count** = `COUNT(skills WHERE endorsement_count >= 1)` — a skill is verified when at least one engagement referencing it is verified.
>
> **Declared skill count** = `COUNT(skills WHERE endorsement_count = 0)` — a skill is declared but not yet verified.

---

## Relationships

```text
users (1) ──────────────── (1) student_profiles
                                    │
                     ┌──────────────┴──────────────┐
                    (N)                        (N)
               skills                    engagements
                    │                         (N)
                    │                 engagement_skills
                    └──────────┬──────────────────┘
                              (N)
                        [via engagement_skills]

users (1) ──────────────── (1) supervisor_profiles
                                    │
                                   (N)
                           supervisor_domains

engagements.supervisor_profile_id ──── supervisor_profiles.id
```

---

## Enum Definitions

### `UserRole`

| Value | Description |
| --- | --- |
| `student` | A candidate who submits engagement records |
| `supervisor` | An institutional authority who verifies records |

### `SupervisorTrustTier`

| Value | When Applied | Effect |
| --- | --- | --- |
| `institutional` | Email domain matches organization domain | Higher credibility weight on verified engagements |
| `independent` | Email domain does not match organization | Standard credibility weight |

### `EngagementStatus`

| Value | Description |
| --- | --- |
| `draft` | Created by student, not yet submitted for verification |
| `pending` | Submitted to supervisor, awaiting action |
| `verified` | Supervisor approved; record is immutable, `block_hash` set |
| `rejected` | Supervisor declined; student cannot resubmit this engagement |
| `edit_requested` | Supervisor flagged for changes; student can edit and resubmit |

### `VerificationType`

| Value | Description |
| --- | --- |
| `institutional` | Verified by an institutional-tier supervisor |
| `independent` | Verified by an independent-tier supervisor |

---

## Auto-generated Fields

### Ledger IDs

| Role | Format | Example |
| --- | --- | --- |
| Student | `PRV-{YEAR}-{4-digit padded sequence}` | `PRV-2026-0089` |
| Supervisor | `PRV-SUP-{4-digit random}` | `PRV-SUP-8821` |

```python
from datetime import datetime
import random

def generate_student_ledger_id(sequence: int) -> str:
    year = datetime.utcnow().year
    return f"PRV-{year}-{str(sequence).zfill(4)}"

def generate_supervisor_ledger_id() -> str:
    suffix = str(random.randint(0, 9999)).zfill(4)
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
import re

def resolve_trust_tier(email: str, organization: str) -> str:
    domain = email.split("@")[-1].lower()
    org_normalized = re.sub(
        r"(university|college|institute|school|ltd|inc|corp)$",
        "",
        organization.lower().strip()
    ).strip()
    if domain and (domain in org_normalized or org_normalized in domain):
        return "institutional"
    return "independent"
```

---

## Auth API Surface

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/auth/signup` | Create user + auto-create role profile; returns JWT |
| `POST` | `/auth/login` | Verify credentials; returns JWT |
| `GET` | `/auth/me` | Return current user + profile from JWT |

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
