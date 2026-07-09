from rest_framework import serializers

from app.api.proyecto.serializers import ProyectoResumenSerializer
from app.models import FuenteDatos, Proyecto, RolUsuario, Usuario


class FuenteDatosSerializer(serializers.ModelSerializer):
    proyecto = ProyectoResumenSerializer(read_only=True)
    proyecto_id = serializers.PrimaryKeyRelatedField(
        queryset=Proyecto.objects.all(),
        source="proyecto",
        write_only=True,
        required=False,
        allow_null=True,
    )
    responsable = serializers.CharField(required=False, allow_blank=True, write_only=True)
    tipo_label = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    fecha_datos = serializers.DateField(source="fecha_recepcion", read_only=True)
    sitio = serializers.SerializerMethodField()

    class Meta:
        model = FuenteDatos
        fields = [
            "id",
            "nombre",
            "descripcion",
            "tipo",
            "tipo_label",
            "url",
            "estado",
            "estado_label",
            "responsable",
            "proyecto",
            "proyecto_id",
            "sitio",
            "fecha_datos",
            "notas",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_sitio(self, obj):
        return None

    def create(self, validated_data):
        responsable = validated_data.pop("responsable", "").strip()
        if responsable:
            reportador, _ = Usuario.objects.get_or_create(nombre=responsable)
            rol_reportador, _ = RolUsuario.objects.get_or_create(
                codigo="reportador",
                defaults={"nombre": "Reportador"},
            )
            reportador.roles.add(rol_reportador)
            validated_data["reportador"] = reportador
        return super().create(validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["responsable"] = instance.reportador.nombre if instance.reportador else ""
        return data
