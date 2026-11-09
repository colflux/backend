import django.db.models.deletion
from django.db import migrations, models


def backfill_proyecto(apps, schema_editor):
    UnidadMuestreo = apps.get_model("app", "UnidadMuestreo")
    for unidad in UnidadMuestreo.objects.select_related("unidad_experimental").all():
        unidad.proyecto_id = unidad.unidad_experimental.proyecto_id
        unidad.save(update_fields=["proyecto"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0116_alter_institucion_nombre_alter_proyecto_nombre"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="sitio",
            name="codigo_metadatos",
        ),
        migrations.AddField(
            model_name="unidadmuestreo",
            name="codigo_metadato",
            field=models.CharField(
                blank=True, max_length=255, verbose_name="código de metadato",
                help_text="Identificador de la unidad de muestreo en el sistema de metadatos externo de la fuente, si lo trae.",
            ),
        ),
        migrations.AddField(
            model_name="unidadmuestreo",
            name="proyecto",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="unidades_muestreo", to="app.proyecto", verbose_name="proyecto",
                help_text="Proyecto al que pertenece esta unidad de muestreo, independiente de si tiene unidad experimental asignada.",
            ),
        ),
        migrations.RunPython(backfill_proyecto, noop),
        migrations.AlterField(
            model_name="unidadmuestreo",
            name="proyecto",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="unidades_muestreo", to="app.proyecto", verbose_name="proyecto",
                help_text="Proyecto al que pertenece esta unidad de muestreo, independiente de si tiene unidad experimental asignada.",
            ),
        ),
        migrations.AddConstraint(
            model_name="unidadmuestreo",
            constraint=models.UniqueConstraint(
                condition=~models.Q(codigo_metadato=""),
                fields=("proyecto", "codigo_metadato"),
                name="unidadmuestreo_proyecto_codigo_metadato_unico",
            ),
        ),
    ]
