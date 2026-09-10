# pk service

A stateless calculator for the ADHD medication manager. It runs on the `pk`
VM (`192.168.56.11:8001`, private network only) and does two things: turn a
dose's absorption/elimination parameters into a sampled concentration curve
and a set of labelled events, and turn a list of doses into an adherence
report. It has no database, no models, no auth, no sessions and no admin --
every value it needs comes in on the request, and nothing survives past the
response.

## Layout

```
pk/
  manage.py
  pk/            settings.py, urls.py, wsgi.py -- Django wiring only
  timeline/      views.py, urls.py -- thin HTTP layer
  model.py       the Bateman maths, plain Python, no Django import
  config.py      every tunable threshold, in one place
  deploy/        the systemd unit installed by provisions/pk.sh
  tests/         runs standalone, no VM or Django install required for
                 tests/test_model.py; tests/test_views.py additionally
                 needs Django (see requirements.txt)
```

## Running the tests

Model tests only need the Python standard library:

```
py -m unittest discover -s tests -t .
```

(pass `-p test_model.py` to run just the model tests). The endpoint tests
additionally need Django installed (`pip install -r requirements.txt` into a
venv), then:

```
py manage.py test tests
```

which runs both `test_model.py` and `test_views.py` -- the latter via
Django's in-process test client, so it still needs no running server and no
VM.

## Running it locally

```
pip install -r requirements.txt
py manage.py runserver 127.0.0.1:8001
```

In deployment, `provisions/pk.sh` installs a pinned venv at `/opt/pk/venv`
and runs `gunicorn pk.wsgi --bind 0.0.0.0:8001` under systemd
(`deploy/pk.service`), with `DEBUG=False` and `ALLOWED_HOSTS` covering the
private IP.

## Medication defaults

`model.py` and `config.py` take every pharmacological parameter (fraction,
delay, ka, ke/half-life) from the request body -- nothing is hardcoded here.

TODO: once `db/seed/medications.json` exists, real per-medication defaults
(ka, ke or half-life, release-component fractions and delays) belong there,
each with `source`, `source_url` and `retrieved` fields filled in from
Medsafe or the NZ Formulary -- not invented here. Until then, `pk` only
computes on whatever `web` sends it.
