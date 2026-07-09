from app.api.base import DataPortalModelViewSet
from app.api.institucion.serializers import InstitucionSerializer
from app.models import Institucion


class InstitucionViewSet(DataPortalModelViewSet):
    queryset = Institucion.objects.all()
    serializer_class = InstitucionSerializer
