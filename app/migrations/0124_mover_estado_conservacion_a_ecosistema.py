# Mueve estado_conservacion/proteccion_legal de DisturbioManual a
# EcosistemaManual: describen el estado de manejo humano del ecosistema
# (taxonomía IDEAM), no algo propio de un evento de disturbio puntual — una
# unidad puede tener varios DisturbioManual con el mismo estado de
# conservación repetido, o ninguno, sin que eso cambie el estado real del
# ecosistema. EcosistemaManual está vacía hoy (sin datos de clasificación
# cargados todavía), así que el backfill crea una fila por unidad de
# muestreo con tipo/valor en null, solo para no perder los 175 valores ya
# cargados bajo el modelo viejo — quedan listas para completarse con la
# clasificación real cuando se cargue.

from django.db import migrations, models


def mover_datos(apps, schema_editor):
    DisturbioManual = apps.get_model("app", "DisturbioManual")
    EcosistemaManual = apps.get_model("app", "EcosistemaManual")

    for disturbio in DisturbioManual.objects.all():
        if not disturbio.estado_conservacion and not disturbio.proteccion_legal:
            continue
        EcosistemaManual.objects.get_or_create(
            unidad_muestreo_id=disturbio.unidad_muestreo_id, tipo=None,
            defaults={
                "estado_conservacion": disturbio.estado_conservacion,
                "proteccion_legal": disturbio.proteccion_legal,
            },
        )


def revertir_datos(apps, schema_editor):
    DisturbioManual = apps.get_model("app", "DisturbioManual")
    EcosistemaManual = apps.get_model("app", "EcosistemaManual")

    for eco in EcosistemaManual.objects.all():
        if not eco.estado_conservacion and not eco.proteccion_legal:
            continue
        DisturbioManual.objects.filter(unidad_muestreo_id=eco.unidad_muestreo_id).update(
            estado_conservacion=eco.estado_conservacion,
            proteccion_legal=eco.proteccion_legal,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0123_renombrar_disturbio_manual'),
    ]

    operations = [
        migrations.AddField(
            model_name='ecosistemamanual',
            name='estado_conservacion',
            field=models.CharField(
                blank=True, max_length=20,
                choices=[
                    ("Natural", "Natural (sin manejo humano significativo)"),
                    ("Seminatural", "Seminatural (manejo bajo, regeneración natural dominante)"),
                    ("Manejado", "Manejado (aprovechamiento, ganadería, agroforestería)"),
                    ("Plantacion", "Plantación (vegetación establecida y manejada)"),
                    ("Artificial_Urbano", "Artificial / Urbano (superficie no natural)"),
                ],
                help_text="Estado del ecosistema frente a la presencia de manejo humano (taxonomía del vocabulario IDEAM).",
                verbose_name="estado de conservación",
            ),
        ),
        migrations.AddField(
            model_name='ecosistemamanual',
            name='proteccion_legal',
            field=models.TextField(
                blank=True,
                help_text="Si el sitio está bajo alguna figura de reserva, parque, santuario, etc.",
                verbose_name="protección legal",
            ),
        ),
        migrations.RunPython(mover_datos, revertir_datos),
        migrations.RemoveField(
            model_name='disturbiomanual',
            name='estado_conservacion',
        ),
        migrations.RemoveField(
            model_name='disturbiomanual',
            name='proteccion_legal',
        ),
    ]
