# Scrappy

Desktop web app where users keep a pantry of ingredients (typed in by hand) and see
recipes ranked by how many of each recipe's ingredients they already have. 

## Source of truth

- The full spec is `docs/requirements.md`. It is not auto-loaded: read the relevant
  section before starting any task. Feature specs are in section 10, the API in 11,
  the data model in 12, configuration in 13, cost rules in 14, milestones in 15.
- Scope is the MVP only. Post-MVP items (spec section 3.2 and Appendix A) are out of
  scope unless the developer explicitly asks.
- If the spec and reality conflict, stop and propose a spec change. Don't silently diverge.

## Working with the developer

- The developer is learning AWS, Terraform, CI/CD, and FastAPI. After each change,
  explain briefly and in plain language what it does and why.
- Work one user story or milestone task at a time. For anything touching more than a
  few files, propose a short plan first.
- Call out every manual step (AWS console, secrets, `aws ssm put-parameter`, GitHub
  settings) as an explicit numbered instruction.
- Ask before: adding a dependency, creating or changing any AWS resource, changing the
  API contract or data model, or deviating from the spec.

## Hard rules

- Never create AWS resources with a fixed monthly cost (RDS, NAT Gateway, load
  balancers, EC2, public IPv4, Route 53 hosted zones, Secrets Manager). The only
  usage-priced service is the Anthropic API, capped at $5/month by the guardrails in
  spec section 14; never weaken or bypass those guardrails.
- Never commit secrets. Anything prefixed `VITE_` is public.
- The running app calls exactly one third-party API: Anthropic, from the backend only,
  for AI substitutions (F7) and recipe generation (F8), and only on an explicit user
  action. TheMealDB is used only by `backend/scripts/import_mealdb.py`. No other runtime
  third-party call, and no AI call from the frontend or from tests — tests stub the client.
- Matching is the SQL query in `backend/app/matching.py`. Don't reimplement it in Python
  or the frontend, and never use a model to rank or count: counting for facts, models for
  judgment (spec section 4).
- No mobile/responsive layout, no camera or photo input, no quantity or unit tracking,
  no demo account, no assumed staples. These are deliberate MVP exclusions (spec
  section 4), not gaps to fill in.

## Commands

Backend (from `backend/`):
- `uv run uvicorn app.main:app --reload` — API on http://127.0.0.1:8000 (docs at /docs)
- `uv run pytest` — tests
- `uv run ruff check . && uv run ruff format --check .` — lint and format check
- `uv run alembic upgrade head` — apply migrations
- `uv run python -m scripts.import_mealdb` — import the recipe catalog

Local database (from repo root): `docker compose up -d`

Frontend (from `frontend/`): `npm run dev`, `npm test`, `npm run lint`,
`npm run typecheck`, `npm run build`

Infrastructure (from `infra/`): `terraform fmt -recursive`, `terraform validate`,
`terraform plan`

Some of these don't exist yet; create them as their milestone is reached.

## Conventions

- Python 3.13 with type hints everywhere. Request/response models live in
  `app/schemas.py`, and routers in `app/routers/`.
- TypeScript in strict mode. All HTTP goes through `src/api/client.ts`; all server
  state goes through TanStack Query hooks in `src/api/hooks.ts`.
- Every feature ships with tests (spec section 10.6).
- Trunk-based: `main` is always deployable. Work on short-lived branches named
  `m<milestone>/<area>` (e.g. `m1/database`), opened as pull requests and merged
  when the change works end to end and all checks pass. Split anything running
  past ~2 days or ~400 changed lines. Small commits, imperative subject lines.
- Never commit or push. When a change is ready, summarize what was done and give
  the exact `git add` / `git commit` commands; the developer reviews, commits, and pushes.

## Definition of done

- The story's acceptance criteria in the spec are met.
- New tests are added and all tests pass.
- Lint, format, and type checks pass.
- `docs/requirements.md` is updated if behavior or design changed (with the developer's
  approval).