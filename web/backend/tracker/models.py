import datetime

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Medication(models.Model):
    """The read-only catalogue of medications users can select from."""
    id = models.SlugField(primary_key=True, max_length=64)
    name = models.CharField(max_length=100)

    # Sent straight through to pk's POST /timeline as the `components` list:
    # [{"fraction", "delay_h", "ka", "ke" or "half_life_h"}, ...]. web never
    # does the maths itself -- it only stores and forwards these parameters.
    #
    # TODO(you): these are illustrative placeholder shapes (one component for
    # immediate-release, two for extended-release), not real pharmacokinetics
    # -- see pk/README.md's "Medication defaults" TODO. Replace with values
    # sourced from Medsafe or the NZ Formulary and fill in source/source_url/
    # retrieved below before presenting this as real data.
    pk_components = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=255, blank=True, default="")
    source_url = models.URLField(blank=True, default="")
    retrieved = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name


class UserMedication(models.Model):
    """A medication a user has selected; is_active marks the current one."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="medication_selections",
    )
    medication = models.ForeignKey(
        Medication, on_delete=models.PROTECT, related_name="user_selections",
    )
    is_active = models.BooleanField(default=True)
    selected_at = models.DateTimeField(auto_now_add=True)
    # The daily dose time doses are compared against when pk classifies a day
    # on_time/late/missed. No UI to change this yet -- everyone is scheduled
    # for 8am until Medications.vue grows a time picker.
    scheduled_time = models.TimeField(default=datetime.time(8, 0))

    class Meta:
        ordering = ["-selected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"], condition=Q(is_active=True),
                name="unique_active_medication_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user} -> {self.medication_id}"


class Dose(models.Model):
    class Status(models.TextChoices):
        ON_TIME = "on-time", "On time"
        LATE = "late", "Late"
        EDITED = "edited", "Edited"
        MISSED = "missed", "Missed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doses",
    )
    medication = models.ForeignKey(
        Medication, on_delete=models.PROTECT, related_name="doses",
    )
    date = models.DateField(default=timezone.localdate)
    taken_at = models.DateTimeField(null=True, blank=True)  # null = missed
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ON_TIME,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-taken_at"]
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.user} - {self.medication_id} - {self.date}"


class Note(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notes",
    )
    text = models.TextField()
    # The day the note is *about*, which is not always the day it was typed --
    # a note written at 1am belongs to the day whose dose it describes. Kept
    # separate from created_at so per-day lookup (and, later, placing notes on
    # the curve) asks about the right day.
    date = models.DateField(default=timezone.localdate)
    # Marks a note the user wants to stand out -- a bad reaction, a skipped
    # dose, something to raise with a prescriber.
    flagged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.user} note @ {self.created_at:%Y-%m-%d %H:%M}"
