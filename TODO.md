# TODO — v1 release

Remaining work to get the project to a submittable v1. Ordered backend →
frontend → data correctness → infrastructure. Items marked *post-v1* are
tracked in [docs/notes/features.md](docs/notes/features.md) and are not
blockers.

Last verified against `frontend/v1-pages` at `bf2cc16`, plus the
`infra/three-vm-v1` branch below, which restructures the three nodes from
`db`/`pk`/`web` to `db`/`backend`/`frontend`: the `pk` VM and its separate
Django project are gone, folded into `backend/pk/` as an in-process Python
package (no HTTP hop, no second Django, one on-time/late rule instead of
two that could disagree); the Vue SPA gets its own `frontend` VM with
nginx; and two demo accounts with ten days of history are now seeded
automatically, so `vagrant up` produces a working, populated app with no
manual setup. See [docs/v1-three-vm-plan.md](docs/v1-three-vm-plan.md) for
the full plan this branch followed, including what was deliberately left
out. Backend, frontend and infrastructure are essentially done. Data
correctness is now the bulk of what is left, and the report with it.

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
      [tracker/tests.py](backend/tracker/tests.py) and
      [users/tests.py](backend/users/tests.py): dose logging, the
      `/timeline/` and `/adherence/` pk passthroughs (pk patched out), pk
      failure modes, notes, and auth on every endpoint. Run with
      `DB_ENGINE=sqlite py manage.py test` from `backend/`. **Updated on
      `infra/three-vm-v1`:** pk stopped being a separate HTTP service (see
      the infra section), so the failure-mode tests this item describes
      (a dead/slow pk giving a 502) no longer apply and were deleted; the
      passthrough tests now patch `compute_timeline`/`compute_adherence`
      instead. The suite is 124 tests now — the difference is pk's own
      model tests (`backend/pk/tests/`) being discovered automatically,
      real end-to-end `/api/timeline/` cases absorbed from pk's old
      endpoint tests, and the seed command's tests.
- [x] **pk failure handling.** ~~Confirmed by test: a dead or slow pk VM
      gives a 502...~~ **Superseded on `infra/three-vm-v1`:** there is no
      longer a pk service to fail — it's an in-process package call, so
      this failure mode doesn't exist any more. Bad input from pk's own
      validation still reaches the caller as a 400 either way
      (`PkInputError` now, not `PkServiceError`).
- [x] **`Note` model fields.** `date` (the day the note is *about*, defaulting
      to today) and `flagged` added, with a migration that backfills existing
      rows from `created_at`. `GET /notes/?date=YYYY-MM-DD` (or `?date=today`)
      does per-day lookup; both fields are settable on POST.
- [ ] *post-v1* — dose `taken_at` editing (`PATCH /doses/<id>/`), per-day
      endpoint (`GET /days/<date>/`), stats endpoint (`GET /doses/stats/`),
      and the LLM summary endpoints. See features.md items 1-6.

## 2. Frontend

- [x] **Finish the Curve page.** Done — step 8 of
      [docs/notes/steps.md](docs/notes/steps.md). [Curve.vue](frontend/src/views/user/Curve.vue)
      draws today's dose as the curve pk computed for it, on a clock-time
      axis anchored to the logged taken time (not the mock's fixed
      6am–midnight window), with pk's milestones marked along it, a NOW
      marker that ticks every minute, and its own states for "no medication
      selected" and "no dose logged yet". The caption says in words that it
      is a modelled average response rather than a measurement.
