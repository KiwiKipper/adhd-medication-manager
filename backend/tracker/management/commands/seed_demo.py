"""Seeds two demo accounts with history, so the app works the moment
`vagrant up` finishes -- no manual setup, nothing to click through first.

    python manage.py seed_demo            # create any demo user that doesn't exist yet
    python manage.py seed_demo --reset     # delete the demo users first, then recreate them

Called by provisions/backend.sh on every provision (with --reset only when
SEED_RESET=1 is set beforehand). Safe to rerun without --reset: an existing
demo username is left untouched, including anything a marker has logged
against it by hand -- a routine `vagrant provision` never wipes real use of
the demo accounts. --reset is the explicit "start over" switch, and only
ever touches the three usernames below.

Accounts (all share one password so there is exactly one thing to
remember in a demo):

    ada    Ada Lovelace    Concerta 36mg, scheduled 08:00
           Ten days of history *including today* -- Today, Day curve,
           History and Notes all have something to show on first load.
    sam    Sam Rivers      Ritalin LA 20mg, scheduled 07:30
           Nine days of history but deliberately *no dose logged today*,
           so the take-dose flow is there to demonstrate.
    admin  (superuser, no medication) -- for /admin/.
"""

import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from tracker.models import Dose, Medication, Note, UserMedication
from tracker.services import classify_dose

DEMO_PASSWORD = "dose-demo-2026"
DEMO_USERNAMES = ["ada", "sam", "admin"]

# Marks "today" in an offsets list below, resolved at run time rather than
# given a fixed minute offset: a dose exists for today the instant the VM
# comes up, whatever time of day that happens to be.
TODAY = "today"

# Offsets in minutes from that day's scheduled time, oldest first (today -
# 9 days ... today). None means no dose was logged that day -- a missed
# dose, left as a gap for /api/adherence/ to synthesize, same as a real gap
# in anyone's log.
ADA_OFFSETS = [3, 12, -5, 48, 7, None, 2, 15, 40, TODAY]
SAM_OFFSETS = [6, -2, 35, 4, 1, 9, None, 5, 11, None]

# {days_ago: (text, flagged)}. Concerta genuinely has a delayed second
# release (see tracker/migrations/0004_seed_pk_components.py), which is what
# the flagged note on ada's +48-late day is describing.
ADA_NOTES = {
    9: ("Good focus by 9am, lasted most of the morning.", False),
    8: ("Ran a few minutes late grabbing the dose, but the day evened out fine.", False),
    7: ("Took it early with breakfast. Smooth, steady day.", False),
    6: ("Crashed hard around 4pm — second release felt late.", True),
    4: ("Skipped; felt off all morning.", True),
    3: ("Appetite dip around lunch, otherwise steady.", False),
    2: ("Good, focused afternoon. No crash this time.", False),
    1: ("Slow start after the late dose, but the afternoon picked up.", False),
}

SAM_NOTES = {
    7: ("Dose felt late today; morning was rough.", False),
    3: ("Missed today — forgot until after lunch.", True),
    1: ("Back on schedule, good energy through the afternoon.", False),
}


class Command(BaseCommand):
    help = (
        "Seeds demo accounts (ada, sam, admin) with ten days of dose/note "
        "history, so the app has something to show the moment `vagrant up` "
        "finishes. Safe to rerun: skips any demo username that already "
        "exists. Pass --reset to delete and regenerate all three."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help=(
                "Delete the demo users first (cascades to their medication "
                "selection, doses and notes) and recreate them from scratch. "
                "Never touches any other account."
            ),
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = User.objects.filter(username__in=DEMO_USERNAMES).delete()
            if deleted:
                self.stdout.write(f"seed_demo: removed {deleted} existing demo row(s)")

        self._seed_admin()
        self._seed_user(
            username="ada", first_name="Ada", last_name="Lovelace",
            email="ada@example.com", medication_id="concerta",
            scheduled_time=datetime.time(8, 0), offsets=ADA_OFFSETS, notes=ADA_NOTES,
        )
        self._seed_user(
            username="sam", first_name="Sam", last_name="Rivers",
            email="sam@example.com", medication_id="ritalin-la",
            scheduled_time=datetime.time(7, 30), offsets=SAM_OFFSETS, notes=SAM_NOTES,
        )

    def _seed_admin(self):
        if User.objects.filter(username="admin").exists():
            self.stdout.write("seed_demo: admin already seeded")
            return
        User.objects.create_superuser(
            username="admin", email="admin@example.com", password=DEMO_PASSWORD,
        )
        self.stdout.write(self.style.SUCCESS(
            f"seed_demo: created admin (superuser) -- password {DEMO_PASSWORD}"
        ))

    @transaction.atomic
    def _seed_user(self, *, username, first_name, last_name, email,
                    medication_id, scheduled_time, offsets, notes):
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"seed_demo: {username} already seeded")
            return

        user = User.objects.create_user(
            username=username, email=email, password=DEMO_PASSWORD,
            first_name=first_name, last_name=last_name,
        )
        medication = Medication.objects.get(pk=medication_id)
        UserMedication.objects.create(
            user=user, medication=medication, is_active=True,
            scheduled_time=scheduled_time,
        )

        today = timezone.localdate()
        tz = timezone.get_current_timezone()
        dose_count = 0

        for index, offset in enumerate(offsets):
            days_ago = len(offsets) - 1 - index
            date = today - datetime.timedelta(days=days_ago)
            if offset is None:
                continue

            scheduled_dt = timezone.make_aware(
                datetime.datetime.combine(date, scheduled_time), tz,
            )
            if offset == TODAY:
                now = timezone.now()
                # A dose exists for today from the moment the VM comes up,
                # whatever time that happens to be: at or after the
                # scheduled time, logged right on schedule; before it, ten
                # minutes "ago" so there is still something for the Curve
                # page to draw rather than a dose logged in the future.
                taken_at = scheduled_dt if scheduled_dt <= now else now - datetime.timedelta(minutes=10)
            else:
                taken_at = scheduled_dt + datetime.timedelta(minutes=offset)

            dose = Dose.objects.create(
                user=user, medication=medication, date=date, taken_at=taken_at,
                status=classify_dose(scheduled_time, taken_at),
            )
            # created_at/updated_at are auto_now(_add) -- set only on
            # .create(). Backdating them a minute after taken_at (rather
            # than leaving them at "when this command ran") is what makes
            # the Today page's "Logged at HH:MM · N min after taking"
            # line read like a normal log instead of naming the
            # provisioning time.
            stamp = taken_at + datetime.timedelta(minutes=1)
            Dose.objects.filter(pk=dose.pk).update(created_at=stamp, updated_at=stamp)
            dose_count += 1

        for days_ago, (text, flagged) in notes.items():
            Note.objects.create(
                user=user, text=text, date=today - datetime.timedelta(days=days_ago),
                flagged=flagged,
            )

        self.stdout.write(self.style.SUCCESS(
            f"seed_demo: created {username} ({dose_count} doses, {len(notes)} notes) "
            f"-- password {DEMO_PASSWORD}"
        ))
