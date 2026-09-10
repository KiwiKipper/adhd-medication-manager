from rest_framework import serializers

from .models import Dose, Medication, Note


class MedicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medication
        fields = ["id", "name"]


class DoseSerializer(serializers.ModelSerializer):
    medication_name = serializers.ReadOnlyField(source="medication.name")

    class Meta:
        model = Dose
        fields = [
            "id", "medication", "medication_name", "date", "taken_at",
            "status", "created_at", "updated_at",
        ]
        read_only_fields = ["date", "status", "created_at", "updated_at"]


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "text", "date", "flagged", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
