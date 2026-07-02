from django.db import models

from .base import TimestampedModel


class FuenteDatos(TimestampedModel):
    TIPO_CHOICES = [
        ("excel", "Excel (.xlsx / .xls)"),
        ("csv", "CSV"),
        ("shapefile", "Shapefile (.shp)"),
        ("geojson", "GeoJSON"),
        ("api", "API externa"),
        ("base_de_datos", "Base de datos"),
        ("otro", "Otro"),
    ]
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente — sin procesar"),
        ("en_proceso", "En proceso"),
        ("completo", "Completo"),
        ("con_errores", "Con errores"),
    ]

    proyecto = models.ForeignKey(
        "app.Proyecto", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fuentes_datos", verbose_name="proyecto",
    )
    sitio = models.ForeignKey(
        "app.Sitio", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fuentes_datos", verbose_name="sitio",
    )

    nombre = models.CharField("nombre", max_length=255)
    descripcion = models.TextField("descripción", blank=True)
    tipo = models.CharField("tipo", max_length=20, choices=TIPO_CHOICES, default="excel")
    url = models.URLField("enlace al archivo", max_length=2048, blank=True)
    estado = models.CharField("estado", max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    responsable = models.CharField("responsable", max_length=255, blank=True)
    fecha_datos = models.DateField("fecha de los datos", null=True, blank=True)
    notas = models.TextField("notas", blank=True)

    class Meta:
        verbose_name = "fuente de datos"
        verbose_name_plural = "fuentes de datos"
        ordering = ["proyecto", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"
