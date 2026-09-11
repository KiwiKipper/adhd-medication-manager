# Moves the Medications page's descriptive copy into the catalogue, so the
# page can render from the API instead of the frontend's placeholderData.js.
#
# The blurb/description text is lifted verbatim from that file and the
# drug_class values from Medications.vue's DRUG_CLASS_LABELS -- this is a
# relocation, not new medical content. Like pk_components (see 0004), none
# of it is sourced yet: source/source_url/retrieved are deliberately left
# blank rather than filled with a plausible-looking citation, and the UI
# says so until they are filled in from Medsafe or the NZ Formulary.

from django.db import migrations

# {medication_id: (drug_class, blurb, description)}
COPY = {
    "concerta": (
        "methylphenidate-class stimulant",
        "Two waves \u2014 a morning rise, a dip, then a broader afternoon peak.",
        "An outer layer releases through the morning; an inner core releases "
        "later, giving a second, broader peak in the afternoon before tapering "
        "off by evening.",
    ),
    "ritalin-ir": (
        "methylphenidate-class stimulant",
        "Comes on quickly and wears off within a few hours \u2014 a single peak.",
        "Releases all at once. Effects are typically felt within half an hour, "
        "peak within one to two hours, and taper off within about four hours.",
    ),
    "ritalin-la": (
        "methylphenidate-class stimulant",
        "An immediate dose, then a second delayed pulse about four hours later.",
        "A capsule combining an immediate-release portion with a second, "
        "delayed-release portion, producing two separate release peaks across "
        "the day.",
    ),
    "dexamf": (
        "amfetamine-class stimulant",
        "Fast onset, single peak, shorter tail than the extended-release options.",
        "An immediate-release tablet. Onset is typically fast, with a single "
        "peak and a shorter overall duration than extended-release formulations.",
    ),
    "vyvanse": (
        "amfetamine-class stimulant (prodrug)",
        "Builds gradually to one broad peak and tapers slowly over the day.",
        "A prodrug that is converted gradually in the body, producing a slow "
        "onset, one broad peak, and a longer, gentler taper than "
        "immediate-release options.",
    ),
}


def seed_copy(apps, schema_editor):
    Medication = apps.get_model("tracker", "Medication")
    for medication_id, (drug_class, blurb, description) in COPY.items():
        Medication.objects.filter(id=medication_id).update(
            drug_class=drug_class, blurb=blurb, description=description,
        )


def unseed_copy(apps, schema_editor):
    Medication = apps.get_model("tracker", "Medication")
    Medication.objects.filter(id__in=COPY.keys()).update(
        drug_class="", blurb="", description="",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0006_medication_blurb_medication_description_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_copy, unseed_copy),
    ]
