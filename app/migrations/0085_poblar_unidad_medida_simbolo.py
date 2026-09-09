import re

from django.db import migrations

_PATRON_SIMBOLO = re.compile(r"\(([^)]+)\)\s*$")


def poblar_simbolo(apps, schema_editor):
    UnidadMedida = apps.get_model("app", "UnidadMedida")
    for unidad in UnidadMedida.objects.filter(simbolo=""):
        match = _PATRON_SIMBOLO.search(unidad.descripcion or "")
        unidad.simbolo = match.group(1) if match else unidad.codigo
        unidad.save(update_fields=["simbolo"])


def revertir(apps, schema_editor):
    UnidadMedida = apps.get_model("app", "UnidadMedida")
    UnidadMedida.objects.update(simbolo="")


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0084_unidad_medida_simbolo_equipo_analizador'),
    ]

    operations = [
        migrations.RunPython(poblar_simbolo, revertir),
    ]
