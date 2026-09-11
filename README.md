# Dose

A personal ADHD medication log: pick a medication and a daily schedule, log
when you actually took it, and see the dose's modelled release curve next
to your real adherence history. Built as three VMs -- a Vue single-page app,
a Django API, and PostgreSQL -- brought up with one `vagrant up` and seeded
with two demo accounts so there is something real to look at immediately.

**Not medical advice.** The release curve is a generic pharmacokinetic
model (a Bateman one-compartment curve), not a measurement of you, and the
medication catalogue's descriptive copy and curve parameters are
illustrative placeholders, not yet sourced from Medsafe or the NZ
Formulary -- see [Data correctness](#data-correctness-not-yet-done) below.
Every page that shows a curve says so.

## Architecture

```
 host browser ──► http://localhost:8000
                        │  (VirtualBox port forward 8000 → 80)
                        ▼
   ┌────────────────────────────────┐
   │ frontend   192.168.56.12       │  nginx: serves the built Vue SPA,
   │                                 │  proxies /api/ /auth/ /admin/ /static/
   └───────────────┬─────────────────┘
                    │ host-only network
   ┌────────────────▼─────────────────┐
   │ backend    192.168.56.11         │  gunicorn running Django 6.1:
   │                                   │  tracker/ users/ pk/
   └────────────────┬──────────────────┘
                    │ psycopg
   ┌────────────────▼──────────────────┐
   │ db         192.168.56.10          │  PostgreSQL 16, database `adhd`
   └────────────────────────────────────┘
```

Three VMs, one per tier, all `bento/ubuntu-24.04`:

- **frontend** -- nginx serves the Vue single-page app (`frontend/`) and
  proxies every API path to the backend VM, so the browser only ever talks
  to one origin. The frontend has no logic of its own beyond presentation;
  it calls the API for everything.
- **backend** -- a Django REST API (`backend/`) under gunicorn: user
  accounts (`users/`), the medication catalogue, dose log and notes
  (`tracker/`), and the release-curve/adherence maths (`backend/pk/`, a
  plain Python package with no Django import of its own, called in-process
  -- not a separate service). Owns the schema on the db VM.
- **db** -- PostgreSQL. Django's migrations own the schema entirely;
  `provisions/db.sh` only creates the role, the database, and opens it to
  the private network.

The host sits on the host-only network as `192.168.56.1`, so `db` and
`backend` are reachable directly from the host with no port forwarding --
see [Running it without the VMs](#running-it-without-the-vms) below.

## Prerequisites

- [Vagrant](https://www.vagrantup.com/) and
  [VirtualBox](https://www.virtualbox.org/).
- About 4 GB of RAM free for the three VMs (1024 + 1024 + 2048 MB) and
  roughly 2 GB of disk for the Ubuntu box image (downloaded once, shared by
  all three nodes).
- Host port 8000 free. If it's busy, Vagrant shifts the forward to another
  port automatically (see [Troubleshooting](#troubleshooting)) and the app
  still works there.
- An internet connection during the first `vagrant up`: the box image,
  `apt` packages, Node from NodeSource, and `npm`/`pip` dependencies are all
  fetched then. Later runs of `vagrant provision` reuse what's cached.

## Getting started

```
git clone <this repo>
cd adhd-medication-manager
vagrant up
```

First run takes roughly 15-20 minutes, almost all of it the Ubuntu box
download and `npm ci` + a production Vite build on the frontend VM. Each
node prints its own provisioning log; `backend` and `frontend` both end
with an explicit health check (a real HTTP request through the full stack,
not just "the process started") and fail loudly rather than leaving a green
`vagrant up` behind a broken site.

Open **http://localhost:8000** and sign in with one of the seeded accounts:

| Username | Password | Medication | Scheduled | What it shows |
|---|---|---|---|---|
| `ada` | `dose-demo-2026` | Concerta 36mg | 08:00 | Ten days of history including a dose logged today -- Today, Day curve, History and Notes all have real content from the first load. |
| `sam` | `dose-demo-2026` | Ritalin LA 20mg | 07:30 | Nine days of history, but **no dose logged today** -- demonstrates the take-dose flow. |

There's also an `admin` superuser (same password) for `/admin/`.

This data comes from `backend/tracker/management/commands/seed_demo.py`,
run automatically by `provisions/backend.sh` on every provision. It's
idempotent -- an existing demo account is left alone, so a routine
`vagrant provision backend` never wipes anything logged against a demo
account by hand. To wipe and regenerate all three demo accounts instead:

```
SEED_RESET=1 vagrant provision backend
```

(never touches any other account).

`vagrant halt` then `vagrant up` again keeps everything in postgres --
provisioning doesn't rerun on a plain boot. `vagrant destroy -f && vagrant
up` is a full reset back to the seeded starting state.

## Running the tests

```
cd backend
DB_ENGINE=sqlite python manage.py test
```

No VM, no postgres, and no running backend required -- `DB_ENGINE=sqlite`
switches to a throwaway local database for the run. This covers the
`tracker` and `users` apps, the `pk` release-curve/adherence module
(`backend/pk/tests/`, which also runs completely standalone with no Django
install: `python -m unittest discover -s pk/tests -t .`), and the seed
command (`backend/tracker/tests_seed.py`).

After `vagrant up`, check the running stack end to end from the host:

```
scripts/smoke.sh
```

Logs in as `ada` and walks every page the frontend calls on load --
medication selection, dose history, the release-curve maths, adherence
classification, notes, the single-page app's client-side routing, and a
static asset served through the proxy. A pass means nginx, the proxy to the
backend VM, gunicorn, Django, `pk`, and postgres are all actually working
together. Point it elsewhere with `BASE=http://192.168.56.12 scripts/smoke.sh`.
Needs `curl` and a Python 3 interpreter; no other dependency.

## Running it without the VMs

Faster to iterate on while changing code. `db` and `backend` are reachable
directly on the host-only network once `vagrant up` has run at least once
(or point at your own local postgres/sqlite instead):

```
cd backend
python -m venv venv && venv/Scripts/activate   # or source venv/bin/activate
pip install -r requirements.txt
DB_HOST=192.168.56.10 DB_PASSWORD=password python manage.py migrate
DB_HOST=192.168.56.10 DB_PASSWORD=password python manage.py seed_demo
DB_HOST=192.168.56.10 DB_PASSWORD=password python manage.py runserver
```

```
cd frontend
npm install
npm run dev
```

`npm run dev`'s dev server proxies `/api`, `/auth`, `/admin` and `/static`
to `http://127.0.0.1:8000` by default (see `vite.config.js`); point it at
the provisioned backend VM instead with
`VITE_DEV_API=http://192.168.56.11:8000 npm run dev`.

## Troubleshooting

- **"fixed port collision" / a different port than 8000 opens.** Vagrant's
  `auto_correct` shifted the forward because something else on the host
  already held 8000; watch the `vagrant up` output for the correction
  warning and use whatever port it actually picked. The app works on any
  port -- the frontend calls the API at its own origin rather than a
  hardcoded host:port.
- **The frontend VM runs out of memory mid-provision.** `npm ci` plus a
  production Vite build is the single biggest memory user in the whole
  project; it's why that node gets 2048 MB while the other two get 1024.
  If it still happens on a constrained host, build on the host instead and
  rsync `frontend/dist/` onto the VM by hand.
- **A provision fails partway through apt/npm/pip.** Every provisioning
  script is safe to rerun: `vagrant provision <backend|frontend|db>` picks
  up from wherever it left off rather than redoing completed work.
- **A script fails with `$'\r': command not found`.** A line-ending issue on
  a fresh Windows checkout -- `.gitattributes` forces `*.sh` and `*/deploy/**`
  to LF, but a very old clone or an aggressive local git config can still
  get this wrong. Re-clone, or `git config core.autocrlf false` and re-checkout.
- **`vagrant up` can't create the host-only network.** VirtualBox's
  host-only networking needs an admin-elevated one-time setup on some
  hosts (particularly Windows); accept the elevation prompt if one appears
  on the first `vagrant up`.

## Security note

`backend/deploy/backend.env` has a Django secret key and a database
password checked into version control. That is deliberate, not an
oversight: these VMs are never exposed outside the host-only network and
this is coursework, not a production deployment. A real deployment would
generate both per host and keep them out of the repository.

## Data correctness (not yet done)

This v1 gets the three-VM infrastructure, the in-process `pk` maths, and
seeded demo data working end to end. It does **not** claim the medication
data is real:

- `Medication.pk_components` (the Bateman-curve parameters `pk` samples)
  are illustrative placeholder shapes -- one component for an
  immediate-release medication, two for extended-release -- not real
  pharmacokinetics. See `backend/pk/README.md` and the comment on
  `Medication.pk_components` in `backend/tracker/models.py`.
- Every medication's `source`/`source_url`/`retrieved` fields are blank.
  The Medications page says so rather than showing a plausible-looking
  citation that doesn't exist.

Both are tracked as open work, not claimed as finished by this release.
