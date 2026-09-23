from django.db.models import ProtectedError

from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response

from app.api.base import DataPortalModelViewSet
from app.api.permisos import EscrituraRequiereReportador
from app.api.proyecto.serializers import ProyectoSerializer
from app.models import Proyecto


class ProyectoViewSet(DataPortalModelViewSet):
    authentication_classes = [*DataPortalModelViewSet.authentication_classes, TokenAuthentication]
    permission_classes = [*DataPortalModelViewSet.permission_classes, EscrituraRequiereReportador]
    queryset = Proyecto.objects.all()
    serializer_class = ProyectoSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"error": "No se puede eliminar: el proyecto tiene unidades experimentales u otros datos que lo protegen."},
                status=status.HTTP_400_BAD_REQUEST,
            )
