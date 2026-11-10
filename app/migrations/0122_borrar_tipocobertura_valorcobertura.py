# Cierra el rediseño de cobertura (ver context/docs/arquitectura/modelo-cobertura.md):
# TipoCobertura/ValorCobertura quedaron huérfanos tras 0121 (CoberturaManual
# ya no los usa, apunta a ClasificacionTipo/ValorClasificacionTipo). Lo
# único que todavía los referenciaba era MapeoColumna.tipo_cobertura (selector
# de "sistema de clasificación" por columna mapeada en el wizard ETL) — se
# repunta a ClasificacionTipo con el mismo mapeo codigo->nombre usado en
# 0119, y recién entonces se borran las tablas viejas.

import django.db.models.deletion
from django.db import migrations, models

_CATEGORIA_POR_CODIGO_COBERTURA = {
    "IPCC": "Cobertura Vegetal",
    "CLC": "Cobertura Vegetal",
    "IGBP": "Cobertura Vegetal",
    "Nombre_local": "Cobertura Vegetal",
    "Vegetacion_funcional": "Cobertura Vegetal",
    "Suelo_IPCC": "Suelo",
    "Koeppen": "Clima",
}
_NOMBRE_NUEVO_POR_CODIGO = {"Nombre_local": "Coloquial"}


def backfill_mapeo_columna(apps, schema_editor):
    MapeoColumna = apps.get_model("app", "MapeoColumna")
    ClasificacionTipo = apps.get_model("app", "ClasificacionTipo")

    for mapeo in MapeoColumna.objects.exclude(tipo_cobertura__isnull=True).select_related("tipo_cobertura"):
        codigo_viejo = mapeo.tipo_cobertura.codigo
        categoria = _CATEGORIA_POR_CODIGO_COBERTURA.get(codigo_viejo, "Cobertura Vegetal")
        nombre_nuevo = _NOMBRE_NUEVO_POR_CODIGO.get(codigo_viejo, codigo_viejo)
        mapeo.tipo_cobertura_nuevo = ClasificacionTipo.objects.get(nombre=nombre_nuevo, categoria=categoria)
        mapeo.save(update_fields=["tipo_cobertura_nuevo"])


def deshacer_backfill(apps, schema_editor):
    MapeoColumna = apps.get_model("app", "MapeoColumna")
    MapeoColumna.objects.update(tipo_cobertura_nuevo=None)


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0121_clasificacion_generica_contraer'),
    ]

    operations = [
        migrations.AddField(
            model_name='mapeocolumna',
            name='tipo_cobertura_nuevo',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='mapeos_columna_nuevo', to='app.clasificaciontipo', verbose_name='tipo de cobertura (nuevo catálogo)',
            ),
        ),
        migrations.RunPython(backfill_mapeo_columna, deshacer_backfill),
        migrations.RemoveField(model_name='mapeocolumna', name='tipo_cobertura'),
        migrations.RenameField(model_name='mapeocolumna', old_name='tipo_cobertura_nuevo', new_name='tipo_cobertura'),
        migrations.AlterField(
            model_name='mapeocolumna',
            name='tipo_cobertura',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='mapeos_columna', to='app.clasificaciontipo', verbose_name='tipo de cobertura',
                help_text="Solo aplica cuando modelo_destino es 'CoberturaManual': etiqueta con qué sistema de "
                          "clasificación (CLC, IPCC, IGBP, …) se guarda el valor de esta columna, ya que una "
                          "unidad de muestreo puede tener varias filas de CoberturaManual (una por columna/sistema de origen).",
            ),
        ),
        migrations.RemoveField(model_name='valorcobertura', name='tipo'),
        migrations.DeleteModel(name='ValorCobertura'),
        migrations.DeleteModel(name='TipoCobertura'),
    ]
