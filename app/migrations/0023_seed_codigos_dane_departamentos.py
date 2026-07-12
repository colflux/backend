from django.db import migrations

CODIGOS_DANE = {
    "Amazonas": "91", "Antioquia": "05", "Arauca": "81", "Atlantico": "08",
    "Bolivar": "13", "Boyaca": "15", "Caldas": "17", "Caqueta": "18",
    "Casanare": "85", "Cauca": "19", "Cesar": "20", "Choco": "27",
    "Cordoba": "23", "Cundinamarca": "25", "Guainia": "94", "Guaviare": "95",
    "Huila": "41", "La_Guajira": "44", "Magdalena": "47", "Meta": "50",
    "Narinio": "52", "Norte_de_Santander": "54", "Putumayo": "86",
    "Quindio": "63", "Risaralda": "66", "San_Andres": "88",
    "Santander": "68", "Sucre": "70", "Tolima": "73",
    "Valle_del_Cauca": "76", "Vaupes": "97", "Vichada": "99",
}


def seed(apps, schema_editor):
    Departamento = apps.get_model("app", "Departamento")
    for nombre, codigo in CODIGOS_DANE.items():
        Departamento.objects.filter(nombre=nombre).update(codigo_dane=codigo)


def unseed(apps, schema_editor):
    Departamento = apps.get_model("app", "Departamento")
    Departamento.objects.filter(nombre__in=CODIGOS_DANE.keys()).update(codigo_dane=None)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0022_departamento_codigo_dane_municipio_codigo_dane"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
