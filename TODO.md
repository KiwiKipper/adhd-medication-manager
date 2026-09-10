# TODO — v1 release

Remaining work to get the project to a submittable v1. Ordered backend →
frontend → data correctness → infrastructure. Items marked *post-v1* are
tracked in [web/features.md](web/features.md) and are not blockers.

Last verified against `main` at 0094bfd (PRs #1 docs/v1-todo, #2
backend/v1-config-and-tests, #3 infra/db-provisioning all merged), plus the
web-provisioning branch below. Backend and infrastructure are essentially
done — `vagrant up` now brings all three nodes up serving the app. The whole
frontend and all of data correctness are still open, and those are the real
remaining v1 work.

## 1. Backend

- [x] **Switch to PostgreSQL.** `settings.py` now defaults to the postgres
      backend pointed at the `db` VM (`192.168.56.10`, database/user `adhd`),
      with `DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` read from the
      environment. `DB_ENGINE=sqlite` switches back to SQLite for local dev
      and for running the test suite without a VM.
- [x] **Production settings.** `DJANGO_SECRET_KEY`, `DJANGO_DEBUG` and
      `DJANGO_ALLOWED_HOSTS` are env-driven with dev-friendly defaults, and
      `STATIC_ROOT` is set so `collectstatic` has somewhere to go.
      `manage.py check` passes with `DJANGO_DEBUG=False`.
- [x] **CORS origins.** `CORS_ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS` now
      cover the web VM (`192.168.56.12`) alongside localhost, and are
      overridable via `DJANGO_CORS_ORIGINS`/`DJANGO_CSRF_ORIGINS`.
- [x] **Write tests.** 66 tests across
      [tracker/tests.py](web/backend/tracker/tests.py) and
      [users/tests.py](web/backend/users/tests.py): dose logging, the
      `/timeline/` and `/adherence/` pk passthroughs (pk patched out), pk
      failure modes, notes, and auth on every endpoint. Run with
      `DB_ENGINE=sqlite py manage.py test` from `web/backend/`.
- [x] **pk failure handling.** Confirmed by test: a dead or slow pk VM gives a
      502 with a readable `error` body, not a 500, and pk's own 400s pass
      through with their message. A timeout is now reported separately from a
      refused connection so `PK_SERVICE_TIMEOUT` is the obvious knob.
- [x] **`Note` model fields.** `date` (the day the note is *about*, defaulting
      to today) and `flagged` added, with a migration that backfills existing
      rows from `created_at`. `GET /notes/?date=YYYY-MM-DD` (or `?date=today`)
      does per-day lookup; both fields are settable on POST.
- [ ] *post-v1* — dose `taken_at` editing (`PATCH /doses/<id>/`), per-day
      endpoint (`GET /days/<date>/`), stats endpoint (`GET /doses/stats/`),
      and the LLM summary endpoints. See features.md items 1-6.

## 2. Frontend

- [ ] **Finish the Curve page.** [Curve.vue](web/frontend/src/views/user/Curve.vue)
      is a 7-line placeholder (`<p>Curve</p>`). This is step 8 of
      [web/steps.md](web/steps.md) and is still untouched.
- [ ] **Finish the Notes page.** [Notes.vue](web/frontend/src/views/user/Notes.vue)
      is the same 7-line placeholder.
- [ ] **Use pk's real curve data.** [lib/curve.js:2-3](web/frontend/src/lib/curve.js#L2-L3)
      still draws the hardcoded `DAY_CURVE_BASE_POINTS` design-mock shape even
      though the timeline/adherence wiring to pk already landed. Feed the
      chart from the pk `/timeline/` response instead.
- [ ] **Medications page off placeholder data.**
      [Medications.vue](web/frontend/src/views/user/Medications.vue) reads
      `MED_DATA` from [lib/placeholderData.js](web/frontend/src/lib/placeholderData.js)
      rather than fetching `/medications/`.
- [ ] **Scheduled dose time picker.** `UserMedication.scheduled_time` defaults
      everyone to 8am and there is no UI to change it, so on-time/late
      classification is wrong for anyone not on an 8am dose.
- [ ] **Retire `placeholderData.js`** once the two items above are done, so
      nothing ships reading mock data.
- [ ] *post-v1* — extract the inline `<svg>` into a shared `CurveChart.vue`,
      notes overlaid on the curve, History aggregate stats, LLM summaries.

## 3. Data correctness

- [ ] **Replace placeholder pharmacokinetics.** `Medication.pk_components` is
      documented in-model as *illustrative placeholder shapes, not real
      pharmacokinetics* — one component for immediate-release, two for
      extended-release. See
      [tracker/models.py:20-25](web/backend/tracker/models.py#L20-L25) and the
      "Medication defaults" section of [pk/README.md](pk/README.md).
- [ ] **Populate provenance fields.** `source`, `source_url` and `retrieved`
      are blank on every `Medication`. Fill them from Medsafe or the NZ
      Formulary, and update the seed migration
      ([0004_seed_pk_components.py](web/backend/tracker/migrations/0004_seed_pk_components.py))
      to match.
- [ ] **Reconcile the two on-time/late classifiers.** Found during the live
      provision test: one dose logged at 09:55 against an 08:00 schedule came
      back from `POST /api/doses/` as `"status": "on-time"`, while
      `/api/adherence/` classified the same day `"status": "late",
      "minutes_late": 115`. web and pk are each deciding this separately and
      disagreeing, so Today and History will contradict each other on screen.
      Decide which one owns the rule — pk is the better home, since it
      already has the thresholds — and have the other defer to it.
- [ ] **Do not present modelled output as measurement.** The curve is a
      Bateman-model prediction; make sure the UI copy says so wherever a curve
      or a milestone time is shown.
- [ ] **Verify timezone handling end to end.** `provisions/common.sh` sets the
      VMs to `Pacific/Auckland` precisely because a UTC default silently
      shifts every timeline by 12-13 hours. Django's half is confirmed —
      [settings.py:191-195](web/backend/config/settings.py#L191-L195) has
      `TIME_ZONE = 'Pacific/Auckland'` with `USE_TZ = True`. Still to check:
      the frontend's local-time formatting and pk's day boundaries agree with
      it once a VM is actually running.

## 4. Infrastructure

- [x] **Write `provisions/web.sh`.** Done — gunicorn running the Django API
      behind nginx, with nginx also serving the built Vue SPA so both answer
      on one origin (`:8000`). The script installs Node 22 from NodeSource
      (vite 8 needs >= 20.19), builds the venv, waits for postgres on the db
      VM, runs `migrate` and `collectstatic`, builds the frontend, installs
      both units, and health-checks `/auth/csrf/` and `/` before exiting.
      Config lives in [web/deploy/](web/deploy/); every step is rerunnable.
- [x] **Decide the web VM's Python.** Done — web moves to
      `bento/ubuntu-24.04` (Python 3.12) for Django 6.1. db and pk stay on
      18.04: pk pins Django 3.2 precisely because that box ships Python 3.6,
      and moving it would mean upgrading pk's Django for no benefit.
- [x] **Check `apt-get update` still works on bionic.** Checked on the
      running db VM — bionic is still served from `archive.ubuntu.com` and
      all four suites resolve, so the EOL worry was unfounded and
      `provisions/common.sh` needs no mirror rewrite. Worth rechecking if a
      provision ever fails at the apt step.
- [x] **Fix the missing DB schema file.** Done — the `schema.sql` line is
      gone from [provisions/db.sh](provisions/db.sh) and Django migrations own
      the schema. The script now also creates the role/database/pg_hba rule
      only if absent (so `vagrant provision` is rerunnable rather than a
      second-run failure), opens `listen_addresses`, and ends with a real
      health check that connects over `192.168.56.10` as `adhd` before
      exiting green.
- [x] **Forward the app ports.** Done — guest 8000 to host 8000 on web (the
      browser entry point), and guest 8001 to host 8001 on pk for debugging.
      The web mapping has to keep host port 8000 specifically, because
      [api.js:6](web/frontend/src/api.js#L6) hardcodes
      `http://localhost:8000`; `auto_correct` is on, so watch for a
      correction warning if something else on the host holds that port.
      Note none of this affects reaching db or pk from the host — the
      `192.168.56.0/24` private network is a VirtualBox host-only adapter, so
      the host sits on it as `192.168.56.1` and can hit postgres and pk
      directly with no forwarding. That is what makes the interim setup
      below work.
- [x] **Remove the dead config block.** Done — it was also actively
      misleading, since it had db and web on each other's addresses.
- [ ] **Write the root README.** [README.md](README.md) is empty (0 bytes). It
      needs the architecture (web/pk/db VMs), setup and `vagrant up`
      instructions, and how to run each test suite — this is what a marker
      reads first.
- [x] **Add `.ua/` to `.gitignore`** (or delete it). Done — the directory is
      gone from the working tree and `git status` is clean.
- [~] **Verify a clean `vagrant destroy && vagrant up`.** Partly done — db
      and web were both destroyed and rebuilt from scratch and come up green,
      and the full path was exercised from the host afterwards: register,
      select a medication, log a dose, then `/timeline/` and `/adherence/`
      returning real pk output. pk itself was not rebuilt, so a genuinely
      clean three-VM run from a fresh checkout is still unproven.
- [ ] **Document both ways to run it** (in the README, once written). The VMs
      now serve the app at `http://localhost:8000` after `vagrant up` — that
      host port must stay 8000, since [api.js:6](web/frontend/src/api.js#L6)
      hardcodes it. The host-side alternative still works and is faster to
      iterate on: db and pk are reachable directly on the host-only network,
      and the settings defaults already point at them. The only thing not
      defaulted is `DB_PASSWORD` (empty by default,
      [provisions/db.sh](provisions/db.sh) sets it to `password`); after that
      it is `manage.py migrate` then `runserver` in `web/backend/`, and
      `npm run dev` in `web/frontend/`.
- [ ] **Delete the stray `ig` file.** There is a tracked file named `ig` at
      the repo root containing what looks like an aborted `.gitignore`
      (`.venv/`, `__pycache__/`, `node_modules/`, `dist/`). Its useful lines
      are already in [.gitignore](.gitignore); delete it.
- [ ] **Stop tracking `web/backend/db.sqlite3`.** A committed dev database
      ships whatever local rows were in it and conflicts on every merge. Add
      it to [.gitignore](.gitignore) and `git rm --cached` it — the postgres
      switch means nothing depends on the file.
- [ ] **Write the report.** Step 11 of [web/steps.md](web/steps.md).
