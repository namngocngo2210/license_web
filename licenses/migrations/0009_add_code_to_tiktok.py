# Generated manually

from django.db import migrations, models
import uuid


def generate_codes_for_existing_licenses(apps, schema_editor):
    LicenseTikTok = apps.get_model('licenses', 'LicenseTikTok')
    for license in LicenseTikTok.objects.all():
        if not license.code:
            license.code = uuid.uuid4()
            license.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0008_add_expired_at_to_tiktok'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensetiktok',
            name='code',
            field=models.UUIDField(null=True, editable=False, unique=True),
        ),
        migrations.RunPython(generate_codes_for_existing_licenses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='licensetiktok',
            name='code',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]

