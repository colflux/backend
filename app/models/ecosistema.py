from django.db import models

from .base import TimestampedModel


class TipoClasificacionEcosistema(TimestampedModel):
    """Catálogo de sistemas de clasificación de ecosistema (hoy solo IDEAM; deja la puerta abierta a Holdridge, Ramsar, etc.)."""

    nombre = models.CharField("nombre", max_length=60, unique=True)

    class Meta:
        verbose_name = "tipo de clasificación de ecosistema"
        verbose_name_plural = "tipos de clasificación de ecosistema"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class ValorClasificacionEcosistema(TimestampedModel):
    """Valor permitido dentro de un sistema de clasificación de ecosistema (ej. "Páramo", "Turbera" en IDEAM).

    Lista tentativa, pendiente de confirmar con Martín (ecólogo) antes de tratarla
    como catálogo cerrado definitivo.
    """

    tipo = models.ForeignKey(
        TipoClasificacionEcosistema, on_delete=models.PROTECT, related_name="valores",
        verbose_name="tipo de clasificación",
    )
    valor = models.CharField("valor", max_length=120)

    class Meta:
        verbose_name = "valor de clasificación de ecosistema"
        verbose_name_plural = "valores de clasificación de ecosistema"
        ordering = ["tipo", "valor"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "valor"], name="valor_ecosistema_unico_por_tipo"),
        ]

    def __str__(self):
        return f"{self.valor} ({self.tipo})"


class EcosistemaManual(TimestampedModel):
    """Ecosistema/zonificación reportado por el equipo de campo para una unidad de muestreo.

    Varias filas por unidad (una por sistema de clasificación) — mismo patrón que
    CoberturaManual. No incluye la capa geométrica oficial (ver docs de arquitectura):
    todavía no se tiene el shapefile/geopackage del Mapa de Ecosistemas IDEAM/IAvH.
    """

    unidad_muestreo = models.ForeignKey(
        "app.UnidadMuestreo", on_delete=models.CASCADE, related_name="ecosistemas_manuales",
        verbose_name="unidad de muestreo",
    )
    tipo = models.ForeignKey(
        "app.ClasificacionTipo", on_delete=models.PROTECT, related_name="ecosistemas_manuales",
        null=True, blank=True, verbose_name="tipo de clasificación",
    )
    valor = models.ForeignKey(
        "app.ValorClasificacionTipo", on_delete=models.PROTECT, related_name="ecosistemas_manuales",
        null=True, blank=True, verbose_name="valor",
        help_text="Vacío si el texto de origen no matchea ningún valor conocido del catálogo (ver valor_texto).",
    )
    valor_texto = models.CharField(
        "valor (texto original)", max_length=120, blank=True,
        help_text="Texto tal como llegó en el import. Se llena siempre; valor queda vacío si no matcheó ningún catálogo.",
    )

    ESTADO_CONSERVACION_CHOICES = [
        ("Natural", "Natural (sin manejo humano significativo)"),
        ("Seminatural", "Seminatural (manejo bajo, regeneración natural dominante)"),
        ("Manejado", "Manejado (aprovechamiento, ganadería, agroforestería)"),
        ("Plantacion", "Plantación (vegetación establecida y manejada)"),
        ("Artificial_Urbano", "Artificial / Urbano (superficie no natural)"),
    ]
    estado_conservacion = models.CharField(
        "estado de conservación", max_length=20, choices=ESTADO_CONSERVACION_CHOICES, blank=True,
        help_text="Estado del ecosistema frente a la presencia de manejo humano (taxonomía del vocabulario IDEAM).",
    )
    proteccion_legal = models.TextField(
        "protección legal", blank=True,
        help_text="Si el sitio está bajo alguna figura de reserva, parque, santuario, etc.",
    )

    class Meta:
        verbose_name = "ecosistema (dato digitado)"
        verbose_name_plural = "ecosistemas (dato digitado)"
        ordering = ["unidad_muestreo", "tipo"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidad_muestreo", "tipo"],
                name="ecosistema_manual_unico_por_unidad_tipo",
            ),
        ]

    def __str__(self):
        return f"{self.valor} — {self.unidad_muestreo}"
