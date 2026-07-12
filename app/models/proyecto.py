from django.db import models

from .base import TimestampedModel


class Institucion(TimestampedModel):
    """Institución participante en los proyectos (universidad, centro de investigación, entidad pública, …)."""

    nombre = models.CharField("nombre", max_length=255)
    correo = models.EmailField("correo electrónico", blank=True)

    class Meta:
        verbose_name = "institución"
        verbose_name_plural = "instituciones"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Proyecto(TimestampedModel):
    """Proyecto de investigación o monitoreo: objetivos, escala espacial, diseño de muestreo, instituciones y usuarios asociados."""

    ESCALA_CHOICES = [
        ("Bioma", "Bioma"),
        ("Regional", "Regional"),
        ("Ecosistema", "Ecosistema"),
        ("Sitio", "Sitio"),
        ("Parcela", "Parcela"),
    ]

    nombre = models.CharField("nombre", max_length=255)
    fecha_inicio = models.DateField("fecha de inicio", null=True, blank=True)
    fecha_fin = models.DateField("fecha de fin", null=True, blank=True)
    coordinador = models.CharField("coordinador", max_length=255, blank=True)
    correo_coordinador = models.EmailField("correo del coordinador", blank=True)
    sitio = models.TextField("descripción del sitio", blank=True)
    abreviatura_sitio = models.CharField("abreviatura del sitio", max_length=80, blank=True)
    objetivo_general = models.TextField("objetivo general", blank=True)
    preguntas_principales = models.TextField("preguntas principales", blank=True)
    escala_espacial = models.CharField("escala espacial", max_length=20, choices=ESCALA_CHOICES, blank=True)
    numero_sitios_monitoreo = models.PositiveIntegerField("número de sitios de monitoreo", null=True, blank=True)
    estructura_muestreo = models.TextField("estructura de muestreo", blank=True)
    tipo_diseno = models.TextField("tipo de diseño", blank=True)
    objetivo_especifico = models.TextField("objetivo específico", blank=True)
    sitio_principal = models.ForeignKey(
        "app.Sitio", on_delete=models.SET_NULL, related_name="proyectos",
        null=True, blank=True, verbose_name="sitio principal",
    )
    instituciones = models.ManyToManyField(
        Institucion,
        through="ProyectoInstitucion",
        related_name="proyectos",
        blank=True,
    )

    class Meta:
        verbose_name = "proyecto"
        verbose_name_plural = "proyectos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class ProyectoInstitucion(models.Model):
    """Relación entre un proyecto y una institución participante."""

    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    institucion = models.ForeignKey(Institucion, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "proyecto institución"
        verbose_name_plural = "proyectos instituciones"
        unique_together = [("proyecto", "institucion")]

    def __str__(self):
        return f"{self.proyecto} — {self.institucion}"


class ProyectoUsuario(models.Model):
    """Relación entre un proyecto y un usuario con el rol que desempeña en él."""

    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name="usuarios_rol")
    usuario = models.ForeignKey("app.Usuario", on_delete=models.CASCADE, related_name="proyectos_rol")
    rol = models.ForeignKey("app.RolUsuario", on_delete=models.CASCADE, related_name="proyectos_usuario")

    class Meta:
        verbose_name = "proyecto usuario"
        verbose_name_plural = "proyectos usuarios"
        unique_together = [("proyecto", "usuario", "rol")]

    def __str__(self):
        return f"{self.proyecto} — {self.usuario} ({self.rol})"
