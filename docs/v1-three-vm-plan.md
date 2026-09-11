# Plan — v1 on three VMs: `frontend`, `backend`, `db`

**Branch:** `infra/three-vm-v1`, cut from `frontend/v1-pages` (that branch already
contains the web-provisioning work; `main` is behind it at `0094bfd`).
**Goal:** from a fresh clone, one `vagrant up` brings up three VMs, and
`http://localhost:8000` is a working app with two seeded accounts, ten days of
dose history, notes, and a live Day-curve page — no manual step anywhere.
**Written:** 2026-09-11, against `bf2cc16`.

This replaces the current `db` / `pk` / `web` layout. The pk maths stops being a
separate VM and HTTP service and becomes a plain Python package inside the Django
backend. The Vue SPA gets its own VM with nginx, and talks to the backend VM over
the host-only network.

---

## 1. Target architecture

```
 host browser ──► http://localhost:8000
                        │  (VirtualBox port forward 8000 → 80)
                        ▼
   ┌──────────────────────────────────┐
   │ frontend  192.168.56.12          │   bento/ubuntu-24.04, 2048 MB (only for the vite build)
   │   nginx :80                      │
   │     /            → Vue SPA dist  │
   │     /api/ /auth/ /admin/ /static/│──────────────┐  proxy_pass
   └──────────────────────────────────┘              ▼
                                  ┌──────────────────────────────────┐
                                  │ backend  192.168.56.11           │  bento/ubuntu-24.04, 1024 MB
                                  │   gunicorn :8000  (Django 6.1)   │
                                  │     tracker/  users/  pk/        │  pk = in-process Bateman maths
                                  │     whitenoise serves /static/   │
                                  └──────────────┬───────────────────┘
                                                 │ psycopg, 5432
                                  ┌──────────────▼───────────────────┐
                                  │ db  192.168.56.10                │  bento/ubuntu-24.04, 1024 MB
                                  │   PostgreSQL 16, database `adhd` │
                                  └──────────────────────────────────┘
```

### Decisions

| Aspect | Today | Proposed | Why |
|---|---|---|---|
| pk maths | Own VM (`pk`, Ubuntu 18.04, Django 3.2, HTTP on :8001) | `backend/pk/` package, called in-process from `tracker/services.py` | `pk/model.py` already imports nothing from Django. Folding it in removes an EOL box, a second Django, `requests`, the 502 failure modes and the web/pk on-time/late disagreement. |
| SPA hosting | nginx on the same VM as Django | nginx on its own `frontend` VM, proxying API paths to `backend` | The ask: one VM per tier. |
| API base URL | Hardcoded `http://localhost:8000` in `api.js` | Relative (`''`), so the SPA calls the origin it was loaded from; Vite dev-server proxy for local work | Frees the host port, and removes CORS from the deployed path entirely. |
| Proxy `Host` header | `$host` (port stripped) | `$http_host` (port kept) | Django strips the port itself before checking `ALLOWED_HOSTS`; keeping it lets the CSRF same-origin check pass for whatever host port Vagrant lands on. See Phase 3. |
| Django static files | nginx alias into `/vagrant` | WhiteNoise inside gunicorn, proxied via frontend nginx | One service on the backend VM; no nginx there. |
| Boxes | 24.04 / 18.04 / 24.04 | `bento/ubuntu-24.04` on all three | One box download, Python 3.12 everywhere, no EOL mirror worry. |
| Private IPs | db .10, pk .11, web .12 | db .10, backend .11, frontend .12 | Reuses the slots; `/etc/hosts` block rewritten with the new names. |
| Host ports | 8000→web:8000, 8001→pk:8001 | 8000→frontend:80. Optional 8001→backend:8000 for curl debugging. | |
| Memory | 1024 / 1024 / 2048 | db 1024 / backend 1024 / frontend 2048 | `npm ci` + `vite build` is the only thing that needs 2 GB. Host needs ~4 GB free. |
| Seed data | None | `manage.py seed_demo`, run by the backend provision after `migrate` | Out-of-the-box users and history. |
| Repo layout | `web/backend`, `web/frontend`, `pk/` | Top-level `backend/`, `frontend/`, `db/`, `provisions/`, `docs/` | Directory names match VM names; `git mv` keeps history. |

