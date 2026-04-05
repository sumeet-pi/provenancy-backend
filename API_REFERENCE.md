# Provenancy — API Reference

**Base URL:** `http://localhost:8000`  
**Auth:** HTTP-only cookie or `Authorization: Bearer <token>`  
**Stack:** FastAPI + PostgreSQL (Supabase)

---

## Auth `/auth`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register — `name, email, password, role` |
| POST | `/auth/login` | Login — `email, password` → token |
| GET | `/auth/me` | Get current user from token |
| POST | `/auth/logout` | Clear session cookie |
| PUT | `/auth/complete-profile` | Fill bio, title, linkedin after signup |

---

## Student Profile `/student`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/student/me` | Own full profile (private) |
| PUT | `/student/me` | Update name, title, bio, linkedin |
| GET | `/student/:id/public` | Public profile — engagements, skills, trust score |

---

## Supervisor Profile `/supervisor`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/supervisor/me` | Own full profile (private) |
| PUT | `/supervisor/me` | Update name, designation, org, bio, domains |
| GET | `/supervisor/:id/public` | Public supervisor profile |

---

## Student Engagements `/engagements`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/engagements` | Student creates engagement |
| GET | `/engagements?status=` | Student's engagements — filter by status |
| GET | `/engagements/:id` | Single engagement detail (student + supervisor shared) |
| PUT | `/engagements/:id` | Edit engagement (draft/pending/edit_requested only) |
| DELETE | `/engagements/:id` | Delete engagement (unverified only) |

**Student status filters:** `all · draft · pending · verified · rejected · edit_requested`

---

## Supervisor Engagements `/supervisor/engagements`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/supervisor/engagements/requests?status=` | Supervisor's verification queue — filter by status |
| POST | `/engagements/:id/approve` | Approve + sign engagement |
| POST | `/engagements/:id/reject` | Reject with reason |
| POST | `/engagements/:id/request-edit` | Request changes from student |

**Supervisor status filters:** `all · pending · verified · rejected · edit_requested`

> `GET /engagements/:id` is shared — both student and supervisor can view a single engagement detail. Response includes supervisor action buttons based on role from JWT.

**Status flow:**
```
draft → pending → verified
               ↘ rejected
               ↘ edit_requested → pending (on resubmit)
```

---

## Skills `/skills`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/skills` | Own skills — verified + declared |
| POST | `/skills` | Add declared skill `{ name }` |
| DELETE | `/skills/:id` | Remove declared skill only (endorsement_count = 0) |

> Skills are **per student** — each skill row is owned by a `student_profile_id`.  
> A skill is **declared** when `endorsement_count = 0` and **verified** when `endorsement_count >= 1`.  
> `endorsement_count` increments automatically when a supervisor approves an engagement that tags that skill. Cannot be manually set.  
> Verified skills are immutable — they cannot be deleted.  
> Public skills are returned as part of `GET /student/:id/public` — no separate public skills endpoint needed.

---

## Dashboard `/dashboard`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard/student` | Stats + recent engagements + top skills |
| GET | `/dashboard/supervisor` | Stats + pending queue + activity feed |

---

## DB Tables

| Table | Key Fields |
|-------|------------|
| `users` | id, email, hashed_password, role, ledger_id |
| `student_profiles` | user_id (FK), full_name, title, bio, linkedin_url, institution |
| `supervisor_profiles` | user_id (FK), full_name, designation, org, bio, email_domain, trust_tier |
| `engagements` | id, student_profile_id (FK), supervisor_profile_id (FK), org, role, status, block_hash, verified_at |
| `skills` | id, student_profile_id (FK), name, endorsement_count |
| `engagement_skills` | engagement_id (FK), skill_id (FK) |

---

**Total: 25 endpoints**  
Build order: Skills → Engagements → Dashboard