from app.api.base import DataPortalModelViewSet
from app.api.proyecto.serializers import ProyectoSerializer
from app.models import Proyecto


class ProyectoViewSet(DataPortalModelViewSet):
    queryset = Proyecto.objects.all()
    serializer_class = ProyectoSerializer