---

## 2. Repository layout after the branch

```
adhd-medication-manager/
├── Vagrantfile
├── README.md                       ← written (currently 0 bytes)
├── TODO.md                         ← updated to point at this plan
├── .gitattributes                  ← deploy/ paths updated
├── .gitignore                      ← backend/staticfiles/, backend/db.sqlite3
├── provisions/
│   ├── common.sh                   ← /etc/hosts block: db, backend, frontend
│   ├── db.sh                       ← unchanged apart from comments
│   ├── backend.sh                  ← from web.sh minus node/nginx/frontend, plus seed
│   └── frontend.sh                 ← node 22, build, nginx proxy, health check through the proxy
├── backend/                        ← was web/backend
│   ├── manage.py
│   ├── requirements.txt            ← was web/requirements.txt; + whitenoise, − requests
│   ├── config/                     ← settings.py loses PK_SERVICE_*, gains WhiteNoise
│   ├── users/
│   ├── tracker/
│   │   ├── services.py             ← in-process calls into pk
│   │   ├── management/commands/seed_demo.py
│   │   └── tests.py, tests_seed.py
│   ├── pk/                         ← was pk/model.py, pk/config.py, pk/tests/test_model.py
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── model.py
│   │   ├── README.md               ← trimmed from pk/README.md
│   │   └── tests/test_model.py
│   └── deploy/
│       ├── backend.env             ← was web/deploy/web.env
│       └── backend.service         ← was web/deploy/web.service
├── frontend/                       ← was web/frontend
│   ├── src/api.js                  ← relative baseURL
│   ├── vite.config.js              ← dev proxy
│   └── deploy/
│       ├── frontend.nginx.conf
│       └── proxy_params_backend
├── db/                             ← exists, empty; gets a short README on what db.sh does
├── scripts/
│   └── smoke.sh                    ← host-side end-to-end check against :8000
└── docs/
    ├── v1-three-vm-plan.md         ← this file
    ├── design/Dose Desktop.html    ← was web/Dose Desktop.html (1.3 MB design mock)
    └── notes/                      ← web/notes.md, steps.md, activate.md, features.md
```

Deleted: `pk/` (whole tree), `provisions/pk.sh`, `provisions/web.sh`, `web/deploy/`,
the stray `ig` file, and `web/backend/db.sqlite3` stops being tracked.

The restructure is the largest diff on the branch and touches every path, so it
goes first and on its own commit, with zero behaviour change, so later commits
are readable.

---

## 3. Phases

Each phase ends with a check you can actually run. Order matters: 0 → 1 → 2 and 3
(either order) → 4 → 5 → 6 → 7.

### Phase 0 — Branch and restructure (no behaviour change)

1. Merge `frontend/v1-pages` into `main` first if possible, then branch. If not,
   branch from `frontend/v1-pages` and say so in the PR.
2. `git mv web/backend backend`, `git mv web/requirements.txt backend/requirements.txt`,
   `git mv web/frontend frontend`, `git mv web/deploy/web.env backend/deploy/backend.env`,
   `git mv web/deploy/web.service backend/deploy/backend.service`,
   `git mv web/deploy/web.nginx.conf frontend/deploy/frontend.nginx.conf`,
   `git mv web/deploy/proxy_params_web frontend/deploy/proxy_params_backend`,
   `git mv "web/Dose Desktop.html" docs/design/`, `git mv web/*.md docs/notes/`.
3. `git rm ig`, `git rm --cached web/backend/db.sqlite3` before the move; add
   `backend/db.sqlite3` to `.gitignore`.
4. `.gitattributes`: replace the two `deploy/**` lines with `*/deploy/** text eol=lf`.
   `.gitignore`: `web/backend/staticfiles/` → `backend/staticfiles/`.
5. Fix paths in comments that name `web/...` (settings.py docstrings, tests
   docstrings, provisions comments):
   `grep -rn "web/" --include=*.py --include=*.sh --include=*.md`.

