# Seeds placeholder Bateman-curve parameters onto the medications 0002
# already created. These are illustrative shapes only -- one component for
# an immediate-release medication, two (an immediate portion plus a delayed
# one) for an extended-release medication -- NOT real pharmacokinetics.
#
# TODO(you): replace with values sourced from Medsafe or the NZ Formulary,
# and fill in each medication's source/source_url/retrieved fields. See
# pk/README.md's "Medication defaults" TODO.

from django.db import migrations

# {medication_id: [{"fraction", "delay_h", "ka", "half_life_h"}, ...]}
PK_COMPONENTS = {
    "ritalin-ir": [
        {"fraction": 1.0, "delay_h": 0.0, "ka": 1.5, "half_life_h": 2.5},
    ],
    "dexamf": [
        {"fraction": 1.0, "delay_h": 0.0, "ka": 1.8, "half_life_h": 3.0},
    ],
    "vyvanse": [
        {"fraction": 1.0, "delay_h": 0.0, "ka": 0.4, "half_life_h": 6.0},
    ],
    "concerta": [
        {"fraction": 0.22, "delay_h": 0.0, "ka": 1.0, "half_life_h": 2.5},
        {"fraction": 0.78, "delay_h": 3.0, "ka": 0.5, "half_life_h": 2.5},
    ],
    "ritalin-la": [
        {"fraction": 0.5, "delay_h": 0.0, "ka": 1.2, "half_life_h": 3.5},
        {"fraction": 0.5, "delay_h": 4.0, "ka": 0.8, "half_life_h": 3.5},
    ],
}


def seed_pk_components(apps, schema_editor):
    Medication = apps.get_model("tracker", "Medication")
    for medication_id, components in PK_COMPONENTS.items():
        Medication.objects.filter(id=medication_id).update(pk_components=components)


def unseed_pk_components(apps, schema_editor):
    Medication = apps.get_model("tracker", "Medication")
    Medication.objects.filter(id__in=PK_COMPONENTS.keys()).update(pk_components=[])


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0003_medication_pk_components_medication_retrieved_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_pk_components, unseed_pk_components),
    ]
