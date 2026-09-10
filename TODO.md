# TODO — v1 release

Remaining work to get the project to a submittable v1. Ordered backend →
frontend → data correctness → infrastructure. Items marked *post-v1* are
tracked in [web/features.md](web/features.md) and are not blockers.

## 1. Backend

- [ ] **Switch to PostgreSQL.** `settings.py` still uses SQLite; the Postgres
      block sits commented out inside a docstring with dummy credentials
      (`mydatabase`/`mydatabaseuser`). Point it at the `db` VM
      (`192.168.56.10`, database `adhd`, user `adhd`) and read credentials
      from environment variables rather than hardcoding them.
      See [web/backend/config/settings.py:85-108](web/backend/config/settings.py#L85-L108).
- [ ] **Production settings.** `DEBUG = True`, `ALLOWED_HOSTS = []` and a
      hardcoded `django-insecure-` `SECRET_KEY` — Django will refuse to serve
      on the web VM as-is. Drive all three from env vars with dev-friendly
      defaults.
- [ ] **CORS origins.** `CORS_ALLOWED_ORIGINS` only lists
      `http://localhost:5173`; add the web VM origin so the built frontend can
      reach the API.
- [ ] **Write tests.** [tracker/tests.py](web/backend/tracker/tests.py) and
      [users/tests.py](web/backend/users/tests.py) are 3-line stubs. The `pk`
      service has real tests; `web` has none. Cover at minimum: dose logging,
      the `/timeline/` and `/adherence/` pk passthroughs (with pk stubbed), and
      auth on the `users` endpoints.
- [ ] **pk failure handling.** Confirm `tracker/services.py` degrades sensibly
      when the pk VM is down or times out (`PK_SERVICE_TIMEOUT`), rather than
      500-ing the Today page.
- [ ] **`Note` model fields.** No `date` or `flagged` field, so per-day note
      lookup and "flagged note" styling can't be expressed yet. Add both if
      the notes-on-curve work lands in v1.
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
