# Migra las Cobertura existentes (una fila con 6 columnas fijas, enlazada a
# uno o varios Sitio vía el FK viejo Sitio.cobertura) a la forma nueva: una
# fila de Cobertura por (sitio, tipo, valor no vacío). Las filas viejas se
# identifican porque `sitio` (agregado en 0080) todavía viene null -las
# nuevas que se crean acá ya nacen con `sitio` seteado-, y se borran al
# terminar de copiar sus datos.

from django.db import migrations

CAMPO_A_TIPO = [
    ("cobertura_clc", "CLC"),
    ("cobertura_nombre_comun", "Nombre_local"),
    ("clima_koeppen", "Koeppen"),
    ("cobertura_igbp", "IGBP"),
    ("cobertura_ipcc", "IPCC"),
    ("suelo_ipcc", "Suelo_IPCC"),
]


def backfill(apps, schema_editor):
    Cobertura = apps.get_model("app", "Cobertura")
    TipoCobertura = apps.get_model("app", "TipoCobertura")
    Sitio = apps.get_model("app", "Sitio")

    tipos = {t.codigo: t for t in TipoCobertura.objects.all()}

    for vieja in list(Cobertura.objects.filter(sitio__isnull=True)):
        sitios = list(Sitio.objects.filter(cobertura_id=vieja.pk))
        for campo, codigo in CAMPO_A_TIPO:
            valor = (getattr(vieja, campo) or "").strip()
            if not valor:
                continue
            for sitio in sitios:
                Cobertura.objects.get_or_create(sitio=sitio, tipo=tipos.get(codigo), nombre=valor)
        vieja.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0081_seed_tipocobertura'),
    ]

    operations = [
        # Irreversible: una vez fusionadas 6 columnas en N filas por sitio,
        # no hay forma de reconstruir la fila 1-a-1 original con la
        # información que queda en la BD.
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
