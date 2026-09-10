"""WSGI entrypoint for the pk service. gunicorn is pointed at pk.wsgi."""
import os
import sys

from django.core.wsgi import get_wsgi_application

# This file lives at pk/pk/wsgi.py; the project root (sibling of model.py,
# config.py and manage.py) is one directory up. gunicorn's WorkingDirectory
# already puts that root on sys.path, so this is normally a no-op -- it just
# means model.py/config.py stay importable even if pk.wsgi is ever loaded by
# a server that does not chdir first.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pk.settings")

application = get_wsgi_application()
