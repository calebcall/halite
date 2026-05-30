# Halite Documentation Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully brand-themed Mintlify documentation site in `docs/` covering every Halite feature (with examples + screenshot placeholders), contributor docs, and a complete API reference auto-generated from the backend's OpenAPI schema.

**Architecture:** A `docs.json`-driven Mintlify site with two tabs (Guides, API Reference). Guide content is hand-authored MDX sourced from `README.md`, `CLAUDE.md`, and the backend/frontend code. The API reference is generated from `app.openapi()` via a new `scripts/gen-openapi.sh` and rendered by Mintlify. Theming matches the brand kit (`logos/brand/`): Halite Amber `#e5a00d`, Plex-dark neutrals, Inter, the Lattice mark.

**Tech Stack:** Mintlify (`mint` CLI via `npx`), MDX + YAML frontmatter, FastAPI `app.openapi()`, Node 26, Python 3.13.

**Source-of-truth files** (read these while authoring — never invent facts):
- `README.md` — feature descriptions, quickstart, curl examples, env notes
- `CLAUDE.md` (repo root) — architecture, commands, conventions
- `.env.example` — full env var list with comments
- `backend/src/halite/<feature>/routes.py` & `schemas.py` — endpoint behavior, request/response shapes
- `logos/brand/README.md` + `logos/brand/tokens/colors.json` — brand values
- Spec: `docs/superpowers/specs/2026-05-30-halite-docs-site-design.md`

**Verification model:** This is a docs site — there are no unit tests. The "test" for each task is that `npx mint dev` starts cleanly and `npx mint broken-links` reports no broken internal links. Run these from inside `docs/`.

---

## Task 1: Scaffold structure, brand assets, theme config

**Files:**
- Create: `docs/logo/lockup-horizontal.svg` (dark-mode logo, copied from brand kit)
- Create: `docs/logo/lockup-horizontal-light.svg` (light-mode variant, dark wordmark text)
- Create: `docs/favicon.svg` (lattice icon, copied from brand kit)
- Create: `docs/style.css` (brand-dark custom CSS)
- Create: `docs/docs.json` (site config + theme + full navigation)
- Create: `docs/README-preview.md` (local preview instructions)
- Create: `.gitignore` entry note (see step 6)

- [ ] **Step 1: Copy brand assets into the docs tree**

```bash
mkdir -p docs/logo
cp logos/brand/lattice/lockup-horizontal.svg docs/logo/lockup-horizontal.svg
cp logos/brand/lattice/icon.svg docs/favicon.svg
```

- [ ] **Step 2: Create the light-mode logo variant**

Copy `docs/logo/lockup-horizontal.svg` to `docs/logo/lockup-horizontal-light.svg`, then in the new file change ONLY the `<text>` element's `fill="#e5a00d"` to `fill="#141414"` (dark wordmark text for light backgrounds; the amber lattice rects stay unchanged). Leave the dark-mode `lockup-horizontal.svg` exactly as copied (amber text reads on dark).

- [ ] **Step 3: Write `docs/style.css`**

```css
/* Halite brand — Plex-dark surfaces + amber accents.
   Brand tokens: logos/brand/tokens/colors.json */
:root {
  --halite-amber: #e5a00d;
  --halite-amber-light: #f5b938;
  --halite-amber-dark: #a77100;
  --halite-black: #0e0e0e;
  --halite-graphite: #141414;
  --halite-onyx: #1f1f1f;
  --halite-slate: #2a2a2a;
  --halite-fog: #999999;
  --halite-bone: #ebebeb;
}

/* Dark-mode surface ramp to match the app's Plex aesthetic. */
.dark body,
html.dark {
  background-color: var(--halite-black);
}

/* Cards / elevated surfaces in dark mode. */
.dark .card,
.dark [class*="rounded"][class*="border"] {
  background-color: var(--halite-onyx);
  border-color: var(--halite-slate);
}

/* Amber accent on inline code in dark mode. */
.dark code {
  color: var(--halite-amber-light);
}

/* Tighten headings to feel native to the Inter wordmark. */
h1, h2, h3 {
  letter-spacing: -0.015em;
}
```

- [ ] **Step 4: Write `docs/docs.json`**

