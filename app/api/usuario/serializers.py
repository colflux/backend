from django.contrib.auth import get_user_model
from django.db import transaction

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
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

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
            "nivel",
            "password",
        ]

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio")
        return value

    def _sincronizar_login(self, usuario, password):
        """Crea o actualiza la cuenta de acceso (auth.User) ligada al usuario.

        El correo es el identificador de login: sin correo no se puede
        asignar contraseña, porque no hay con qué loguearse después.
        """
        if not password:
            return
        correo = usuario.correo or usuario.correo_institucional
        if not correo:
            raise serializers.ValidationError(
                {"password": "El usuario necesita un correo para poder asignarle una contraseña."}
            )

        User = get_user_model()
        auth_user = usuario.auth_user
        if auth_user is None:
            auth_user, creada = User.objects.get_or_create(username=correo, defaults={"email": correo})
            if not creada:
                # Ya existía una cuenta de acceso con este correo (por ejemplo un
                # superusuario) y no está ligada a este Usuario todavía — no la
                # reutilizamos silenciosamente, porque eso le pisaría la
                # contraseña a una cuenta ajena.
                raise serializers.ValidationError(
                    {"password": "Ya existe una cuenta de acceso con este correo. Usa otro correo o contacta a un administrador."}
                )
            usuario.auth_user = auth_user
            usuario.save(update_fields=["auth_user", "updated_at"])
        elif auth_user.username != correo:
            auth_user.username = correo
            auth_user.email = correo

        auth_user.set_password(password)
        auth_user.save()

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password", "")
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

        self._sincronizar_login(usuario, password)
        return usuario

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        self._sincronizar_login(instance, password)
        return instance
