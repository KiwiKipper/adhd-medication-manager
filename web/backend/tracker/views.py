from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Dose, Medication, Note, UserMedication
from .serializers import DoseSerializer, MedicationSerializer, NoteSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def medications_view(request) -> Response:
    medications = Medication.objects.all()
    return Response(MedicationSerializer(medications, many=True).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def my_medication_view(request) -> Response:
    if request.method == "POST":
        medication = get_object_or_404(Medication, pk=request.data.get("medication"))
        UserMedication.objects.filter(user=request.user, is_active=True).update(is_active=False)
        UserMedication.objects.create(user=request.user, medication=medication, is_active=True)
    else:
        medication = Medication.objects.filter(
            user_selections__user=request.user, user_selections__is_active=True
        ).first()

    if medication is None:
        return Response({"medication": None})
    return Response({"medication": MedicationSerializer(medication).data})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def doses_view(request) -> Response:
    if request.method == "POST":
        medication_id = request.data.get("medication")
        if medication_id:
            medication = get_object_or_404(Medication, pk=medication_id)
        else:
            active = UserMedication.objects.filter(user=request.user, is_active=True).first()
            if active is None:
                return Response(
                    {"error": "No active medication selected."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            medication = active.medication

        taken_at = request.data.get("taken_at") or timezone.now()
        today = timezone.localdate()
        dose, created = Dose.objects.get_or_create(
            user=request.user, date=today,
            defaults={"medication": medication, "taken_at": taken_at, "status": Dose.Status.ON_TIME},
        )
        if not created:
            dose.medication = medication
            dose.taken_at = taken_at
            dose.status = Dose.Status.EDITED
            dose.save()

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(DoseSerializer(dose).data, status=response_status)

    doses = Dose.objects.filter(user=request.user)
    if request.query_params.get("date") == "today":
        doses = doses.filter(date=timezone.localdate())
    else:
        doses = doses.filter(date__gte=timezone.localdate() - timezone.timedelta(days=13))
    return Response(DoseSerializer(doses, many=True).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def notes_view(request) -> Response:
    if request.method == "POST":
        note = Note.objects.create(user=request.user, text=request.data.get("text", ""))
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)

    notes = Note.objects.filter(user=request.user)
    return Response(NoteSerializer(notes, many=True).data)