```json
{
  "$schema": "https://mintlify.com/docs.json",
  "theme": "maple",
  "name": "Halite",
  "description": "A modern self-hosted web console for SaltStack.",
  "colors": {
    "primary": "#e5a00d",
    "light": "#f5b938",
    "dark": "#a77100"
  },
  "appearance": { "default": "dark" },
  "background": { "color": { "light": "#ffffff", "dark": "#0e0e0e" } },
  "logo": {
    "light": "/logo/lockup-horizontal-light.svg",
    "dark": "/logo/lockup-horizontal.svg",
    "href": "https://github.com/calebcall/halite"
  },
  "favicon": "/favicon.svg",
  "fonts": { "family": "Inter" },
  "styling": { "codeblocks": "dark" },
  "navigation": {
    "tabs": [
      {
        "tab": "Guides",
        "groups": [
          {
            "group": "Get Started",
            "pages": ["index", "quickstart", "deployment", "configuration"]
          },
          {
            "group": "Concepts",
            "pages": [
              "concepts/how-it-works",
              "concepts/authentication",
              "concepts/rbac",
              "concepts/audit-log"
            ]
          },
          {
            "group": "Features",
            "pages": [
              "features/overview",
              "features/minions",
              "features/keys",
              "features/jobs",
              "features/run",
              "features/templates",
              "features/inventory",
              "features/fleet",
              "features/users-roles",
              "features/audit",
              "features/settings",
              "features/about"
            ]
          },
          {
            "group": "Develop",
            "pages": [
              "develop/architecture",
              "develop/backend",
              "develop/database",
              "develop/frontend",
              "develop/local-development",
              "develop/testing",
              "develop/api-spec"
            ]
          }
        ]
      },
      {
        "tab": "API Reference",
        "groups": [
          {
            "group": "API Reference",
            "pages": ["api/introduction"]
          },
          {
            "group": "Endpoints",
            "openapi": "api/openapi.json"
          }
        ]
      }
    ]
  },
  "navbar": {
    "links": [
      { "label": "GitHub", "href": "https://github.com/calebcall/halite" }
    ]
  },
  "footer": {
    "socials": { "github": "https://github.com/calebcall/halite" }
  }
}
```

- [ ] **Step 5: Write `docs/README-preview.md`**

````markdown
# Previewing the Halite docs locally

```bash
cd docs
npx mint dev        # serves at http://localhost:3000
npx mint broken-links   # validate internal links
```

