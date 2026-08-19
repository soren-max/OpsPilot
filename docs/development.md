# Development

## Prerequisites

- Git
- Python 3.13 (current verified runtime)
- uv
- Node.js 22+ and npm
- Docker and Ansible only for optional integration work

## Environment Setup

```bash
git clone https://github.com/soren-max/OpsPilot.git
cd OpsPilot
cp .env.example .env
uv sync --project backend --extra dev
cd frontend && npm ci
```

Replace all `.env` placeholders locally. Never commit `.env` or credentials.

## Backend

```bash
uv run --project backend uvicorn app.main:app --reload --app-dir backend
```

## Frontend

```bash
cd frontend
npm run dev
```

## Database

SQLite is the development default. Apply migrations from `backend`:

```bash
uv run --project backend alembic -c backend/alembic.ini upgrade head
```

## Testing, Linting, and Type Checking

```bash
uv run --project backend pytest backend/tests
uv run --project backend ruff check backend/app backend/tests
uv run --project backend mypy backend/app

cd frontend
npm test
npm run lint
npm run typecheck
npm run build
```

Run `python scripts/check-secrets.py` from the repository root before every public PR.

## Branch Workflow

Update `main` with `git pull --ff-only`, then create a focused branch. Do not develop or force
push on `main`.

## Commit Convention

Use Conventional Commits and keep each commit reviewable: `feat:`, `fix:`, `refactor:`, `test:`,
`docs:`, `ci:`, `chore:`, or `build:`. Do not use WIP commits in a review-ready branch.

## PR Process

Open a Draft PR, complete the template, wait for all required CI jobs, review the full diff and
commit history, and only then mark it ready. Project owners decide when and how to merge.
