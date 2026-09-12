# pk

The release-curve and adherence maths for the ADHD medication manager, as a
plain Python package with no Django import and no I/O of its own. It used to
be a separate HTTP service on its own VM; it is now called in-process from
`tracker/services.py` (`compute_timeline`, `compute_adherence`,
`classify_dose`), which is the only code outside this package that should
import it. It does two things: turn a dose's absorption/elimination
parameters into a sampled concentration curve and a set of labelled events,
and turn a list of doses into an adherence report -- on_time/late/missed,
by the single `classify()` rule both `POST /api/doses/` and
`GET /api/adherence/` now share, so the two can no longer disagree about the
same dose.

## Layout

```
pk/
  __init__.py
  model.py       the Bateman maths and classify(), plain Python, no Django import
  config.py      every tunable threshold, in one place
  tests/
    test_model.py  runs standalone, no Django install required
```

## Running the tests

Standard library only:

```
py -m unittest discover -s pk/tests -t .
```

(from `backend/`; pass `-p test_model.py` to run just this module). Also
picked up automatically by `manage.py test` as part of the full suite --
Django's test runner discovers `test*.py` files under the current directory
regardless of `INSTALLED_APPS`, and `pk` isn't a Django app (no models, no
`apps.py`, not in `INSTALLED_APPS`).

## Medication defaults

`model.py` and `config.py` take every pharmacological parameter (fraction,
delay, ka, ke/half-life) from the caller -- nothing is hardcoded here.

TODO: once real per-medication defaults (ka, ke or half-life, release-component
fractions and delays) are sourced from Medsafe or the NZ Formulary, they
belong on `tracker.Medication.pk_components` (see
`tracker/migrations/0004_seed_pk_components.py`), each with `source`,
`source_url` and `retrieved` filled in -- not invented here. Until then, `pk`
only computes on whatever `tracker` sends it.
