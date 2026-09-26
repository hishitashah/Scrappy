# Scrappy — Requirements and Technical Specification

**Target ship date:** Wednesday, October 28, 2026
**Developer time:** about 10 hours/week

This document is the source of truth for Scrappy's scope and design. Implement one milestone task or user story at a time. If implementation reality conflicts with this document, stop and propose a change to the document instead of silently diverging. Anything marked post-MVP is out of scope until the MVP ships.

---

## 1. Product overview

Scrappy is a desktop web app that answers one question: **"What can I actually make with what's in my kitchen right now?"**

Users keep a pantry of ingredients, typed in by hand, and the app ranks recipes by how many of each recipe's ingredients the user already has. Every result names the ingredients that are missing.

Most recipe sites start from a recipe and send the user shopping. Scrappy inverts that: it starts from what the user has and works backwards. That constraint drives the design decisions below.

**Working name:** Scrappy.

---

## 2. Users and project context

**Target user.** Someone who cooks but doesn't meal-plan: college students, people at the end of a grocery week, anyone wondering whether a few random items add up to dinner. They won't spend more than about 60 seconds before the app shows value.

**Project context.**
- Scrappy is a portfolio project for a new-grad software engineering job search. The deployed app will mostly be seen by recruiters and interviewers evaluating the code and the live demo, not by real end users.
- It's also how the developer is learning AWS, Terraform, CI/CD with GitHub Actions, and FastAPI.
- Code should be clear and conventional rather than clever, with design decisions documented where they're made, since the developer needs to be able to explain every choice in an interview.

**Constraints**

| Constraint | Value |
|---|---|
| Budget | $0/month after AWS credits run out (see section 14) |
| Time | 10 hours/week; MVP complete by October 28, 2026 |
| Platform | Desktop web only — see section 4 |
| Development machine | macOS |
| AWS region | us-east-1 |

---

## 3. Scope

### 3.1 MVP features

**User-facing**

| ID | Feature | Summary |
|---|---|---|
| F1 | Pantry editing | Add ingredients by typing, with autocomplete from the known ingredient list; remove one with a single tap |
| F2 | Recipe matching | Recipes ranked by the percentage of their ingredients the user has |
| F3 | Match transparency | Each result shows "You have 3 of 7" and names the missing ingredients |
| F4 | Recipe detail | Ingredients with measurements (owned ones marked), numbered steps, photo, category, cuisine, and video/source links |
| F5 | Accounts | Sign up, log in, log out, and reset password. The entire app requires login. |
| F6 | Saved pantry | Each user's pantry is stored in the database and loads on login |

**Engineering**

| ID | Deliverable | Summary |
|---|---|---|
| E1 | Recipe catalog import | A script that loads TheMealDB into Postgres and normalizes ingredient names |
| E2 | Automated tests | Backend and frontend tests, written alongside each feature |
| E3 | Infrastructure as code | Every AWS resource defined in Terraform |
| E4 | CI/CD | GitHub Actions: checks on every pull request, automatic deploy on merge to `main` |
| E5 | Health and logging | `/health` endpoint, request logs in CloudWatch, error handling |
| E6 | README | Live link, demo GIF, architecture diagram, key decisions, local setup |

### 3.2 Post-MVP backlog (in priority order)

1. AI ingredient substitutions
2. Favorites
3. AI recipe generation when nothing matches
4. Ingredient hierarchy, so "chicken" matches recipes that need "chicken breast"
5. End-to-end browser tests (Playwright)
6. Least-privilege permissions for the CI deploy role
7. Cook history, shopping list, dietary filters, expiry nudges, personalization

Stories for these are in Appendix A.

### 3.3 Explicitly out of scope

Nutrition tracking and calorie counting. Meal planning calendars. Grocery delivery integration. Social features, sharing, comments, ratings. A native or mobile-optimized experience of any kind (see section 4). Camera or photo-based ingredient entry of any kind. Quantity or unit tracking of any kind (see section 4). Multi-user households sharing one pantry. Recipe authoring by users. Calls to any third-party API at runtime. Any infrastructure with a fixed monthly cost. A custom domain (the default CloudFront URL is used). A shared or pre-filled demo account. Assumed pantry staples.

### 3.4 MVP definition of done

A new visitor can open the public URL on a laptop, create an account, add and remove ingredients with autocomplete, see ranked matches with the missing ingredients named, open a recipe, and sign out and back in to find the pantry intact.

In addition:
- Every merge to `main` deploys automatically through CI/CD.
- All AWS infrastructure is defined in Terraform.
- Hosting costs $0/month.
- The README documents the architecture and key decisions.

---

## 4. Design decisions

These are deliberate. Don't change them without updating this section.

**Recipe data is imported once; the app never calls a third-party API at runtime.** A one-time import script copies TheMealDB's recipes into Scrappy's own Postgres database. After that, every user action is served by Scrappy's own API reading Scrappy's own database. TheMealDB is contacted only when the import script runs. This means there are no rate limits and no per-search cost, and the matching logic is Scrappy's own and testable. (Spoonacular was rejected: its terms forbid storing its data and cap caching at one hour.)

**Matching is a SQL query, not AI.** Ranking recipes by ingredient overlap is deterministic set math: fast, free, explainable, and reproducible. An LLM would be slower, costlier, and non-deterministic. AI is reserved for fuzzy judgment calls, such as substitutions (post-MVP).

**Matching reads the saved pantry.** `GET /matches` loads the caller's pantry on the server; the client sends no ingredient list. The matching logic itself is a pure function (`find_matches(session, ingredient_ids, limit)`), testable without HTTP or auth.

