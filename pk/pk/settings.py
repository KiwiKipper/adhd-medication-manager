"""Minimal Django settings for the pk service.

Deliberately excludes:

* DATABASES -- pk never reads or writes a database. web fetches parameters
  from db and hands pk only the numbers it needs; if any code path here ever
  touched django.db it should fail loudly rather than quietly connecting
  somewhere.
* django.contrib.admin / auth / sessions / messages -- pk knows nothing
  about users, accounts, logins or cookies. There is nothing to administer
  and nothing to log into.
* Any ORM models or migrations -- there is no persistent state between
  requests. Restarting the process (or scaling it out) loses nothing,
  because there is nothing to lose.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# pk holds no sessions, no cookies and no user data, so there is nothing for
# a secret key to protect cryptographically here -- but Django's internals
# still expect a non-empty value. Override with PK_SECRET_KEY in deployment
# if you want a per-install value; a fixed development fallback is fine for
# a service with no secrets.
SECRET_KEY = os.environ.get(
    "PK_SECRET_KEY",
    "pk-service-holds-no-secrets-this-key-signs-nothing-sensitive",
)

# Must be False in deployment: this is a private, non-authenticated service
# and a DEBUG=True stack trace would leak internals to whatever can reach it.
DEBUG = os.environ.get("PK_DEBUG", "false").strip().lower() == "true"

# pk sits on a private network with no forwarded port and is reachable only
# from web, but Django still validates the Host header it receives. Default
# covers the private IP pk is provisioned at, the /etc/hosts alias every VM
# gets from provisions/common.sh, and localhost for running off-VM.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "PK_ALLOWED_HOSTS", "192.168.56.11,pk,localhost,127.0.0.1"
    ).split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "timeline",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "pk.urls"

WSGI_APPLICATION = "pk.wsgi.application"

# No DATABASES setting at all -- see module docstring.

USE_TZ = True  # Internal bookkeeping only. Every timestamp pk emits keeps
               # the UTC offset supplied by the caller; nothing is converted
               # through this or through the server's local time.

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
