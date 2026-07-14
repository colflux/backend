from django.http import JsonResponse
from rest_framework.exceptions import ValidationError

from app.api.base import DataPortalModelViewSet
from app.api.datos.serializers import FuenteDatosSerializer
from app.api.proyecto.serializers import ProyectoResumenSerializer
from app.models import FuenteDatos, Proyecto


class FuenteDatosViewSet(DataPortalModelViewSet):
    queryset = FuenteDatos.objects.select_related("proyecto", "reportador")
    serializer_class = FuenteDatosSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        proyecto_id = self.request.query_params.get("proyecto")
        if proyecto_id:
            qs = qs.filter(proyecto_id=proyecto_id)
        return qs

    def perform_update(self, serializer):
        if serializer.instance.estado == "completo":
            raise ValidationError("Esta fuente ya tiene datos cargados: no se puede editar.")
        super().perform_update(serializer)


def fuentes_datos_api(request):
    proyecto_id = request.GET.get("proyecto")
    qs = FuenteDatos.objects.select_related("proyecto", "reportador")
    if proyecto_id:
        qs = qs.filter(proyecto_id=proyecto_id)

    fuentes = FuenteDatosSerializer(qs, many=True).data
    proyectos = ProyectoResumenSerializer(Proyecto.objects.all(), many=True).data

    return JsonResponse({"fuentes": fuentes, "proyectos": proyectos}, json_dumps_params={"ensure_ascii": False})
