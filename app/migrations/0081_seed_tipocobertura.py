from django.db import migrations

TIPOS_COBERTURA = [
    ("CLC", "CLC (Corine Land Cover)"),
    ("Nombre_local", "Nombre local"),
    ("Koeppen", "Clima Köppen"),
    ("IGBP", "IGBP"),
    ("IPCC", "IPCC"),
    ("Suelo_IPCC", "Suelo IPCC"),
]


def seed(apps, schema_editor):
    TipoCobertura = apps.get_model("app", "TipoCobertura")
    for codigo, nombre in TIPOS_COBERTURA:
        TipoCobertura.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})


def unseed(apps, schema_editor):
    TipoCobertura = apps.get_model("app", "TipoCobertura")
    TipoCobertura.objects.filter(
        codigo__in=[codigo for codigo, _ in TIPOS_COBERTURA], coberturas__isnull=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0080_tipocobertura_cobertura_sitio_tipo_nombre'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
