# Cierra el rediseño de Disturbio: el dato de 0113 ya vive en
# TipoDisturbio/UnidadMuestreoDisturbio, se puede borrar el modelo viejo
# (atributo único por Sitio) y su FK.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0113_backfill_unidad_muestreo_disturbio'),
    ]

    operations = [
        migrations.RemoveField(model_name='sitio', name='disturbio'),
        migrations.DeleteModel(name='Disturbio'),
    ]
