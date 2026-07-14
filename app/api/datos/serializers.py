from rest_framework import serializers

from app.api.proyecto.serializers import ProyectoResumenSerializer
from app.models import FuenteDatos, Proyecto, Usuario


class FuenteDatosSerializer(serializers.ModelSerializer):
    proyecto = ProyectoResumenSerializer(read_only=True)
    proyecto_id = serializers.PrimaryKeyRelatedField(
        queryset=Proyecto.objects.all(),
        source="proyecto",
        write_only=True,
        required=False,
        allow_null=True,
    )
    responsable = serializers.CharField(read_only=True)
    responsable_id = serializers.PrimaryKeyRelatedField(read_only=True, source="reportador")
    responsable_id_write = serializers.PrimaryKeyRelatedField(
        queryset=Usuario.objects.filter(roles__codigo="reportador").distinct(),
        source="reportador",
        write_only=True,
        required=False,
        allow_null=True,
    )
    tipo_label = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_label = serializers.CharField(source="get_estado_display", read_only=True)
    fecha_datos = serializers.DateField(source="fecha_recepcion", read_only=True)
    sitio = serializers.SerializerMethodField()
    ultima_carga_importada_id = serializers.SerializerMethodField()

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
            "responsable_id",
            "responsable_id_write",
            "proyecto",
            "proyecto_id",
            "sitio",
            "fecha_datos",
            "notas",
            "created_at",
            "ultima_carga_importada_id",
        ]
        read_only_fields = ["created_at"]

    def get_sitio(self, obj):
        return None

    def get_ultima_carga_importada_id(self, obj):
        carga = obj.cargas.filter(estado="importado").order_by("-created_at").first()
        return carga.pk if carga else None

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["responsable"] = instance.reportador.nombre if instance.reportador else ""
        return data
