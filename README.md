# Dose

A personal ADHD medication log. You pick a medication and a daily schedule,
log when you actually took each dose, and see the dose's modelled release
curve next to your adherence history.

There are two ways to run it, from the same scripts:

- **Locally**, on three VMs (a Vue frontend, a Django API, and PostgreSQL).
  One `vagrant up` builds all three and seeds two demo accounts. See
  [Quick start](#quick-start).
- **On AWS**, as two EC2 instances, managed PostgreSQL on RDS, and SNS
  email alerts when a dose is logged late. One `terraform apply` builds it
  all. See [Deploying to AWS](#deploying-to-aws).

> **Not medical advice.** The release curve comes from a generic
> pharmacokinetic model (a Bateman one-compartment curve), not from
> measurements of you. The medication descriptions and curve parameters are
> placeholders and have not yet been checked against Medsafe or the NZ
> Formulary. Every page that shows a curve says so. See
> [Known gaps](#known-gaps).

## Contents

- [Quick start](#quick-start)
- [Architecture](#architecture)
- [Deploying to AWS](#deploying-to-aws)
- [Running without the VMs](#running-without-the-vms)
- [Tests](#tests)
- [Verifying a deployment](#verifying-a-deployment)
- [Resetting and removing](#resetting-and-removing)
- [Troubleshooting](#troubleshooting)
- [Security note](#security-note)
- [From local VMs to AWS](#from-local-vms-to-aws)
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

## Deploying to AWS

The same app on AWS, built entirely from [infra/terraform/](infra/terraform/).
The Vagrant `db` VM is replaced by RDS, and SNS adds a feature the local
version can't have: an email to a supporter when a dose is logged late.

```
 browser ──HTTP :80──►┌──────────────────────────────┐ SG dose-frontend:
                      │ dose-frontend   EC2 t3.micro │  80 from anywhere
                      │ nginx + built Vue SPA        │  22 from my_ip
                      └──────────────┬───────────────┘
                                     │ HTTP :8000 to 172.31.0.20 (private, inside the VPC)
                      ┌──────────────▼───────────────┐ SG dose-backend:
                      │ dose-backend    EC2 t3.micro │  8000 from SG dose-frontend only
                      │ gunicorn + Django            │  22 from my_ip
                      │ instance profile: LabRole    │
                      └───────┬──────────────┬───────┘
                 psycopg :5432│              │HTTPS sns:Publish
                      ┌───────▼────────┐  ┌──▼─────────────────────┐
                      │ dose-db  RDS   │  │ dose-alerts  SNS topic │
                      │ PostgreSQL 16  │  │ → email subscription   │
                      │ not public     │  └────────────────────────┘
                      └────────────────┘ SG dose-db: 5432 from SG dose-backend only
```

- **dose-frontend**: an EC2 instance provisioned at first boot by the same
  `scripts/common.sh` and `scripts/frontend.sh` as the `frontend` VM. nginx
  proxies API paths to the backend's fixed private IP.
- **dose-backend**: an EC2 instance provisioned by `scripts/backend.sh`. It
  reads an env file generated by Terraform instead of the committed one.
  It gets AWS credentials from the Learner Lab's `LabInstanceProfile`
  (role `LabRole`), so no keys are stored on it.
- **dose-db**: RDS PostgreSQL 16 (`db.t3.micro`, 20 GB). Django migrations
  and the demo seed run against it from the backend, exactly as on the VM.
- **dose-alerts**: an SNS topic with an email subscription. When a dose is
  logged more than 30 minutes after its schedule, the backend publishes one
  message ([backend/tracker/notify.py](backend/tracker/notify.py)) and SNS
  emails every confirmed subscriber.

### Data flow: a late dose

1. The browser POSTs `/api/doses/` to nginx on dose-frontend.
2. nginx proxies it to gunicorn on dose-backend over the private network.
3. Django classifies the dose as late and writes the `Dose` row to RDS.
4. Because the row was just created (not edited), Django calls
   `sns:Publish` on `dose-alerts`, with credentials from the instance
   profile. A failure is logged and never fails the dose write.
5. SNS emails the supporter. History then reads the dose back from RDS.

### Trust boundaries

| Boundary | Allowed | Enforced by |
|---|---|---|
| Internet → frontend | HTTP 80 from anywhere; SSH 22 only from `my_ip` | SG `dose-frontend` |
| Frontend → backend | 8000 only from instances in SG `dose-frontend` (a group reference, not an IP range); SSH 22 only from `my_ip` | SG `dose-backend` |
| Backend → database | 5432 only from instances in SG `dose-backend`; RDS has no public address | SG `dose-db`, `publicly_accessible = false` |
| Backend → SNS | IAM permissions of `LabRole`, via the instance profile; short-lived credentials from instance metadata | IAM |

The backend's port 8000 is not reachable from the internet. Only the
frontend can call it.

### Tools and versions

Developed and tested with:

| Tool | Version |
|---|---|
| Terraform | 1.16.4 |
| AWS CLI | 2.37.9 |
| Terraform providers | `hashicorp/aws` 6.68.0, `hashicorp/random` 3.9.1 (pinned in [.terraform.lock.hcl](infra/terraform/.terraform.lock.hcl)) |
| Instances | Ubuntu 24.04 (latest Canonical AMI, looked up at deploy time) |
| Region | `us-east-1` (the only region the AWS Academy Learner Lab allows) |

Every resource is named `dose-<role>` and tagged `Project=dose` and
`Course=COSC349-A2`, which makes them easy to find in the console.

### One-time setup (manual steps)

These can't be automated, and each one says why:

1. **Start the Learner Lab** and copy the credentials from *AWS Details →
   AWS CLI* into `~/.aws/credentials` (under `[default]`), with region
   `us-east-1`. Learner Lab has no long-lived IAM users. The session token
   expires when the lab session ends (about 4 hours), so repeat this step
   whenever `aws` or `terraform` reports `ExpiredToken`. Check it with
   `aws sts get-caller-identity`.
2. **Create the SSH key pair**, once per lab account, and keep it out of the
   repository:
   ```
   aws ec2 create-key-pair --key-name dose-key --query KeyMaterial --output text > ~/.ssh/dose-key.pem
   ```
   The private key exists only on your machine, and never in Git or Terraform state.
3. **Fill in your variables:**
   ```
   cd infra/terraform
   cp terraform.tfvars.example terraform.tfvars
   ```
   Then edit `terraform.tfvars` (it's gitignored):

   | Variable | Required | Default | Meaning |
   |---|---|---|---|
   | `my_ip` | yes | | Your public IP as `/32` (`curl -s https://checkip.amazonaws.com`). Only this address can SSH in. Update it and re-apply when your network changes |
   | `alert_email` | yes | | Where late-dose alerts go |
   | `key_name` | no | `dose-key` | EC2 key pair name |
   | `git_ref` | no | `main` | Branch the instances clone at first boot |
   | `region` | no | `us-east-1` | AWS region |
   | `project` | no | `dose` | Name prefix and `Project` tag |

4. **After the first apply, confirm the SNS subscription.** AWS emails
   `alert_email` a "Subscription Confirmation" link. Alerts are only
   delivered after you click it. AWS requires the recipient to opt in, and
   Terraform can't do that on your behalf.

### Deploy

```
cd infra/terraform
terraform init
terraform apply
```

A full deploy from nothing took **7 min 8 s** for `terraform apply`, and the
site was serving **9 min 31 s** after the apply started (measured 2026-10-12).
Most of that is RDS, about 8 minutes. The instances provision themselves
from the public repository after Terraform returns. The frontend waits for
the backend, which waits for RDS, so the site answers a few minutes after
`apply` finishes. Follow along with
`ssh -i ~/.ssh/dose-key.pem ubuntu@<dns> sudo tail -f /var/log/cloud-init-output.log`.

`terraform output` prints the URL (`frontend_url`), the RDS endpoint and
the SNS topic ARN. Sign in with the demo accounts from
[Quick start](#quick-start).

### Verify

From the repository root (Git Bash on Windows):

```
bash scripts/cloud-smoke.sh
```

It asks AWS whether both instances are running, RDS is available and the
SNS topic has a confirmed subscriber. It then signs in as `dev1` through
the public URL, **writes a note and reads it back** (a round trip through
nginx, the backend and RDS), and reads the dose history, timeline and
adherence report. It prints `cloud-smoke: all checks passed` and exits 0,
or lists each failed check and exits 1. Each run adds one note marked
`cloud-smoke` to `dev1`.

### Redeploy after a code change

The instances clone the repository only at first boot. Push the change, then
replace the instance:

```
terraform apply -replace=aws_instance.backend    # or aws_instance.frontend
```

A change to either `infra/templates/*.tftpl` file replaces its instance on
the next `apply` automatically.

### Stop, start and destroy

```
bash scripts/cloud-stop.sh     # stop both instances and RDS, keep all data
bash scripts/cloud-start.sh    # start them again and print the new URL
```

A stopped instance gets a **new public DNS name** when it starts, so the
URL changes. `cloud-start.sh` refreshes Terraform state and prints the new
one. The Learner Lab also stops everything when a session ends, so run
`cloud-start.sh` after starting a new session.

AWS restarts a stopped RDS instance by itself after 7 days.

```
terraform destroy
```

**`terraform destroy` deletes the database.** RDS is created with
`skip_final_snapshot = true`, so no snapshot is kept, and every logged dose
and note is gone. Use `cloud-stop.sh` to pause without losing data.

### Cost

Prices for `us-east-1`, on-demand, were taken from AWS's published price
data on 2026-10-11. The full workings and assumptions are in the report.

| | Running (lightly used) | Stopped |
|---|---|---|
| 2 × EC2 t3.micro ($0.0104/h) | $15.18/month | $0 |
| 2 × public IPv4 ($0.005/h) | $7.30/month | $0 |
| RDS db.t3.micro ($0.018/h) | $13.14/month | $0 (for up to 7 days) |
| EBS 20 GB gp3 ($0.08/GB-month) | $1.60/month | $1.60/month |
| RDS storage 20 GB ($0.115/GB-month) | $2.30/month | $2.30/month |
| SNS (about 30 alerts/month) | under $0.01 | $0 |
| **Total** | **≈ $39.50/month** | **≈ $3.90/month** |

Storage is the only cost while stopped. The Learner Lab bills against its
course credit rather than a card.

### AWS troubleshooting

**`ExpiredToken` / `RequestExpired` from `aws` or `terraform`.** The Learner
Lab session ended. Re-paste the credentials (step 1 above).

**SSH times out.** Your public IP no longer matches `my_ip`. Update
`terraform.tfvars` and run `terraform apply`. Only the two SSH rules change.

**The old URL stopped working.** The instances were stopped and started.
Run `bash scripts/cloud-start.sh`, or
`terraform apply -refresh-only` then `terraform output frontend_url`.

**No alert email.** Check that the subscription is confirmed:
`aws sns list-subscriptions-by-topic --topic-arn $(terraform output -raw sns_topic_arn)`
should show an ARN, not `PendingConfirmation`. Also check spam. Only late
doses alert, and only when first logged, not on an edit.

**Site returns 502.** nginx is up but the backend isn't answering yet.
On a fresh deploy it is still provisioning, so check its
`cloud-init-output.log`.

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
vagrant ssh backend -c "sudo SEED_RESET=1 bash /vagrant/scripts/backend.sh"
```

(`SEED_RESET=1 vagrant provision backend` does not work: Vagrant doesn't
pass host environment variables into the VM.)

The seeded history is relative to the day it was generated, so on VMs
left running for a few days `smoke.sh` reports `no row dated today`.
Resetting the seed fixes that.

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

**`git clone` fails with `Filename too long` (Windows).** One migration
file has a long name, and a deep clone folder pushes the path past
Windows' 260-character limit. Clone into a shorter folder, or enable long
paths first with `git config --global core.longpaths true`.

**`vagrant up` can't create the host-only network.** On some hosts
(especially Windows), VirtualBox needs admin rights the first time. Accept
the elevation prompt.

## Security note

`backend/deploy/backend.env` contains a Django secret key and a database
password, and both are committed on purpose. The VMs are only reachable on
the host-only network, and this is coursework, not a production deployment.
A real deployment would generate both per host and keep them out of the
repository.

The AWS deployment does exactly that: Terraform generates both
(`random_password`), writes them into `/etc/dose/backend.env` (mode 0600)
on the backend instance, and keeps them only in its local state file.
`.gitignore` excludes `*.tfstate`, `*.tfvars` and `*.pem`, so neither the
state, your IP and email, nor the SSH key can be committed.

## From local VMs to AWS

The first version of Dose ran only on Vagrant. That version is tagged
[`v1.0.0`](https://github.com/KiwiKipper/adhd-medication-manager/releases/tag/v1.0.0).
The AWS deployment reuses its application code and provisioning scripts.
What changed, and why:

| Local (v1.0.0) | AWS | Why |
|---|---|---|
| `db` VM running PostgreSQL, set up by `scripts/db.sh` | RDS PostgreSQL 16 | AWS handles patching, backups and storage. The app doesn't change, because Django already read `DB_HOST` and friends from the environment |
| Scripts read the repo from `/vagrant` | `APP_ROOT` (default `/vagrant`), so EC2 clones to `/opt/dose` and runs the same scripts | One set of provisioning scripts for both targets. Vagrant behaves exactly as before |
| nginx upstream hard-coded to `192.168.56.11` | `__BACKEND_ADDR__` placeholder, filled in by `frontend.sh` from `BACKEND_ADDR` | Terraform supplies the backend's private IP |
| Backend systemd unit hard-coded `WorkingDirectory=/vagrant/backend` | `backend.sh` rewrites it to the real path when installing the unit | Without this, gunicorn can't import the app off Vagrant |
| `/etc/hosts` entries for `db`, `backend`, `frontend` | Only written on Vagrant | The `192.168.56.x` addresses don't exist on AWS |
| Committed `backend.env` with a fixed secret key and DB password | Generated per deploy by Terraform, written only to the instance | Real secrets stay out of Git |
| Fixed host-only IPs, chosen in the Vagrantfile | Default VPC. The backend gets a fixed private IP (`.20` in its subnet); public DNS comes from AWS | A fixed backend IP lets the frontend be configured without Terraform depending on the backend instance |
| Port forward `localhost:8000` → frontend | Frontend's public DNS on port 80; backend not reachable from the internet | Security groups replace the private host-only network |
| No notifications | SNS late-dose email alerts | A managed service that does something a supporter can see |
| `scripts/smoke.sh` (read-only, Vagrant) | Also `scripts/cloud-smoke.sh` (AWS checks plus a write and read-back through RDS) | Verifies the deployed cloud system end to end |

The Vagrant path still works unchanged: `vagrant up` and `smoke.sh` pass
on this version.

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