**When nothing matches, the result is an empty list.** The API returns `200 []`, and the UI shows an empty state. There is no fallback call to anything else. (Post-MVP, AI recipe generation adds an explicit, user-triggered fallback.)

**Login is required everywhere.** There's no anonymous browsing and no demo or shared account. Every page requires a signed-in user, which removes a second code path entirely: no anonymous pantries, no browser-stored state, no merge-on-signup logic.

**Only catalog ingredients enter a pantry.** Matching works only on canonical ingredients, so an unknown item like "leftover curry" could never match anything. Accepting it would quietly mislead the user. The autocomplete shows "No match" instead, and free text that doesn't resolve to a known ingredient can't be added. A misspelling is not simply rejected: when nothing matches, the autocomplete offers the closest catalog ingredients as "Did you mean…?", which the user must confirm. Correcting a typo therefore takes one click, but nothing outside the catalog is ever stored.

**Ingredient names are parsed; quantities are not stored.** If a user types "1 egg" or "a cup of rice," the input is matched against the ingredient catalog by name, and any leading quantity or unit words are discarded during matching — they are never saved or used in any calculation. The pantry only ever records which ingredients a user has, never how much. This is a deliberate simplification: quantity-aware matching would require unit conversion (cups to grams to ounces, per ingredient) to compare what a user has against what a recipe needs, which is substantial complexity for a portfolio project. The trade-off is that a user who has 1 egg and a recipe that needs 6 still shows as "having" egg. The recipe detail page always shows exact measurements, so a user finds out real quantities before cooking; the pantry's job is only to narrow down candidates, not to guarantee sufficiency.

**Staples are not assumed.** Every ingredient in a recipe counts toward its total, including salt, oil, and water. Match percentages are therefore honest but often lower for simple recipes. The pantry editor shows a hint: "Tip: add basics like salt, oil, and water for more accurate matches."

**Autocomplete filters in the browser.** The ingredient list is a few kilobytes, so the client downloads it once and filters locally. Calling the API per keystroke would cost six requests to type "garlic."

**Desktop web only, no mobile layout, no camera.** Every use case (typing ingredients, reading matches, reading a recipe) is fully served by a page viewed on a laptop. Recruiters and interviewers will overwhelmingly view the deployed app on a laptop. Given a fixed time budget, building and testing a separate mobile layout, or any camera-based ingredient entry, would spend hours on a use case the product doesn't need and few reviewers will exercise. The layout is designed for a wide screen with a mouse and keyboard; it isn't optimized to break gracefully on a phone, and that's intentional, not an oversight.

**Missing data isn't invented.** TheMealDB has no cooking times or servings, so the app doesn't show them rather than guess.

**Hosting costs $0/month.** No resource with a fixed monthly charge is ever created (see section 14).

---

## 5. User stories (MVP)

### Accounts

**US-1** — As a new user, I want to create an account with my email and a password, so that my pantry is saved across devices.
- Password rules: at least 8 characters, with a lowercase letter, an uppercase letter, and a number. The form checks them before submitting, and Cognito enforces them on the server.
- A duplicate email shows "An account with this email already exists," not a generic failure.
- Successful signup logs the user straight in, with no email verification step.

**US-2** — As a returning user, I want to log in and land on my saved pantry, so that I can get to results in one step.
- The session survives a browser refresh and lasts up to 30 days.
- The pantry and results load behind visible loading states, never a blank screen.
- Logging out returns to the login screen and clears the previous user's data from memory.

**US-16** — As a user who forgot my password, I want to reset it by email, so that I don't lose my pantry.
- "Forgot password" is on the login screen.
- An emailed code lets the user set a new password.

### Pantry

**US-3** — As a user, I want to add an ingredient by typing, with suggestions as I type, so that my entries are consistent enough to match reliably.
- Suggestions come from the canonical ingredient list and appear after the first character.
- "Eggs," "eggs," and "egg" all suggest "Egg."
- Leading quantity or unit words ("1", "a cup of") are ignored when matching what's typed against the catalog; nothing about quantity is stored.
- Ingredients already in the pantry aren't suggested, so duplicates are impossible.
- Text matching no known ingredient, but close to one, shows "Did you mean …?" with up to three
  suggestions. Choosing one adds that ingredient; Enter alone adds nothing.
- Text close to nothing in the catalog shows "No match — try a simpler name" and can't be added.

**US-4** — As a user, I want to remove an ingredient in one tap, so that my pantry stays accurate as I use things up.
- The item disappears immediately, without waiting for the server.
- If the server call fails, the item reappears with an error message.

**US-17** — As a user, I want "Eggs," "egg," and "2 large eggs" to count as the same ingredient, so that match results are accurate.
- Recipe ingredients are mapped to canonical ingredients at import: case, spacing, and plurals are normalized, and a synonym list is applied.
- Unmappable recipe ingredients are added to the catalog and written to an import report for review, never silently dropped.
- Have/need counts use canonical ingredients only.

### Matching and recipes

**US-5** — As a user, I want recipes ranked by how much of each I can already make, so that the most achievable options are at the top.
- Each result shows a match percentage and a have/need count.
- Results are sorted by match percentage, then number of owned ingredients, then title, so the order is stable.
- Results update automatically after any pantry change.
- There are two distinct empty states. Empty pantry: "Add a few ingredients to see what you can make." No overlap: "No recipes use these ingredients yet."

**US-6** — As a user, I want to see exactly which ingredients I'm missing for a given recipe, so that I can judge whether it's worth it.
- Missing ingredients are named on each result card and marked on the detail page.
- The missing count always equals total minus have.

