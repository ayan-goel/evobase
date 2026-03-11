# Coreloop — Frontend ↔ Backend Gap Analysis

What the MVP spec promises vs. what actually exists today.

---

## Critical — App is non-functional without these

### 1. No authentication whatsoever

**Spec says:** "User installs the GitHub App and selects a repository." Implies logged-in users with identity.

**Backend reality:**
- `get_current_user()` in `app/auth/dependencies.py` is a stub that always returns a hardcoded UUID (`00000000-...0001`). No JWT validation, no token check.
- There are no signup or login endpoints.
- Settings endpoints (`GET/PUT /repos/{repo_id}/settings`) don't even use the auth dependency — anyone can read/write them.

**Frontend reality:**
- No login page, no signup page, no auth provider/context.
- No Supabase Auth client (`@supabase/supabase-js` not even in `package.json`).
- No `middleware.ts` to protect routes.
- `lib/api.ts` sends zero auth headers with requests.
- No session storage, no token refresh, nothing.

**What's needed:**
- Supabase Auth integration (both client-side and backend JWT verification).
- Login / signup page (email+password or GitHub OAuth or both).
- Next.js middleware to redirect unauthenticated users to login.
- Auth context/provider wrapping the app.
- `api.ts` must send `Authorization: Bearer <token>` on every request.
- Backend `get_current_user()` must actually validate the Supabase JWT.
- Settings and other unprotected endpoints need auth guards.

---

### 2. No GitHub App connection flow

**Spec says:** "User installs the GitHub App and selects a repository."

**Backend reality:**
- Webhook handler (`POST /github/webhooks`) receives `installation` events but only logs them — doesn't persist installation IDs or auto-create repos.
- `github/service.py` has `installation_id = 0` hardcoded (line 42). PR creation can never work.
- `POST /repos/connect` exists but requires the caller to already know `github_repo_id` and `org_id` — there's no way to discover repos from a GitHub installation.
- No endpoint to list repos available via a GitHub App installation.
- No endpoint to initiate the GitHub App install/OAuth flow.
- No database model for storing GitHub App installations.

**Frontend reality:**
- Dashboard empty state says "Install the GitHub App to get started" but there's no link, button, or page for that.
- No `/github/install` page that redirects to `github.com/apps/YOUR_APP/installations/new`.
- No `/github/callback` page to handle the redirect back after installation.
- No "connect a repo" modal or page that lists available repos from the installation.
- No way for a user to actually add a repository.

**What's needed:**
- Database model for GitHub App installations (`installations` table with `installation_id`, `account_login`, `user_id`).
- Webhook handler must persist installations and repos on `installation`/`installation_repositories` events.
- Endpoint: `GET /github/installations/{installation_id}/repos` to list repos available to connect.
- Frontend: "Connect Repository" button → redirects to GitHub App install page.
- Frontend: `/github/callback` page that handles redirect, shows available repos, lets user select.
- Store `installation_id` on `Repository` so PR creation can get a real token.

---

### 3. No onboarding / first-run experience

**Spec says:** "No setup. No prompts. No manual configuration. Just: connect your repo → come back later → review real improvements."

**Reality:** A new user hits the homepage → clicks "Get Started" → lands on `/dashboard` → sees "No repositories connected yet" → dead end. There is literally no next step available in the UI.

**What's needed:**
- After login, if user has no org, auto-create one (or prompt).
- Prominent "Connect Repository" CTA on the empty dashboard.
- That CTA either opens the GitHub App install flow or (if already installed) shows a repo picker.
- After connecting a repo, auto-trigger the first baseline run.

---

## Major — App works but key features are broken or missing

### 4. PR creation is completely broken

`github/service.py` hardcodes `owner = "owner"`, `repo_name = "repo"`, `installation_id = 0` (lines 40-42). Even if a user clicks "Create PR", it will fail because:
- No real installation token can be obtained (id is 0).
- Owner/repo are literal strings, not from the database.
- `github_full_name` is available on the Repository model but `service.py` doesn't use it.

**What's needed:**
- Store `installation_id` on Repository.
- Parse `owner`/`repo` from `github_full_name`.
- Use a real installation token flow.

---

### 5. No real-time run status updates

**Spec says:** "Supabase Realtime (for run updates)" in the tech stack.

**Reality:** The repo page fetches run data once via server component. If a user triggers a run, the page shows "Queued" via `TriggerRunButton` state, but:
- There's no polling to update run status (queued → running → completed/failed).
- No Supabase Realtime subscription.
- User must manually refresh the page to see updated status.
- No progress indicator for a running run.

