# Cierra el rediseño de CoberturaManual: quita sitio/nombre (ya migrados por
# 0109), endurece unidad_muestreo/valor a NOT NULL y agrega la constraint
# final.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0110_backfill_cobertura_manual'),
    ]

    operations = [
        migrations.RemoveField(model_name='coberturamanual', name='sitio'),
        migrations.RemoveField(model_name='coberturamanual', name='nombre'),
        migrations.AlterField(
            model_name='coberturamanual',
            name='unidad_muestreo',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, related_name='coberturas',
                to='app.unidadmuestreo', verbose_name='unidad de muestreo',
            ),
        ),
        migrations.AlterField(
            model_name='coberturamanual',
            name='valor',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name='coberturas_reportadas',
                to='app.valorcobertura', verbose_name='valor',
            ),
        ),
        migrations.AlterModelOptions(
            name='coberturamanual',
            options={'ordering': ['unidad_muestreo', 'tipo'], 'verbose_name': 'cobertura', 'verbose_name_plural': 'coberturas'},
        ),
        migrations.AddConstraint(
            model_name='coberturamanual',
            constraint=models.UniqueConstraint(fields=('unidad_muestreo', 'tipo', 'valor'), name='cobertura_unica_por_unidad_tipo_valor'),
        ),
    ]
