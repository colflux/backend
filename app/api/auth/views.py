import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from app.api.usuario.serializers import UsuarioSerializer
from app.models import PasswordResetToken, Usuario

RESET_TOKEN_TTL = timedelta(hours=1)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        correo = (request.data.get("correo") or "").strip()
        password = request.data.get("password") or ""
        if not correo or not password:
            return Response({"error": "Correo y contraseña son obligatorios."}, status=status.HTTP_400_BAD_REQUEST)

        usuario = (
            Usuario.objects.select_related("auth_user")
            .filter(Q(correo__iexact=correo) | Q(correo_institucional__iexact=correo))
            .first()
        )
        auth_user = usuario.auth_user if usuario else None
        if not auth_user or not auth_user.is_active or not auth_user.check_password(password):
            return Response({"error": "Credenciales inválidas."}, status=status.HTTP_401_UNAUTHORIZED)

        token, _ = Token.objects.get_or_create(user=auth_user)
        return Response({"token": token.key, "usuario": UsuarioSerializer(usuario).data})


class RegistroView(APIView):
    """Registro self-service: crea un Usuario nuevo con nivel `ciudadano` (default del modelo).

    Endpoint separado de `POST /api/usuarios/` (que exige sesión para
    asignar `password`, ver `BloquearPasswordAnonima`) porque este sí debe
    ser público, pero solo para crear cuentas propias sin privilegios — no
    admite elegir nivel, así no sirve como vía alterna para auto-asignarse
    más acceso. Un admin sube el nivel después desde `/team`.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registro"

    @transaction.atomic
    def post(self, request):
        nombre = (request.data.get("nombre") or "").strip()
        correo = (request.data.get("correo") or "").strip()
        password = request.data.get("password") or ""

        if not nombre or not correo or not password:
            return Response(
                {"error": "Nombre, correo y contraseña son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ya_existe = Usuario.objects.filter(
            Q(correo__iexact=correo) | Q(correo_institucional__iexact=correo)
        ).exists()
        User = get_user_model()
        if ya_existe or User.objects.filter(username__iexact=correo).exists():
            return Response(
                {"error": "Ya existe una cuenta con este correo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        auth_user = User.objects.create_user(username=correo, email=correo, password=password)
        usuario = Usuario.objects.create(nombre=nombre, correo=correo, auth_user=auth_user)

        token, _ = Token.objects.get_or_create(user=auth_user)
        return Response(
            {"token": token.key, "usuario": UsuarioSerializer(usuario).data},
            status=status.HTTP_201_CREATED,
        )


class ForgotPasswordView(APIView):
    """Punto de entrada del flujo self-service de recuperación de contraseña.

    Responde 200 exista o no el correo, para no revelar por enumeración qué
    correos tienen cuenta en la plataforma.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "forgot-password"

    def post(self, request):
        correo = (request.data.get("correo") or "").strip()
        if not correo:
            return Response({"error": "El correo es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        usuario = (
            Usuario.objects.select_related("auth_user")
            .filter(Q(correo__iexact=correo) | Q(correo_institucional__iexact=correo))
            .first()
        )
        auth_user = usuario.auth_user if usuario else None
        if auth_user and auth_user.is_active:
            reset_token = PasswordResetToken.objects.create(
                auth_user=auth_user,
                expira_en=timezone.now() + RESET_TOKEN_TTL,
            )
            enlace = f"{settings.FRONTEND_URL}/reset-password?token={reset_token.token}"
            send_mail(
                subject="Recuperar contraseña — COLFLUX",
                message=(
                    "Hola,\n\n"
                    "Recibimos una solicitud para restablecer tu contraseña en COLFLUX.\n"
                    f"Este enlace es válido por 1 hora:\n\n{enlace}\n\n"
                    "Si no solicitaste esto, puedes ignorar este correo."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[correo],
                fail_silently=False,
            )

        return Response({"detail": "Si el correo existe, se envió un enlace de recuperación."})


class ResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "reset-password"

    @transaction.atomic
    def post(self, request):
        token_raw = request.data.get("token") or ""
        password = request.data.get("password") or ""
        if not token_raw or not password:
            return Response({"error": "Token y contraseña son obligatorios."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token_uuid = uuid.UUID(str(token_raw))
        except ValueError:
            return Response({"error": "El enlace no es válido o ya expiró."}, status=status.HTTP_400_BAD_REQUEST)

        reset_token = PasswordResetToken.objects.select_related("auth_user").filter(token=token_uuid).first()
        if not reset_token or not reset_token.esta_vigente():
            return Response({"error": "El enlace no es válido o ya expiró."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(password, user=reset_token.auth_user)
        except DjangoValidationError as exc:
            return Response({"error": " ".join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        reset_token.auth_user.set_password(password)
        reset_token.auth_user.save()
        reset_token.usado = True
        reset_token.save(update_fields=["usado", "updated_at"])

        # Invalida cualquier otro token pendiente de esta cuenta (ej. si se
        # pidieron varios enlaces seguidos, solo el que se usó queda válido).
        PasswordResetToken.objects.filter(auth_user=reset_token.auth_user, usado=False).exclude(
            pk=reset_token.pk
        ).update(usado=True)

        return Response({"detail": "Contraseña actualizada correctamente."})


class LogoutView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        usuario = getattr(request.user, "usuario", None)
        if usuario is None:
            return Response({"error": "Esta cuenta no tiene un usuario asociado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(UsuarioSerializer(usuario).data)