**US-7** — As a user, I want to open a recipe and see full instructions, so that I can cook it without leaving the app.
- The page shows the photo, title, category, cuisine, every ingredient with its measurement, and numbered steps.
- Owned and missing ingredients are visually distinct.
- Links to the recipe's video and original source appear when available.
- Going back returns to the results without reloading them.

**Definition of done for every story:**
- Acceptance criteria are met.
- Tests are added and passing.
- Lint, format, and type checks pass.
- This document is updated if behavior or design changed.

---

## 6. Screens and UX

Desktop-only. No mobile breakpoints, no touch-specific interactions, no phone layout. The layout assumes a wide screen, a mouse, and a keyboard.

| Screen | Route | Contents |
|---|---|---|
| Login | Shown whenever signed out | App name and a one-line pitch; Amplify's sign-in, create-account, and forgot-password forms |
| Home | `/` | Header (app name, sign out); pantry editor with the basics hint; ranked results |
| Recipe detail | `/recipes/:id` | Back link; photo; title; category and cuisine tags; ingredients with owned/missing marks; numbered steps; video and source links |

**Layout.** Home uses two fixed columns: the pantry on the left, results on the right. No responsive stacking or breakpoint logic is implemented.

**Style.** look at png in the docs folder

**States.**
- **Loading:** skeleton placeholders shaped like the real content.
- **Errors:** shown inline with a "Try again" button.
- **Crashes:** a top-level error boundary offers a reload.

**Not in the MVP:** dark mode, animations, custom illustration, any mobile or tablet layout, camera or photo capture of any kind.

---

## 7. Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend framework | React 19 + TypeScript (strict), built with Vite | Static build output; widely used |
| Routing | React Router | Two routes |
| Server state | TanStack Query 5 | Caching, loading and error states, refetching after mutations |
| Styling | Tailwind CSS 4 | No separate design system needed |
| Autocomplete | Headless UI `Combobox` | Keyboard navigation and ARIA roles built in |
| Login UI | Amplify UI `Authenticator` (`@aws-amplify/ui-react`) + `aws-amplify` 6 | Ready-made sign-up, sign-in, and password-reset screens for Cognito |
| Frontend tests | Vitest + React Testing Library + MSW | Component tests against a mocked API |
| API | FastAPI + Pydantic 2 | Validation, response models, docs at `/docs` |
| Database access | SQLAlchemy 2 (ORM models for tables; raw SQL for matching) + psycopg 3 | The matching query stays readable SQL |
| Migrations | Alembic | Versioned schema changes, run by CI before each deploy |
| Settings | pydantic-settings | Typed configuration from environment variables |
| Token verification | PyJWT (`PyJWKClient`) | Verifies Cognito access tokens inside FastAPI |
| Normalization | `inflect` + a synonym list | Singular/plural handling for ingredient names |
| Lambda adapter | Mangum | Runs the FastAPI app on Lambda |
| Backend tooling | uv, ruff, pytest | Dependencies and lockfile, lint and format, tests |
| Compute | AWS Lambda (Python 3.13, x86_64) with a Function URL | Permanent free tier |
| Frontend hosting | Private S3 bucket + CloudFront | HTTPS static hosting; permanent free tier |
| Database | Neon Postgres 17, free plan, AWS us-east-1 | Relational matching; RDS has no permanent free tier |
| Auth | Amazon Cognito user pool | Free up to 10,000 monthly active users |
| Secrets | SSM Parameter Store (standard tier) | Free |
| Infrastructure as code | Terraform 1.11+ with AWS provider 6.x | Reproducible infrastructure |
| CI/CD | GitHub Actions with AWS access via OIDC | No long-lived AWS keys |
| Local development | Docker Compose (Postgres 17) | Same Postgres version everywhere |

**Rejected alternatives**

| Option | Why not |
|---|---|
| RDS | About $15/month after credits |
| DynamoDB | Not SQL; matching would move into application code |
| API Gateway | Free for only 12 months; a Function URL is free permanently |
| ECS Fargate | About $30/month minimum with a load balancer |
| Vercel + Render | Render's free backend sleeps and can take up to a minute to wake; skips the AWS learning goal |
| Custom login screens | Amplify UI provides them, including password reset |
| A native or React Native mobile app | No feature needs device hardware; one web codebase fits the time budget and the learning goals |

---

## 8. Architecture and request flow

```
One-time setup:  import script → TheMealDB API → Scrappy's Postgres (Neon)

Every session:
  Login:      Browser → Cognito (sign in, receive tokens)
  Page load:  Browser → CloudFront → S3 (built React files)
  API calls:  Browser → Lambda Function URL → FastAPI (Mangum) → Postgres
              (every call carries the Cognito access token)

Deploys:      GitHub Actions → AWS (via OIDC) and → Neon (migrations)
```

**Two different APIs.** "TheMealDB API" is a third-party service, called only by the import script. "The API" everywhere else in this document means Scrappy's own FastAPI backend, which the browser calls for every user action.

**Request lifecycle.**
1. The browser calls the Function URL with `Authorization: Bearer <access token>`.
2. Because the page and the API are on different origins, the browser first sends a CORS preflight request, which the Function URL's CORS configuration answers.
3. Lambda invokes Mangum, which hands the request to FastAPI.
4. FastAPI verifies the token, validates the input, queries Postgres, and returns JSON.

**Latency.** Warm requests should take well under one second. A cold Lambda plus a suspended Neon compute can reach about one to two seconds, so every data view needs a loading state.

---

## 9. Repository layout

