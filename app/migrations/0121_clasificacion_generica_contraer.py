# Paso 3/3 del rediseño "clasificación genérica" (ver 0119/0120 y
# context/docs/arquitectura/modelo-cobertura.md): ahora que tipo_nuevo/
# valor_nuevo/valor_texto están respaldados (backfill de 0120), se borran
# los campos/catálogos viejos (TipoCobertura, ValorCobertura,
# TipoClasificacionEcosistema, ValorClasificacionEcosistema, el FK
# `disturbio` de UnidadMuestreoDisturbio) y se renombran tipo_nuevo/
# valor_nuevo a su nombre final tipo/valor.
#
# OJO: a propósito NO se usa Remove+Add (lo que generaría `makemigrations`
# por defecto) para tipo_nuevo/valor_nuevo -> tipo/valor: eso borraría los
# datos ya backfillteados en 0120. Se usa RenameField para conservarlos, y
# RemoveField solo para los campos viejos (tipo/valor originales, que
# apuntaban a TipoCobertura/ValorCobertura/TipoClasificacionEcosistema/
# ValorClasificacionEcosistema, y que 0120 nunca tocó).
#
# TipoCobertura/ValorCobertura se borran del todo en esta migración (ya no
# los usa nada, ver modelo-cobertura.md); TipoClasificacionEcosistema/
# ValorClasificacionEcosistema y el catálogo Disturbio se dejan vivos por
# ahora (fuera de alcance de este cambio, sin consumidores en el modelo pero
# sin otro reemplazo armado todavía).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0120_clasificacion_backfill_campos_nuevos'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='unidadmuestreodisturbio',
            options={
                'ordering': ['unidad_muestreo', 'tipo'],
                'verbose_name': 'disturbio de unidad de muestreo',
                'verbose_name_plural': 'disturbios de unidad de muestreo',
            },
        ),

        # --- CoberturaManual: tipo/valor viejos (FK a TipoCobertura/ValorCobertura) fuera, tipo_nuevo/valor_nuevo pasan a ser los definitivos ---
        migrations.RemoveField(model_name='coberturamanual', name='tipo'),
        migrations.RemoveField(model_name='coberturamanual', name='valor'),
        migrations.RenameField(model_name='coberturamanual', old_name='tipo_nuevo', new_name='tipo'),
        migrations.RenameField(model_name='coberturamanual', old_name='valor_nuevo', new_name='valor'),
        migrations.AlterField(
            model_name='coberturamanual',
            name='tipo',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='coberturas_reportadas', to='app.clasificaciontipo', verbose_name='tipo',
                help_text='Sistema de clasificación de este valor. Vacío si el valor de origen no matchea ningún sistema conocido.',
            ),
        ),
        migrations.AlterField(
            model_name='coberturamanual',
            name='valor',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='coberturas_reportadas', to='app.valorclasificaciontipo', verbose_name='valor',
                help_text='Vacío si el texto de origen no matchea ningún valor conocido del catálogo (ver valor_texto).',
            ),
        ),
        migrations.AlterField(
            model_name='coberturamanual',
            name='valor_texto',
            field=models.CharField(
                blank=True, max_length=160, verbose_name='valor (texto original)',
                help_text='Texto tal como llegó en el import. Se llena siempre; valor queda vacío si no matcheó ningún catálogo.',
            ),
        ),

        # --- EcosistemaManual: mismo patrón ---
        migrations.RemoveField(model_name='ecosistemamanual', name='tipo'),
        migrations.RemoveField(model_name='ecosistemamanual', name='valor'),
        migrations.RenameField(model_name='ecosistemamanual', old_name='tipo_nuevo', new_name='tipo'),
        migrations.RenameField(model_name='ecosistemamanual', old_name='valor_nuevo', new_name='valor'),
        migrations.AlterField(
            model_name='ecosistemamanual',
            name='tipo',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='ecosistemas_manuales', to='app.clasificaciontipo', verbose_name='tipo de clasificación',
            ),
        ),
        migrations.AlterField(
            model_name='ecosistemamanual',
            name='valor',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='ecosistemas_manuales', to='app.valorclasificaciontipo', verbose_name='valor',
                help_text='Vacío si el texto de origen no matchea ningún valor conocido del catálogo (ver valor_texto).',
            ),
        ),
        migrations.AlterField(
            model_name='ecosistemamanual',
            name='valor_texto',
            field=models.CharField(
                blank=True, max_length=120, verbose_name='valor (texto original)',
                help_text='Texto tal como llegó en el import. Se llena siempre; valor queda vacío si no matcheó ningún catálogo.',
            ),
        ),

        # --- UnidadMuestreoDisturbio: 'disturbio' (FK al catálogo Disturbio) fuera, tipo_nuevo/valor_nuevo pasan a ser los definitivos ---
        migrations.RemoveField(model_name='unidadmuestreodisturbio', name='disturbio'),
        migrations.RenameField(model_name='unidadmuestreodisturbio', old_name='tipo_nuevo', new_name='tipo'),
        migrations.RenameField(model_name='unidadmuestreodisturbio', old_name='valor_nuevo', new_name='valor'),
        migrations.AlterField(
            model_name='unidadmuestreodisturbio',
            name='tipo',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='disturbios_unidad', to='app.clasificaciontipo', verbose_name='tipo',
            ),
        ),
        migrations.AlterField(
            model_name='unidadmuestreodisturbio',
            name='valor',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='disturbios_unidad', to='app.valorclasificaciontipo', verbose_name='valor',
                help_text='Vacío si el texto de origen no matchea ningún valor conocido del catálogo (ver valor_texto).',
            ),
        ),
        migrations.AlterField(
            model_name='unidadmuestreodisturbio',
            name='valor_texto',
            field=models.CharField(
                blank=True, max_length=160, verbose_name='valor (texto original)',
                help_text='Texto tal como llegó en el import. Se llena siempre; valor queda vacío si no matcheó ningún catálogo.',
            ),
        ),
    ]