**Check:** `cd backend && DB_ENGINE=sqlite python manage.py test` → 66 pass.
`cd frontend && npm ci && npm run build` → dist produced.

### Phase 1 — Fold pk into the backend

The pk HTTP surface was: `POST /timeline {taken_at, components}` →
`{taken_at, events, curve, computed_by, model_version}`, and
`POST /adherence {doses}` → `{days, adherence, streak_days, missed, of, ...}`.
The frontend reads `events`, `curve`, `days[].status`, `adherence`, `streak_days`,
`missed`, `of`. Those shapes must not change.

1. **Move the maths.** `git mv pk/model.py backend/pk/model.py`,
   `git mv pk/config.py backend/pk/config.py`, add `backend/pk/__init__.py`.
   In `model.py` change `import config` → `from . import config`. The Python 3.6
   constraints in its docstring can go; nothing needs rewriting. It is a plain
   package, not a Django app: no `INSTALLED_APPS` entry, no models.
2. **Rewrite `tracker/services.py`** as the only call site:

   ```python
   from pk import config, model

   IDENTITY = {"computed_by": "backend.pk", "model_version": config.MODEL_VERSION}

   class PkInputError(ValueError):
       """Bad parameters or timestamp; the view turns it into a 400."""

   def compute_timeline(taken_at, components):
       # taken_at: an aware datetime (off Dose.taken_at, converted to local
       # time first) or an ISO string with an offset (the ?taken_at= query
       # param). Strings still go through model.parse_iso_datetime so a
       # missing offset is still a 400.
       try:
           if isinstance(taken_at, str):
               taken_at = model.parse_iso_datetime(taken_at)
           samples, events = model.build_timeline(components)
       except model.ModelError as exc:
           raise PkInputError(str(exc))
       return {
           "taken_at": taken_at.isoformat(),
           "events": model.events_payload(events, taken_at),
           "curve": model.curve_payload(samples),
           **IDENTITY,
       }

   def compute_adherence(doses):
       try:
           return {**model.adherence_report(doses), **IDENTITY}
       except model.ModelError as exc:
           raise PkInputError(str(exc))

   def classify_dose(scheduled_time, taken_at):
       """The one on-time/late rule, shared by POST /doses/ and the seeder.
       Wraps model.classify() with the local-time conversion."""
   ```

   `views.py`: `call_pk_timeline` → `compute_timeline`, `call_pk_adherence` →
   `compute_adherence`, `except PkServiceError` → `except PkInputError` returning
   400. The 502 branches disappear. When `taken_at` comes from a `Dose` row, pass
   `timezone.localtime(dose.taken_at)` rather than `.isoformat()`: Django stores
   UTC, and the events must carry the `+12:00`/`+13:00` offset the frontend
   expects to display.
3. **Settings and deps.** Delete `PK_SERVICE_URL` / `PK_SERVICE_TIMEOUT` from
   `settings.py` and `backend.env`. Drop `requests`, `certifi`,
   `charset-normalizer`, `idna`, `urllib3` from `requirements.txt` (nothing else
   imports them — confirm with grep). Add `whitenoise` (latest 6.x; Phase 2).
4. **Tests.**
   - `git mv pk/tests/test_model.py backend/pk/tests/test_model.py`; fix the
     `sys.path` hack and imports (`from pk import config, model`). It is plain
     `unittest`, so Django's runner picks it up as part of `manage.py test`.
   - `pk/tests/test_views.py` cases (malformed components → 400, missing offset
     → 400, single-component medication has no second release, events are
     chronological and keep the input offset) move into `tracker/tests.py` as
     tests against `/api/timeline/` with a real `Medication` row, then the file is
     deleted.
   - Delete `PkFailureTests` and `PkServiceTests` (they test HTTP failure modes
     that no longer exist) and the `_FakeResponse` helper. `TimelineTests` and
     `AdherencePayloadTests` currently patch `tracker.views.call_pk_*`; patch
     `tracker.views.compute_*` instead where they assert on the payload web
     builds, and let the rest run the real maths.
   - Test count goes from 66 to roughly 66 − 11 + 40 (model) + ~6 (moved view
     cases). Record the real number in the README.
