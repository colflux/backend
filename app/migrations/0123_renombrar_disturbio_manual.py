# Renombra UnidadMuestreoDisturbio -> DisturbioManual: mismo patrón que
# CoberturaManual/EcosistemaManual ("dato digitado" por el equipo de campo
# para una unidad de muestreo). Solo renombra la tabla, no toca datos.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0122_borrar_tipocobertura_valorcobertura'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='UnidadMuestreoDisturbio',
            new_name='DisturbioManual',
        ),
    ]
