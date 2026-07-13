import django.db.models.deletion
from django.db import migrations, models


def backfill_proyecto(apps, schema_editor):
    UnidadExperimental = apps.get_model('app', 'UnidadExperimental')
    Proyecto = apps.get_model('app', 'Proyecto')
    primer_proyecto = Proyecto.objects.order_by('id').first()
    if primer_proyecto is not None:
        UnidadExperimental.objects.filter(proyecto__isnull=True).update(proyecto=primer_proyecto)


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0029_unidadmuestreo_sitio'),
    ]

    operations = [
        migrations.AddField(
            model_name='unidadexperimental',
            name='proyecto',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='unidades_experimentales', to='app.proyecto', verbose_name='proyecto'),
        ),
        migrations.RunPython(backfill_proyecto, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='unidadexperimental',
            name='proyecto',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='unidades_experimentales', to='app.proyecto', verbose_name='proyecto'),
        ),
        migrations.AddConstraint(
            model_name='unidadexperimental',
            constraint=models.UniqueConstraint(fields=('proyecto', 'nombre'), name='unidad_experimental_unica_por_proyecto'),
        ),
    ]