5. **Reconcile on-time/late (closes TODO §3 item 3).** Add to `pk/model.py`:

   ```python
   def classify(scheduled_minutes, taken_minutes, late_after_minutes=None):
       """Returns (status, minutes_late) — the rule adherence_report already uses."""
   ```

   and have `adherence_report` call it. In `doses_view` POST, when creating a
   dose set `status` from `classify(...)` against the active selection's
   `scheduled_time` (local time) instead of hardcoding `ON_TIME`; a re-log the
   same day still becomes `EDITED`. The seeder (Phase 4) uses the same function,
   so Today's list and History can no longer disagree.
   While here, unify the spelling: `STATUS_ON_TIME = "on-time"` in `pk/model.py`
   to match `Dose.Status`, and remove the `.replace('_', '-')` in
   `History.vue`. One codebase now, one spelling.
6. **Delete** `pk/` (everything left), `provisions/pk.sh`. Trim `pk/README.md` into
   `backend/pk/README.md`: what the maths is, thresholds live in `config.py`,
   how to run its tests. Remove every "pk VM / 192.168.56.11:8001" sentence.
7. Update comments that say "computed by the pk service" in `api.js`, `curve.js`,
   `timeline.js`, `Curve.vue`, `TodayTimeline.vue`, `History.vue`, `Medications.vue`
   to "computed by the backend's pk module". Behaviour unchanged.

**Check:** `DB_ENGINE=sqlite python manage.py test` green. `python manage.py
runserver` + `curl -b cookies 'localhost:8000/api/timeline/?taken_at=2026-09-11T08:00:00+12:00&medication=concerta'`
returns `curve` with 289 samples (24 h / 5 min + 1) and
`"computed_by": "backend.pk"`.

### Phase 2 — The `backend` VM

1. **`provisions/backend.sh`** = today's `web.sh` with the node, frontend-build and
   nginx sections removed, and these changes:
   - `VENV=/opt/backend/venv`, `BACKEND=/vagrant/backend`, `DEPLOY=/vagrant/backend/deploy`.
   - Install `backend.env` to `/etc/backend.env` (keep the key/value read loop —
     do not source it; the reasoning comment stays).
   - Wait for postgres (existing loop), `migrate --noinput`, `collectstatic --noinput`.
   - Seed: `python manage.py seed_demo` (plus `--reset` when `SEED_RESET=1` is in
     the environment; see Phase 4). Print the demo credentials at the end.
   - Install and restart `backend.service`.
   - Health: `curl -sf http://127.0.0.1:8000/auth/csrf/` and
     `curl -sf http://127.0.0.1:8000/static/admin/css/base.css` (proves WhiteNoise).
2. **`backend/deploy/backend.service`**: `WorkingDirectory=/vagrant/backend`,
   `EnvironmentFile=/etc/backend.env`,
   `ExecStart=/opt/backend/venv/bin/gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 3`.
   Binding all interfaces is deliberate: nginx on the frontend VM must reach it
   across the host-only network. The only exposure is that network plus the
   optional debug forward.
3. **`backend/deploy/backend.env`**:

   ```
   DJANGO_SECRET_KEY=<keep the checked-in VM-only key; README explains why>
   DJANGO_DEBUG=False
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.56.11,backend,192.168.56.12,frontend
   DB_ENGINE=postgresql
   DB_NAME=adhd
   DB_USER=adhd
   DB_PASSWORD=password
   DB_HOST=192.168.56.10
   DB_PORT=5432
   # Same-origin via the frontend proxy; these only matter for the Origin check
   # and for the optional direct :8001 debug forward.
   DJANGO_CSRF_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://192.168.56.12,http://localhost:8001
   # Dev only: a laptop Vite server pointed at the VM.
   DJANGO_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   SEED_DEMO=1
   ```
4. **`settings.py`**: add `whitenoise.middleware.WhiteNoiseMiddleware` directly
   after `SecurityMiddleware`; `STATIC_ROOT` stays. Default `ALLOWED_HOSTS` list
   gets the new names. Remove the `PK_SERVICE_*` block. Default
   `_DEFAULT_FRONTEND_ORIGINS` drops the `192.168.56.12` entries.
