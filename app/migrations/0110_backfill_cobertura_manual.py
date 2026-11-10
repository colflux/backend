# Migra CoberturaManual de (sitio, tipo, nombre libre) a (unidad_muestreo,
# tipo, valor catalogado): por cada fila vieja, resuelve/crea su ValorCobertura
# y la reemplaza por una fila nueva por cada UnidadMuestreo del sitio (fan-out,
# mismo patrón que 0082_backfill_cobertura_eav.py). Si el sitio no tiene
# ninguna UnidadMuestreo, la fila se descarta (decisión explícita: caso
# "Trillizas", sin unidades de muestreo cargadas).
#
# También absorbe Vegetacion.tipo_cobertura como un TipoCobertura más
# ("Vegetacion_funcional"): por cada Sitio.vegetacion seteado, crea una fila
# de CoberturaManual (orden_dominancia="Primaria") por cada UnidadMuestreo del
# sitio. Al momento de escribir esta migración no hay ninguna fila de
# Vegetacion enlazada a un Sitio en producción, pero se deja el código
# genérico por si llega a haberla antes de correr esta migración.

from django.db import migrations


def backfill(apps, schema_editor):
    CoberturaManual = apps.get_model("app", "CoberturaManual")
    ValorCobertura = apps.get_model("app", "ValorCobertura")
    TipoCobertura = apps.get_model("app", "TipoCobertura")
    Sitio = apps.get_model("app", "Sitio")

    # 1) Resolver/crear ValorCobertura para cada (tipo, nombre) existente.
    valores_cache = {}
    for fila in CoberturaManual.objects.filter(valor__isnull=True, sitio__isnull=False):
        clave = (fila.tipo_id, fila.nombre)
        valor = valores_cache.get(clave)
        if valor is None:
            valor, _ = ValorCobertura.objects.get_or_create(tipo_id=fila.tipo_id, valor=fila.nombre)
            valores_cache[clave] = valor
        fila.valor = valor
        fila.save(update_fields=["valor"])

    # 2) Fan-out: cada fila vieja (sitio, tipo, valor) -> una fila nueva por
    # UnidadMuestreo del sitio. Se borra la fila vieja al terminar.
    for fila_vieja in list(CoberturaManual.objects.filter(sitio__isnull=False)):
        unidades = list(fila_vieja.sitio.unidades_muestreo.all())
        for unidad in unidades:
            CoberturaManual.objects.get_or_create(
                unidad_muestreo=unidad, tipo_id=fila_vieja.tipo_id, valor=fila_vieja.valor,
            )
        fila_vieja.delete()

    # 3) Vegetación funcional: absorbida como TipoCobertura "Vegetacion_funcional".
    tipo_vegetacion, _ = TipoCobertura.objects.get_or_create(
        codigo="Vegetacion_funcional", defaults={"nombre": "Vegetación funcional"},
    )
    Vegetacion = apps.get_model("app", "Vegetacion")
    choices_vegetacion = dict(Vegetacion._meta.get_field("tipo_cobertura").choices or [])
    for sitio in Sitio.objects.exclude(vegetacion__isnull=True).select_related("vegetacion"):
        vegetacion = sitio.vegetacion
        if not vegetacion.tipo_cobertura:
            continue
        etiqueta = choices_vegetacion.get(vegetacion.tipo_cobertura, vegetacion.tipo_cobertura)
        valor, _ = ValorCobertura.objects.get_or_create(tipo=tipo_vegetacion, valor=etiqueta)
        for unidad in sitio.unidades_muestreo.all():
            CoberturaManual.objects.get_or_create(
                unidad_muestreo=unidad, tipo=tipo_vegetacion, valor=valor,
                defaults={"porcentaje": vegetacion.porcentaje_cobertura, "orden_dominancia": "Primaria"},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0109_cobertura_manual_sitio_nullable'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
