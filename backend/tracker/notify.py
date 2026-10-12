"""Late-dose alerts over Amazon SNS.

The backend publishes one message to a topic, and SNS delivers it to every
confirmed subscriber (on AWS, the supporter's email). Off AWS -- Vagrant, a
laptop, the test suite -- SNS_TOPIC_ARN is unset and this does nothing.

Credentials come from the EC2 instance profile (LabInstanceProfile) via
boto3's default chain, so no keys are stored on the instance.
"""
import logging
import os

import boto3
from django.utils import timezone

from .models import Dose

logger = logging.getLogger(__name__)


def notify_if_late(dose, scheduled_time=None):
    """Best-effort SNS alert for a late dose. Never raises: a failed alert
    must not fail the dose write that triggered it."""
    topic = os.environ.get("SNS_TOPIC_ARN")
    if not topic or dose.status != Dose.Status.LATE:
        return

    taken = timezone.localtime(dose.taken_at).strftime("%H:%M") if dose.taken_at else "unknown"
    scheduled = scheduled_time.strftime("%H:%M") if scheduled_time else "unscheduled"
    medication = dose.medication.name
    lines = [
        f"{dose.user.username} logged today's dose late.",
        "",
        f"Medication: {medication}",
        f"Scheduled:  {scheduled}",
        f"Taken:      {taken} ({dose.date.isoformat()})",
    ]
    try:
        boto3.client("sns").publish(
            TopicArn=topic,
            # SNS caps email subjects at 100 characters.
            Subject=f"Dose: {dose.user.username} took {medication} late"[:100],
            Message="\n".join(lines),
        )
    except Exception:
        logger.exception("SNS publish failed for dose %s", dose.pk)
