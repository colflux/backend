from app.api.base import DataPortalModelViewSet
from app.api.institucion.serializers import InstitucionSerializer
from app.models import Aliado


class InstitucionViewSet(DataPortalModelViewSet):
    queryset = Aliado.objects.all()
    serializer_class = InstitucionSerializer
