from django.contrib import admin

from .models import Dose, Medication, Note, UserMedication


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("id", "name")


@admin.register(UserMedication)
class UserMedicationAdmin(admin.ModelAdmin):
    list_display = ("user", "medication", "is_active", "selected_at")
    list_filter = ("is_active",)
    search_fields = ("user__username", "medication__name")


@admin.register(Dose)
class DoseAdmin(admin.ModelAdmin):
    list_display = ("user", "medication", "date", "taken_at", "status")
    list_filter = ("status", "medication")
    search_fields = ("user__username",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "text")
    search_fields = ("user__username", "text")
