from rest_framework import serializers

from app.models import Aliado


class InstitucionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aliado
        fields = ["id", "nombre", "correo"]

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio")
        return value
