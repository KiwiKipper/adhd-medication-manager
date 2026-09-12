"""Seeds the demo accounts, so the app works the moment `vagrant up` finishes.

    python manage.py seed_demo           # create any account that doesn't exist
    python manage.py seed_demo --reset   # delete them first, then recreate

Called by scripts/backend.sh on every provision, with --reset only when
SEED_RESET=1 is set. Without --reset an existing account is left alone,
including anything logged against it by hand, so a routine `vagrant provision`
never wipes real use of the demo logins. --reset only ever touches the two
usernames below.

    admin / password         Vyvanse 30mg, scheduled 08:00, superuser
    dev1  / firstpassword    Dexamfetamine 5mg, scheduled 07:30

Both get ten days of history including today, so Today, Curve, History and
Notes all have something to show on first load.
"""

import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from tracker.models import Dose, Medication, Note, UserMedication
from tracker.services import classify_dose

DEMO_USERNAMES = ["admin", "dev1"]

# Marks "today" in the offset lists, resolved at run time rather than given a
# fixed offset: a dose exists for today the instant the VM comes up, whatever
# time of day that is.
TODAY = "today"

# Offsets in minutes from that day's scheduled time, oldest first (today
# minus 9 days ... today). None means nothing was logged -- a missed dose,
# left as a gap for /api/adherence/ to synthesize.
#
# Hand-written rather than randomised, so two `vagrant up`s agree and
# tests_seed.py can assert on the result. The spread is deliberate: mostly
# on time, the odd late day and one gap, which is what makes the History
# page, the adherence percentage and the streak show something real.
ADMIN_OFFSETS = [4, -3, 11, 38, 2, None, 7, 25, -6, TODAY]
DEV1_OFFSETS = [9, 1, 44, -2, 16, 5, None, 31, 3, TODAY]

# {days_ago: (text, flagged)}. Flagged marks something the user would want to
# raise with a prescriber.
ADMIN_NOTES = {
    9: ("Good focus by 9am, lasted most of the morning.", False),
    8: ("Took it a little early with breakfast. Steady day.", False),
    6: ("Long ramp-up today — didn't feel it properly until nearly 10.", True),
    4: ("Skipped; felt off all morning.", True),
    3: ("Appetite dip around lunch, otherwise fine.", False),
    2: ("Good, focused afternoon. No crash.", False),
    1: ("Slow start after the late dose, afternoon picked up.", False),
}

DEV1_NOTES = {
    8: ("Wore off faster than expected, flat by mid-afternoon.", True),
    5: ("Solid day. Kept on top of everything.", False),
    3: ("Missed it — forgot until after lunch.", True),
    1: ("Back on schedule, good energy through the afternoon.", False),
}


class Command(BaseCommand):
    help = (
        "Seeds the demo accounts (admin, dev1) with ten days of dose and note "
        "history. Safe to rerun: skips any username that already exists. Pass "
        "--reset to delete and regenerate both."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help=(
                "Delete the demo users first (cascading to their medication "
                "selection, doses and notes) and recreate them. Never touches "
                "any other account."
            ),
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = User.objects.filter(username__in=DEMO_USERNAMES).delete()
            if deleted:
                self.stdout.write(f"seed_demo: removed {deleted} existing demo row(s)")

        self._seed_user(
            username="admin", password="password", superuser=True,
            first_name="Admin", last_name="User", email="admin@example.com",
            medication_id="vyvanse", scheduled_time=datetime.time(8, 0),
            offsets=ADMIN_OFFSETS, notes=ADMIN_NOTES,
        )
        self._seed_user(
            username="dev1", password="firstpassword", superuser=False,
            first_name="Dev", last_name="One", email="dev1@example.com",
            medication_id="dexamf", scheduled_time=datetime.time(7, 30),
            offsets=DEV1_OFFSETS, notes=DEV1_NOTES,
        )

    @transaction.atomic
    def _seed_user(self, *, username, password, superuser, first_name, last_name,
                   email, medication_id, scheduled_time, offsets, notes):
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"seed_demo: {username} already seeded")
            return

        # create_user/create_superuser skip the AUTH_PASSWORD_VALIDATORS, which
        # is the only reason a password this weak can be set here at all.
        create = User.objects.create_superuser if superuser else User.objects.create_user
        user = create(
            username=username, email=email, password=password,
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
                # Today's dose exists from the moment the VM comes up, whatever
                # time that is: on schedule if we're past it, otherwise ten
                # minutes "ago" so the Curve page has something to draw rather
                # than a dose logged in the future.
                taken_at = scheduled_dt if scheduled_dt <= now else now - datetime.timedelta(minutes=10)
            else:
                taken_at = scheduled_dt + datetime.timedelta(minutes=offset)

            dose = Dose.objects.create(
                user=user, medication=medication, date=date, taken_at=taken_at,
                status=classify_dose(scheduled_time, taken_at),
            )
            # created_at/updated_at are auto_now(_add), so they're set to when
            # this command ran. Backdating them to just after taken_at is what
            # makes Today's "Logged at HH:MM · N min after taking" read like a
            # normal log instead of naming the provisioning time.
            stamp = taken_at + datetime.timedelta(minutes=1)
            Dose.objects.filter(pk=dose.pk).update(created_at=stamp, updated_at=stamp)
            dose_count += 1

        for days_ago, (text, flagged) in notes.items():
            Note.objects.create(
                user=user, text=text, date=today - datetime.timedelta(days=days_ago),
                flagged=flagged,
            )

        role = " (superuser)" if superuser else ""
        self.stdout.write(self.style.SUCCESS(
            f"seed_demo: created {username}{role} -- password {password} "
            f"({dose_count} doses, {len(notes)} notes, {medication.name})"
        ))
