from rest_framework import serializers

from app.api.institucion.serializers import InstitucionSerializer
from app.models import Institucion, Proyecto


class ProyectoResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proyecto
        fields = ["id", "nombre"]


class ProyectoSerializer(serializers.ModelSerializer):
    instituciones = serializers.PrimaryKeyRelatedField(
        queryset=Institucion.objects.all(), many=True, required=False
    )
    instituciones_detalle = InstitucionSerializer(source="instituciones", many=True, read_only=True)

    class Meta:
        model = Proyecto
        fields = [
            "id",
            "nombre",
            "coordinador",
            "correo_coordinador",
            "escala_espacial",
            "objetivo_general",
            "fecha_inicio",
            "fecha_fin",
            "instituciones",
            "instituciones_detalle",
        ]
