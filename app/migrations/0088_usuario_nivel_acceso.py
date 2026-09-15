from django.db import migrations, models


NIVELES_ACCESO = ("ciudadano", "investigador", "reportador", "admin")


def migrar_roles_a_nivel(apps, schema_editor):
    """Convierte los roles (M2M) de cada usuario en un único nivel en cascada.

    admin_datos -> admin; reportador -> reportador; investigador -> investigador;
    basico/coordinador (sin equivalente en la cascada) -> ciudadano (default).
    Un usuario con auth_user superusuario siempre queda en admin, sin importar
    qué roles tuviera antes.
    """
    Usuario = apps.get_model("app", "Usuario")
    for usuario in Usuario.objects.prefetch_related("roles").select_related("auth_user"):
        codigos = set(usuario.roles.values_list("codigo", flat=True))
        if "admin_datos" in codigos or (usuario.auth_user and usuario.auth_user.is_superuser):
            nivel = "admin"
        elif "reportador" in codigos:
            nivel = "reportador"
        elif "investigador" in codigos:
            nivel = "investigador"
        else:
            nivel = "ciudadano"
        usuario.nivel = nivel
        usuario.save(update_fields=["nivel"])


def revertir_nivel_a_roles(apps, schema_editor):
    """No-op: no hay forma de reconstruir la asignación original de roles."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0086_usuario_auth_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="nivel",
            field=models.CharField(
                choices=[
                    ("ciudadano", "Ciudadano"),
                    ("investigador", "Investigador"),
                    ("reportador", "Reportador"),
                    ("admin", "Administrador"),
                ],
                default="ciudadano",
                max_length=20,
                verbose_name="nivel de acceso",
            ),
        ),
        migrations.RunPython(migrar_roles_a_nivel, revertir_nivel_a_roles),
        migrations.RemoveField(
            model_name="usuario",
            name="roles",
        ),
        migrations.DeleteModel(
            name="UsuarioRol",
        ),
    ]