5. **`provisions/db.sh`**: comment text only ("the backend VM"), and switch the
   `pg_hba` method from `md5` to `scram-sha-256`, which is what PG16 stores
   passwords as anyway. Everything else stays.

**Check:** `vagrant up db backend`; the provision ends green; from the host
`curl http://192.168.56.11:8000/auth/csrf/` → 200 (the host sits on the
host-only network as 192.168.56.1).

### Phase 3 — The `frontend` VM

1. **`frontend/src/api.js`**:

   ```js
   const api = axios.create({
     // Same origin the page was served from. nginx on the frontend VM proxies
     // /api/, /auth/, /admin/ and /static/ to the backend VM, so the browser
     // never makes a cross-origin request. VITE_API_BASE overrides it for a
     // laptop frontend pointed at a remote backend.
     baseURL: import.meta.env.VITE_API_BASE ?? '',
     ...
   })
   ```
2. **`frontend/vite.config.js`**: a `server.proxy` for `/api`, `/auth`, `/admin`,
   `/static` → `process.env.VITE_DEV_API ?? 'http://127.0.0.1:8000'`, so
   `npm run dev` against a local `runserver` or against the backend VM
   (`VITE_DEV_API=http://192.168.56.11:8000 npm run dev`) needs no code change.
3. **`frontend/deploy/frontend.nginx.conf`**:

   ```nginx
   upstream backend { server 192.168.56.11:8000; }

   server {
       listen 80 default_server;
       server_name _;
       root /opt/frontend/dist;
       index index.html;

       location = /index.html { add_header Cache-Control "no-store"; }

       location /api/    { proxy_pass http://backend; include /etc/nginx/proxy_params_backend; }
       location /auth/   { proxy_pass http://backend; include /etc/nginx/proxy_params_backend; }
       location /admin/  { proxy_pass http://backend; include /etc/nginx/proxy_params_backend; }
       location /static/ { proxy_pass http://backend; include /etc/nginx/proxy_params_backend; }

       location / { try_files $uri $uri/ /index.html; }
   }
   ```

   **`proxy_params_backend`** uses `proxy_set_header Host $http_host;` (port
   kept). The existing file's comment says `$host` is needed because
   `ALLOWED_HOSTS` compares with the port attached; that is not how Django
   works — `HttpRequest.get_host()` splits the port off before `validate_host`.
   Keeping the port matters for CSRF: Django's Origin check first compares the
   `Origin` header against `scheme://get_host()` *with* port, and only falls back
   to `CSRF_TRUSTED_ORIGINS` if that fails. With `$http_host`, a POST from
   `http://localhost:8000` (or a port Vagrant auto-corrected to) passes on the
   same-origin rule alone.
4. **`provisions/frontend.sh`**: node 22 from NodeSource (guarded), rsync
   `/vagrant/frontend` → `/opt/frontend` excluding `node_modules`/`dist`,
   `npm ci --no-audit --no-fund`, `npm run build`, install the nginx site and
   proxy params, remove the stock default site, `nginx -t`, restart. Then:
   - wait up to 60 s for `http://192.168.56.11:8000/auth/csrf/` (the backend may
     still be finishing its own provision in a `vagrant up` of a single node);
   - health: `curl -sf http://127.0.0.1/` → 200 and
     `curl -sf http://127.0.0.1/auth/csrf/` → 200 *through the proxy*, which is
     the whole chain: nginx → backend → postgres.
5. **Vagrantfile**: `frontend` forwards guest 80 → host 8000 with `auto_correct`.
   Because the SPA now uses a relative base URL, an auto-corrected port still
   works; the provision prints the actual URL.

**Check:** `vagrant up frontend`; open `http://localhost:8000`, log in (Phase 4
accounts), hard-refresh on `/curve` returns the SPA not a 404; `/admin/` renders
with CSS.

### Phase 4 — Seed users and history (`manage.py seed_demo`)

