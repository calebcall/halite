# Halite Documentation Site — Design

**Date:** 2026-05-30
**Status:** Approved (pending spec review)
**Branch:** `docs/mintlify-site`

## Goal

A gorgeous, fully brand-themed [Mintlify](https://mintlify.com/docs) documentation site living in `docs/`, covering:

- Every Halite feature, with usage instructions and examples (screenshots added later by the maintainer).
- A complete API reference, auto-generated from the backend's OpenAPI schema.
- Contributor/developer documentation derived from the codebase architecture.
- Theming that matches the Halite brand kit (Halite Amber `#e5a00d`, Plex-dark neutrals, Inter, the Lattice mark).

## Decisions (from brainstorming)

| Decision | Choice |
| --- | --- |
| Audience | Operators **and** contributors (developer section included) |
| API reference | Auto-generated from OpenAPI; interactive playground disabled |
| Logo mark | Lattice (horizontal lockup header, lattice icon favicon) |
| Hosting | Repo source + local preview (`mint dev`); no CI added now |
| Screenshots | Maintainer adds them; guides ship text-complete with marked image placeholders |
| Git | Branch `docs/mintlify-site`; root `CLAUDE.md` from `/init` committed first |

## Non-goals

- Deploying to Mintlify's hosted platform (maintainer connects the repo later).
- CI / GitHub Actions (explicitly deferred).
- Generating real UI screenshots (no live Salt master available).
- Any change to backend or frontend application code. The only repo-level addition outside `docs/` is one script: `scripts/gen-openapi.sh`.

## Site structure

Two tabs in `docs.json` navigation.

### Tab: Guides

**Group — Get Started**
- `index` — Introduction / landing (what Halite is, the master/minion + lattice metaphor, feature overview cards)
- `quickstart` — Docker quickstart (the README's copy/paste path, both profiles)
- `deployment` — Installation & deployment: Postgres profile (`compose.yml`) vs SQLite homelab profile (`compose.sqlite.yml`), the Dockerfile, `COOKIE_SECRET`/`COOKIE_SECURE`, reverse-proxy/TLS notes, `TRUSTED_PROXIES`
- `configuration` — Environment variables (full `.env.example` reference table) **and** the in-app Salt-API connection settings (URL, eauth, service credentials, encrypted at rest), inventory scheduler knobs

**Group — Concepts**
- `concepts/how-it-works` — The poll-into-DB model: schedulers poll Salt-API, ingest into snapshot/index tables, routes serve from the DB; graceful degradation when Salt is unconfigured/unavailable
- `concepts/authentication` — Signed-cookie sessions, Argon2, session TTL, bootstrap admin
- `concepts/rbac` — `verb:resource` permission globs, built-in `admin`/`operator`/`viewer` roles, custom roles, how checks resolve
- `concepts/audit-log` — Every authorization decision is recorded; what's captured

**Group — Features** (one page each: purpose, how to use, examples, permissions required, image placeholders)
- `features/overview` — Dashboard KPIs + the three charts, 24h activity bucketing, 30s refresh
- `features/minions` — Live minion status, grains drill-down
- `features/keys` — Accept / reject / delete pending keys
- `features/jobs` — Browse jobs, per-minion results, highstate parsing, kill running jobs
- `features/run` — Dispatch execution-module functions, target types, function catalog (salt-docs autocomplete)
- `features/templates` — Saved/shareable command templates for the Run page
- `features/inventory` — Package inventory 3-level drill-down, background refresh scheduler
- `features/fleet` — Fleet health & highstate compliance: per-minion health, compliance over time, top failures, run detail
- `features/users-roles` — Managing users, assigning roles, custom roles & permissions
- `features/audit` — Querying the audit log
- `features/settings` — In-app Salt-API connection + poller toggles (admin)
- `features/about` — The in-app colophon / brand story

**Group — Develop** (contributor docs, sourced from `CLAUDE.md` + code)
- `develop/architecture` — Big picture: backend/frontend split, single Docker image, RuntimeConfig as hub
- `develop/backend` — Feature-module shape (`routes`/`service`/`schemas`/`models` + `ingest`/`scheduler`), RuntimeConfig wiring/reload, SaltAPIClient (lazy login, retries, error translation), schedulers
- `develop/database` — Dual-backend (Postgres + SQLite), `db_dialect.py` portability, Alembic migrations, dual-backend test fixtures
- `develop/frontend` — React 19 + TanStack Router/Query, shadcn/ui, generated API types, feature-folder layout
- `develop/local-development` — venv + `dev.sh`, frontend `npm run dev`, ports/proxy
- `develop/testing` — pytest (SQLite + `HALITE_TEST_PG=1`), single-test invocation, vitest, `npm run build`, ruff
- `develop/api-spec` — Regenerating `openapi.json` via `scripts/gen-openapi.sh` after schema changes

### Tab: API Reference

- `api/introduction` — Auth model (POST `/api/auth/login` → cookie; `/api/auth/me`), error conventions (401 unauth, 403 forbidden, 502/503 Salt degradation), curl examples (from the README)
- Auto-generated endpoint pages from `docs/api/openapi.json`, grouped by the 13 OpenAPI tags: `auth`, `minions`, `keys`, `jobs`, `run`, `inventory`, `fleet`, `templates`, `salt-docs`, `users`, `roles`, `audit`, `settings`.

## Theming

All values from `logos/brand/tokens/colors.json`.

```jsonc
// docs.json (excerpt)
{
  "theme": "maple",                       // clean, content-forward preset
  "name": "Halite",
  "colors": {
    "primary": "#e5a00d",                 // Halite Amber
    "light":   "#f5b938",                 // amber-light (dark-mode legibility)
    "dark":    "#a77100"                  // amber-dark
  },
  "appearance": { "default": "dark" },    // brand reads strongest on dark
  "background": { "color": { "light": "#ffffff", "dark": "#0e0e0e" } },
  "logo": {
    "light": "/logo/lockup-horizontal-dark-text.svg",
    "dark":  "/logo/lockup-horizontal.svg",
    "href":  "https://github.com/calebcall/halite"
  },
  "favicon": "/favicon.svg",              // lattice icon
  "fonts": { "family": "Inter" },         // matches wordmark + app body font
  "styling": { "codeblocks": "dark" }
}
```

- **Custom CSS** (`docs/style.css`, auto-loaded by Mintlify): push the Plex-dark neutral surface ramp (`#0e0e0e` → `#141414` → `#1f1f1f` → `#2a2a2a`), card/border tones, amber accent on links/active-nav, and Inter tuning — to take the dark theme beyond what `docs.json` exposes natively.
- **Assets**: copy the Lattice horizontal lockup SVG and lattice `icon.svg` (favicon) from `logos/brand/` into `docs/logo/`. The existing lockup is amber-on-transparent (works on dark backgrounds); for the light-mode logo slot, produce a variant with dark wordmark text (the amber lattice icon stays).
- Playground disabled: the generated `openapi.json` is post-processed to add `x-mint` metadata setting the playground to `none` (no public server to call); request/response **examples** still render.

## API generation workflow

New script `scripts/gen-openapi.sh` (mirrors the existing `scripts/gen-types.sh`):

1. Ensure backend venv (or instruct: `pip install -e '.[dev]'`).
2. Boot the app against a throwaway SQLite DB with a generated `COOKIE_SECRET` and dump `app.openapi()` to JSON.
3. Post-process: inject top-level `x-mint` (playground `none`) and write to `docs/api/openapi.json`.

The committed `docs/api/openapi.json` is what Mintlify renders. `develop/api-spec` documents re-running the script after backend schema changes. **The script will be run once during implementation to produce the committed spec** — so the API reference reflects the real, current schema rather than hand-typed endpoints.

## Files created

```
docs/
├── docs.json                     # site config + navigation + theme
├── style.css                     # brand-dark custom CSS
├── favicon.svg                   # lattice icon
├── logo/
│   ├── lockup-horizontal.svg              # dark-mode (amber on transparent)
│   └── lockup-horizontal-dark-text.svg    # light-mode variant
├── index.mdx                     # landing / introduction
├── quickstart.mdx
├── deployment.mdx
├── configuration.mdx
├── concepts/{how-it-works,authentication,rbac,audit-log}.mdx
├── features/{overview,minions,keys,jobs,run,templates,inventory,fleet,users-roles,audit,settings,about}.mdx
├── develop/{architecture,backend,database,frontend,local-development,testing,api-spec}.mdx
├── api/
│   ├── introduction.mdx
│   └── openapi.json              # generated, committed
├── README-preview.md             # how to run `mint dev`
└── CLAUDE.md                     # existing — unchanged

scripts/gen-openapi.sh            # new
```

## Content principles

- Accurate to the code — no invented endpoints, options, or behavior. Where the README hedged ("used in later plans"), document the live in-app Settings flow that the code implements.
- Second-person voice; prerequisites first; language tags on all code blocks; relative internal links; alt text on every image placeholder (per `docs/CLAUDE.md` standards).
- Image placeholders use Mintlify `<Frame>` with a descriptive caption and a clearly-marked TODO path so the maintainer can drop screenshots in.
- Each feature page notes the RBAC permission(s) required to use it.

## Verification

- `npx mint dev` (or `mint dev`) renders the site locally with no broken-link / schema warnings.
- `npx mint broken-links` passes.
- `docs/api/openapi.json` is valid and produced by the real app (not hand-authored).
- Spot-check: every navigation entry resolves to an existing MDX file; theme renders dark with amber accents and the Lattice logo.

## Open risks

- Mintlify's exact custom-CSS auto-load behavior and the `x-mint` playground key are version-sensitive; if a key is rejected at `mint dev` time, fall back to the documented alternative (e.g., per-operation playground control) and note it.
- The light-mode dark-text logo variant must be produced from the existing SVG; if that proves fiddly, fall back to using the amber lockup in both slots (it remains legible on Mintlify's light background).
