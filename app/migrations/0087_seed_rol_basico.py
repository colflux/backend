from django.db import migrations


def crear_rol_basico(apps, schema_editor):
    RolUsuario = apps.get_model("app", "RolUsuario")
    RolUsuario.objects.get_or_create(codigo="basico", defaults={"nombre": "Básico"})


def eliminar_rol_basico(apps, schema_editor):
    RolUsuario = apps.get_model("app", "RolUsuario")
    RolUsuario.objects.filter(codigo="basico").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0086_usuario_auth_user"),
    ]

    operations = [
        migrations.RunPython(crear_rol_basico, eliminar_rol_basico),
    ]