```
scrappy/
├── CLAUDE.md
├── docs/requirements.md
├── backend/
│   ├── app/
│   │   ├── main.py         FastAPI app, routers, Mangum handler
│   │   ├── settings.py     configuration (pydantic-settings)
│   │   ├── db.py           SQLAlchemy engine and sessions
│   │   ├── models.py       ORM table definitions
│   │   ├── schemas.py      Pydantic request/response models
│   │   ├── auth.py         token verification, current-user dependency
│   │   ├── normalize.py    ingredient-name normalization
│   │   ├── matching.py     the matching query
│   │   └── routers/        ingredients.py, pantry.py, matches.py,
│   │                       recipes.py
│   ├── migrations/         Alembic
│   ├── scripts/            import_mealdb.py
│   ├── data/                aliases.json (+ git-ignored API cache)
│   ├── tests/
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── api/             client.ts, hooks.ts
│   │   ├── auth/            amplify.ts, LoginScreen.tsx
│   │   ├── components/      PantryEditor, IngredientCombobox,
│   │   │                    ResultsList, RecipeCard
│   │   ├── pages/           HomePage.tsx, RecipeDetailPage.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── infra/
│   ├── bootstrap/           Terraform state bucket (applied once)
│   ├── lambdas/              pre_signup.py
│   ├── main.tf               providers, backend, default tags
│   ├── frontend.tf           S3, CloudFront
│   ├── api.tf                Lambda, Function URL, logs, SSM
│   ├── auth.tf                Cognito
│   ├── github.tf              OIDC provider, deploy role
│   └── outputs.tf
├── .github/workflows/ci.yml
├── docker-compose.yml       local Postgres
└── README.md
```


**Conventions:**
- Frontend tests sit next to their components (`PantryEditor.test.tsx`).
- The raw TheMealDB download is cached in `backend/data/` but git-ignored, so the public repo doesn't redistribute the dataset.

---

## 10. Feature implementation specs

### 10.1 F1 — Pantry editing

**Behavior.** A search box above a list of ingredient chips, with the basics hint below the search box. Typing shows up to 8 suggestions; Enter or a click adds one. Each chip has an × that removes it immediately.

**Frontend**

- `PantryEditor` renders `IngredientCombobox`, the hint, and the chips.
- `IngredientCombobox` uses Headless UI `Combobox`.
- `useIngredients()` loads `GET /ingredients` once per session (`staleTime: Infinity`).
- Filtering runs in the browser: strip any leading quantity/unit words from the query (a small stopword list: numbers, "a", "an", "cup", "cups", "tbsp", "tsp", "oz", "of", etc.), lowercase the remainder, match it against each ingredient's `name` and `aliases`, rank prefix matches first, exclude ingredients already in the pantry, and show the top 8.
- When that yields nothing, fall back to a "Did you mean…?" list: rank the catalog by Levenshtein
  distance to the query and keep up to three within a distance of 1 for queries shorter than 5
  characters, or 2 otherwise. The list is visually distinct from ordinary suggestions and is never
  auto-selected: pressing Enter with no selection adds nothing. Below that distance nothing is
  offered and the "No match" message stands. The comparison is pure client-side string distance,
  with no API call and no new dependency.
- `usePantry()` loads `GET /pantry`.
- `useAddPantryItems()` calls `POST /pantry/items`, then invalidates the `pantry` and `matches` queries.
- `useRemovePantryItem()` calls `DELETE /pantry/items/{id}` with an optimistic update:
  - `onMutate` removes the chip from the cache.
  - `onError` restores it and shows an error.
  - `onSettled` invalidates `pantry` and `matches`.

**API**

- `GET /ingredients` returns `[{id, name, display_name, aliases}]`, with `Cache-Control: private, max-age=86400`.
- `GET /pantry` returns `[{ingredient_id, display_name, added_at}]`, sorted by `display_name`.
- `POST /pantry/items` takes `{"ingredient_ids": [int]}` (1–50 IDs) and returns the updated pantry.
  - Unknown IDs return 422 with the list of bad IDs.
  - IDs already in the pantry are ignored.
- `DELETE /pantry/items/{ingredient_id}` returns 204, including when the item was absent (idempotent).

Note: only `ingredient_id` is ever sent or stored for a pantry item. There is no quantity field anywhere in this API.

**Backend**

- The code lives in `routers/ingredients.py` and `routers/pantry.py`.
- Insert with `INSERT … ON CONFLICT DO NOTHING`.
- Before inserting, validate the IDs with a single `SELECT id FROM ingredients WHERE id = ANY(:ids)`.

**Tests**

- Backend:
  - A duplicate add leaves one row.
  - Unknown IDs return 422.
  - Delete is idempotent.
  - A user can't read or change another user's pantry.
- Frontend:
  - Typing "egg" suggests "Egg."
  - Typing "1 egg" or "a cup of rice" still suggests "Egg" / "Rice."
  - Typing "garlick" offers "Did you mean Garlic?"; choosing it adds Garlic, and Enter alone does not.
  - Typing "zzzzz" shows "No match — try a simpler name" with no suggestions.
  - Owned items aren't suggested.
  - × removes the chip before the server responds.
  - A failed delete restores the chip.

### 10.2 F2 + F3 — Recipe matching and transparency

**Behavior.** A results list of up to 20 cards. Each card shows a thumbnail, the title, a percentage badge, "You have 3 of 7," and "Missing: oil, salt, soy sauce, spring onion." The list updates after every pantry change.

**Frontend**

- `ResultsList` and `RecipeCard`.
- `useMatches()` loads `GET /matches`.
- Loading shows six skeleton cards.
- The empty states follow US-5, chosen by whether the pantry is empty.
- Errors show inline with "Try again."
- Clicking a card navigates to `/recipes/:id`.

**API.** `GET /matches?limit=20` (`limit` 1–50) returns `[{id, title, thumbnail_url, have, total, match, missing}]`.

**Backend**

