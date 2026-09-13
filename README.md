# Dose

A personal ADHD medication log. You pick a medication and a daily schedule,
log when you actually took each dose, and see the dose's modelled release
curve next to your adherence history.

The app runs on three VMs (a Vue frontend, a Django API, and PostgreSQL).
One `vagrant up` builds all three and seeds two demo accounts.

> **Not medical advice.** The release curve comes from a generic
> pharmacokinetic model (a Bateman one-compartment curve), not from
> measurements of you. The medication descriptions and curve parameters are
> placeholders and have not yet been checked against Medsafe or the NZ
> Formulary. Every page that shows a curve says so. See
> [Known gaps](#known-gaps).

## Contents

- [Quick start](#quick-start)
- [Architecture](#architecture)
- [Running without the VMs](#running-without-the-vms)
- [Tests](#tests)
- [Verifying a deployment](#verifying-a-deployment)
- [Resetting and removing](#resetting-and-removing)
- [Troubleshooting](#troubleshooting)
- [Security note](#security-note)
- [Known gaps](#known-gaps)

## Quick start

### Requirements

Developed and tested on:

| | Version |
|---|---|
| Host OS | Windows 11 (x86_64) |
| Vagrant | 2.4.9 |
| VirtualBox | 7.2.16 |
| Git | 2.55 (Git Bash runs `scripts/smoke.sh` on Windows) |

macOS and Linux on x86_64 should also work, but haven't been tested. ARM
hosts such as Apple Silicon are not supported.

You also need:

- About 4 GB of free RAM (the VMs get 1024, 1024 and 2048 MB) and about
  2 GB of disk for the Ubuntu base box.
- Port 8000 free on the host. If something else holds it, Vagrant picks
  another port (see [Troubleshooting](#troubleshooting)).
- An internet connection for the first `vagrant up`.
- For `scripts/smoke.sh` only: bash, `curl` and Python 3 on the host.

### Start it

```
git clone <this repo>
cd adhd-medication-manager
vagrant up
```

The first run takes 15 to 20 minutes. Most of that is downloading the
Ubuntu box and building the frontend. The `backend` and `frontend`
provisioners each finish with a real HTTP request through the stack, so if
something is broken, `vagrant up` fails instead of reporting success.

Open **http://localhost:8000** and sign in:

| Username | Password | Medication | Scheduled | Notes |
|---|---|---|---|---|
| `admin` | `password` | Vyvanse 30mg | 08:00 | Superuser, can also use `/admin/` |
| `dev1` | `firstpassword` | Dexamfetamine 5mg | 07:30 | Ordinary account |

Each account has ten days of history: a mix of on-time and late doses, one
missed day, and a dose logged today. Every page has data to show from the
first load.

## Architecture

```
 host browser ──► http://localhost:8000
                        │  (VirtualBox port forward 8000 → 80)
                        ▼
   ┌─────────────────────────────────┐
   │ frontend   192.168.56.12        │  nginx: serves the built Vue SPA,
   │                                 │  proxies /api/ /auth/ /admin/ /static/
   └───────────────┬─────────────────┘
                    │ host-only network
   ┌────────────────▼──────────────────┐
   │ backend    192.168.56.11          │  gunicorn running Django 6.1:
   │                                   │  tracker/ users/ pk/
   └────────────────┬──────────────────┘
                    │ psycopg
   ┌────────────────▼───────────────────┐
   │ db         192.168.56.10           │  PostgreSQL 16, database `adhd`
   └────────────────────────────────────┘
```

All three VMs use `bento/ubuntu-24.04`.

- **frontend** (`frontend/`): nginx serves the built Vue app and proxies
  API paths to the backend, so the browser only talks to one origin. The
  frontend only handles presentation and gets all data from the API.
- **backend** (`backend/`): a Django REST API under gunicorn. `users/`
  handles accounts, `tracker/` holds the medication catalogue, dose log and
  notes, and `pk/` does the release-curve and adherence maths. `pk` is a
  plain Python package with no Django imports, called in-process.
- **db**: PostgreSQL. Django migrations own the schema. `scripts/db.sh`
  only creates the role and database and opens it to the private network.

The host is `192.168.56.1` on the host-only network, so it can reach `db`
and `backend` directly without port forwarding.

### Tools

| Tool | Runs on | Used for |
|---|---|---|
| VirtualBox | host | Runs the VMs and the `192.168.56.0/24` host-only network |
| Vagrant | host | Defines the VMs in the [Vagrantfile](Vagrantfile); builds, provisions and destroys them |
| Shell scripts ([scripts/](scripts/)) | all VMs | `common.sh` runs everywhere, then `db.sh`, `backend.sh` or `frontend.sh`. All are safe to rerun |
| PostgreSQL 16 | db | Users, medication catalogue, doses and notes |
| Django + Django REST Framework | backend | API, auth, ORM and migrations; dependencies pinned in [requirements.txt](backend/requirements.txt) |
| gunicorn (systemd) | backend | Serves Django on `:8000` |
| WhiteNoise | backend | Serves the Django admin's static files |
| Node 22 + npm + Vite | frontend | `npm ci` installs from [package-lock.json](frontend/package-lock.json); Vite builds the app |
| nginx | frontend | Serves the built app and proxies to the backend |

## Running without the VMs

This is faster when you're changing code, because Django and Vite run
directly on your machine. Django still needs a database, so pick one of the
two options below.

Set up a virtualenv first:

```
cd backend
python -m venv venv
source venv/Scripts/activate   # Git Bash on Windows; source venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

**Option 1: Postgres on the `db` VM.** The VM must be running. If it's
halted or aborted, every command fails with `connection timeout expired`.
Check with `vagrant status`.

```
vagrant up db
DB_HOST=192.168.56.10 DB_PASSWORD=password python manage.py migrate
DB_HOST=192.168.56.10 DB_PASSWORD=password python manage.py seed_demo
DB_HOST=192.168.56.10 DB_PASSWORD=password python manage.py runserver
```

If `db` was just created, the first command can time out. Wait a few
seconds and run it again.

**Option 2: SQLite, no VMs.** Data goes in `backend/db.sqlite3`.

```
DB_ENGINE=sqlite python manage.py migrate
DB_ENGINE=sqlite python manage.py seed_demo
DB_ENGINE=sqlite python manage.py runserver
```

Then start the frontend in another terminal:

```
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api`, `/auth`, `/admin` and `/static` to
`http://127.0.0.1:8000` (see `vite.config.js`). To use the backend VM
instead, run `VITE_DEV_API=http://192.168.56.11:8000 npm run dev`.

## Tests

```
cd backend
DB_ENGINE=sqlite python manage.py test
```

This needs no VMs or Postgres. It covers the `tracker` and `users` apps,
the `pk` module, and the seed command (`backend/tracker/tests_seed.py`).

The `pk` tests also run without Django installed:

```
cd backend
python -m unittest discover -s pk/tests -t .
```

## Verifying a deployment

With the VMs up, run this from the repository root (Git Bash on Windows):

```
bash scripts/smoke.sh
```

It checks that all three VMs are running, then logs in as `admin` through
nginx and reads the medication selection, dose history, notes, curve and
adherence report. It doesn't change any data. On success it prints
`smoke: all checks passed` and exits 0. Otherwise it lists each failed
check and exits 1.

If Vagrant moved the host port, pass the new one:

```
BASE=http://localhost:2203 bash scripts/smoke.sh
```

## Resetting and removing

The seed command (`backend/tracker/management/commands/seed_demo.py`) runs
on every backend provision. It leaves existing demo accounts alone, so
`vagrant provision backend` won't wipe doses you logged by hand. To wipe
and regenerate the two demo accounts (no other accounts are touched):

```
SEED_RESET=1 vagrant provision backend
```

`vagrant halt` followed by `vagrant up` keeps all data, because
provisioning doesn't rerun on a normal boot.

To delete the VMs and everything in them, including the database:

```
vagrant destroy -f
```

Run `vagrant up` afterwards to rebuild from the seeded starting state.
Vagrant keeps the downloaded base box so rebuilds are faster. To remove it:

```
vagrant box remove bento/ubuntu-24.04
```

The host-only network adapter stays, since other VirtualBox VMs may use it.
You can remove it in VirtualBox's Network Manager.

## Troubleshooting

**The app opens on a port other than 8000.** Another program was using
8000, so Vagrant picked a different port. The `vagrant up` output shows
which one. The app works on any port.

**`connection timeout expired` when running Django on the host.** The `db`
VM isn't running. Run `vagrant up db`, or use SQLite (see
[Running without the VMs](#running-without-the-vms)).

**The frontend VM runs out of memory while provisioning.** The frontend
build uses the most memory, which is why that VM gets 2048 MB. If it still
fails, build on the host and copy `frontend/dist/` onto the VM.

**Provisioning fails partway through apt, npm or pip.** Run
`vagrant provision <db|backend|frontend>` again. The scripts pick up where
they stopped.

**A script fails with `$'\r': command not found`.** The script has Windows
line endings. `.gitattributes` forces LF for `*.sh` and `*/deploy/**`, but
an old clone or a local git setting can override it. Re-clone, or run
`git config core.autocrlf false` and check the files out again.

**`vagrant up` can't create the host-only network.** On some hosts
(especially Windows), VirtualBox needs admin rights the first time. Accept
the elevation prompt.

## Security note

`backend/deploy/backend.env` contains a Django secret key and a database
password, and both are committed on purpose. The VMs are only reachable on
the host-only network, and this is coursework, not a production deployment.
A real deployment would generate both per host and keep them out of the
repository.

## Known gaps

The infrastructure, the `pk` maths and the demo data work end to end. The
medication data is not real yet:

- `Medication.pk_components`, the curve parameters that `pk` uses, are
  placeholder shapes: one component for immediate-release medications and
  two for extended-release. See `backend/pk/README.md` and the comment on
  `Medication.pk_components` in `backend/tracker/models.py`.
- Every medication's `source`, `source_url` and `retrieved` fields are
  blank. The Medications page says so instead of showing a made-up
  citation.
