from rest_framework import serializers

from app.models import Institucion, RolUsuario, Usuario


class RolUsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolUsuario
        fields = ["id", "codigo", "nombre"]


class UsuarioSerializer(serializers.ModelSerializer):
    cargo = serializers.CharField(required=False, allow_blank=True)
    correo = serializers.EmailField(required=False, allow_blank=True)
    correo_institucional = serializers.EmailField(required=False, allow_blank=True)
    institucion = serializers.PrimaryKeyRelatedField(
        queryset=Institucion.objects.all(),
        required=False,
        allow_null=True,
    )
    institucion_nombre = serializers.CharField(source="institucion.nombre", read_only=True)
    roles = serializers.SlugRelatedField(
        many=True,
        slug_field="codigo",
        queryset=RolUsuario.objects.all(),
        required=False,
    )

    class Meta:
        model = Usuario
        fields = [
            "id",
            "nombre",
            "cargo",
            "correo",
            "correo_institucional",
            "institucion",
            "institucion_nombre",
            "roles",
        ]

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio")
        return value

    def create(self, validated_data):
        roles = validated_data.pop("roles", [])
        nombre = validated_data.pop("nombre")
        correo = validated_data.get("correo", "")
        if correo and not validated_data.get("correo_institucional"):
            validated_data["correo_institucional"] = correo

        usuario, created = Usuario.objects.get_or_create(
            nombre=nombre,
            defaults=validated_data,
        )
        self.created = created

        if not created:
            changed_fields = []
            for field, value in validated_data.items():
                if value and not getattr(usuario, field):
                    setattr(usuario, field, value)
                    changed_fields.append(field)
            if changed_fields:
                changed_fields.append("updated_at")
                usuario.save(update_fields=changed_fields)

        if not roles:
            rol_reportador, _ = RolUsuario.objects.get_or_create(
                codigo="reportador",
                defaults={"nombre": "Reportador"},
            )
            roles = [rol_reportador]
        usuario.roles.add(*roles)

        return usuario
