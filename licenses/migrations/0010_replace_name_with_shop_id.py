# Generated manually

from django.db import migrations, models


def copy_name_to_shop_id(apps, schema_editor):
    LicenseTikTok = apps.get_model('licenses', 'LicenseTikTok')
    for license in LicenseTikTok.objects.all():
        if license.name and not license.shop_id:
            license.shop_id = license.name
            license.save(update_fields=['shop_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0009_add_code_to_tiktok'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensetiktok',
            name='shop_id',
            field=models.CharField(max_length=200, null=True, verbose_name='Mã cửa hàng'),
        ),
        migrations.RunPython(copy_name_to_shop_id, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='licensetiktok',
            name='name',
        ),
        migrations.AlterField(
            model_name='licensetiktok',
            name='shop_id',
            field=models.CharField(max_length=200, verbose_name='Mã cửa hàng'),
        ),
    ]

