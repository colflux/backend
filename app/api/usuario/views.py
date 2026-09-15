from rest_framework import mixins, status, viewsets
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from app.api.base import DataPortalModelViewSet
from app.api.permisos import EscrituraRequiereAdmin
from app.api.usuario.serializers import RolUsuarioSerializer, SolicitudNivelSerializer, UsuarioSerializer
from app.models import RolUsuario, SolicitudNivel, Usuario


class BloquearPasswordAnonima(BasePermission):
    """Exige sesión autenticada para crear o cambiar la contraseña de acceso de un Usuario.

    El resto de operaciones de UsuarioViewSet sigue abierto (AllowAny,
    heredado de DataPortalModelViewSet) — solo se restringe el campo
    `password`, que es lo único que habilita loguearse como ese usuario.
    """

    def has_permission(self, request, view):
        if request.data.get("password"):
            return bool(request.user and request.user.is_authenticated)
        return True


class UsuarioViewSet(DataPortalModelViewSet):
    authentication_classes = [*DataPortalModelViewSet.authentication_classes, TokenAuthentication]
    permission_classes = [*DataPortalModelViewSet.permission_classes, BloquearPasswordAnonima, EscrituraRequiereAdmin]
    queryset = Usuario.objects.select_related("institucion")
    serializer_class = UsuarioSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        output = self.get_serializer(instance)
        response_status = status.HTTP_201_CREATED if getattr(serializer, "created", True) else status.HTTP_200_OK
        data = {**output.data, "created": getattr(serializer, "created", True)}
        return Response(data, status=response_status)


class ReportadorViewSet(UsuarioViewSet):
    def get_queryset(self):
        return super().get_queryset().filter(nivel__in=["reportador", "admin"])


class RolUsuarioViewSet(DataPortalModelViewSet):
    authentication_classes = [*DataPortalModelViewSet.authentication_classes, TokenAuthentication]
    permission_classes = [*DataPortalModelViewSet.permission_classes, EscrituraRequiereAdmin]
    queryset = RolUsuario.objects.all()
    serializer_class = RolUsuarioSerializer


class SolicitudNivelViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Solicitudes de un usuario para subir su nivel de acceso, revisadas por un admin.

    Cualquier usuario autenticado crea y ve sus propias solicitudes; solo un
    admin ve todas y puede resolverlas (cambiar `estado`), lo que además
    actualiza `Usuario.nivel` si queda `aprobada`. No hay `destroy`: una
    solicitud resuelta queda como historial.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = SolicitudNivelSerializer

    def _usuario_actual(self):
        usuario = getattr(self.request.user, "usuario", None)
        if usuario is None:
            raise PermissionDenied("Esta cuenta no tiene un usuario asociado.")
        return usuario

    def get_queryset(self):
        usuario = self._usuario_actual()
        queryset = SolicitudNivel.objects.select_related("usuario", "resuelta_por")
        if usuario.tiene_nivel("admin"):
            return queryset
        return queryset.filter(usuario=usuario)

    def perform_create(self, serializer):
        usuario = self._usuario_actual()
        if SolicitudNivel.objects.filter(usuario=usuario, estado="pendiente").exists():
            raise ValidationError("Ya tienes una solicitud pendiente de resolver.")
        nivel_solicitado = serializer.validated_data.get("nivel_solicitado")
        if usuario.tiene_nivel(nivel_solicitado):
            raise ValidationError({"nivel_solicitado": "Ese nivel no es superior al que ya tienes."})
        serializer.save(usuario=usuario, estado="pendiente")

    def perform_update(self, serializer):
        usuario = self._usuario_actual()
        if not usuario.tiene_nivel("admin"):
            raise PermissionDenied("Solo un administrador puede resolver solicitudes.")
        instancia = serializer.save(resuelta_por=usuario)
        if instancia.estado == "aprobada":
            instancia.usuario.nivel = instancia.nivel_solicitado
            instancia.usuario.save(update_fields=["nivel", "updated_at"])
