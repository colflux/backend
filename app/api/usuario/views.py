from rest_framework import status
from rest_framework.response import Response

from app.api.base import DataPortalModelViewSet
from app.api.usuario.serializers import RolUsuarioSerializer, UsuarioSerializer
from app.models import RolUsuario, Usuario


class UsuarioViewSet(DataPortalModelViewSet):
    queryset = Usuario.objects.select_related("institucion").prefetch_related("roles")
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
        return super().get_queryset().filter(roles__codigo="reportador").distinct()


class RolUsuarioViewSet(DataPortalModelViewSet):
    queryset = RolUsuario.objects.all()
    serializer_class = RolUsuarioSerializer
