# TODO — v1 release

Remaining work to get the project to a submittable v1. Ordered backend →
frontend → data correctness → infrastructure. Items marked *post-v1* are
tracked in [web/features.md](web/features.md) and are not blockers.

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
- [ ] **Do not present modelled output as measurement.** The curve is a
      Bateman-model prediction; make sure the UI copy says so wherever a curve
      or a milestone time is shown.
- [ ] **Verify timezone handling end to end.** `provisions/common.sh` sets the
      VMs to `Pacific/Auckland` precisely because a UTC default silently
      shifts every timeline by 12-13 hours — confirm Django's `TIME_ZONE`,
      `USE_TZ`, and the frontend's local-time formatting all agree.

## 4. Infrastructure

- [ ] **Write `provisions/web.sh`.** Currently just `#!/bin/bash` / `set -e`
      — it does nothing. Needs: venv + `pip install -r web/requirements.txt`,
      `manage.py migrate`, `collectstatic`, a gunicorn systemd unit, and the
      Vue build (or `npm run dev --host`). Model it on
      [provisions/pk.sh](provisions/pk.sh), which is the one node that is
      fully provisioned (idempotent, systemd unit, post-provision health check).
- [ ] **Fix the missing DB schema file.**
      [provisions/db.sh:8](provisions/db.sh#L8) runs
      `psql adhd -f /vagrant/db/schema.sql`, but there is no `db/` directory in
      the repo — `vagrant up` fails on the db VM. Either add `db/schema.sql` or
      drop that line and let Django migrations own the schema (preferred, since
      the models already define it).
- [ ] **Forward the app ports.** [Vagrantfile](Vagrantfile) only forwards SSH
      (2200-2202). Nothing exposes Django (8000) or Vite (5173) to the host, so
      the app can't be opened from a browser.
- [ ] **Remove the dead config block.** The whole first
      `Vagrant.configure("2")` block at the top of the Vagrantfile is commented
      out and superseded by the `servers=[...]` version below it.
- [ ] **Write the root README.** [README.md](README.md) is empty (0 bytes). It
      needs the architecture (web/pk/db VMs), setup and `vagrant up`
      instructions, and how to run each test suite — this is what a marker
      reads first.
- [ ] **Add `.ua/` to `.gitignore`** (or delete it) — it is scratch output from
      the codebase-analysis tooling and currently shows as untracked.
- [ ] **Verify a clean `vagrant destroy && vagrant up`** brings all three VMs up
      green, end to end, on a fresh checkout.
- [ ] **Write the report.** Step 11 of [web/steps.md](web/steps.md).