A management command at `backend/tracker/management/commands/seed_demo.py`. It
is the thing that makes "works out of the box" true, so it has tests.

**Accounts** (all passwords `dose-demo-2026` — 14 chars, passes every validator,
and one password to remember for a demo):

| username | name | medication | scheduled | role in the demo |
|---|---|---|---|---|
| `ada` | Ada Lovelace, ada@example.com | Concerta 36mg | 08:00 | Full history incl. today → Today, Curve, History, Notes all populated on first load |
| `sam` | Sam Rivers, sam@example.com | Ritalin LA 20mg | 07:30 | History but **no dose today** → shows the "Take dose" flow |
| `admin` | superuser | — | — | `/admin/` |

**Ten days of doses, today − 9 … today**, as offsets in minutes from the
scheduled time (`None` = no row, i.e. missed), oldest first:

```
ada: [ +3, +12,  -5, +48, +7, None, +2, +15, +40, TODAY ]
sam: [ +6,  -2, +35,  +4, +1,   +9, None, +5, +11, None  ]
```

- Status comes from `classify()` (Phase 1), so +48/+40/+35 are `late`, the rest
  `on-time`. Missed days have no row; `/api/adherence/` synthesises them, as it
  does today.
- `TODAY` for ada: `taken_at = scheduled time today` if that is already in the
  past, otherwise `now − 10 min`. Either way a dose exists for today and the
  Curve page has something to draw the moment the VM is up. sam deliberately has
  none.
- `created_at`/`updated_at` are `auto_now*`, so set them afterwards with
  `.update(created_at=taken_at + 1min, updated_at=taken_at + 1min)`; otherwise the
  Today page shows "Logged at … · N min after taking" with N = minutes since
  provisioning.
- All times are built as aware datetimes in `Pacific/Auckland`
  (`timezone.make_aware(datetime.combine(date, time), timezone.get_current_timezone())`);
  `Dose.date` is the local date.

**Notes** — eight for ada across the window, two `flagged` ("Crashed hard around
4pm — second release felt late", "Skipped; felt off all morning" on the missed
day), three for sam. Text should read like a real log, not lorem.

**Idempotency** — default run: if a demo username already exists, skip that user
and print "already seeded". `--reset`: delete the three demo users (cascade
removes their selections, doses and notes) and recreate. The provision runs
`seed_demo` every time and `seed_demo --reset` only when `SEED_RESET=1`, so
`vagrant provision backend` never wipes what a marker has logged unless asked.
The command never touches non-demo users.

**Tests** (`tracker/tests_seed.py`): running twice yields the same row counts;
ada has 9 dose rows spanning exactly 10 local dates with today present and in
the past; sam has no row for today; every status equals
`classify(scheduled, taken)`; `--reset` after a manual extra note brings the
count back; a non-demo user survives `--reset`.

### Phase 5 — Vagrantfile

```ruby
servers = [
  { hostname: "db",       ip: "192.168.56.10", ssh_port: 2200, memory: 1024, forwarded: [] },
  { hostname: "backend",  ip: "192.168.56.11", ssh_port: 2201, memory: 1024,
    # Debug only -- the app reaches backend over the private network.
    forwarded: [{ guest: 8000, host: 8001 }] },
  { hostname: "frontend", ip: "192.168.56.12", ssh_port: 2202, memory: 2048,
    # The entry point. nginx serves the SPA and proxies the API to backend.
    forwarded: [{ guest: 80, host: 8000 }] },
]
```

One box for all three (`bento/ubuntu-24.04`). Order is boot order: VirtualBox
brings them up sequentially, so `backend.sh` can rely on db being provisioned
and `frontend.sh` on backend — each still waits on the port it needs, because a
single-node `vagrant provision` must also work. Header comment rewritten to
describe the three tiers and why 24.04 everywhere. `common.sh` writes the new
`/etc/hosts` block (`db`, `backend`, `frontend`).

After `vagrant halt` / `vagrant up`, provisioners do not rerun, so seeded and
user-entered data persist in postgres on the db VM. `vagrant destroy -f &&
vagrant up` is the reset.

### Phase 6 — Verification

