from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from app.api.usuario.serializers import UsuarioSerializer
from app.models import Usuario


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
