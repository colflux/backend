from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0117_mover_codigo_metadato_a_unidad_muestreo"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="unidadmuestreo",
            name="unidadmuestreo_proyecto_codigo_metadato_unico",
        ),
        migrations.RemoveField(
            model_name="unidadmuestreo",
            name="proyecto",
        ),
        migrations.RemoveField(
            model_name="unidadmuestreo",
            name="fuente_datos",
        ),
        migrations.AlterField(
            model_name="unidadmuestreo",
            name="unidad_experimental",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE, related_name="unidades_muestreo",
                to="app.unidadexperimental", verbose_name="unidad experimental",
                help_text=(
                    "Unidad experimental a la que pertenece. Se resuelve sola con la que se creó o "
                    "seleccionó en el paso anterior para la misma fila del archivo — si la fuente no "
                    "distingue unidad experimental de unidad de muestreo, el importador crea una "
                    "unidad experimental igual, nunca se deja sin asignar (de ahí sale el proyecto: "
                    "`unidad_experimental.proyecto`, siempre obligatorio)."
                ),
            ),
        ),
        migrations.AddConstraint(
            model_name="unidadmuestreo",
            constraint=models.UniqueConstraint(
                condition=~models.Q(codigo_metadato=""),
                fields=("unidad_experimental", "codigo_metadato"),
                name="unidadmuestreo_unidad_experimental_codigo_metadato_unico",
            ),
        ),
    ]
