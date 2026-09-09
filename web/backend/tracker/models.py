from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Medication(models.Model):
    """The read-only catalogue of medications users can select from."""
    id = models.SlugField(primary_key=True, max_length=64)
    name = models.CharField(max_length=100)

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} note @ {self.created_at:%Y-%m-%d %H:%M}"
