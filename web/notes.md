1. _init_ treat like python package
2. asgi, and wsgi to communicate with web server
3. settings.py
4. urls.py to routre ot redirect
5. manage.py acts as command line tool

How to create new apps:
python manage.py startapp newapp

use-cases for apps:
    auth
    different users
    display different pages?

In new app:
    admin.py -> register database models
    apps.py
    models.py -> write models
    tests.py -> write automated tests
    views.py -> create views or routes 

Any time make a change to db models:
    Need to change migration
    python manage.py makemigrations


Django admin panel
    need to create user:
        python manage.py createsuperuser
    manage.py runserver
    locahost:8000/admin
    