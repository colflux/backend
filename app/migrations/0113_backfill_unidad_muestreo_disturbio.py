# Migra Disturbio de (atributo de Sitio, un solo disturbio por sitio) a
# TipoDisturbio/UnidadMuestreoDisturbio (catálogo + instancia por unidad de
# muestreo, varias por sitio vía fan-out, mismo patrón que
# 0110_backfill_cobertura_manual.py). Por cada Sitio con un Disturbio viejo
# asociado: resuelve/crea el TipoDisturbio por nombre (get_tipo_display() del
# viejo campo 'tipo') y crea una fila de UnidadMuestreoDisturbio por cada
# UnidadMuestreo del sitio, copiando los campos de instancia.
# es_dominante=True: hoy solo se trackea un disturbio por sitio, por
# definición es "el" dominante.

from django.db import migrations


def backfill(apps, schema_editor):
    Sitio = apps.get_model("app", "Sitio")
    TipoDisturbio = apps.get_model("app", "TipoDisturbio")
    UnidadMuestreoDisturbio = apps.get_model("app", "UnidadMuestreoDisturbio")

    tipo_cache = {}
    for sitio in Sitio.objects.exclude(disturbio__isnull=True).select_related("disturbio"):
        disturbio_viejo = sitio.disturbio
        nombre_tipo = disturbio_viejo.get_tipo_display()
        tipo_disturbio = tipo_cache.get(nombre_tipo)
        if tipo_disturbio is None:
            tipo_disturbio, _ = TipoDisturbio.objects.get_or_create(nombre=nombre_tipo)
            tipo_cache[nombre_tipo] = tipo_disturbio

        for unidad in sitio.unidades_muestreo.all():
            UnidadMuestreoDisturbio.objects.get_or_create(
                unidad_muestreo=unidad, disturbio=tipo_disturbio,
                defaults={
                    "descripcion": disturbio_viejo.descripcion,
                    "fecha_inicio": disturbio_viejo.fecha_inicio,
                    "fecha_fin": disturbio_viejo.fecha_fin,
                    "incertidumbre_anios": disturbio_viejo.incertidumbre_anios,
                    "anios_disturbio": disturbio_viejo.anios_disturbio,
                    "anios_desde_fin": disturbio_viejo.anios_desde_fin,
                    "estado_actual": disturbio_viejo.estado_actual,
                    "estado_conservacion": disturbio_viejo.estado_conservacion,
                    "proteccion_legal": disturbio_viejo.proteccion_legal,
                    "es_dominante": True,
                },
            )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0112_tipo_disturbio_y_unidad_muestreo_disturbio'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