**What's needed (pick one):**
- **Option A:** Supabase Realtime subscription on the `runs` table.
- **Option B:** Client-side polling (simpler) — poll `GET /repos/{repoId}/runs` every N seconds while any run is queued/running.

---

### 6. Frontend API calls will all 401 once auth is real

Every function in `lib/api.ts` calls `apiFetch()` which does a plain `fetch()` with no headers. Once the backend enforces real JWT auth, every single API call will fail.

**What's needed:**
- `apiFetch` must read the Supabase session token and attach `Authorization: Bearer <token>`.
- Handle 401 responses (redirect to login or refresh token).

---

### 7. No user/org management

- No "create organization" flow (the spec has `organizations` table with `owner_id`).
- `POST /repos/connect` requires `org_id` but the user has no way to create or discover their org.
- No profile page, no account settings.

**What's needed (MVP minimum):**
- Auto-create a default org when a user first signs up.
- Alternatively, a simple org creation step in onboarding.
- Backend endpoint or auto-logic to resolve "current user's org" without requiring `org_id` in every request.

---

## Moderate — Functional gaps that degrade the experience

### 8. No "connect repo" page after GitHub App is installed

Even once the GitHub flow exists, there's no UI to:
- See which repos are available from the GitHub installation.
- Select repos to connect.
- See connection status.

---

### 9. Repo detail page doesn't auto-refresh after triggering a run

`TriggerRunButton` shows "Queued" but the runs list below it stays stale. User has to manually reload.

---

### 10. No loading states on server-rendered pages

All pages (dashboard, repo, proposal) catch API errors silently and show empty states. There are:
- No loading skeletons or spinners during data fetch.
- No error states that tell the user what went wrong.
- No retry buttons.

If the API is down, the dashboard just shows "No repositories connected" which is misleading.

---

### 11. Settings page has no auth protection

`GET /repos/{repo_id}/settings` and `PUT /repos/{repo_id}/settings` have no auth dependency. Anyone who guesses a repo UUID can read and modify settings.

---

### 12. `typecheck_cmd` in frontend types but not used

`Repository` interface in `types.ts` has `typecheck_cmd: string | null` but no page displays it. The settings form doesn't let you edit detection commands at all.

---

### 13. No way to manually override detected commands

The spec says: "If test detection fails: Proposal creation disabled until user confirms command."

There's no UI for a user to:
- See what was auto-detected (install/build/test/bench commands).
- Override or confirm detected commands.
- Be warned that detection failed.

---

## Minor — Polish and completeness

### 14. Branding/copy still references old names in docs

`mvp.md` and `technical-mvp.md` still say "SelfOpt" throughout. The `.gitignore` also references `selfopt-*` in temp dir patterns.

---

### 15. No favicon or app icon

Using default Next.js assets. No Coreloop branding in `public/`.

---

### 16. Nav has only "Dashboard" link

No links to: docs, GitHub repo, settings, logout, user profile.

---

### 17. No mobile navigation

Nav hides the "Dashboard" link on mobile (`hidden sm:flex`). On small screens the only navigation is the "Coreloop" logo link.

---

### 18. Homepage "View on GitHub" links to `ayan-goel/evobase`

The GitHub URL in `app/page.tsx` still points to the old repo name.

---

### 19. No Suspense boundaries on client components

Per the project's own coding rules: "Wrap client components in Suspense with fallback." None of the client components (`TriggerRunButton`, `SettingsForm`, `CreatePRButton`, etc.) are wrapped.

---

### 20. No E2E tests

The technical MVP spec requires Playwright E2E tests for: connect repo, view baseline, view proposal, create PR. None exist.

---

## Implementation priority (recommended order)

| Priority | Gap | Why |
|----------|-----|-----|
| P0 | #1 Auth | Nothing works without identity |
| P0 | #2 GitHub App flow | Can't connect repos = app is useless |
| P0 | #3 Onboarding | Dead end after login |
| P0 | #4 Fix PR creation | Core value prop is broken |
| P1 | #6 Auth headers in API client | All calls fail once auth is real |
| P1 | #7 Org management | Required for repo connection |
| P1 | #5 Real-time run updates | Core UX for monitoring runs |
| P1 | #8 Repo picker | Complete the connection flow |
| P2 | #9 Auto-refresh after trigger | Polish |
| P2 | #10 Loading/error states | Polish |
| P2 | #11 Settings auth | Security |
| P2 | #13 Command override UI | Spec compliance |
| P3 | #14-20 | Branding, polish, tests |