1. **Unit tests**: `cd backend && DB_ENGINE=sqlite python manage.py test` — tracker,
   users, pk model, seeder. Must be green before any VM work is trusted.
2. **`scripts/smoke.sh`** — runs on the host (Git Bash) after `vagrant up`,
   against `${BASE:-http://localhost:8000}` with a cookie jar:
   1. `GET /auth/csrf/` → 200, cookie set.
   2. `POST /auth/login/` as `ada` → 200.
   3. `GET /api/my-medication/` → `medication.id == "concerta"`, `scheduled_time == "08:00"`.
   4. `GET /api/doses/` → at least 9 rows; one with `date == today`.
   5. `GET /api/timeline/` → `curve` has 289 samples, `events[0].label == "Taken"`,
      `computed_by == "backend.pk"`.
   6. `GET /api/adherence/` → `of == 14`, `streak_days ≥ 1`, a `late` day present.
   7. `GET /api/notes/` → ≥ 8, at least one `flagged`.
   8. `GET /curve` → 200 with `<div id="app">` (SPA fallback works).
   9. `GET /static/admin/css/base.css` → 200 (WhiteNoise through the proxy).
   Non-zero exit and the failing step's body on any miss.
3. **Browser checklist**, written into the README as the manual acceptance run:
   log in as ada → Today shows a timeline with milestones and the last-10-days
   list; Day curve draws with NOW marker; History shows 14 rows with late and
   missed pills and a streak; Notes shows grouped days with two flagged;
   Medications previews each curve and saving a time works. Log out, log in as
   sam → Take dose → timeline appears → edit the time → curve shifts.
4. **The acceptance run**: in a temporary directory, `git clone` the branch,
   `vagrant up`, `scripts/smoke.sh`. No local state, no prior boxes apart from
   the one download. Record wall-clock time and the three VMs' RAM in the README.
   Then `vagrant halt && vagrant up` and re-run the smoke script: data persisted.

### Phase 7 — Documentation

- **README.md** (currently empty — the first thing a marker reads): what the
  app is; the architecture diagram from §1; prerequisites (VirtualBox, Vagrant,
  ~4 GB RAM free, host port 8000 free); `vagrant up` and what to expect
  (~15–20 min first time, mostly the box download and `npm ci`); the URL; the
  demo accounts table; how to run the unit tests and the smoke script; dev mode
  (host `runserver` against the db VM + `npm run dev` with the proxy); the
  `SEED_RESET=1 vagrant provision backend` refresh; troubleshooting (port
  auto-correct message, build OOM, CRLF on scripts, VirtualBox host-only range,
  `apt` failures mid-provision → `vagrant provision <node>`); the security note
  that the checked-in secret key and DB password are VM-only by design.
- **TODO.md**: tick the infrastructure section, add a line pointing at this plan,
  and leave §3 *Data correctness* items honest — placeholder pharmacokinetics
  and blank provenance are **not** solved by this plan, and the UI continues to
  say so.
- **`backend/pk/README.md`**, **`db/README.md`** as described above.

---

## 4. File-by-file change list

| File | Action |
|---|---|
| `Vagrantfile` | Rewrite node list (Phase 5) and header comment |
| `provisions/common.sh` | `/etc/hosts` names |
| `provisions/db.sh` | comments; `scram-sha-256` |
| `provisions/backend.sh` | new (from `web.sh`) |
| `provisions/frontend.sh` | new (from `web.sh`) |
| `provisions/web.sh`, `provisions/pk.sh` | delete |
| `backend/config/settings.py` | WhiteNoise middleware; drop `PK_SERVICE_*`; default hosts/origins |
| `backend/requirements.txt` | + `whitenoise`; − `requests` and its four transitive pins |
| `backend/tracker/services.py` | in-process `compute_timeline` / `compute_adherence` / `classify_dose` |
| `backend/tracker/views.py` | call the new services; set `Dose.status` via `classify` |
| `backend/tracker/tests.py` | drop HTTP-failure tests; absorb pk view cases; patch new names |
| `backend/tracker/tests_seed.py` | new |
| `backend/tracker/management/commands/seed_demo.py` | new |
| `backend/pk/{__init__,config,model}.py`, `tests/test_model.py`, `README.md` | moved from `pk/`; `classify()` added; `"on-time"` spelling |
| `backend/deploy/backend.env`, `backend.service` | moved from `web/deploy`; edited per Phase 2 |
| `frontend/src/api.js` | relative `baseURL` |
| `frontend/vite.config.js` | dev proxy |
| `frontend/src/views/user/History.vue` | drop the `_`→`-` normalisation |
| `frontend/src/**` comments | "pk service" → "pk module" |
| `frontend/deploy/frontend.nginx.conf`, `proxy_params_backend` | new (from `web/deploy`), `$http_host` |
| `scripts/smoke.sh` | new |
| `README.md`, `TODO.md`, `db/README.md` | write / update |
| `.gitattributes`, `.gitignore` | paths |
| `ig`, `web/backend/db.sqlite3` (tracking), `pk/**` | remove |
| `web/Dose Desktop.html`, `web/*.md` | move under `docs/` |

