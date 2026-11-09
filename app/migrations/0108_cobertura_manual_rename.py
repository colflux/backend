# Rediseño de Cobertura: FK de Sitio -> UnidadMuestreo, texto libre -> catálogo
# ValorCobertura. RenameModel conserva los datos existentes; los campos nuevos
# (unidad_muestreo, valor) nacen nullable para poder backfillearlos en la
# siguiente migración antes de endurecerlos a NOT NULL.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0107_ecosistema_manual'),
    ]

    operations = [
        migrations.CreateModel(
            name='ValorCobertura',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('valor', models.CharField(max_length=160, verbose_name='valor')),
                ('tipo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='valores', to='app.tipocobertura', verbose_name='tipo')),
            ],
            options={
                'verbose_name': 'valor de cobertura',
                'verbose_name_plural': 'valores de cobertura',
                'ordering': ['tipo', 'valor'],
            },
        ),
        migrations.AddConstraint(
            model_name='valorcobertura',
            constraint=models.UniqueConstraint(fields=('tipo', 'valor'), name='valor_cobertura_unico_por_tipo'),
        ),
        migrations.RenameModel(old_name='Cobertura', new_name='CoberturaManual'),
        migrations.RemoveConstraint(
            model_name='coberturamanual',
            name='cobertura_unica_por_sitio_tipo_nombre',
        ),
        migrations.AlterField(
            model_name='coberturamanual',
            name='tipo',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='coberturas_reportadas', to='app.tipocobertura', verbose_name='tipo',
                help_text="Sistema de clasificación de este valor. Vacío si el valor de origen no matchea ningún sistema conocido.",
            ),
        ),
        migrations.AddField(
            model_name='coberturamanual',
            name='unidad_muestreo',
            field=models.ForeignKey(
                null=True, blank=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='coberturas', to='app.unidadmuestreo', verbose_name='unidad de muestreo',
            ),
        ),
        migrations.AddField(
            model_name='coberturamanual',
            name='valor',
            field=models.ForeignKey(
                null=True, blank=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='coberturas_reportadas', to='app.valorcobertura', verbose_name='valor',
            ),
        ),
        migrations.AddField(
            model_name='coberturamanual',
            name='porcentaje',
            field=models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='% cobertura'),
        ),
        migrations.AddField(
            model_name='coberturamanual',
            name='orden_dominancia',
            field=models.CharField(
                max_length=12, blank=True, verbose_name='orden de dominancia',
                choices=[('Primaria', 'Primaria'), ('Secundaria', 'Secundaria'), ('Terciaria', 'Terciaria')],
            ),
        ),
    ]
