from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from app.models import Usuario


class Command(BaseCommand):
    help = (
        "Detecta desalineaciones entre auth.User y app.Usuario: Usuario sin "
        "auth_user (no puede loguearse) y auth.User sin Usuario ligado (no "
        "aparece en /team ni en la API de usuarios). Sale con código de error "
        "si encuentra alguno, para poder usarse como chequeo de salud."
    )

    def handle(self, *args, **options):
        User = get_user_model()

        usuarios_sin_login = Usuario.objects.filter(auth_user__isnull=True)
        ligados = set(Usuario.objects.exclude(auth_user__isnull=True).values_list("auth_user_id", flat=True))
        logins_sin_usuario = User.objects.exclude(id__in=ligados)

        if not usuarios_sin_login.exists() and not logins_sin_usuario.exists():
            self.stdout.write(self.style.SUCCESS("Sin desalineaciones: cada auth.User tiene su Usuario y viceversa."))
            return

        if usuarios_sin_login.exists():
            self.stdout.write(self.style.WARNING(f"Usuario sin auth_user ({usuarios_sin_login.count()}):"))
            for u in usuarios_sin_login:
                self.stdout.write(f"  - id={u.id} nombre={u.nombre!r} correo={u.correo or u.correo_institucional!r}")

        if logins_sin_usuario.exists():
            self.stdout.write(self.style.WARNING(f"auth.User sin Usuario ligado ({logins_sin_usuario.count()}):"))
            for au in logins_sin_usuario:
                self.stdout.write(f"  - id={au.id} username={au.username!r} email={au.email!r} superuser={au.is_superuser}")

        raise CommandError("Se encontraron cuentas desalineadas (ver detalle arriba).")
