# Refactor de Cobertura a un esquema sitio/tipo/nombre (ver
# app/models/cobertura.py): esta migración solo agrega la nueva forma, sin
# tocar las columnas viejas todavía -eso pasa en 0083, después de que 0082
# haya migrado los datos existentes-.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0079_alter_cobertura_suelo_ipcc'),
    ]

    operations = [
        migrations.CreateModel(
            name='TipoCobertura',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('codigo', models.CharField(max_length=30, unique=True, verbose_name='código')),
                ('nombre', models.CharField(max_length=120, verbose_name='nombre')),
            ],
            options={
                'verbose_name': 'tipo de cobertura',
                'verbose_name_plural': 'tipos de cobertura',
                'ordering': ['nombre'],
            },
        ),
        migrations.AddField(
            model_name='mapeocolumna',
            name='tipo_cobertura',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='mapeos_columna', to='app.tipocobertura',
                verbose_name='tipo de cobertura',
                help_text="Solo aplica cuando modelo_destino es 'Cobertura': etiqueta con qué sistema de "
                          "clasificación (CLC, IPCC, IGBP, …) se guarda el valor de esta columna, ya que un "
                          "sitio puede tener varias filas de Cobertura (una por columna/sistema de origen).",
            ),
        ),
        # sitio/nombre nacen nullable/blank a propósito -distinto del modelo
        # final (ver 0083)- para poder agregarlas a filas ya existentes sin
        # default forzado; se migran en 0082 y recién ahí se cierran.
        migrations.AddField(
            model_name='cobertura',
            name='sitio',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='coberturas', to='app.sitio', verbose_name='sitio',
            ),
        ),
        migrations.AddField(
            model_name='cobertura',
            name='tipo',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='coberturas', to='app.tipocobertura', verbose_name='tipo',
                help_text='Sistema de clasificación de este valor. Vacío si el valor de origen no matchea ningún sistema conocido.',
            ),
        ),
        migrations.AddField(
            model_name='cobertura',
            name='nombre',
            field=models.CharField(blank=True, default='', max_length=160, verbose_name='nombre reportado'),
        ),
    ]
