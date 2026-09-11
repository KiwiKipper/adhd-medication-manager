from rest_framework import serializers

from .models import Dose, Medication, Note


class MedicationSerializer(serializers.ModelSerializer):
    """The catalogue entry as the Medications page needs it.

    Includes the provenance fields even though they are still blank on every
    row: the page shows "no source recorded yet" when they are, which is the
    honest thing to say about copy and curve parameters that have not been
    checked against Medsafe or the NZ Formulary. `pk_components` is not
    exposed -- the frontend never does the maths, it asks pk via
    /api/timeline/ for a curve.
    """

    class Meta:
        model = Medication
        fields = [
            "id", "name", "blurb", "description", "drug_class",
            "source", "source_url", "retrieved",
        ]


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
