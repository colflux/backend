"""Control de acceso por nivel (cascada ciudadano < investigador < reportador < admin).

Dos formas de uso, según el tipo de vista:
- Vistas DRF (ViewSets/APIView): permission class `EscrituraRequiereNivel` (o sus
  subclases), que deja lectura libre y exige el nivel mínimo solo en escritura.
- Vistas planas de Django (JsonResponse, sin DRF): decorador `requiere_nivel`,
  que identifica al usuario a mano por el header `Authorization: Token <key>`
  (estas vistas no pasan por `authentication_classes` de DRF).
"""

from functools import wraps

from django.http import JsonResponse
from rest_framework.authtoken.models import Token
from rest_framework.permissions import SAFE_METHODS, BasePermission


def usuario_del_token(request):
    """Resuelve el `Usuario` de dominio ligado al token del header Authorization, si hay uno válido."""
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Token "):
        return None
    try:
        token = Token.objects.select_related("user__usuario").get(key=auth[len("Token "):].strip())
    except Token.DoesNotExist:
        return None
    return getattr(token.user, "usuario", None)


def requiere_nivel(minimo):
    """Decorador para vistas planas de Django: exige que el usuario del token tenga al menos `minimo`."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            usuario = usuario_del_token(request)
            if usuario is None or not usuario.tiene_nivel(minimo):
                return JsonResponse({"error": "No tienes permiso para esta acción."}, status=403)
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


class EscrituraRequiereNivel(BasePermission):
    """Permission class DRF: lectura (GET/HEAD/OPTIONS) libre, escritura exige `nivel_minimo`."""

    nivel_minimo = "reportador"

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        usuario = getattr(request.user, "usuario", None)
        return bool(usuario and usuario.tiene_nivel(self.nivel_minimo))


class EscrituraRequiereReportador(EscrituraRequiereNivel):
    nivel_minimo = "reportador"


class EscrituraRequiereAdmin(EscrituraRequiereNivel):
    nivel_minimo = "admin"