- `routers/matches.py` loads the current user's pantry ingredient IDs. If the pantry is empty, it returns `[]` without querying. Otherwise it calls `matching.find_matches(session, ingredient_ids, limit)`.
- `find_matches` executes this query (verified against Postgres with fixture data):

```sql
WITH scored AS (
  SELECT r.id, r.title, r.image_url,
         count(*) FILTER (WHERE ri.ingredient_id = ANY(:have))           AS have,
         count(*)                                                          AS total,
         array_agg(i.display_name ORDER BY ri.position)
           FILTER (WHERE ri.ingredient_id <> ALL(:have))                  AS missing
  FROM recipes r
  JOIN recipe_ingredients ri ON ri.recipe_id = r.id
  JOIN ingredients i         ON i.id = ri.ingredient_id
  GROUP BY r.id, r.title, r.image_url
)
SELECT id, title, image_url AS thumbnail_url, have, total,
       round(100.0 * have / total)::int AS match,
       coalesce(missing, '{}')          AS missing
FROM scored
WHERE have > 0
ORDER BY match DESC, have DESC, title ASC
LIMIT :limit;
```

- `have`, `total`, and `missing` come from one query, so `total − have = len(missing)` always holds.
- Confirmed example: a fixture catalog with "Egg fried rice" (rice, egg, garlic, oil, salt, soy sauce, spring onion) and "Boiled egg" (egg, water, salt), with a pantry of egg, rice, and garlic, returns exactly:
  1. Egg fried rice: 3/7, 43%, missing oil, salt, soy sauce, spring onion.
  2. Boiled egg: 1/3, 33%, missing water, salt.

**Scaling note.** At a few thousand recipe-ingredient rows, a full scan takes milliseconds. At much larger scale, first filter to recipes containing at least one owned ingredient, using an index on `recipe_ingredients.ingredient_id`.

**Tests**

- Use a fixture catalog: boiled egg (egg, water, salt), egg fried rice (rice, egg, garlic, oil, salt, soy sauce, spring onion), fried chicken (chicken, flour, oil, salt, pepper), and pancakes (flour).
- A pantry of egg, rice, and garlic must return exactly the two rows above, in that order, and must exclude fried chicken and pancakes.
- The `total − have = len(missing)` invariant holds for every row.
- An empty pantry returns `[]`.
- A pantry whose ingredients appear in no recipe returns `[]`.

### 10.3 F4 — Recipe detail

**Behavior.** As described in US-7. Owned ingredients are green; missing ones are muted red.

**Frontend**

- Route `/recipes/:id` renders `RecipeDetailPage` with `useRecipe(id)`.
- Back navigation uses browser history, so the cached results reappear instantly.
- A 404 shows "Recipe not found" with a link home.

**API.** `GET /recipes/{id}` returns `{id, title, category, area, image_url, youtube_url, source_url, steps: [str], ingredients: [{id, display_name, measure, owned}]}`, or 404.

**Backend.** `routers/recipes.py`. The `owned` flag is computed against the user's pantry. Ingredients are ordered by `recipe_ingredients.position`.

**Tests.** A missing ID returns 404; `owned` flags match the pantry; steps and ingredients come back in order.

### 10.4 F5 + F6 — Accounts, login wall, saved pantry

**Behavior.** Signed-out visitors see only the login screen. After signing in, they see Home with their own pantry. The header has "Sign out."

**Frontend**

- `auth/amplify.ts` calls `Amplify.configure` with:
  - the user pool ID and app client ID from `VITE_` variables
  - `loginWith: { email: true }`
  - `passwordFormat` matching US-1, so the form validates before submitting
- `<Authenticator>` wraps the app, which creates the login wall. Email is the only signup field. The `Header` slot shows the app name and pitch.
- `api/client.ts` exports `apiFetch()`, and every hook uses it. It calls `fetchAuthSession()`, which refreshes expired tokens, and sets `Authorization: Bearer <access token>`.
- A 401 response triggers `signOut()`.
- On sign-out, `queryClient.clear()` removes the previous user's cached data.

**Backend (`auth.py`)**

`get_current_user` is a dependency applied to every router except `/health`. It supports two modes.

**`AUTH_MODE=cognito`**
- It verifies the bearer token with PyJWT. `PyJWKClient` is created at module level, so each Lambda instance fetches Cognito's keys once and caches them.
- It checks:
  - the RS256 signature
  - `exp`
  - `iss` equal to `https://cognito-idp.us-east-1.amazonaws.com/<pool id>`
  - `token_use` equal to `access`
  - `client_id` equal to the app client ID
- Any failure returns 401 with `WWW-Authenticate: Bearer`.
- On success, it runs `INSERT INTO users (id) VALUES (:sub) ON CONFLICT DO NOTHING` and returns the `sub`.

**`AUTH_MODE=shared`**
- It skips token checks and returns the fixed user `shared-user`.
- This mode is used locally before Cognito exists, and briefly on the live site between the first deploy and the login milestone.
- Settings validation refuses `shared` mode when `ENV=prod` unless `ALLOW_SHARED_MODE=true` is set. That flag is removed when login ships.

**AWS (`auth.tf`)**

- **User pool:** email as the username, the password policy from US-1, account recovery by email, and Cognito's default email sender.
- **App client:**
  - no client secret
  - auth flows `ALLOW_USER_SRP_AUTH` and `ALLOW_REFRESH_TOKEN_AUTH`
  - access token valid 1 hour, refresh token valid 30 days
- **Pre-sign-up trigger:** `infra/lambdas/pre_signup.py`. When `triggerSource` is `PreSignUp_SignUp`, it sets `autoConfirmUser` and `autoVerifyEmail` to true. This skips verification while still allowing password-reset emails.
  - Accepted trade-off: someone can register an email address they don't own.