The API reference renders from `api/openapi.json`. Regenerate that file after
backend schema changes with `../scripts/gen-openapi.sh` (see the "Regenerating
the API spec" page).
````

- [ ] **Step 6: Add a Mintlify ignore entry to `.gitignore`**

Append to the repo-root `.gitignore`:

```
# Mintlify local preview
docs/.mint/
```

- [ ] **Step 7: Create placeholder MDX files so `mint dev` can start**

The `docs.json` references pages that don't exist yet. Create a minimal stub for every page listed in navigation so the build is valid now; later tasks fill them in. For each path below, create the file with this exact frontmatter-only stub (replace `<Title>` with a human title):

Pages to stub: `index`, `quickstart`, `deployment`, `configuration`, `concepts/how-it-works`, `concepts/authentication`, `concepts/rbac`, `concepts/audit-log`, `features/overview`, `features/minions`, `features/keys`, `features/jobs`, `features/run`, `features/templates`, `features/inventory`, `features/fleet`, `features/users-roles`, `features/audit`, `features/settings`, `features/about`, `develop/architecture`, `develop/backend`, `develop/database`, `develop/frontend`, `develop/local-development`, `develop/testing`, `develop/api-spec`, `api/introduction`.

```mdx
---
title: "<Title>"
description: "Placeholder — filled in by a later task."
---

Coming soon.
```

- [ ] **Step 8: Verify the site starts and links resolve**

Run:
```bash
cd docs && npx mint dev
```
Expected: server starts at `http://localhost:3000` with no schema errors. Stop it (Ctrl-C), then:
```bash
cd docs && npx mint broken-links
```
Expected: no broken links (the API endpoints group will be empty until Task 2 — that is fine).

- [ ] **Step 9: Commit**

```bash
git add docs/ .gitignore
git commit -m "docs: scaffold Mintlify site, brand theme, and assets"
```

---

## Task 2: Generate the OpenAPI spec

**Files:**
- Create: `scripts/gen-openapi.sh`
- Create: `docs/api/openapi.json` (generated output, committed)

- [ ] **Step 1: Write `scripts/gen-openapi.sh`**

```sh
#!/usr/bin/env sh
set -eu

# Generate docs/api/openapi.json from the backend's live OpenAPI schema, then
# inject x-mint metadata to disable the interactive playground (Halite is
# self-hosted; there is no public server to call). Mirrors scripts/gen-types.sh.

cd "$(dirname "$0")/.."

SPEC_DB="$(mktemp -t halite-openapi.XXXXXX)"
trap 'rm -f "$SPEC_DB"' EXIT

cd backend
if [ ! -d ".venv" ]; then
  python3.13 -m venv .venv
  . .venv/bin/activate
  pip install --upgrade pip
  pip install -e '.[dev]'
else
  . .venv/bin/activate
fi

DATABASE_URL="sqlite+aiosqlite:///$SPEC_DB" \
COOKIE_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" \
COOKIE_SECURE=false \
PYTHONPATH=src \
python -c "
import json
from halite.config import Settings
from halite.auth.cookies import CookieCodec
from halite.main import create_app

settings = Settings()
app = create_app(settings=settings, codec=CookieCodec(settings.cookie_secret))
spec = app.openapi()
# Disable Mintlify's interactive playground (no public server to call);
# request/response examples still render.
spec['x-mint'] = {'metadata': {'playground': 'none'}}
print(json.dumps(spec, indent=2))
" > ../docs/api/openapi.json

echo "Wrote docs/api/openapi.json"
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/gen-openapi.sh
```

- [ ] **Step 3: Run it to produce the spec**

Run:
```bash
./scripts/gen-openapi.sh
```
Expected: prints `Wrote docs/api/openapi.json`. (First run installs the backend venv — may take a minute.)

- [ ] **Step 4: Sanity-check the generated spec**

Run:
```bash
python3 -c "import json; d=json.load(open('docs/api/openapi.json')); print(len(d['paths']), 'paths'); print(sorted({t for p in d['paths'].values() for op in p.values() if isinstance(op,dict) for t in op.get('tags',[])}))"
```
Expected: a non-zero path count and the tag list including `auth`, `minions`, `keys`, `jobs`, `run`, `inventory`, `fleet`, `templates`, `salt-docs`, `users`, `roles`, `audit`, `settings`.

- [ ] **Step 5: Verify the API reference renders**

Run `cd docs && npx mint dev`, open `http://localhost:3000`, switch to the API Reference tab, confirm endpoint pages render grouped by tag and the playground "Try it" control is absent. Stop the server.

- [ ] **Step 6: Commit**

```bash
git add scripts/gen-openapi.sh docs/api/openapi.json
git commit -m "docs: generate committed OpenAPI spec for API reference"
```

---

## Task 3: Get Started pages

**Files:**
- Modify: `docs/index.mdx`, `docs/quickstart.mdx`, `docs/deployment.mdx`, `docs/configuration.mdx`

Authoring rules for every content page (Tasks 3–8):
- Keep the `title` + `description` frontmatter; write `description` as a concise SEO summary.
- Second-person voice. Language tags on every code block. Relative internal links (e.g. `/features/run`).
- Image placeholders use this exact pattern (maintainer fills the `src` later):
  ```mdx
  <Frame caption="<describe the screenshot>">
    <img src="/images/<page>-<thing>.png" alt="<descriptive alt text>" />
  </Frame>
  ```
- Use Mintlify components where they help: `<Card>`/`<CardGroup>`, `<Steps>`/`<Step>`, `<Tabs>`/`<Tab>`, `<Note>`, `<Warning>`, `<Tip>`, `<ParamField>`/`<ResponseField>`.

- [ ] **Step 1: Write `docs/index.mdx` (Introduction / landing)**

Frontmatter: `title: "Halite"`, `description: "A modern self-hosted web console for SaltStack."`

Content (source: `README.md` Features + Why halite sections):
- One-paragraph intro: Halite is a self-hosted web console that manages a SaltStack deployment end-to-end from one UI.
- The lattice metaphor (1–2 sentences, from README "Why halite"): NaCl unit cell ↔ Salt master + minions.
- A `<CardGroup cols={2}>` of `<Card>`s linking to the main feature pages (Overview `/features/overview`, Minions `/features/minions`, Keys `/features/keys`, Jobs `/features/jobs`, Run `/features/run`, Inventory `/features/inventory`, Fleet `/features/fleet`, Users & Roles `/features/users-roles`), each with a `lucide`-style icon name (e.g. `icon="gauge"`, `icon="server"`, `icon="key"`).
- A `<Card horizontal icon="rocket" href="/quickstart">` get-started call to action.
- One `<Frame>` placeholder for a dashboard hero screenshot.

- [ ] **Step 2: Write `docs/quickstart.mdx`**

Frontmatter: `title: "Quickstart"`, `description: "Run Halite locally with Docker in a few minutes."`

Content (source: `README.md` "Quick start (Docker)"):
- `<Note>` prerequisites: Docker + Docker Compose, a reachable salt-api (`rest_cherrypy`) endpoint (optional for first boot — the UI runs without it and degrades gracefully).
- A `<Steps>` block:
  1. Clone + `cp .env.example .env`
  2. `./scripts/gen-bootstrap-secret.sh` → paste into `COOKIE_SECRET`
  3. Choose a profile via `<Tabs>`: **SQLite (homelab)** — flip `DATABASE_URL` to the `sqlite+aiosqlite:////data/halite.db` line, run `docker compose -f compose.sqlite.yml up --build`; **Postgres** — keep default `DATABASE_URL`, run `docker compose -f compose.yml up --build`.
  4. Browse to `http://localhost:8080/`, sign in `admin` / `changeme`.
- A "Verify without the browser" section with the three README curl examples (login → `/api/auth/me` → `/api/audit?limit=10`), each in a `bash` code block.
- `<Warning>` change the bootstrap admin password and set `COOKIE_SECURE=true` in production.
- Next-steps `<CardGroup>` linking `/configuration` and `/features/settings`.

- [ ] **Step 3: Write `docs/deployment.mdx`**

Frontmatter: `title: "Installation & Deployment"`, `description: "Deploy Halite with Postgres or SQLite, behind a TLS proxy."`

Content (source: `compose.yml`, `compose.sqlite.yml`, `Dockerfile`, `.env.example`, `README.md`):
- Read `compose.yml`, `compose.sqlite.yml`, and `Dockerfile` first; describe the two profiles accurately (services, volumes, ports — do not invent).
- `<Tabs>`: Postgres profile vs SQLite homelab profile — what each brings up and when to pick it.
- The single Docker image serves the built SPA + API on `LISTEN_PORT` (default 8080).
- TLS / reverse proxy section: set `COOKIE_SECURE=true` behind HTTPS; `TRUSTED_PROXIES` for forwarded-for handling.
- `<Note>` on `BUILD_HASH` shown in the sidebar footer (source: recent git commits about BUILD_HASH) — optional, only if confirmed in the Dockerfile/compose.
- Link to `/configuration` for the full env reference.

- [ ] **Step 4: Write `docs/configuration.mdx`**

Frontmatter: `title: "Configuration"`, `description: "Environment variables and in-app Salt-API settings."`

Content (source: `.env.example` verbatim semantics + `backend/src/halite/config.py` + `backend/src/halite/settings/`):
- Section "Environment variables" — a table or `<ParamField>` list covering every var in `.env.example`: `DATABASE_URL`, `COOKIE_SECRET`, `SESSION_TTL_MINUTES`, `COOKIE_SECURE`, `INVENTORY_REFRESH_MINUTES`, `INVENTORY_REFRESH_INITIAL_DELAY_S`, `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_PASSWORD`, `LISTEN_HOST`, `LISTEN_PORT`, `TRUSTED_PROXIES`, `LOG_LEVEL`, `LOG_FORMAT`. Use each var's `.env.example` comment as its description.
- `<Note>` clarifying the Salt-API connection is **not** set via env in current builds — it lives in the in-app Settings (DB-backed, password encrypted at rest). Cross-link `/features/settings` and `/concepts/how-it-works`.
- Section "Inventory background scheduler" — explain `INVENTORY_REFRESH_MINUTES` (0 disables) and the initial delay.

- [ ] **Step 5: Verify and commit**

```bash
cd docs && npx mint broken-links
```
Expected: no broken links. Then:
```bash
git add docs/index.mdx docs/quickstart.mdx docs/deployment.mdx docs/configuration.mdx
git commit -m "docs: write Get Started pages"
```

---

## Task 4: Concepts pages

**Files:**
- Modify: `docs/concepts/how-it-works.mdx`, `docs/concepts/authentication.mdx`, `docs/concepts/rbac.mdx`, `docs/concepts/audit-log.mdx`

Follow the Task 3 authoring rules.

- [ ] **Step 1: Write `docs/concepts/how-it-works.mdx`**

Frontmatter: `title: "How Halite Works"`, `description: "The poll-into-DB architecture and graceful degradation."`

Content (source: `CLAUDE.md` Architecture, `backend/src/halite/runtime.py`, `backend/src/halite/salt/client.py`, `backend/src/halite/<feature>/ingest.py`):
- The master/minion topology and where Halite sits (talks to `salt-api`'s `rest_cherrypy`).
- The **poll-into-DB / serve-from-DB** model: background schedulers poll Salt → ingest into snapshot/index tables → routes serve from the DB. Why: Salt-API is slow and sometimes unavailable.
- **Graceful degradation**: if no Salt credentials are stored, the client is `None`, schedulers are off, and salt-backed endpoints return 503 / empty data instead of crashing.
- Live calls are reserved for actions (Run, key accept/reject, kill job).
- A simple diagram: use a `mermaid` code block (`flowchart`) showing Salt master → salt-api → Halite schedulers → DB snapshots → API/UI.

- [ ] **Step 2: Write `docs/concepts/authentication.mdx`**

Frontmatter: `title: "Authentication & Sessions"`, `description: "Signed-cookie sessions and the bootstrap admin."`

Content (source: `backend/src/halite/auth/`, `backend/src/halite/deps.py`, `.env.example`):
- Signed-cookie sessions (itsdangerous), Argon2 password hashing.
- `SESSION_TTL_MINUTES` controls session lifetime; `COOKIE_SECURE` gates HTTPS-only cookies.
- Bootstrap admin: `BOOTSTRAP_ADMIN_USERNAME`/`PASSWORD` honored only when no users exist.
- Login flow: `POST /api/auth/login` sets the cookie; `GET /api/auth/me` returns the current user; logout endpoint. Cross-link `/api/introduction`.
- `<Warning>` on changing default credentials.

- [ ] **Step 3: Write `docs/concepts/rbac.mdx`**

Frontmatter: `title: "RBAC & Permissions"`, `description: "Roles, verb:resource permission globs, and how checks resolve."`

Content (source: `backend/src/halite/rbac/engine.py`, `rbac/seed.py`, `deps.py`):
- Permissions are `(verb, resource_glob)` pairs attached to roles; a user accumulates the union across their roles.
- Globs are anchored shell-style (`*`, `?`), `:` as namespace separator (examples: `key:web-*`, `minion:db-*`). `check()` returns true iff at least one permission matches both verb and resource.
- Built-in roles `admin` / `operator` / `viewer` (describe each from `rbac/seed.py` — read it; list the actual seeded permissions, do not guess) plus arbitrary custom roles.
- Inactive users always fail the check.
- A worked example table: a few `verb` + `resource` requests and whether `operator` passes.
- Cross-link `/features/users-roles`.

- [ ] **Step 4: Write `docs/concepts/audit-log.mdx`**

Frontmatter: `title: "Audit Logging"`, `description: "Every authorization decision is recorded."`

Content (source: `backend/src/halite/audit/`):
- Every authorization decision is written to the DB audit log (read `audit/writer.py` and `audit/models.py` for the captured fields — list the real columns).
- Queryable/paginated at `/api/audit`. Cross-link `/features/audit`.

- [ ] **Step 5: Verify and commit**

```bash
cd docs && npx mint broken-links
git add docs/concepts/
git commit -m "docs: write Concepts pages"
```

---

## Task 5: Feature pages (set A: overview, minions, keys, jobs, run, templates)

**Files:**
- Modify: `docs/features/overview.mdx`, `docs/features/minions.mdx`, `docs/features/keys.mdx`, `docs/features/jobs.mdx`, `docs/features/run.mdx`, `docs/features/templates.mdx`

Per-page rule: each page MUST include (a) what it does, (b) how to use it (steps), (c) at least one example, (d) a "Permissions required" `<Note>` naming the RBAC `verb:resource` (read the feature's `routes.py` `require_perm(...)` calls for exact values — do not guess), (e) at least one `<Frame>` screenshot placeholder. Source descriptions from `README.md` Features + the feature's `routes.py`/`service.py`/`schemas.py`.

- [ ] **Step 1: Write `docs/features/overview.mdx`**

`title: "Overview"`, `description: "Dashboard KPIs and fleet activity charts."`
Content (source: README + `backend/src/halite/minions`,`jobs`,`keys` + `frontend/src/features/overview`): the four KPIs (online minions, pending keys, running jobs, jobs in 24h), the three charts (minion-status donut, 24h job-activity area, key-status bar), server-side bucketing on the activity endpoint, 30s auto-refresh. Screenshot placeholder of the dashboard.

- [ ] **Step 2: Write `docs/features/minions.mdx`**

`title: "Minions"`, `description: "Live minion status and grains."`
Content: live status of connected minions, grains drill-down on demand. How to open a minion and inspect grains. Note minion data is served from the snapshot table (cross-link `/concepts/how-it-works`). Permissions from `minions/routes.py`. Screenshot placeholder.

- [ ] **Step 3: Write `docs/features/keys.mdx`**

`title: "Keys"`, `description: "Accept, reject, or delete minion keys."`
Content: key states (accepted/pending/rejected/denied — confirm against `keys/`/`minions/ingest.py` `_KEY_STATUS_BY_BUCKET`), accept/reject/delete actions and what each does on the master, a `<Steps>` walkthrough of accepting a pending key. `<Warning>` deleting a key. Permissions from `keys/routes.py`. Screenshot placeholder.

- [ ] **Step 4: Write `docs/features/jobs.mdx`**

`title: "Jobs"`, `description: "Browse jobs, inspect results, and kill running jobs."`
Content: browse recent jobs (served from the jobs index), open a job to see per-minion results, highstate parsing of results, kill a running job mid-flight. Mention the jobs index lookback/ingest window only if relevant. Permissions from `jobs/routes.py`. Screenshot placeholders (job list + job detail).

- [ ] **Step 5: Write `docs/features/run.mdx`**

`title: "Run"`, `description: "Dispatch Salt execution-module functions against any target."`
Content (source: `run/schemas.py`, `run/routes.py`, `salt_docs/`): dispatch any `module.function` against a target. Document the six target types from `TargetType`: `glob`, `list`, `pcre`, `grain`, `nodegroup`, `compound` (one line each). `fun` must be `module.function`. `args` (list) and `kwargs` (object). The function catalog/autocomplete comes from salt-docs. A worked example: run `test.ping` against `glob` `*`, and `pkg.version` with an arg. Returns `{ jid, minions }`. Cross-link `/features/templates` and the API page. Permissions from `run/routes.py`. Screenshot placeholder.

- [ ] **Step 6: Write `docs/features/templates.mdx`**

`title: "Command Templates"`, `description: "Save and share reusable Run commands."`
Content (source: `templates/routes.py`,`schemas.py`): save a Run command as a template, the `is_shared` flag (shared vs personal), list/create/update/delete. How a template prefills the Run form. Permissions from `templates/routes.py`. Screenshot placeholder.

- [ ] **Step 7: Verify and commit**

```bash
cd docs && npx mint broken-links
git add docs/features/overview.mdx docs/features/minions.mdx docs/features/keys.mdx docs/features/jobs.mdx docs/features/run.mdx docs/features/templates.mdx
git commit -m "docs: write feature pages (overview, minions, keys, jobs, run, templates)"
```

---

## Task 6: Feature pages (set B: inventory, fleet, users-roles, audit, settings, about)

**Files:**
- Modify: `docs/features/inventory.mdx`, `docs/features/fleet.mdx`, `docs/features/users-roles.mdx`, `docs/features/audit.mdx`, `docs/features/settings.mdx`, `docs/features/about.mdx`

Same per-page rule as Task 5.

- [ ] **Step 1: Write `docs/features/inventory.mdx`**

`title: "Inventory"`, `description: "Package inventory across the fleet."`
Content (source: `inventory/routes.py`,`service.py`,`scheduler.py`): 3-level drill-down (package → versions → installed-on, or minion → packages), manual refresh vs the background scheduler (`INVENTORY_REFRESH_MINUTES`), version comparison. Cross-link `/configuration`. Permissions from `inventory/routes.py`. Screenshot placeholder.

- [ ] **Step 2: Write `docs/features/fleet.mdx`**

`title: "Fleet Health"`, `description: "Highstate compliance and fleet health."`
Content (source: `fleet/routes.py`,`service.py`,`parser.py`): fleet health endpoint, compliance over time series, top failures, per-run detail. Health statuses and the `_STALE_AFTER` (2 days) staleness rule — read `fleet/service.py` for the real status values. How highstate runs are ingested/parsed. Permissions from `fleet/routes.py`. Screenshot placeholder.

- [ ] **Step 3: Write `docs/features/users-roles.mdx`**

`title: "Users & Roles"`, `description: "Manage users, roles, and permissions."`
Content (source: `users/routes.py`, `roles/routes.py`, `rbac/`): create/manage users, assign roles, create custom roles with `verb:resource` permissions, password reset/change. Cross-link `/concepts/rbac`. Permissions from the routes. Screenshot placeholders (user list + role editor).

- [ ] **Step 4: Write `docs/features/audit.mdx`**

`title: "Audit Log"`, `description: "Query the authorization audit trail."`
Content (source: `audit/routes.py`): browse/paginate/query the audit log, the filters available (read `audit/routes.py` query params). Cross-link `/concepts/audit-log`. Permissions from the route. Screenshot placeholder.

- [ ] **Step 5: Write `docs/features/settings.mdx`**

`title: "Settings"`, `description: "Configure the Salt-API connection and pollers."`
Content (source: `settings/routes.py`,`schemas.py`,`service.py`, `runtime.py`): the in-app admin Settings — Salt-API URL, eauth, service username/password (encrypted at rest via `settings/crypto.py`), TLS verify, per-group poller toggles. Saving rewires the live client + schedulers (`runtime.reload`) with no restart. `<Warning>` admin-only. Permissions from `settings/routes.py`. Screenshot placeholder.

- [ ] **Step 6: Write `docs/features/about.mdx`**

`title: "About"`, `description: "The in-app colophon and brand story."`
Content (source: README "Why halite", `frontend/src/features/about`, `logos/brand/`): the `/about` page shows the brand kit, palette, and project story. Briefly describe what's there and the halite/NaCl metaphor. Screenshot placeholder of the colophon.

- [ ] **Step 7: Verify and commit**

```bash
cd docs && npx mint broken-links
git add docs/features/inventory.mdx docs/features/fleet.mdx docs/features/users-roles.mdx docs/features/audit.mdx docs/features/settings.mdx docs/features/about.mdx
git commit -m "docs: write feature pages (inventory, fleet, users-roles, audit, settings, about)"
```

---

## Task 7: Develop (contributor) pages

**Files:**
- Modify: `docs/develop/architecture.mdx`, `docs/develop/backend.mdx`, `docs/develop/database.mdx`, `docs/develop/frontend.mdx`, `docs/develop/local-development.mdx`, `docs/develop/testing.mdx`, `docs/develop/api-spec.mdx`

Primary source: repo-root `CLAUDE.md` (it already distills the architecture). Cross-check against the code it references. Follow Task 3 authoring rules; these pages are text-heavy and need no screenshots.

- [ ] **Step 1: Write `docs/develop/architecture.mdx`**

`title: "Architecture"`, `description: "Backend/frontend split and the RuntimeConfig hub."`
Content (source: `CLAUDE.md` Architecture): big picture — FastAPI backend + React SPA in one Docker image; RuntimeConfig owns the salt client + schedulers; the two settings systems (env `Settings` vs DB `AppSettings`). Reuse the `mermaid` flow from `/concepts/how-it-works` or link to it.

- [ ] **Step 2: Write `docs/develop/backend.mdx`**

`title: "Backend"`, `description: "Feature modules, RuntimeConfig, SaltAPIClient, schedulers."`
Content (source: `CLAUDE.md` + `backend/src/halite/`): the self-contained feature-module shape (`routes`/`service`/`schemas`/`models` + `ingest`/`scheduler`), `RuntimeConfig` boot/reload/teardown, `SaltAPIClient` (lazy login, lock-guarded refresh, retries, `SaltAPIError`/`SaltAPIUnavailable`), `salt_client_or_503` + `wrap_salt_errors`. `require_perm` usage. Use a file-tree snippet of one feature module.

- [ ] **Step 3: Write `docs/develop/database.mdx`**

`title: "Database & Migrations"`, `description: "Dual-backend portability and Alembic."`
Content (source: `CLAUDE.md` + `backend/src/halite/db_dialect.py`, `backend/alembic/`): Postgres + SQLite support, the `db_dialect.py` portability helpers (`lower_eq`), Alembic migration workflow (`alembic upgrade head`, `alembic revision -m`), the dated migration filename convention.

- [ ] **Step 4: Write `docs/develop/frontend.mdx`**

`title: "Frontend"`, `description: "React 19, TanStack, shadcn/ui, generated API types."`
Content (source: `CLAUDE.md` + `frontend/`): React 19 + TanStack Router/Query, 30s refresh on list views, shadcn/ui + Radix + Tailwind, Recharts lazy chunk, feature-folder layout, the **generated** `shared/api` types (regenerate via `gen-types.sh` — never hand-edit).

- [ ] **Step 5: Write `docs/develop/local-development.mdx`**

`title: "Local Development"`, `description: "Run the backend and frontend locally."`
Content (source: `README.md` Development + `CLAUDE.md` Commands + `scripts/dev.sh`): backend venv + `../scripts/dev.sh` (throwaway SQLite, reload, :8080); frontend `npm install` + `npm run dev` (:5173, proxies `/api`); regenerate types with `./scripts/gen-types.sh`. Use a two-tab `<Tabs>` (Backend / Frontend) and a `<Note>` about running both terminals.

- [ ] **Step 6: Write `docs/develop/testing.mdx`**

`title: "Testing"`, `description: "pytest dual-backend, vitest, lint, build."`
Content (source: `CLAUDE.md` Commands + `backend/tests/conftest.py`): `pytest -v` (SQLite) and `HALITE_TEST_PG=1 pytest -v` (adds Postgres via testcontainers); single-file and single-test invocations; why DB fixtures are sync (alembic `env.py` uses `asyncio.run()`); `ruff check`/`ruff format`; frontend `npm test` + `npm run build`; `npm run lint`.

- [ ] **Step 7: Write `docs/develop/api-spec.mdx`**

`title: "Regenerating the API spec"`, `description: "Keep the API reference in sync with the backend."`
Content: run `./scripts/gen-openapi.sh` after changing backend Pydantic schemas/routes; it boots the app against a throwaway SQLite DB, dumps `app.openapi()`, injects the `x-mint` playground-off metadata, and writes `docs/api/openapi.json`. Commit the regenerated file. Note the relationship to `gen-types.sh` (frontend types from the same schema).

- [ ] **Step 8: Verify and commit**

```bash
cd docs && npx mint broken-links
git add docs/develop/
git commit -m "docs: write contributor (Develop) pages"
```

---

## Task 8: API introduction page

**Files:**
- Modify: `docs/api/introduction.mdx`

- [ ] **Step 1: Write `docs/api/introduction.mdx`**

Frontmatter: `title: "API Overview"`, `description: "Authenticate and call the Halite API."`

Content (source: `README.md` curl examples + `backend/src/halite/auth/routes.py`, `deps.py`, `salt/deps.py`):
- All endpoints live under `/api`. Authentication is a signed session cookie obtained from `POST /api/auth/login`.
- A `bash` example: login (`-c cookies.txt`), then call `GET /api/auth/me` and `GET /api/audit?limit=10` with `-b cookies.txt` (the three README examples).
- Error conventions: `401` (not authenticated / expired), `403` (lacks the required `verb:resource` permission), `503` (Salt-API not configured/unreachable), `502` (Salt-API returned an error — message extracted from the CherryPy/JSON body). Source: `salt/deps.py` `wrap_salt_errors`.
- `<Note>` the interactive playground is disabled because Halite is self-hosted; use the curl examples against your own instance. Cross-link `/concepts/authentication` and `/concepts/rbac`.
- Point to the Endpoints group in the sidebar for the full reference.

- [ ] **Step 2: Verify and commit**

```bash
cd docs && npx mint broken-links
git add docs/api/introduction.mdx
git commit -m "docs: write API overview page"
```

---

## Task 9: Final verification

- [ ] **Step 1: Full link check**

Run:
```bash
cd docs && npx mint broken-links
```
Expected: no broken links.

- [ ] **Step 2: Confirm no placeholder stubs remain**

Run:
```bash
grep -rl "Coming soon." docs --include=*.mdx
```
Expected: no output (every stub from Task 1 has been filled in).

- [ ] **Step 3: Dev render smoke test**

Run `cd docs && npx mint dev`, then manually confirm: dark theme with amber accents, Lattice logo in the header, favicon present, all four Guide groups populated, the API Reference tab lists endpoints grouped by tag with no "Try it" playground. Stop the server.

- [ ] **Step 4: Confirm frontmatter on every page**

Run:
```bash
for f in $(find docs -name '*.mdx'); do head -1 "$f" | grep -q '^---$' || echo "MISSING FRONTMATTER: $f"; done
```
Expected: no output.

- [ ] **Step 5: Final commit (if anything changed)**

```bash
git add docs/
git commit -m "docs: final verification pass for Mintlify site" || echo "nothing to commit"
```

---

## Self-review notes

- **Spec coverage:** Get Started (Task 3), Concepts (Task 4), all 12 Features (Tasks 5–6), Develop (Task 7), API auto-gen + intro (Tasks 2, 8), theming + assets + logo variant (Task 1), `gen-openapi.sh` (Task 2), local-preview README (Task 1). All spec sections map to a task.
- **Accuracy guard:** every content task names the exact source files to read and forbids inventing `require_perm` values, role permissions, status enums, and audit fields — the engineer reads the code for those.
- **Screenshots:** handled as `<Frame>` placeholders with alt text; maintainer fills `src` later (Task 3 authoring rule).
- **Verification:** docs have no unit tests; `mint dev` + `mint broken-links` + frontmatter/stub greps are the gates.
