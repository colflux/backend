from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0099_fuentedatos_institucion"),
    ]

    operations = [
        migrations.AddField(
            model_name="fuentedatos",
            name="metodologia",
            field=models.CharField(
                blank=True,
                choices=[
                    ("flujos", "Flujos (CO2/CH4)"),
                    ("cos", "Carbono Orgánico del Suelo (COS)"),
                    ("biomasa", "Biomasa"),
                    ("mom", "Materia Orgánica Muerta (MOM)"),
                ],
                max_length=20,
                verbose_name="metodología",
            ),
        ),
    ]
