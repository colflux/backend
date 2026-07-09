from rest_framework import serializers

from app.models import Proyecto


class ProyectoResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proyecto
        fields = ["id", "codigo", "nombre"]


class ProyectoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proyecto
        fields = [
            "id",
            "codigo",
            "nombre",
            "coordinador",
            "correo_coordinador",
            "escala_espacial",
            "objetivo_general",
            "fecha_inicio",
            "fecha_fin",
        ]