- **Permission:** a Lambda permission lets Cognito invoke the trigger.

**Tests**

- Backend: a valid token passes. Each of these returns 401:
  - an expired token
  - the wrong issuer
  - an ID token instead of an access token
  - the wrong client ID
  - a missing header
- These tests sign tokens with a locally generated RSA key and patch the key client; they never call AWS.
- Frontend: `apiFetch` attaches the header, and a 401 triggers sign-out.

### 10.5 E1 — Recipe catalog import

**Command:** `uv run python -m scripts.import_mealdb`, which writes to whatever database `DATABASE_URL` points to.

**Steps**

1. **Fetch.** Use httpx2 (the maintained successor to httpx, which Starlette's test client also prefers) against `https://www.themealdb.com/api/json/v1/1/`, the free test key, which is allowed for development and educational use.
   - `list.php?i=list` returns the canonical ingredient list.
   - `search.php?f=a` through `f=z`, then `f=0` through `f=9` (36 calls), return every meal
     with full details. Digits are included because TheMealDB holds at least one meal whose
     title starts with a number, which an a–z sweep would silently miss.
   - Responses are cached to a git-ignored file.
2. **Parse.** Pair `strIngredient1–20` with `strMeasure1–20`, skipping empty slots.
3. **Normalize** (`app/normalize.py`):
   - Lowercase, trim, collapse spaces, and strip punctuation.
   - Singularize the last word with `inflect`. An exceptions list protects words it would break: asparagus, couscous, hummus, molasses.
   - Apply `data/aliases.json` (for example, "garlic clove" → "garlic").
4. **Map** each name to a canonical ingredient. If none matches, create the ingredient and log it to `import_report.csv`. The fix is to add an alias and re-run.
5. **Deduplicate within a recipe.** When two lines map to one ingredient, keep the first position and join the measures with " + ".
6. **Write** everything in one transaction:
   - Upsert recipes by `(source, source_id)`.
   - Replace each recipe's ingredient rows.
   - Split `strInstructions` on line breaks into `steps`, dropping blank lines and "STEP n" prefixes.
7. **Print a summary:** recipes, ingredients, and unmapped names.

Re-running the script must change nothing.

**Tests**
- Table-driven normalization tests, with at least 20 cases including the exceptions.
- Parsing a fixture meal.
- Importing the fixture and checking counts.
- Importing twice produces no duplicates.

### 10.6 E2 — Testing standards

**Backend**
- pytest against real Postgres: Docker locally (a `scrappy_test` database) and a Postgres 17 service container in CI.
- Alembic builds the schema once per test session.
- Each test runs in a transaction that is rolled back afterward.
- API tests use FastAPI's `TestClient` with `app.dependency_overrides[get_current_user]`.
- Coverage is reported with pytest-cov, with no hard threshold.

**Frontend**
- Vitest with jsdom and React Testing Library; MSW intercepts API calls.
- Cover the pantry editor, results rendering (counts and missing names), and both empty states.

**Not in the MVP:** end-to-end browser tests.

### 10.7 E3 — Infrastructure as code

**State and conventions**
- Terraform 1.11+ with the S3 backend and `use_lockfile = true` (native locking, no DynamoDB table).
- The state bucket is created once by `infra/bootstrap/`, which keeps local state.
- AWS provider pinned to 6.x, with `default_tags = { project = "scrappy" }`.

**Frontend hosting (`frontend.tf`)**
- **S3 bucket:** private, all public access blocked, no website hosting.
- **CloudFront distribution:**
  - Origin Access Control, plus a bucket policy that allows only this distribution
  - `default_root_object = "index.html"`
  - custom error responses mapping 403 and 404 to `/index.html` with status 200, so client-side routes survive a refresh
  - HTTP redirected to HTTPS
  - `PriceClass_100`
  - the managed CachingOptimized cache policy
  - the default `*.cloudfront.net` certificate

**API (`api.tf`)**
- **Lambda:**
  - `python3.13`, `x86_64`
  - handler `app.main.handler`
  - 512 MB memory, 10-second timeout
  - code from the zip that CI builds, with `source_code_hash`
  - environment variables: `ENV`, `APP_VERSION`, `AUTH_MODE`, `DATABASE_URL_PARAM`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`
- **Function URL:**
  - auth type `NONE`, because the app verifies Cognito tokens itself
  - CORS origins: the CloudFront domain and `http://localhost:5173`
  - methods GET, POST, DELETE; headers `authorization` and `content-type`; max age 3600
- **Function resource policy:** it must grant both `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` to `*`, conditioned on `lambda:FunctionUrlAuthType = NONE` and `lambda:InvokedViaFunctionUrl = true`. Function URLs created since October 2025 require both actions; missing the second causes 403 Forbidden.
- **CORS lives in one place.** In production the Function URL handles CORS. FastAPI's `CORSMiddleware` is enabled only when `ENV=local`, because enabling both produces duplicate headers that browsers reject.
- **CloudWatch log group:** `/aws/lambda/scrappy-api` with 14-day retention. Create it in Terraform before the first invocation; otherwise Lambda creates one that keeps logs forever.
- **SSM parameter:** `/scrappy/prod/database_url`, a SecureString.
  - Terraform creates it with a placeholder and `lifecycle { ignore_changes = [value] }`.
  - The real value is set once with `aws ssm put-parameter --overwrite`, so it never enters Terraform state or git.
- **Lambda role:** `AWSLambdaBasicExecutionRole` plus `ssm:GetParameter` on that one parameter only.

**GitHub access (`github.tf`)**
- An OIDC provider for `token.actions.githubusercontent.com` with audience `sts.amazonaws.com`.
- A deploy role whose trust policy requires `sub = repo:<owner>/scrappy:ref:refs/heads/main`, so pull requests get no AWS access.
- For the MVP, the role has `AdministratorAccess`, constrained by that trust policy. Least privilege is a post-MVP item.

**Outputs:** site URL, API URL, bucket name, distribution ID, user pool ID, app client ID.

**Neon (configured manually)**
- One project in AWS us-east-1 on Postgres 17.
- Two connection strings:
  - **Pooled** (host contains `-pooler`) for Lambda, stored in SSM.
  - **Direct** for Alembic and the import script, stored as the GitHub secret `NEON_DIRECT_URL`.
- The Lambda-side SQLAlchemy engine uses:
  - `pool_size=1` and `max_overflow=0`
  - `pool_pre_ping=True`
  - `connect_args={"prepare_threshold": None}` (disables server-side prepared statements behind the pooler)
  - `sslmode=require`

### 10.8 E4 — CI/CD (`.github/workflows/ci.yml`)

Triggered on every pull request and every push to `main`. The first three jobs run in parallel.

**backend**
- `astral-sh/setup-uv`, then `uv sync --locked`
- `ruff check` and `ruff format --check`
- `alembic upgrade head` against a Postgres 17 service container
- `pytest --cov`

**frontend**
- `actions/setup-node` (Node 24, npm cache), then `npm ci`
- `npm run lint`, `npm run typecheck`, `npm test -- --run`, `npm run build`

**infra**
- `hashicorp/setup-terraform`
- `terraform fmt -check -recursive`, `terraform init -backend=false`, `terraform validate`
- No AWS credentials are needed.

**deploy**

Runs only on pushes to `main`, after all three jobs pass. It uses `concurrency: deploy-prod` and `permissions: id-token: write`.

1. `aws-actions/configure-aws-credentials` assumes the deploy role through OIDC (role ARN in the repository variable `AWS_DEPLOY_ROLE_ARN`).
2. **Build the Lambda package:**
   - `uv export --no-dev --no-hashes --format requirements-txt`, then `uv pip install --target build/package --python-platform x86_64-manylinux_2_28 --python-version 3.13 --only-binary :all: -r requirements.txt`.
   - Copy `app/` in and zip.
   - This builds a Linux package from any OS; verified, about 18 MB zipped.
   - Don't bundle boto3; the Lambda runtime provides it.
3. **Migrate:** `alembic upgrade head` against `NEON_DIRECT_URL`. Migrations run before new code goes live, so they must be backward-compatible (add columns; never rename or drop them in the same deploy).
4. **Apply infrastructure:** `terraform init` and `terraform apply -auto-approve`. This also deploys the new Lambda code.
5. **Smoke test:** `curl --fail "$API_URL/health"`, and check that `version` equals the commit SHA.
6. **Deploy the frontend:**
   - Build with `VITE_` values from Terraform outputs.
   - Upload the hashed assets with `Cache-Control: public, max-age=31536000, immutable`.
   - Then upload `index.html` with `no-cache`.
   - Then invalidate `/index.html` in CloudFront.

**Repository settings**
- Branch protection on `main` requires the backend, frontend, and infra jobs to pass.
- All work goes through feature branches and pull requests.

### 10.9 E5 — Health and logging

- **`GET /health`** returns `{"status": "ok", "version": "<APP_VERSION>"}` and never touches the database, so health checks don't wake Neon.
- **Request logging:** a middleware logs one line per request with the method, path, status, duration in milliseconds, and user ID. View the logs with `aws logs tail /aws/lambda/scrappy-api --follow`.
- **Errors:** an exception handler logs unexpected errors with their stack trace and returns `{"detail": "Internal error"}`.
- **Frontend:** a top-level error boundary.

### 10.10 E6 — README

In order:
1. Name and one-line pitch
2. Live link
3. A 20-second GIF of a search
4. Features
5. An architecture diagram in Mermaid
6. Key decisions from section 4
7. Tech stack
8. Testing and CI, with a status badge
9. How it stays at $0/month
10. Local setup
11. Post-MVP roadmap

---

## 11. API reference

All endpoints except `/health` require `Authorization: Bearer <Cognito access token>`, or shared mode. Errors use FastAPI's standard `{"detail": ...}` shape.

| Method | Path | Request | Success | Errors |
|---|---|---|---|---|
| GET | `/health` | — | 200 `{status, version}` | — |
| GET | `/ingredients` | — | 200 `[{id, name, display_name, aliases}]` | 401 |
| GET | `/pantry` | — | 200 `[{ingredient_id, display_name, added_at}]` | 401 |
| POST | `/pantry/items` | `{"ingredient_ids": [int]}`, 1–50 IDs | 200 updated pantry | 401, 422 |
| DELETE | `/pantry/items/{ingredient_id}` | — | 204 | 401 |
| GET | `/matches` | `?limit=1–50` (default 20) | 200 `[{id, title, thumbnail_url, have, total, match, missing}]` | 401, 422 |
| GET | `/recipes/{id}` | — | 200 recipe detail (see 10.3) | 401, 404 |

`/docs` and `/openapi.json` stay enabled in production.

---

## 12. Data model

Tables are defined as SQLAlchemy ORM models in `models.py`, and Alembic migrations are generated from them. The matching query is plain SQL.

| Table | Column | Type | Notes |
|---|---|---|---|
| `ingredients` | `id` | serial PK | |
| | `name` | text, unique, not null | Normalized (lowercase, singular) |
| | `display_name` | text, not null | E.g. "Chicken Breast" |
| | `aliases` | text[], default `{}` | Extra autocomplete terms, e.g. "eggs" |
| `recipes` | `id` | serial PK | |
| | `source` | text, not null | `themealdb`; `generated` post-MVP |
| | `source_id` | text | `idMeal`; unique with `source` |
| | `title` | text, not null | |
| | `category`, `area` | text | |
| | `image_url`, `youtube_url`, `source_url` | text | Optional |
| | `steps` | jsonb, not null | Array of strings |
| | `total_minutes`, `servings` | integer, nullable | Always empty in the MVP |
| | `created_at` | timestamptz, default now() | |
| `recipe_ingredients` | `recipe_id` | int FK → recipes, cascade delete | PK with `ingredient_id` |
| | `ingredient_id` | int FK → ingredients | |
| | `measure` | text | E.g. "2 cups" — display only, never parsed or compared |
| | `position` | smallint | Display order |
| `users` | `id` | text PK | Cognito `sub`, or `shared-user` |
| | `created_at` | timestamptz, default now() | |
| `pantry_items` | `user_id` | text FK → users, cascade delete | PK with `ingredient_id` |
| | `ingredient_id` | int FK → ingredients | |
| | `added_at` | timestamptz, default now() | |

Note: `pantry_items` has no quantity column, by design (see section 4).

---

## 13. Configuration and secrets

**Backend** (read by pydantic-settings)

| Variable | Local | CI tests | Production (Lambda) |
|---|---|---|---|
| `ENV` | `local` | `test` | `prod` |
| `DATABASE_URL` | Docker Postgres, from `.env` | Service container | Not set |
| `DATABASE_URL_PARAM` | — | — | `/scrappy/prod/database_url`, read from SSM once per cold start |
| `AUTH_MODE` | `shared` until login ships, then `cognito` | Overridden in tests | `shared` until login ships, then `cognito` |
| `ALLOW_SHARED_MODE` | — | — | `true` only until login ships |
| `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID` | From Terraform outputs | — | Set by Terraform |
| `APP_VERSION` | `local` | — | Commit SHA |

**Frontend** (compiled into public JavaScript; never put secrets here): `VITE_API_URL`, `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID`.

**Where secrets live**
- **Neon pooled URL:** SSM, for Lambda.
- **Neon direct URL:** GitHub secret `NEON_DIRECT_URL`, for CI.
- **Local values:** git-ignored `.env` files.
- No secret is ever committed.

---

## 14. Cost rules

**Rule:** never create a resource that charges a fixed amount just for existing.

**Prohibited:** RDS, NAT Gateway, load balancers, EC2 instances, public IPv4 addresses, Route 53 hosted zones, Secrets Manager.

**Free tiers relied on**
- **Lambda:** 1M requests and 400,000 GB-seconds per month.
- **CloudFront:** 1 TB and 10M requests per month.
- **Cognito:** up to 10,000 monthly active users.
- **Neon:** 100 compute-hours and 0.5 GB per month; suspends after 5 minutes idle.
- **GitHub Actions:** free on public repositories.

S3 storage for the frontend costs fractions of a cent. CloudWatch log retention is capped at 14 days.

**No VPC.** Lambda runs outside a VPC and reaches Neon over TLS, so no NAT Gateway is needed.

**Account guardrails:** an AWS Budget alert at $1/month that excludes credits.

---

## 15. Milestones

| Milestone | Target | Scope | Exit criteria |
|---|---|---|---|
| M1 | Sep 27 | Finish setup; Docker Compose Postgres; ORM models and first migration; E1 import | `uv run pytest` passes; the local database holds the full TheMealDB catalog |
| M2 | Oct 4 | API for F1, F2/F3, F4 in shared mode, with tests; React scaffold; F1 UI | Ingredients can be added in the browser and matches returned locally |
| M3 | Oct 11 | F2/F3 results UI; F4 detail page; E5; start E3 | The full app works locally; the first AWS resources are applied |
| M4 | Oct 18 | Finish E3; Neon and production import; E4 pipeline | Live URL in shared mode; merging to `main` deploys |
| M5 | Oct 25 | F5/F6: Cognito, login wall, token verification, per-user pantries | The live app requires login; pantries are per user |
| M6 | Oct 28 | E6 README; fixes | The MVP definition of done (3.4) is met |

**If behind schedule**, cut in this order:
1. Frontend component tests (keep backend tests)
2. Visual polish

Never cut deployment, login, backend tests, or the README.

---

## 16. Open questions

- **Recipe count:** TheMealDB has several hundred recipes. Evaluate match quality after M1; a second source is a post-MVP option.
- **TheMealDB terms:** the free test key covers development and educational use. Confirm whether a public deployment needs supporter status before M4.
- **Shared mode:** between M4 and M5, all visitors to the live site share one pantry. Accepted.

---

## Appendix A — Post-MVP stories

**AI substitutions.** As a user, I want substitution suggestions for an ingredient I'm missing, so that I can cook anyway. Suggestions prefer items in the user's pantry, each includes a one-line reason, and all are labeled AI-generated.

**Favorites.** As a user, I want to favorite recipes, so that I can find ones I liked again.

**AI recipe generation.** As a user, I want to generate a recipe from my exact ingredients when nothing matches, so that the app is useful in the worst case. Generated recipes are visibly labeled and can be saved.

**Cook history.** As a user, I want to mark a recipe as cooked, so that I have a history of what I've made.

**Shopping list.** As a user, I want a shopping list of everything I'm missing across chosen recipes, so that one trip covers several meals. Duplicates are merged and the list is copyable as plain text.

**Others:** dietary filters, expiry nudges (using `pantry_items.added_at`), and personalization from history and favorites. A quantity-aware pantry, if ever pursued, would need a unit-conversion layer and should be scoped as its own project, not a quick addition.