from rest_framework import serializers

from app.models import Reportador


class ReportadorSerializer(serializers.ModelSerializer):
    cargo = serializers.CharField(required=False, allow_blank=True)
    correo = serializers.EmailField(required=False, allow_blank=True)
    correo_institucional = serializers.EmailField(required=False, allow_blank=True)
    institucion_asociada = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Reportador
        fields = [
            "id",
            "nombre",
            "cargo",
            "correo",
            "correo_institucional",
            "institucion_asociada",
        ]

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio")
        return value

    def create(self, validated_data):
        nombre = validated_data.pop("nombre")
        correo = validated_data.get("correo", "")
        if correo and not validated_data.get("correo_institucional"):
            validated_data["correo_institucional"] = correo

        responsable, created = Reportador.objects.get_or_create(
            nombre=nombre,
            defaults=validated_data,
        )
        self.created = created

        if not created:
            changed_fields = []
            for field, value in validated_data.items():
                if value and not getattr(responsable, field):
                    setattr(responsable, field, value)
                    changed_fields.append(field)
            if changed_fields:
                changed_fields.append("updated_at")
                responsable.save(update_fields=changed_fields)

        return responsable
