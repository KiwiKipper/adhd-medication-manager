# db

The `db` VM runs PostgreSQL 16 (`bento/ubuntu-24.04`, `192.168.56.10`). This
directory holds no files of its own -- everything it would otherwise
contain is either code (Django owns the schema) or generated at provision
time (the role, the database, postgres's own config).

## What's actually here

Nothing tracked. `scripts/db.sh` is what provisions this node:

- installs `postgresql`;
- creates the `adhd` role and database if they don't already exist
  (rerunning `vagrant provision db` is a no-op, not a failure);
- sets `listen_addresses = '*'` and adds a `pg_hba.conf` rule so the
  `backend` VM can connect over the host-only network
  (`192.168.56.0/24`) with `scram-sha-256` auth, rather than only the
  local UNIX socket;
- health-checks itself by connecting over that same private IP as the
  `adhd` role before exiting, so a green provision actually means the
  backend VM can reach it -- not just that postgres is running somewhere.

## Schema

There is no `schema.sql` here and never should be one: `backend/manage.py
migrate` (run by `scripts/backend.sh`) creates every table from
`backend/tracker/models.py` and `backend/users/`, and the data migrations in
`backend/tracker/migrations/` seed the medication catalogue. Django's
migration history is the schema's source of truth.

## Credentials

`DB_NAME`/`DB_USER`/`DB_PASSWORD` are set at the top of `scripts/db.sh`
and must match `backend/deploy/backend.env` exactly -- changing one without
the other breaks the backend VM's next `migrate`. They're checked into
version control because this is a coursework VM with no public exposure;
see the root README's security note.

## Reaching it directly

The host sits on the same host-only network as `192.168.56.1`, so postgres
is reachable straight from the host with no port forwarding:

```
PGPASSWORD=password psql -h 192.168.56.10 -U adhd -d adhd
```

useful for inspecting seeded data (see `backend/tracker/management/commands/seed_demo.py`)
without going through the API at all.
