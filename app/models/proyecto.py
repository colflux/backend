from django.db import models

from .base import TimestampedModel


class Aliado(TimestampedModel):
    nombre = models.CharField("nombre", max_length=255)
    correo = models.EmailField("correo electrónico", blank=True)

    class Meta:
        verbose_name = "aliado"
        verbose_name_plural = "aliados"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Proyecto(TimestampedModel):
    ESCALA_CHOICES = [
        ("Bioma", "Bioma"),
        ("Regional", "Regional"),
        ("Ecosistema", "Ecosistema"),
        ("Sitio", "Sitio"),
        ("Parcela", "Parcela"),
    ]

    codigo = models.CharField("código", max_length=80, unique=True)
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
    aliados = models.ManyToManyField(Aliado, through="ProyectoAliado", related_name="proyectos", blank=True)

    class Meta:
        verbose_name = "proyecto"
        verbose_name_plural = "proyectos"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"


class ProyectoAliado(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    aliado = models.ForeignKey(Aliado, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "proyecto aliado"
        verbose_name_plural = "proyectos aliados"
        unique_together = [("proyecto", "aliado")]

    def __str__(self):
        return f"{self.proyecto} — {self.aliado}"
