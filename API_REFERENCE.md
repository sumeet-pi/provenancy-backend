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

## Engagements `/engagements`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/engagements` | Student creates engagement |
| GET | `/engagements` | Student's all engagements `?status=all/verified/pending` |
| GET | `/engagements/:id` | Single engagement detail (student + supervisor) |
| PUT | `/engagements/:id` | Edit engagement (pending/draft only) |
| DELETE | `/engagements/:id` | Delete engagement (unverified only) |
| POST | `/engagements/:id/approve` | Supervisor approves + signs |
| POST | `/engagements/:id/reject` | Supervisor rejects with reason |
| POST | `/engagements/:id/request-edit` | Supervisor requests changes |
| GET | `/engagements/supervisor/requests` | Supervisor's verification queue `?status=pending` |

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
| DELETE | `/skills/:id` | Remove declared skill only |
| GET | `/skills/public/:user_id` | Public skills for student profile |

> Skills shift from **declared → verified** automatically when a supervisor approves an engagement that tags them.

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
| `users` | id, name, email, hashed_password, role |
| `student_profiles` | user_id (FK), title, bio, linkedin_url, ledger_id |
| `supervisor_profiles` | user_id (FK), designation, org, bio, admin_id, domains |
| `engagements` | id, student_id, supervisor_id, org, role, status, ref_id |
| `skills` | id, user_id, name, type (declared/verified), verification_count |
| `engagement_skills` | engagement_id (FK), skill_id (FK) |

---

**Total: 26 endpoints**  
Build order: Auth → Profiles → Engagements → Skills → Dashboard