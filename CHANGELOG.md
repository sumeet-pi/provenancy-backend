# Changelog

All notable changes to the Provenancy backend are documented here.

---

## [1.0.0] — April 2026

First complete release of the Provenancy backend. Built from scratch over the course of the project by a 3-member team.

### Infrastructure
- FastAPI server with SQLAlchemy ORM
- PostgreSQL database hosted on Supabase
- Connection via Supabase pooler URL for campus network compatibility
- Deployed on Render

### Authentication
- User registration with role selection (student / supervisor)
- JWT-based authentication with HTTP-only cookie support
- Password hashing with passlib + bcrypt
- Token expiry set to 7 days (10080 minutes)
- `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/complete-profile`

### Student Profile
- Per-student profile with name, title, bio, linkedin, institution
- Auto-generated ledger ID on signup (`PRV-YYYY-XXXX` format)
- Private profile endpoint and public profile endpoint
- `/student/me`, `/student/:id/public`

### Supervisor Profile
- Per-supervisor profile with designation, organization, bio, domains
- Trust tier system — institutional vs independent based on email domain
- Auto-generated admin ID (`PRV-SUP-XXXX` format)
- `/supervisor/me`, `/supervisor/:id/public`

### Engagements
- Full engagement lifecycle — draft → pending → verified / rejected / edit_requested
- Student creates engagements and assigns to supervisor via email
- Supervisor can approve, reject, or request edits
- Block hash generated on approval for immutability
- Status filtering for both student and supervisor views
- Student routes: `POST /engagements`, `GET /engagements?status=`, `GET /engagements/:id`, `PUT /engagements/:id`, `DELETE /engagements/:id`
- Supervisor routes: `GET /supervisor/engagements/requests?status=`, `POST /engagements/:id/approve`, `POST /engagements/:id/reject`, `POST /engagements/:id/request-edit`

### Skills
- Per-student skill system with declared and verified states
- Skill shifts from declared → verified when endorsement_count >= 1
- Endorsement count increments automatically on engagement approval
- Verified skills are immutable — cannot be deleted
- `GET /skills`, `POST /skills`, `DELETE /skills/:id`

### Skill Master
- Global searchable skill database seeded from two sources:
  - O*NET Technology Skills dataset (8,824 unique skills)
  - Programming languages and frameworks dataset (4,371 skills)
  - Combined and deduplicated to ~12,000+ unique skills
- Case-insensitive search with priority ordering (exact → prefix → contains)
- Special character support (C++, C#) via URL encoding
- `GET /skills/search?q=`

### Dashboard
- Aggregated stats endpoint for student dashboard
- Aggregated stats endpoint for supervisor dashboard
- `GET /dashboard/student`, `GET /dashboard/supervisor`

### Security
- CORS configured via environment variable
- All secrets in `.env`, never hardcoded
- SSL required on database connection
- Input validation via Pydantic schemas
- Global exception handler for unhandled errors

---

## What's Next (Planned)

- Refresh token support for silent session renewal
- Email notifications when supervisor approves/rejects
- Pagination on all list endpoints
- Rate limiting on auth endpoints
- Admin role and admin dashboard
- Blockchain-backed verification (future scope)