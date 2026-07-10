from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0010_fuentedatos_url_charfield"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cargaarchivo",
            name="archivo",
            field=models.FileField(blank=True, upload_to="cargas/%Y/%m/", verbose_name="archivo"),
        ),
    ]