- [x] **Finish the Notes page.** Done —
      [Notes.vue](frontend/src/views/user/Notes.vue) lists every note
      grouped by the day it is *about* (`Note.date`, so a note typed at 1am
      still belongs to the previous day's dose), with a flagged-only filter
      and a form that can file a note against an earlier day and flag it.
      Routed at `/notes` with a nav entry; the Today sidebar now fetches
      `?date=today` and links here for the rest.
- [x] **Use pk's real curve data.** Done — `DAY_CURVE_BASE_POINTS` and
      `dayCurvePath` are gone. [lib/curve.js](frontend/src/lib/curve.js)
      now only maps pk's `curve: [{ t_h, level }]` samples onto chart
      coordinates: a polyline through the actual samples, deliberately not a
      smoothed spline, so nothing is invented between them.
- [x] **Medications page off placeholder data.** Done — the page fetches
      `/api/medications/`, and the "release shape" beside a medication is
      the curve pk computes for it via the new
      `GET /api/timeline/?medication=<id>`, asked for at the user's own
      scheduled time. The blurb/description/drug-class copy moved into the
      catalogue (migrations 0006/0007) rather than living in the frontend.
- [x] **Scheduled dose time picker.** Done — `GET/POST /api/my-medication/`
      now carries `scheduled_time`, and the Medications page has a picker
      for it. Posting a time alone updates the current selection in place
      (no medication re-select, no new row), and switching medication keeps
      the time already set. That value is what `/api/adherence/` sends pk to
      classify against, so on-time/late is no longer wrong for everyone not
      on an 8am dose.
- [x] **Retire `placeholderData.js`.** Done — the file is deleted and
      nothing imports it. Note its per-medication `source` line ("Medsafe
      consumer medicine information · retrieved 6 Sep 2026") was invented:
      the catalogue's `source`/`source_url`/`retrieved` are genuinely empty,
      so the Medications and Curve pages now say no source has been recorded
      yet rather than displaying a citation that does not exist. Filling
      them in is the provenance item in section 3.
- [ ] *post-v1* — extract the inline `<svg>` into a shared `CurveChart.vue`,
      notes overlaid on the curve, History aggregate stats, LLM summaries.

## 3. Data correctness

- [ ] **Replace placeholder pharmacokinetics.** `Medication.pk_components` is
      documented in-model as *illustrative placeholder shapes, not real
      pharmacokinetics* — one component for immediate-release, two for
      extended-release. See
      [tracker/models.py:20-25](backend/tracker/models.py#L20-L25) and the
      "Medication defaults" section of [pk/README.md](backend/pk/README.md).
- [ ] **Populate provenance fields.** `source`, `source_url` and `retrieved`
      are blank on every `Medication`. Fill them from Medsafe or the NZ
      Formulary, and update the seed migration
      ([0004_seed_pk_components.py](backend/tracker/migrations/0004_seed_pk_components.py))
      to match.
- [x] **Reconcile the two on-time/late classifiers.** Done, on
      `infra/three-vm-v1` — added `pk.model.classify(scheduled_minutes,
      taken_minutes)`, the one rule `adherence_report` already used, and
      `tracker.services.classify_dose` wraps it for `POST /api/doses/` to
      set a dose's status with, instead of the hardcoded `ON_TIME` it used
      before. The exact repro case (08:00 schedule, 09:55 taken) is now a
      test: `DoseLoggingTests.test_doses_and_adherence_agree_on_the_same_dose`
      in [tracker/tests.py](backend/tracker/tests.py).
- [~] **Do not present modelled output as measurement.** Partly done — the
      Curve page, the Today timeline and the Medications release shape each
      carry a line saying the curve and its milestones are a modelled
      average response rather than a measurement, alongside the nav's
      standing disclaimer. Still to check: the History page's wording, and
      anywhere the report ends up quoting a milestone time.
- [ ] **Verify timezone handling end to end.** `provisions/common.sh` sets the
      VMs to `Pacific/Auckland` precisely because a UTC default silently
      shifts every timeline by 12-13 hours. Django's half is confirmed —
      [settings.py:198-202](backend/config/settings.py#L198-L202) has
      `TIME_ZONE = 'Pacific/Auckland'` with `USE_TZ = True`. Still to check:
      the frontend's local-time formatting and pk's day boundaries agree with
      it once a VM is actually running.

## 4. Infrastructure

The items below through "Remove the dead config block" describe the
original `db`/`pk`/`web` layout and are left as the historical record of
that work. `infra/three-vm-v1` restructured that into `db`/`backend`/
`frontend` — see [docs/v1-three-vm-plan.md](docs/v1-three-vm-plan.md) for
why and how, and the root [README.md](README.md) for the layout as it
stands now. The remaining items in this section are updated in place.

- [x] **Write `provisions/web.sh`.** Done — gunicorn running the Django API
      behind nginx, with nginx also serving the built Vue SPA so both answer
      on one origin (`:8000`). The script installs Node 22 from NodeSource
      (vite 8 needs >= 20.19), builds the venv, waits for postgres on the db
      VM, runs `migrate` and `collectstatic`, builds the frontend, installs
      both units, and health-checks `/auth/csrf/` and `/` before exiting.
      Config lived in `web/deploy/` (now split across
      [backend/deploy/](backend/deploy/) and
      [frontend/deploy/](frontend/deploy/) — see the infra-section note
      above); every step is rerunnable.
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
      [api.js:6](frontend/src/api.js#L6) hardcodes
      `http://localhost:8000`; `auto_correct` is on, so watch for a
      correction warning if something else on the host holds that port.
      Note none of this affects reaching db or pk from the host — the
      `192.168.56.0/24` private network is a VirtualBox host-only adapter, so
      the host sits on it as `192.168.56.1` and can hit postgres and pk
      directly with no forwarding. That is what makes the interim setup
      below work.
- [x] **Remove the dead config block.** Done — it was also actively
      misleading, since it had db and web on each other's addresses.
- [x] **Write the root README.** Done, on `infra/three-vm-v1` —
      [README.md](README.md) now has the three-VM architecture diagram,
      prerequisites, `vagrant up` instructions and what to expect, the
      seeded demo accounts table, how to run every test suite and
      `scripts/smoke.sh`, both ways to run it, troubleshooting, and the
      security note about the checked-in secrets.
- [x] **Add `.ua/` to `.gitignore`** (or delete it). Done — the directory is
      gone from the working tree and `git status` is clean.
- [~] **Verify a clean `vagrant destroy && vagrant up`.** Still partly
      done, now against the new layout: `infra/three-vm-v1`'s restructure,
      the `pk` fold-in, the seed command, the new `provisions/backend.sh` /
      `provisions/frontend.sh`, and the Vagrantfile were all verified the
      ways that don't need a VM — `DB_ENGINE=sqlite manage.py test` (124/124),
      `manage.py check` with `DJANGO_DEBUG=False`, `npm run build`,
      `bash -n` on every provisioning script, and `scripts/smoke.sh` run
      against a real seeded `manage.py runserver` instance standing in for
      the backend VM. A genuine `vagrant destroy -f && vagrant up` on the
      new three-node Vagrantfile has not been run — VirtualBox's host-only
      networking needs an interactive admin-elevated setup on first use,
      which wasn't available in the session that did this work. That run,
      plus a pass of `scripts/smoke.sh` against the real stack, is the one
      thing left to confirm before calling this done.
- [x] **Document both ways to run it** (in the README). Done — see the
      README's "Getting started" (the three VMs) and "Running it without
      the VMs" (host-side `runserver` + `npm run dev`, both pointed at the
      `db`/`backend` VMs over the host-only network) sections.
- [x] **Delete the stray `ig` file.** Done.
- [x] **Stop tracking `backend/db.sqlite3`.** Done — the file moved
      (untracked) to `backend/db.sqlite3` along with the rest of the
      restructure, and `.gitignore` covers the new path.
- [ ] **Write the report.** Step 11 of [docs/notes/steps.md](docs/notes/steps.md).
