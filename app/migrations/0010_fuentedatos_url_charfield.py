from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0009_usuario_roles_institucion"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fuentedatos",
            name="url",
            field=models.CharField(
                blank=True,
                max_length=2048,
                verbose_name="enlace o ruta al archivo",
            ),
        ),
    ]
