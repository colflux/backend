from django.contrib.gis.db import models as gis_models
from django.db import models

from .base import TimestampedModel


class ClasificacionTipo(TimestampedModel):
    """Catálogo genérico de sistemas de clasificación (IPCC, CLC, IGBP, Coloquial,
    Suelo IPCC, Köppen, IDEAM, Disturbio, uso del suelo propio de Colflux, …),
    reemplaza los catálogos antes separados por dominio (TipoCobertura,
    TipoClasificacionEcosistema, Disturbio)."""

    CATEGORIA_CHOICES = [
        ("Cobertura Vegetal", "Cobertura Vegetal"),
        ("Suelo", "Suelo"),
        ("Clima", "Clima"),
        ("Ecosistema", "Ecosistema"),
        ("Disturbio", "Disturbio"),
        ("Uso Suelo", "Uso Suelo"),
    ]

    nombre = models.CharField("nombre", max_length=60)
    categoria = models.CharField("categoría", max_length=30, choices=CATEGORIA_CHOICES)
    descripcion = models.TextField("descripción", blank=True)

    class Meta:
        verbose_name = "tipo de clasificación"
        verbose_name_plural = "tipos de clasificación"
        ordering = ["categoria", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["nombre", "categoria"], name="clasificacion_tipo_unica"),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.categoria})"


class ValorClasificacionTipo(TimestampedModel):
    """Valor permitido dentro de un sistema de clasificación (ej. "Forest Land" en
    IPCC, "Páramo" en IDEAM, "Fuego" en Disturbio)."""

    tipo = models.ForeignKey(
        ClasificacionTipo, on_delete=models.PROTECT, related_name="valores", verbose_name="tipo",
    )
    valor = models.CharField("valor", max_length=160)

    class Meta:
        verbose_name = "valor de clasificación"
        verbose_name_plural = "valores de clasificación"
        ordering = ["tipo", "valor"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "valor"], name="valor_clasificacion_unico_por_tipo"),
        ]

    def __str__(self):
        return f"{self.valor} ({self.tipo})"


class ClasificacionArea(TimestampedModel):
    """Área real (geometría) de un valor de clasificación — capa futura, sin datos
    hoy: reemplaza lo que hubieran sido CoberturaArea/EcosistemaArea por separado.
    Se llena cuando haya un mapa oficial (IDEAM/IAvH u otro) para digitalizar."""

    tipo = models.ForeignKey(ClasificacionTipo, on_delete=models.PROTECT, related_name="areas", verbose_name="tipo")
    valor = models.ForeignKey(
        ValorClasificacionTipo, on_delete=models.PROTECT, related_name="areas", verbose_name="valor",
    )
    geom = gis_models.PolygonField("geometría", srid=4326, null=True, blank=True)

    class Meta:
        verbose_name = "área de clasificación"
        verbose_name_plural = "áreas de clasificación"
        ordering = ["tipo", "valor"]

    def __str__(self):
        return f"{self.valor} — área"
