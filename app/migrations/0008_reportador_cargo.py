from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0007_add_mapeo_valores_to_mapeocolumna"),
    ]

    operations = [
        migrations.AddField(
            model_name="reportador",
            name="cargo",
            field=models.CharField(blank=True, max_length=255, verbose_name="cargo"),
        ),
    ]
