# Generated manually for the usuarios/roles domain refactor.

import django.db.models.deletion
from django.db import migrations, models


def migrar_reportadores_a_usuarios(apps, schema_editor):
    Reportador = apps.get_model("app", "Reportador")
    Institucion = apps.get_model("app", "Institucion")
    RolUsuario = apps.get_model("app", "RolUsuario")
    Usuario = apps.get_model("app", "Usuario")
    UsuarioRol = apps.get_model("app", "UsuarioRol")
    FuenteDatos = apps.get_model("app", "FuenteDatos")

    rol_reportador, _ = RolUsuario.objects.get_or_create(
        codigo="reportador",
        defaults={"nombre": "Reportador"},
    )

    reportador_to_usuario = {}
    for reportador in Reportador.objects.all():
        institucion = None
        nombre_institucion = (reportador.institucion_asociada or "").strip()
        if nombre_institucion:
            institucion, _ = Institucion.objects.get_or_create(
                nombre=nombre_institucion,
                defaults={"correo": ""},
            )

        usuario = Usuario.objects.create(
            nombre=reportador.nombre,
            cargo=reportador.cargo,
            correo_institucional=reportador.correo_institucional,
            correo=reportador.correo,
            institucion=institucion,
        )
        UsuarioRol.objects.get_or_create(usuario=usuario, rol=rol_reportador)
        reportador_to_usuario[reportador.pk] = usuario.pk

    for fuente in FuenteDatos.objects.exclude(reportador_id__isnull=True):
        usuario_id = reportador_to_usuario.get(fuente.reportador_id)
        if usuario_id:
            fuente.reportador_usuario_id = usuario_id
            fuente.save(update_fields=["reportador_usuario"])


def crear_roles_base(apps, schema_editor):
    RolUsuario = apps.get_model("app", "RolUsuario")
    roles = {
        "reportador": "Reportador",
        "coordinador": "Coordinador",
        "investigador": "Investigador",
        "admin_datos": "Administrador de datos",
    }
    for codigo, nombre in roles.items():
        RolUsuario.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0008_reportador_cargo"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Aliado",
            new_name="Institucion",
        ),
        migrations.AlterModelOptions(
            name="institucion",
            options={
                "ordering": ["nombre"],
                "verbose_name": "institución",
                "verbose_name_plural": "instituciones",
            },
        ),
        migrations.RenameModel(
            old_name="ProyectoAliado",
            new_name="ProyectoInstitucion",
        ),
        migrations.RenameField(
            model_name="proyecto",
            old_name="aliados",
            new_name="instituciones",
        ),
        migrations.RenameField(
            model_name="proyectoinstitucion",
            old_name="aliado",
            new_name="institucion",
        ),
        migrations.AlterModelOptions(
            name="proyectoinstitucion",
            options={
                "verbose_name": "proyecto institución",
                "verbose_name_plural": "proyectos instituciones",
            },
        ),
        migrations.AlterUniqueTogether(
            name="proyectoinstitucion",
            unique_together={("proyecto", "institucion")},
        ),
        migrations.CreateModel(
            name="RolUsuario",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("codigo", models.CharField(max_length=80, unique=True, verbose_name="código")),
                ("nombre", models.CharField(max_length=120, verbose_name="nombre")),
            ],
            options={
                "verbose_name": "rol de usuario",
                "verbose_name_plural": "roles de usuario",
                "ordering": ["nombre"],
            },
        ),
        migrations.CreateModel(
            name="Usuario",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("nombre", models.CharField(max_length=255, verbose_name="nombre")),
                ("cargo", models.CharField(blank=True, max_length=255, verbose_name="cargo")),
                (
                    "correo_institucional",
                    models.EmailField(blank=True, max_length=254, verbose_name="correo institucional"),
                ),
                (
                    "correo",
                    models.EmailField(blank=True, max_length=254, verbose_name="correo personal"),
                ),
                (
                    "institucion",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="usuarios",
                        to="app.institucion",
                        verbose_name="institución",
                    ),
                ),
            ],
            options={
                "verbose_name": "usuario",
                "verbose_name_plural": "usuarios",
                "ordering": ["nombre"],
            },
        ),
        migrations.CreateModel(
            name="UsuarioRol",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "rol",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="app.rolusuario",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="app.usuario",
                    ),
                ),
            ],
            options={
                "verbose_name": "usuario rol",
                "verbose_name_plural": "usuarios roles",
                "unique_together": {("usuario", "rol")},
            },
        ),
        migrations.AddField(
            model_name="usuario",
            name="roles",
            field=models.ManyToManyField(
                blank=True,
                related_name="usuarios",
                through="app.UsuarioRol",
                to="app.rolusuario",
            ),
        ),
        migrations.AddField(
            model_name="fuentedatos",
            name="reportador_usuario",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fuentes_datos",
                to="app.usuario",
                verbose_name="reportador",
            ),
        ),
        migrations.RunPython(migrar_reportadores_a_usuarios, migrations.RunPython.noop),
        migrations.RunPython(crear_roles_base, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="fuentedatos",
            name="reportador",
        ),
        migrations.RenameField(
            model_name="fuentedatos",
            old_name="reportador_usuario",
            new_name="reportador",
        ),
        migrations.DeleteModel(
            name="Reportador",
        ),
    ]
