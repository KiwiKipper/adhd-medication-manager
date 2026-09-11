from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Dose, Medication, Note, UserMedication
from .serializers import DoseSerializer, MedicationSerializer, NoteSerializer
from .services import PkServiceError, call_pk_adherence, call_pk_timeline


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def medications_view(request) -> Response:
    medications = Medication.objects.all()
    return Response(MedicationSerializer(medications, many=True).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def my_medication_view(request) -> Response:
    """The user's active medication and the daily time it is scheduled for.

    POST takes "medication" (a catalogue id), "scheduled_time" ("HH:MM"), or
    both. Sending only a time changes the schedule of the current selection,
    so the Medications page's time picker does not have to re-select the
    medication to move someone off the 8am default -- which is what made
    on-time/late classification wrong for anyone not on an 8am dose.
    """
    active = UserMedication.objects.filter(user=request.user, is_active=True).first()

    if request.method == "POST":
        scheduled_time = None
        raw_time = request.data.get("scheduled_time")
        if raw_time is not None:
            # parse_time returns None for the wrong shape but raises for a
            # well-formed impossible time ("25:00"), the same split parse_date
            # has in notes_view below; both are the caller's mistake.
            try:
                scheduled_time = parse_time(raw_time) if isinstance(raw_time, str) else None
            except ValueError:
                scheduled_time = None
            if scheduled_time is None:
                return Response(
                    {"error": "scheduled_time must be HH:MM."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        medication_id = request.data.get("medication")
        if medication_id:
            medication = get_object_or_404(Medication, pk=medication_id)
        elif active is not None:
            medication = active.medication
        else:
            return Response(
                {"error": "medication is required until one has been selected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if active is not None and active.medication_id == medication.id:
            # Same medication, new time: keep the existing selection (and its
            # selected_at) rather than replacing the row for a time change.
            if scheduled_time is not None:
                active.scheduled_time = scheduled_time
                active.save(update_fields=["scheduled_time"])
        else:
            UserMedication.objects.filter(user=request.user, is_active=True).update(is_active=False)
            fields = {"scheduled_time": scheduled_time} if scheduled_time else {}
            # An unspecified time carries the previous selection's time over,
            # so switching medication does not silently reset it to 8am.
            if not fields and active is not None:
                fields = {"scheduled_time": active.scheduled_time}
            active = UserMedication.objects.create(
                user=request.user, medication=medication, is_active=True, **fields,
            )

    if active is None:
        return Response({"medication": None, "scheduled_time": None})
    return Response({
        "medication": MedicationSerializer(active.medication).data,
        "scheduled_time": active.scheduled_time.strftime("%H:%M"),
    })


@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def doses_view(request) -> Response:
    if request.method == "DELETE":
        # Resets today's log so the user can re-take their dose from scratch.
        Dose.objects.filter(user=request.user, date=timezone.localdate()).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def timeline_view(request) -> Response:
    """The release-curve timeline for one dose, computed by pk.

    Defaults to today's logged dose of the active medication; pass
    ?taken_at=<ISO-8601 with offset> to ask about a different moment, and
    ?medication=<catalogue id> to ask about a medication the user has not
    selected -- which is what the Medications page previews a curve with,
    instead of drawing a hand-made shape. web only gathers the medication's
    curve parameters and a taken_at from the database -- pk does the maths.
    """
    medication_id = request.query_params.get("medication")
    if medication_id:
        medication = get_object_or_404(Medication, pk=medication_id)
    else:
        active = UserMedication.objects.filter(user=request.user, is_active=True).first()
        if active is None:
            return Response(
                {"error": "No active medication selected."}, status=status.HTTP_400_BAD_REQUEST,
            )
        medication = active.medication

    taken_at = request.query_params.get("taken_at")
    if not taken_at:
        dose = Dose.objects.filter(user=request.user, date=timezone.localdate()).first()
        if dose is None or dose.taken_at is None:
            return Response(
                {"error": "No dose logged for today yet."}, status=status.HTTP_400_BAD_REQUEST,
            )
        taken_at = dose.taken_at.isoformat()

    if not medication.pk_components:
        return Response(
            {"error": f"{medication.name} has no release-curve parameters configured yet."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = call_pk_timeline(taken_at, medication.pk_components)
    except PkServiceError as exc:
        return Response({"error": exc.message}, status=exc.status_code)

    return Response(result)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def adherence_view(request) -> Response:
    """Adherence stats over the last `days` days (default 14), computed by
    pk. web only gathers each day's scheduled/taken time from the database
    -- classifying a day as on_time/late/missed is pk's job, not web's."""
    active = UserMedication.objects.filter(user=request.user, is_active=True).first()
    if active is None:
        return Response(
            {"error": "No active medication selected."}, status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        days = int(request.query_params.get("days", 14))
    except (TypeError, ValueError):
        return Response({"error": "days must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
    days = max(1, days)

    today = timezone.localdate()
    scheduled = active.scheduled_time.strftime("%H:%M")

    window_start = today - timezone.timedelta(days=days - 1)
    doses_by_date = {
        dose.date: dose
        for dose in Dose.objects.filter(user=request.user, date__gte=window_start)
    }

    # The database only has rows for days a dose was actually logged; any
    # day in the window with no row is a missed dose, so it is synthesized
    # here rather than left out of pk's picture entirely.
    payload_doses = []
    for offset in range(days):
        date = today - timezone.timedelta(days=offset)
        dose = doses_by_date.get(date)
        taken_at = (
            timezone.localtime(dose.taken_at).strftime("%H:%M")
            if dose and dose.taken_at else None
        )
        payload_doses.append({"date": date.isoformat(), "scheduled": scheduled, "taken_at": taken_at})

    try:
        result = call_pk_adherence(payload_doses)
    except PkServiceError as exc:
        return Response({"error": exc.message}, status=exc.status_code)

    return Response(result)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def notes_view(request) -> Response:
    """The signed-in user's notes.

    GET accepts ?date=YYYY-MM-DD (or ?date=today) to fetch just that day's
    notes; without it every note is returned, newest day first. POST takes
    "text", and optionally "date" (defaults to today) and "flagged".
    """
    if request.method == "POST":
        serializer = NoteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        note = serializer.save(user=request.user)
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)

    notes = Note.objects.filter(user=request.user)

    date = request.query_params.get("date")
    if date == "today":
        notes = notes.filter(date=timezone.localdate())
    elif date:
        # parse_date returns None for the wrong shape but raises for a
        # well-formed impossible date ("2026-02-30"); both are the caller's
        # mistake, not a server error.
        try:
            parsed = parse_date(date)
        except ValueError:
            parsed = None
        if parsed is None:
            return Response(
                {"error": "date must be YYYY-MM-DD or 'today'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        notes = notes.filter(date=parsed)

    return Response(NoteSerializer(notes, many=True).data)
