# Copia MuestraAmbiental.microtopo (por lectura) a UnidadMuestreo.microtopografia
# (fijo por unidad): si varias lecturas de la misma unidad reportan microtopo,
# la primera que se procese gana (no hay forma de saber cuál es "la correcta"
# si llegan a diferir).

from django.db import migrations


def backfill(apps, schema_editor):
    MuestraAmbiental = apps.get_model("app", "MuestraAmbiental")
    Microtopografia = apps.get_model("app", "Microtopografia")

    catalogo = {m.nombre: m for m in Microtopografia.objects.all()}

    for muestra in MuestraAmbiental.objects.exclude(microtopo="").select_related("unidad_muestreo"):
        unidad = muestra.unidad_muestreo
        if unidad.microtopografia_id is not None:
            continue
        valor = catalogo.get(muestra.microtopo)
        if valor is None:
            continue
        unidad.microtopografia = valor
        unidad.save(update_fields=["microtopografia"])


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0103_microtopografia_catalogo'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
