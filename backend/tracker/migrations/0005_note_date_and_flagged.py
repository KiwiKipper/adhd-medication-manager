"""Note.date (the day a note is *about*) and Note.flagged.

Existing rows are backfilled from created_at rather than all landing on the
day the migration happened to run, so a pre-existing note stays attached to
the day it was written about.
"""

import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_note_date(apps, schema_editor):
    Note = apps.get_model('tracker', 'Note')
    for note in Note.objects.all().iterator():
        note.date = timezone.localtime(note.created_at).date()
        note.save(update_fields=['date'])


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0004_seed_pk_components'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='note',
            options={'ordering': ['-date', '-created_at']},
        ),
        migrations.AddField(
            model_name='note',
            name='date',
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
        migrations.AddField(
            model_name='note',
            name='flagged',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(backfill_note_date, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='note',
            index=models.Index(fields=['user', 'date'], name='tracker_not_user_id_4d79a8_idx'),
        ),
    ]
