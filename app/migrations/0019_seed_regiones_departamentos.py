from django.db import migrations

REGIONES_DEPARTAMENTOS = {
    "Andes": [
        "Antioquia", "Boyaca", "Caldas", "Cundinamarca", "Huila",
        "Norte_de_Santander", "Quindio", "Risaralda", "Santander", "Tolima",
    ],
    "Caribe": [
        "Atlantico", "Bolivar", "Cesar", "Cordoba", "La_Guajira",
        "Magdalena", "Sucre",
    ],
    "Pacifico": ["Choco", "Valle_del_Cauca", "Cauca", "Narinio"],
    "Orinoquia": ["Arauca", "Casanare", "Meta", "Vichada"],
    "Amazonas": ["Amazonas", "Caqueta", "Guainia", "Guaviare", "Putumayo", "Vaupes"],
    "Insular": ["San_Andres"],
}


def seed(apps, schema_editor):
    Region = apps.get_model("app", "Region")
    Departamento = apps.get_model("app", "Departamento")
    for region_nombre, departamentos in REGIONES_DEPARTAMENTOS.items():
        region, _ = Region.objects.get_or_create(nombre=region_nombre)
        for depto_nombre in departamentos:
            Departamento.objects.get_or_create(
                nombre=depto_nombre, defaults={"region": region}
            )


def unseed(apps, schema_editor):
    Region = apps.get_model("app", "Region")
    Departamento = apps.get_model("app", "Departamento")
    nombres = [d for deptos in REGIONES_DEPARTAMENTOS.values() for d in deptos]
    Departamento.objects.filter(nombre__in=nombres, municipios__isnull=True).delete()
    Region.objects.filter(
        nombre__in=REGIONES_DEPARTAMENTOS.keys(), departamentos__isnull=True
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0018_alter_region_nombre"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
