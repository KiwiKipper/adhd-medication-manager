from django.db import migrations

MEDICATIONS = [
    ("concerta", "Concerta 36mg"),
    ("ritalin-ir", "Ritalin IR 10mg"),
    ("ritalin-la", "Ritalin LA 20mg"),
    ("dexamf", "Dexamfetamine 5mg"),
    ("vyvanse", "Vyvanse 30mg"),
]


def seed_medications(apps, schema_editor):
    Medication = apps.get_model("tracker", "Medication")
    for id_, name in MEDICATIONS:
        Medication.objects.get_or_create(id=id_, defaults={"name": name})


def remove_medications(apps, schema_editor):
    Medication = apps.get_model("tracker", "Medication")
    Medication.objects.filter(id__in=[id_ for id_, _ in MEDICATIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_medications, remove_medications),
    ]
