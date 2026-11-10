# Completa el catálogo Disturbio (ClasificacionTipo id=9) con los valores
# oficiales del vocabulario DOM_DIST_MGMT de AmeriFlux/BADM que faltaban.
# Solo 3 de los 11 valores estándar habían sido sembrados (los únicos
# presentes en los datos viejos migrados en 0001_initial); este seed agrega
# los 8 restantes para que el catálogo quede completo según la fuente
# oficial (ver context/docs/arquitectura/modelo-disturbio.md).

from django.db import migrations

VALORES_FALTANTES = [
    "Agricultura",
    "Sequía",
    "Fuego",
    "Silvicultura",
    "Evento hidrológico",
    "Plagas y enfermedades",
    "Tormenta o viento",
    "Extremos de temperatura",
]


def seed(apps, schema_editor):
    ClasificacionTipo = apps.get_model("app", "ClasificacionTipo")
    ValorClasificacionTipo = apps.get_model("app", "ValorClasificacionTipo")
    tipo = ClasificacionTipo.objects.get(categoria="Disturbio", nombre="Disturbio")
    for valor in VALORES_FALTANTES:
        ValorClasificacionTipo.objects.get_or_create(tipo=tipo, valor=valor)


def revertir(apps, schema_editor):
    ClasificacionTipo = apps.get_model("app", "ClasificacionTipo")
    ValorClasificacionTipo = apps.get_model("app", "ValorClasificacionTipo")
    tipo = ClasificacionTipo.objects.get(categoria="Disturbio", nombre="Disturbio")
    ValorClasificacionTipo.objects.filter(tipo=tipo, valor__in=VALORES_FALTANTES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0124_mover_estado_conservacion_a_ecosistema'),
    ]

    operations = [
        migrations.RunPython(seed, revertir),
    ]