Suggested commits, in order: restructure → fold pk (+tests) → backend VM →
frontend VM → seed command (+tests) → Vagrantfile + smoke script → docs.

---

## 5. Risks and how the plan handles them

| Risk | Mitigation |
|---|---|
| `npm ci` + `vite build` OOM on the frontend VM | 2048 MB on that node only; documented. Fallback if it ever recurs: build on the host and rsync `dist/` (a `FRONTEND_PREBUILT=1` switch in `frontend.sh`). |
| Network fetches during provision (box, apt, NodeSource, npm, pip) | Every script is rerunnable; README says `vagrant provision <node>` resumes. |
| Host port 8000 already in use | `auto_correct` shifts it; relative base URL + `$http_host` mean the app still works on the shifted port; the provision prints the real URL. |
| Host browser not on NZ time | The SPA formats times in the browser's zone while the VMs and Django run `Pacific/Auckland`; seeded 08:00 doses will display shifted on a non-NZ host. Documented; v1 does not pin the browser zone. |
| CRLF on `.sh` / `deploy/` files from a Windows checkout | `.gitattributes` paths updated in Phase 0; first thing to check if a provision fails on line 2. |
| Restructure conflicts with other open branches | Do Phase 0 first, merge quickly; only `frontend/v1-pages` is ahead of `main` today. |
| Seed staleness (the "10 days ending today" window ages) | `SEED_RESET=1 vagrant provision backend` regenerates; never automatic. |
| Seeded today-dose in the future if provisioned before 08:00 | Handled: falls back to `now − 10 min`. |
| Losing the "separate compute service" story from the report | `computed_by` / `model_version` stay on every response; the module boundary (`backend/pk/` imports no Django) is the new story, and it is a stronger one. |
| `/admin/` through the proxy | `/static/` is proxied to WhiteNoise; the smoke script checks one admin CSS file. |

---

## 6. Definition of done (v1)

- [ ] Fresh clone → `vagrant up` → three VMs green, no manual steps, no warnings that matter.
- [ ] `http://localhost:8000` loads; `ada` / `dose-demo-2026` logs in.
- [ ] Today, Day curve, Notes, Medications, History all render real seeded data for `ada` on first visit.
- [ ] `sam` demonstrates the take-dose → timeline → edit-time path.
- [ ] `scripts/smoke.sh` exits 0 against the running stack.
- [ ] `manage.py test` green (backend + pk model + seeder), count recorded in the README.
- [ ] `vagrant halt && vagrant up` keeps data; `vagrant destroy -f && vagrant up` rebuilds identically.
- [ ] `/api/doses/` POST status and `/api/adherence/` status agree for the same dose.
- [ ] README written; TODO.md updated; `pk/`, `web/`, `ig`, tracked sqlite gone.

## 7. Explicitly out of scope

features.md items 1–6 (dose `PATCH`, per-day endpoint, stats, LLM summaries, notes
on the curve), real pharmacokinetic parameters and Medsafe/NZF provenance, HTTPS,
per-host secrets, and any change to the pk maths beyond `classify()` and the
status spelling.
