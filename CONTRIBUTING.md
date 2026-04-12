# Contributing to Provenancy Backend

## Team

| Member | Role | Repo |
|--------|------|------|
| Sumeet Rawat | Backend | Backend repo |
| Aman Verma | Database | Backend repo (DB layer) |
| Prashiv Goyal | Frontend | Frontend repo |

---

## How We Work

### Current Workflow
- Backend and frontend are in separate repositories
- All development happens on the `main` branch
- Pull before you start working — always
- Push only working, tested code
- Frontend pulls backend changes and integrates APIs

### Day-to-Day

```bash
# Before starting any work
git pull origin main

# After making changes
git add .
git commit -m "brief description of what you did"
git push origin main

# If there are conflicts
git pull origin main  # resolve conflicts first
git push origin main
```

---

## Commit Message Format

During development we kept commit messages simple and informal. Going forward, try to write something that briefly describes what changed — even a single sentence helps teammates understand the history.

```
# good enough
"added skill search endpoint"
"fixed cors issue"
"updated engagement routes"
"removed declared skills table"

# going forward (post-MVP ideal format)
feat: add skill search endpoint
fix: cors header issue on login
update: engagement status filter
```

---

## Environment Setup

Never commit `.env` — share credentials privately via WhatsApp or direct message.

If you add a new environment variable:
1. Add it to your local `.env`
2. Tell teammates to add it to their `.env`
3. Document it in `README.md`

---

## Before Pushing

Quick checklist before every push:

```
☐ Server starts without errors
☐ Endpoint you changed works in Postman or browser
☐ No hardcoded credentials or secrets in code
☐ .env is not staged (check with git status)
```

---

## Going Forward (Post-MVP)

Once the project scales, we plan to move to:

- Feature branches — `feature/feature-name`, `fix/bug-name`
- Pull requests before merging to main
- Code review by at least one other teammate
- Never push directly to main

---

## Questions

Reach out on WhatsApp group before making any breaking changes to shared APIs or DB schema.