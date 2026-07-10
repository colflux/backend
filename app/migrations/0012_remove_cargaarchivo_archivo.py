from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0011_cargaarchivo_archivo_blank"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="cargaarchivo",
            name="archivo",
        ),
    ]
