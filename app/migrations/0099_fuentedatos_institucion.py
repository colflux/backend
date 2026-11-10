from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0098_cargaarchivo_progreso_actual_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="fuentedatos",
            name="institucion",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fuentes_datos",
                to="app.institucion",
                verbose_name="entidad",
            ),
        ),
    ]
